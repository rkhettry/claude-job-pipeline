#!/usr/bin/env python3
"""Localhost web UI for triaging jobs in <repo>/jobs.xlsx, plus a live
pipeline view (`/runs`) that visualizes the daily sourcing run.

Run from terminal (cd into your clone of the repo first):
    python3 ./triage_server.py

Then open http://localhost:8765/ in your browser.
Press Ctrl+C in the terminal to stop.
"""

import json
import os
import re
import shlex
import sys
import shutil
import subprocess
import webbrowser
import threading
import datetime
import mimetypes
from urllib.parse import unquote
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Auto-install openpyxl if missing (one-time)
try:
    from openpyxl import load_workbook
except ImportError:
    print("Installing openpyxl (one-time)...", file=sys.stderr)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "openpyxl", "--quiet", "--break-system-packages"],
        check=False,
    )
    from openpyxl import load_workbook  # type: ignore

# Paths
REPO_ROOT = Path(__file__).resolve().parent
# RESUME_ROOT holds your resume materials (experiences/, profile.md, master/resume.tex,
# etc.) that the tailoring spec reads. By default it's the same as REPO_ROOT — drop your
# resume files alongside the pipeline scripts. Set the RESUME_ROOT env var to override
# (e.g. if you keep resume materials in a separate private directory).
RESUME_ROOT = Path(os.environ.get("RESUME_ROOT", str(REPO_ROOT)))
# Back-compat alias used throughout the file:
AUTOMATION_DIR = REPO_ROOT
XLSX_PATH = REPO_ROOT / "jobs.xlsx"
SPEC_PATH = REPO_ROOT / "resume-tailoring-spec.md"
LOGS_DIR = REPO_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
PORT = 8765

# Sourcing pipeline stages — used by /runs live-view to show which step Claude is on.
# Order is the pipeline order (preflight → ... → done). Patterns matched against
# ANSI-stripped log content; the LATEST stage seen wins as "current".
STAGE_DEFS = [
    ("preflight",          "Pre-flight",        r"(?i)(read(ing)?\s+(the\s+)?spec|read(ing)?\s+.*jobs\.xlsx|existing.*rows|build.*dedup|pre.?flight)"),
    ("simplify",           "SimplifyJobs",      r"(?i)(simplifyjobs|simplify[\s_\-]*jobs|simplify.*readme)"),
    ("jobright_repo",      "jobright-ai repo",  r"(?i)(jobright-ai/2026|jobright.*repo|2026-software-engineer)"),
    ("jobright_minisite",  "jobright minisite", r"(?i)(jobright\.ai/minisites|newgrad-jobs|is\s+new\s+grad|jobright.*minisite|claude-in-chrome.*jobright)"),
    ("linkedin",           "LinkedIn",          r"(?i)(linkedin\.com/jobs|f_tpr=r86400|linkedin.*search)"),
    ("filter",             "Filter & prestige", r"(?i)(apply.*prestige|prestige bar|hard.?avoid|tier[\s\-]*a\b)"),
    ("dedupe",             "Dedupe",            r"(?i)(dedup|canonical.*url|already in sheet|skip.*dup)"),
    ("append",             "Append rows",       r"(?i)(openpyxl|wb\.save|append.*row|appending|writing.*xlsx)"),
    ("email",              "Email digest",      r"(?i)(mail\.google\.com|gmail|compose|digest email)"),
    ("done",               "DONE",              r"(?i)(done\s+[—\-].+added|^done\s+[—\-]|finished.*one-line)"),
]
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def _find_active_sourcing_log():
    """Return the most-recent sourcing-*.log (Path) or None."""
    candidates = sorted(
        LOGS_DIR.glob("sourcing-*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _is_run_active(log_path) -> bool:
    """A run is 'active' if the log file was modified in the last 90 seconds."""
    if not log_path or not log_path.exists():
        return False
    age = datetime.datetime.now().timestamp() - log_path.stat().st_mtime
    return age < 90


def _detect_stages(log_text: str):
    """Walk the ANSI-stripped log; return (current_id, set(completed_ids)).

    Current = highest-index stage that has matched anywhere in the log.
    Completed = every stage that matched somewhere, minus current.
    """
    seen = set()
    max_idx = -1
    for i, (sid, _, pattern) in enumerate(STAGE_DEFS):
        if re.search(pattern, log_text):
            seen.add(sid)
            if i > max_idx:
                max_idx = i
    if max_idx < 0:
        return None, set()
    current = STAGE_DEFS[max_idx][0]
    return current, seen - {current}

# Claude Code invocation
CLAUDE_BIN = shutil.which("claude") or "claude"


def spawn_claude_tailor(job_id: int) -> Path:
    """Open Terminal.app running Claude Code interactively with the tailoring prompt.

    The prompt is passed as a CLI argument to `claude`, NOT typed in after launch —
    this eliminates the keystroke-injection race that left Claude sitting idle when
    the typing happened before the TUI was ready to accept input.

    Returns the path to the launch log file.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOGS_DIR / f"tailor-{job_id}-{timestamp}.log"

    prompt = (
        f"Read {SPEC_PATH} and execute it for job_id={job_id}. "
        f"The job row lives at id={job_id} in {XLSX_PATH}. "
        f"Working directory is {RESUME_ROOT}. "
        f"Follow the agentic verification loop in §5 of the spec (max 4 iterations). "
        f"When done, update the resume_version column in jobs.xlsx for this job_id per §7 "
        f"(use openpyxl from Bash). "
        f"If anything fails, write 'error: <one-line reason>' to that column instead. "
        f"After finishing the initial tailoring, stay in this conversation so I can ask for "
        f"adjustments live. Begin now."
    )

    # Build the shell command. shlex.quote handles all shell escaping (the prompt
    # may contain $, quotes, etc). claude auto-submits a positional prompt arg.
    inner_cmd = (
        f"cd {shlex.quote(str(RESUME_ROOT))} && "
        f"claude --dangerously-skip-permissions {shlex.quote(prompt)}"
    )

    # AppleScript-escape the inner command for embedding in `do script "..."`
    cmd_esc = inner_cmd.replace("\\", "\\\\").replace('"', '\\"')

    # Use Terminal.app only. With the prompt passed as a CLI arg we don't need
    # keystroke injection anyway, and Terminal.app behaves more predictably than
    # iTerm 2 across user configs (custom startup commands, profiles, etc.).
    applescript = f'''
tell application "Terminal"
    activate
    do script "{cmd_esc}"
end tell
'''

    script_path = LOGS_DIR / f"launch-{job_id}-{timestamp}.applescript"
    script_path.write_text(applescript)

    log_fh = open(log_path, "w", encoding="utf-8", errors="replace")
    log_fh.write(f"=== tailor launch job_id={job_id} at {timestamp} ===\n")
    log_fh.write(f"cwd: {RESUME_ROOT}\n")
    log_fh.write(f"prompt: {prompt}\n")
    log_fh.write(f"applescript: {script_path}\n")
    log_fh.write("=" * 60 + "\n")

    try:
        result = subprocess.run(
            ["osascript", str(script_path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        log_fh.write(f"osascript exit: {result.returncode}\n")
        if result.stdout:
            log_fh.write(f"stdout: {result.stdout}\n")
        if result.stderr:
            log_fh.write(f"stderr: {result.stderr}\n")
        if result.returncode != 0:
            _set_resume_version(
                job_id,
                f"error: terminal launch failed (osascript exit {result.returncode})",
            )
    except FileNotFoundError:
        log_fh.write("ERROR: osascript not found — are you on macOS?\n")
        _set_resume_version(job_id, "error: osascript missing (macOS required)")
    except subprocess.TimeoutExpired:
        log_fh.write("ERROR: osascript timed out launching terminal.\n")
        _set_resume_version(job_id, "error: terminal launch timed out")
    except Exception as e:
        log_fh.write(f"ERROR: {e}\n")
        _set_resume_version(job_id, f"error: terminal launch raised {type(e).__name__}")
    finally:
        log_fh.close()

    return log_path


def _set_resume_version(job_id: int, value: str) -> None:
    """Write to the resume_version cell for a given job_id."""
    try:
        wb = load_workbook(XLSX_PATH)
        ws = wb["jobs"]
        headers = [c.value for c in ws[1]]
        if "resume_version" not in headers:
            return
        rv_idx = headers.index("resume_version")
        for r in ws.iter_rows(min_row=2):
            if r[0].value == job_id:
                r[rv_idx].value = value
                break
        wb.save(XLSX_PATH)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# HTML/JS UI (same look as the Cowork artifact, but talks to /api endpoints)
# ---------------------------------------------------------------------------

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Jobs Triage</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #fafbfc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif; font-size: 14px; }
body { padding: 0 16px; max-width: 920px; margin: 0 auto; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 4px 12px; border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; background: #fafbfc; z-index: 5; }
.title { font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }
.subtitle { font-size: 12px; color: #64748b; margin-top: 2px; }
.stats { display: flex; gap: 16px; align-items: center; }
.stat { display: flex; flex-direction: column; align-items: flex-end; }
.stat-num { font-size: 20px; font-weight: 600; line-height: 1; font-variant-numeric: tabular-nums; }
.stat-label { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }
.stat.pending .stat-num { color: #0f172a; }
.stat.yes .stat-num { color: #16a34a; }
.stat.no .stat-num { color: #94a3b8; }
.stat.maybe .stat-num { color: #d97706; }

.filters { display: flex; gap: 6px; padding: 12px 4px; flex-wrap: wrap; }
.chip { padding: 5px 11px; border-radius: 999px; border: 1px solid #e2e8f0; background: white; cursor: pointer; font-size: 12px; font-weight: 500; color: #475569; user-select: none; transition: all 0.15s; }
.chip:hover { border-color: #cbd5e1; background: #f1f5f9; }
.chip.active { background: #0f172a; border-color: #0f172a; color: white; }
.chip .count { opacity: 0.6; margin-left: 4px; font-variant-numeric: tabular-nums; }
.chip.active .count { opacity: 0.85; }

.cards { display: flex; flex-direction: column; gap: 10px; padding: 4px 0 100px; }
.card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; transition: opacity 0.25s, transform 0.25s, max-height 0.25s; overflow: hidden; }
.card.removing { opacity: 0; transform: translateX(20px); max-height: 0; padding-top: 0; padding-bottom: 0; margin-top: -10px; border-width: 0; }
.card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.company { font-size: 16px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.2; }
.role { font-size: 13px; color: #334155; margin-top: 4px; line-height: 1.35; }
.meta { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 8px; font-size: 12px; color: #64748b; }
.meta-item { display: inline-flex; align-items: center; gap: 4px; }
.reasoning { font-size: 12px; color: #475569; margin-top: 8px; font-style: italic; border-left: 2px solid #e2e8f0; padding-left: 8px; }

.tier { font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 999px; letter-spacing: 0.04em; text-transform: uppercase; white-space: nowrap; }
.tier-A { background: #dcfce7; color: #15803d; }
.tier-wedge { background: #dbeafe; color: #1d4ed8; }
.tier-unsure { background: #fef3c7; color: #b45309; }

.actions { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
.btn { padding: 7px 12px; border-radius: 7px; border: 1px solid #e2e8f0; background: white; color: #0f172a; cursor: pointer; font-size: 12px; font-weight: 500; font-family: inherit; transition: all 0.12s; display: inline-flex; align-items: center; gap: 5px; text-decoration: none; }
.btn:hover { border-color: #cbd5e1; background: #f8fafc; }
.btn-apply { background: #0f172a; color: white; border-color: #0f172a; }
.btn-apply:hover { background: #1e293b; border-color: #1e293b; }
.btn-yes { color: #15803d; border-color: #bbf7d0; }
.btn-yes:hover { background: #f0fdf4; border-color: #86efac; }
.btn-no { color: #b91c1c; border-color: #fecaca; }
.btn-no:hover { background: #fef2f2; border-color: #fca5a5; }
.btn-maybe { color: #b45309; border-color: #fde68a; }
.btn-maybe:hover { background: #fffbeb; border-color: #fcd34d; }
.btn-undo { color: #475569; }

.decision-tag { font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 4px; }
.decision-yes { background: #dcfce7; color: #15803d; }
.decision-no { background: #fee2e2; color: #b91c1c; }
.decision-maybe { background: #fef3c7; color: #b45309; }

.tailor-state { margin-top: 10px; padding: 10px 12px; border-radius: 8px; display: flex; align-items: center; gap: 10px; font-size: 12px; }
.tailor-pending { background: #fef9c3; color: #854d0e; border: 1px solid #fde68a; }
.tailor-ready { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
.tailor-error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.tailor-state .tail-spin { width: 13px; height: 13px; border: 2px solid #d6b441; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; }
.tailor-state .open-link { margin-left: auto; padding: 4px 10px; background: #047857; color: white; text-decoration: none; border-radius: 6px; font-weight: 500; font-size: 12px; }
.tailor-state .open-link:hover { background: #065f46; }

.state { text-align: center; padding: 60px 20px; color: #64748b; }
.state-emoji { font-size: 36px; margin-bottom: 12px; }
.state-title { font-size: 15px; font-weight: 600; color: #0f172a; margin-bottom: 6px; }
.state-text { font-size: 13px; max-width: 360px; margin: 0 auto; line-height: 1.5; }
.retry-btn { margin-top: 14px; padding: 8px 16px; border-radius: 7px; border: 1px solid #0f172a; background: #0f172a; color: white; cursor: pointer; font-size: 13px; font-weight: 500; font-family: inherit; }

.toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #0f172a; color: white; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 500; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.2); z-index: 100; display: flex; gap: 12px; align-items: center; transition: opacity 0.2s, transform 0.2s; }
.toast.error { background: #b91c1c; }
.toast.hidden { opacity: 0; pointer-events: none; transform: translateX(-50%) translateY(8px); }
.toast .toast-undo { background: rgba(255,255,255,0.18); color: white; border: none; padding: 4px 10px; border-radius: 5px; cursor: pointer; font-size: 12px; font-weight: 500; }
.toast .toast-undo:hover { background: rgba(255,255,255,0.28); }

.spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid #e2e8f0; border-top-color: #0f172a; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 6px; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-block { display: flex; gap: 10px; align-items: center; justify-content: center; padding: 30px; color: #64748b; font-size: 13px; }
.reload-btn { padding: 5px 10px; border-radius: 6px; border: 1px solid #e2e8f0; background: white; color: #475569; cursor: pointer; font-size: 12px; font-weight: 500; font-family: inherit; }
.reload-btn:hover { background: #f1f5f9; }
a { color: inherit; }
</style>
</head>
<body>

<div class="top">
  <div>
    <div class="title">Jobs Triage</div>
    <div class="subtitle" id="subtitle">Loading…</div>
  </div>
  <div class="stats">
    <div class="stat pending"><div class="stat-num" id="count-pending">·</div><div class="stat-label">Pending</div></div>
    <div class="stat yes"><div class="stat-num" id="count-yes">·</div><div class="stat-label">Yes</div></div>
    <div class="stat maybe"><div class="stat-num" id="count-maybe">·</div><div class="stat-label">Maybe</div></div>
    <div class="stat no"><div class="stat-num" id="count-no">·</div><div class="stat-label">No</div></div>
    <a href="/runs" class="reload-btn" style="text-decoration:none;color:inherit;padding:5px 10px;" title="Live sourcing run">▶ Live</a>
    <button class="reload-btn" id="reload-btn" title="Reload">↻</button>
  </div>
</div>

<div class="filters" id="filters">
  <button class="chip active" data-filter="pending">Pending<span class="count" id="ch-pending">·</span></button>
  <button class="chip" data-filter="A">Tier A<span class="count" id="ch-A">·</span></button>
  <button class="chip" data-filter="wedge">Wedge<span class="count" id="ch-wedge">·</span></button>
  <button class="chip" data-filter="unsure">Unsure<span class="count" id="ch-unsure">·</span></button>
  <button class="chip" data-filter="yes">Yes<span class="count" id="ch-yes">·</span></button>
  <button class="chip" data-filter="no">No<span class="count" id="ch-no">·</span></button>
  <button class="chip" data-filter="all">All<span class="count" id="ch-all">·</span></button>
</div>

<div id="content">
  <div class="loading-block"><span class="spinner"></span>Loading jobs…</div>
</div>

<div class="toast hidden" id="toast"><span id="toast-msg"></span><button class="toast-undo" id="toast-undo" style="display:none">Undo</button></div>

<script>
(function() {
  // Injected by the server at render time — used to strip the absolute RESUME_ROOT
  // prefix off resume_version paths when building /resume-files/ URLs.
  window.__RESUME_ROOT_PREFIX__ = "__RESUME_ROOT_PREFIX__";
  let rows = [];
  let activeFilter = localStorage.getItem('jobs-triage-filter') || 'pending';
  let lastUndo = null;
  const $ = (id) => document.getElementById(id);
  const content = $('content');

  async function fetchJobs() {
    const res = await fetch('/api/jobs', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return await res.json();
  }
  async function postDecision(id, decision) {
    const res = await fetch('/api/decide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: Number(id), decision }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    return data;
  }

  function escapeHtml(s) {
    return (s == null ? '' : String(s)).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[c]));
  }
  function tierClass(t) {
    const lo = (t || '').toLowerCase();
    if (lo === 'a') return 'tier-A';
    if (lo === 'wedge') return 'tier-wedge';
    if (lo === 'unsure') return 'tier-unsure';
    return '';
  }
  function tierLabel(t) {
    const lo = (t || '').toLowerCase();
    if (lo === 'a') return 'Tier A';
    if (lo === 'wedge') return 'Wedge';
    if (lo === 'unsure') return 'Unsure';
    return t || '';
  }
  function decisionTag(d) {
    if (d === 'yes') return '<span class="decision-tag decision-yes">✓ Yes</span>';
    if (d === 'no') return '<span class="decision-tag decision-no">✗ No</span>';
    if (d === 'maybe') return '<span class="decision-tag decision-maybe">○ Maybe</span>';
    return '';
  }

  function computeCounts() {
    const counts = { pending: 0, yes: 0, no: 0, maybe: 0, A: 0, wedge: 0, unsure: 0, all: rows.length };
    for (const r of rows) {
      const d = (r.decision || 'pending').toLowerCase();
      counts[d] = (counts[d] || 0) + 1;
      const t = (r.tier || '').toLowerCase();
      if (d === 'pending') {
        if (t === 'a') counts.A++;
        else if (t === 'wedge') counts.wedge++;
        else if (t === 'unsure') counts.unsure++;
      }
    }
    return counts;
  }

  function applyFilter(r, filter) {
    const d = (r.decision || 'pending').toLowerCase();
    const t = (r.tier || '').toLowerCase();
    if (filter === 'all') return true;
    if (filter === 'pending') return d === 'pending';
    if (filter === 'yes') return d === 'yes';
    if (filter === 'no') return d === 'no';
    if (filter === 'maybe') return d === 'maybe';
    if (filter === 'A') return d === 'pending' && t === 'a';
    if (filter === 'wedge') return d === 'pending' && t === 'wedge';
    if (filter === 'unsure') return d === 'pending' && t === 'unsure';
    return true;
  }

  function tailorStateHtml(r) {
    const rv = (r.resume_version || '').trim();
    if (!rv) return '';
    if (rv === 'tailoring') {
      return `<div class="tailor-state tailor-pending"><span class="tail-spin"></span><span>Tailoring resume… Claude Code is iterating on the 1-pager. Refreshes automatically.</span><button class="btn btn-no" data-act="cancel-tailor" data-id="${escapeHtml(r.id)}" style="margin-left:auto;">Cancel</button></div>`;
    }
    if (rv.toLowerCase().startsWith('error:')) {
      return `<div class="tailor-state tailor-error"><span>⚠️ ${escapeHtml(rv)}</span><button class="btn btn-yes" data-act="retry-tailor" data-id="${escapeHtml(r.id)}" style="margin-left:auto;">Retry</button></div>`;
    }
    // Path to a folder or .pdf. Build a URL-safe link to the PDF.
    // The server tells us the RESUME_ROOT prefix to strip; everything else passes through.
    let rel = rv;
    const prefix = (window.__RESUME_ROOT_PREFIX__ || '');
    if (prefix && rel.startsWith(prefix)) rel = rel.slice(prefix.length).replace(/^\/+/, '');
    // URL-encode each path segment (filenames have spaces in the new convention)
    function encodePath(p) { return p.split('/').map(s => encodeURIComponent(s)).join('/'); }
    let pdfUrl;
    if (rel.endsWith('.pdf')) {
      pdfUrl = '/resume-files/' + encodePath(rel);
    } else {
      // legacy: folder path without filename — fall back to tailored.pdf
      if (!rel.endsWith('/')) rel = rel + '/';
      pdfUrl = '/resume-files/' + encodePath(rel) + 'tailored.pdf';
    }
    return `<div class="tailor-state tailor-ready"><span>✓ Resume ready</span><a class="open-link" target="_blank" href="${escapeHtml(pdfUrl)}">Open PDF ↗</a></div>`;
  }

  function cardHtml(r) {
    const dec = (r.decision || 'pending').toLowerCase();
    const isPending = dec === 'pending';
    const tier = tierClass(r.tier);
    const tlabel = tierLabel(r.tier);
    return `
      <div class="card" data-id="${escapeHtml(r.id)}">
        <div class="card-head">
          <div style="min-width: 0; flex: 1;">
            <div class="company">${escapeHtml(r.company)}</div>
            <div class="role">${escapeHtml(r.role)}</div>
          </div>
          <div style="display:flex; flex-direction:column; gap:6px; align-items:flex-end;">
            ${tier ? `<span class="tier ${tier}">${escapeHtml(tlabel)}</span>` : ''}
            ${!isPending ? decisionTag(dec) : ''}
          </div>
        </div>
        <div class="meta">
          ${r.location ? `<span class="meta-item">📍 ${escapeHtml(r.location)}</span>` : ''}
          ${r.comp && r.comp !== 'unknown' ? `<span class="meta-item">💰 ${escapeHtml(r.comp)}</span>` : ''}
          ${r.source ? `<span class="meta-item">🔗 ${escapeHtml(r.source)}</span>` : ''}
          ${r.posted_date ? `<span class="meta-item">📅 ${escapeHtml(r.posted_date)}</span>` : ''}
        </div>
        ${r.reasoning ? `<div class="reasoning">${escapeHtml(r.reasoning)}</div>` : ''}
        ${tailorStateHtml(r)}
        <div class="actions">
          ${r.apply_url ? `<a class="btn btn-apply" target="_blank" rel="noopener" href="${escapeHtml(r.apply_url)}">Apply ↗</a>` : ''}
          ${isPending ? `
            <button class="btn btn-yes" data-act="yes" data-id="${escapeHtml(r.id)}">✓ Yes</button>
            <button class="btn btn-maybe" data-act="maybe" data-id="${escapeHtml(r.id)}">○ Maybe</button>
            <button class="btn btn-no" data-act="no" data-id="${escapeHtml(r.id)}">✗ No</button>
          ` : `
            <button class="btn btn-undo" data-act="pending" data-id="${escapeHtml(r.id)}">↺ Reset to pending</button>
          `}
        </div>
      </div>
    `;
  }

  function render() {
    const counts = computeCounts();
    $('count-pending').textContent = counts.pending;
    $('count-yes').textContent = counts.yes;
    $('count-maybe').textContent = counts.maybe;
    $('count-no').textContent = counts.no;
    $('ch-pending').textContent = counts.pending;
    $('ch-A').textContent = counts.A;
    $('ch-wedge').textContent = counts.wedge;
    $('ch-unsure').textContent = counts.unsure;
    $('ch-yes').textContent = counts.yes;
    $('ch-no').textContent = counts.no;
    $('ch-all').textContent = counts.all;
    const dt = new Date();
    $('subtitle').textContent = `${rows.length} total · loaded ${dt.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;

    document.querySelectorAll('.chip').forEach(c => {
      c.classList.toggle('active', c.dataset.filter === activeFilter);
    });

    const filtered = rows.filter(r => applyFilter(r, activeFilter));
    if (!filtered.length) {
      const msg = activeFilter === 'pending'
        ? { e: '🎯', t: 'All caught up', m: 'No pending jobs right now. The noon-PT scheduled task will refresh this with new finds.' }
        : { e: '∅', t: 'Nothing matches this filter', m: 'Try another filter, or wait for the next scheduled run.' };
      content.innerHTML = `<div class="state"><div class="state-emoji">${msg.e}</div><div class="state-title">${msg.t}</div><div class="state-text">${msg.m}</div></div>`;
      return;
    }
    content.innerHTML = `<div class="cards">${filtered.map(cardHtml).join('')}</div>`;
  }

  let pollTimer = null;
  function maybeStartPolling() {
    const anyTailoring = rows.some(r => (r.resume_version || '').trim() === 'tailoring');
    if (anyTailoring && !pollTimer) {
      pollTimer = setInterval(() => loadJobs(true), 8000);
    } else if (!anyTailoring && pollTimer) {
      clearInterval(pollTimer); pollTimer = null;
    }
  }

  async function loadJobs(silent) {
    if (!silent) content.innerHTML = `<div class="loading-block"><span class="spinner"></span>Loading jobs…</div>`;
    try {
      const data = await fetchJobs();
      if (data.error) throw new Error(data.error);
      rows = data.rows || [];
      const tierRank = { A: 0, wedge: 1, unsure: 2, '': 3 };
      rows.sort((a, b) => {
        const da = (a.decision || 'pending').toLowerCase();
        const db = (b.decision || 'pending').toLowerCase();
        if (da !== db) {
          const dorder = { pending: 0, maybe: 1, yes: 2, no: 3 };
          return (dorder[da] ?? 9) - (dorder[db] ?? 9);
        }
        const ra = tierRank[a.tier] ?? 9;
        const rb = tierRank[b.tier] ?? 9;
        if (ra !== rb) return ra - rb;
        return parseInt(a.id) - parseInt(b.id);
      });
      render();
      maybeStartPolling();
    } catch (e) {
      content.innerHTML = `<div class="state"><div class="state-emoji">⚠️</div><div class="state-title">Couldn't load jobs</div><div class="state-text">${escapeHtml(e.message)}</div><button class="retry-btn" id="retry-btn">Retry</button></div>`;
      $('subtitle').textContent = 'Error';
      const r = document.getElementById('retry-btn');
      if (r) r.addEventListener('click', () => loadJobs());
    }
  }

  async function decide(id, decision) {
    const row = rows.find(r => String(r.id) === String(id));
    if (!row) return;
    if (decision === 'cancel-tailor') {
      await cancelTailor(id);
      return;
    }
    if (decision === 'retry-tailor') {
      // Reset resume_version and re-trigger Yes
      row.resume_version = '';
      decision = 'yes';
    }
    const prev = row.decision || 'pending';
    const prevRv = row.resume_version || '';
    row.decision = decision;
    // optimistic: if we're saying yes, show the tailoring state immediately
    if (decision === 'yes' && (!(row.resume_version || '').startsWith('/'))) {
      row.resume_version = 'tailoring';
    }
    const cardEl = document.querySelector(`.card[data-id="${id}"]`);
    const willHide = !applyFilter(row, activeFilter);
    if (cardEl && willHide) cardEl.classList.add('removing');
    try {
      const resp = await postDecision(id, decision);
      lastUndo = { id, prev };
      let msg = `#${id} → ${decision}`;
      if (resp && resp.tailoring_started) msg += ' · tailoring kicked off';
      showToast(msg, true);
      setTimeout(() => { render(); maybeStartPolling(); }, willHide ? 250 : 0);
    } catch (e) {
      // Roll back optimistic UI (decision + the tailoring state we set)
      row.decision = prev;
      row.resume_version = prevRv;
      if (cardEl) cardEl.classList.remove('removing');
      render();
      showToast('Save failed: ' + e.message, false, false);
    }
  }

  async function cancelTailor(id) {
    try {
      const res = await fetch('/api/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: Number(id) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
      showToast(`#${id} cancelled · back to pending (close the Terminal window manually)`, false);
      await loadJobs(true);
    } catch (e) {
      showToast('Cancel failed: ' + e.message, false, false);
    }
  }

  async function doUndo() {
    if (!lastUndo) return;
    const { id, prev } = lastUndo;
    lastUndo = null;
    await decide(id, prev);
  }

  let toastTimer;
  function showToast(msg, withUndo, autoHide = true) {
    const t = $('toast');
    $('toast-msg').textContent = msg;
    $('toast-undo').style.display = withUndo ? '' : 'none';
    t.classList.toggle('error', !withUndo && !autoHide);
    t.classList.remove('hidden');
    clearTimeout(toastTimer);
    if (autoHide) toastTimer = setTimeout(() => t.classList.add('hidden'), 3500);
  }

  document.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (chip) {
      activeFilter = chip.dataset.filter;
      localStorage.setItem('jobs-triage-filter', activeFilter);
      render();
      return;
    }
    const btn = e.target.closest('button[data-act]');
    if (btn) { decide(btn.dataset.id, btn.dataset.act); return; }
    if (e.target.id === 'toast-undo') { doUndo(); $('toast').classList.add('hidden'); }
    if (e.target.id === 'reload-btn') { loadJobs(); }
  });

  loadJobs();
})();
</script>
</body>
</html>
"""


RUNS_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sourcing run — live</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #fafbfc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif; font-size: 14px; }
body { padding: 0 16px 60px; max-width: 1100px; margin: 0 auto; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 4px 12px; border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; background: #fafbfc; z-index: 5; }
.title { font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }
.subtitle { font-size: 12px; color: #64748b; margin-top: 2px; font-variant-numeric: tabular-nums; }
.back-link { font-size: 13px; color: #475569; text-decoration: none; padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; }
.back-link:hover { background: #f1f5f9; }

.status-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; letter-spacing: 0.02em; }
.status-pill.live { background: #dbeafe; color: #1d4ed8; }
.status-pill.idle { background: #f1f5f9; color: #64748b; }
.status-pill.stalled { background: #fef3c7; color: #b45309; }
.status-pill.done { background: #dcfce7; color: #15803d; }
.status-pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.status-pill.live .dot { animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.pipeline { display: flex; flex-wrap: wrap; gap: 6px; padding: 22px 0 18px; align-items: stretch; }
.stage { flex: 1 1 0; min-width: 92px; padding: 12px 8px; border-radius: 10px; border: 1.5px solid #e2e8f0; background: white; display: flex; flex-direction: column; align-items: center; gap: 6px; text-align: center; transition: all 0.25s; }
.stage-icon { width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; }
.stage-name { font-size: 11px; font-weight: 500; line-height: 1.25; letter-spacing: 0.01em; }
.stage.pending { color: #94a3b8; border-color: #e2e8f0; }
.stage.pending .stage-icon { background: #f1f5f9; color: #cbd5e1; }
.stage.active { color: #1d4ed8; border-color: #93c5fd; background: #eff6ff; box-shadow: 0 0 0 4px rgba(59,130,246,0.12); }
.stage.active .stage-icon { background: #1d4ed8; color: white; animation: spin 1.3s linear infinite; }
.stage.stalled { color: #b45309; border-color: #fde68a; background: #fffbeb; }
.stage.stalled .stage-icon { background: #f59e0b; color: white; }
.stage.completed { color: #15803d; border-color: #86efac; background: #f0fdf4; }
.stage.completed .stage-icon { background: #15803d; color: white; }
@keyframes spin { to { transform: rotate(360deg); } }
.arrow { align-self: center; color: #cbd5e1; font-size: 16px; padding: 0 2px; user-select: none; }

.panel { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 0; overflow: hidden; margin-top: 8px; }
.panel-head { padding: 10px 14px; border-bottom: 1px solid #e2e8f0; font-size: 12px; font-weight: 600; color: #475569; display: flex; align-items: center; justify-content: space-between; }
.panel-head .log-path { font-family: SF Mono, Monaco, monospace; font-weight: 400; font-size: 11px; color: #94a3b8; max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-pre { background: #0f172a; color: #e2e8f0; padding: 14px 16px; font-family: SF Mono, Monaco, monospace; font-size: 11px; line-height: 1.55; max-height: 480px; overflow-y: scroll; margin: 0; white-space: pre-wrap; word-break: break-word; }
.log-pre::-webkit-scrollbar { width: 10px; }
.log-pre::-webkit-scrollbar-thumb { background: #334155; border-radius: 5px; }
.log-empty { padding: 40px 20px; text-align: center; color: #94a3b8; font-size: 13px; }

.error-banner { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; padding: 10px 14px; border-radius: 8px; margin: 12px 0; font-size: 13px; }
</style>
</head>
<body>

<div class="top">
  <div>
    <div class="title">Sourcing run · live <span id="status-pill" class="status-pill idle"><span class="dot"></span><span id="status-label">idle</span></span></div>
    <div class="subtitle" id="subtitle">Loading…</div>
  </div>
  <a class="back-link" href="/">← Back to triage</a>
</div>

<div class="pipeline" id="pipeline"></div>

<div class="panel">
  <div class="panel-head">
    <span>Live log tail</span>
    <span class="log-path" id="log-path"></span>
  </div>
  <pre class="log-pre" id="log-tail"><div class="log-empty">Waiting for log…</div></pre>
</div>

<script>
(function() {
  const $ = (id) => document.getElementById(id);
  const tailEl = $('log-tail');
  const pipelineEl = $('pipeline');
  let userScrolled = false;
  tailEl.addEventListener('scroll', () => {
    const atBottom = tailEl.scrollTop + tailEl.clientHeight >= tailEl.scrollHeight - 8;
    userScrolled = !atBottom;
  });

  function setStatus(state, label) {
    const pill = $('status-pill');
    pill.className = 'status-pill ' + state;
    $('status-label').textContent = label;
  }

  function renderStages(stages) {
    const parts = [];
    stages.forEach((s, i) => {
      let icon = '';
      if (s.state === 'completed') icon = '✓';
      else if (s.state === 'active') icon = '⟳';
      else if (s.state === 'stalled') icon = '!';
      else icon = '·';
      parts.push(`<div class="stage ${s.state}" title="${s.id}"><div class="stage-icon">${icon}</div><div class="stage-name">${s.name}</div></div>`);
      if (i < stages.length - 1) parts.push('<div class="arrow">→</div>');
    });
    pipelineEl.innerHTML = parts.join('');
  }

  async function refresh() {
    try {
      const res = await fetch('/api/run-status', { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();

      renderStages(data.stages || []);

      if (!data.has_log) {
        setStatus('idle', 'no runs yet');
        $('subtitle').textContent = 'No sourcing log found. The daily cron at 12:00 PT will create one.';
        tailEl.innerHTML = '<div class="log-empty">No log yet. Trigger a run with <code>launchctl start com.&lt;username&gt;.daily-sourcing</code> or by running <code>bash scripts/launch_daily_sourcing.sh</code> directly.</div>';
        $('log-path').textContent = '';
        return;
      }

      const isDone = data.current_stage === 'done';
      if (isDone) setStatus('done', 'done');
      else if (data.is_active) setStatus('live', 'live');
      else setStatus('stalled', 'stalled');

      const mtime = data.log_mtime ? new Date(data.log_mtime) : null;
      const mtimeStr = mtime ? mtime.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'}) : '';
      $('subtitle').textContent = (data.current_stage || 'starting') + ' · last log activity ' + mtimeStr;
      $('log-path').textContent = data.log_path || '';

      const tail = data.tail || '';
      if (tail) {
        // Avoid rerendering identical content — preserves scroll position
        if (tailEl.dataset.last !== tail) {
          tailEl.textContent = tail;
          tailEl.dataset.last = tail;
          if (!userScrolled) tailEl.scrollTop = tailEl.scrollHeight;
        }
      } else {
        tailEl.innerHTML = '<div class="log-empty">Log exists but no readable content yet.</div>';
      }
    } catch (e) {
      setStatus('stalled', 'error');
      $('subtitle').textContent = 'Refresh failed: ' + e.message;
    }
  }

  refresh();
  setInterval(refresh, 2500);
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, data):
        self._send(code, json.dumps(data, default=str), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = HTML.replace("__RESUME_ROOT_PREFIX__", str(RESUME_ROOT.resolve()))
            self._send(200, html, "text/html; charset=utf-8")
            return
        if self.path in ("/runs", "/runs/"):
            self._send(200, RUNS_HTML, "text/html; charset=utf-8")
            return
        if self.path == "/api/jobs":
            self._handle_jobs()
            return
        if self.path == "/api/run-status":
            self._handle_run_status()
            return
        if self.path == "/api/health":
            self._send_json(200, {"ok": True, "xlsx": str(XLSX_PATH), "xlsx_exists": XLSX_PATH.exists(), "claude_bin": CLAUDE_BIN})
            return
        if self.path.startswith("/resume-files/"):
            self._serve_resume_file(self.path[len("/resume-files/"):])
            return
        self._send(404, "Not Found", "text/plain")

    def _handle_run_status(self):
        """Return the active sourcing run's stage + log tail. Used by /runs."""
        try:
            log_path = _find_active_sourcing_log()
            if not log_path:
                self._send_json(200, {
                    "has_log": False,
                    "is_active": False,
                    "stages": [{"id": s, "name": n, "state": "pending"} for s, n, _ in STAGE_DEFS],
                    "tail": "",
                    "log_path": None,
                    "log_mtime": None,
                })
                return

            text = log_path.read_text(encoding="utf-8", errors="replace")
            stripped = _strip_ansi(text)
            current, completed = _detect_stages(stripped)
            active = _is_run_active(log_path)

            stages = []
            for sid, name, _ in STAGE_DEFS:
                if sid == current:
                    state = "active" if active else "stalled"
                elif sid in completed:
                    state = "completed"
                else:
                    state = "pending"
                stages.append({"id": sid, "name": name, "state": state})

            # Tail: last ~60 cleaned, non-empty lines
            lines = [ln.rstrip() for ln in stripped.splitlines() if ln.strip()]
            tail = "\n".join(lines[-60:])

            self._send_json(200, {
                "has_log": True,
                "is_active": active,
                "stages": stages,
                "tail": tail,
                "log_path": str(log_path),
                "log_mtime": datetime.datetime.fromtimestamp(log_path.stat().st_mtime).isoformat(),
                "current_stage": current,
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _serve_resume_file(self, relpath: str):
        """Serve files from RESUME_ROOT — needed so the UI can link to tailored PDFs."""
        try:
            relpath = relpath.split("?", 1)[0].split("#", 1)[0]
            # URL-decode (filenames have spaces like "<Your Name> SWE Newgrad Resume Upstart.pdf")
            relpath = unquote(relpath)
            target = (RESUME_ROOT / relpath).resolve()
            # Safety: must be inside RESUME_ROOT
            if RESUME_ROOT.resolve() not in target.parents and target != RESUME_ROOT.resolve():
                self._send(403, "Forbidden", "text/plain")
                return
            if not target.exists() or not target.is_file():
                self._send(404, "Not Found", "text/plain")
                return
            ctype, _ = mimetypes.guess_type(str(target))
            ctype = ctype or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send(500, f"Error: {e}", "text/plain")

    def do_POST(self):
        if self.path == "/api/decide":
            self._handle_decide()
            return
        if self.path == "/api/cancel":
            self._handle_cancel()
            return
        self._send(404, "Not Found", "text/plain")

    def _handle_jobs(self):
        try:
            if not XLSX_PATH.exists():
                self._send_json(500, {"error": f"xlsx not found at {XLSX_PATH}"})
                return
            wb = load_workbook(XLSX_PATH, data_only=True)
            ws = wb["jobs"]
            headers = [c.value for c in ws[1]]
            rows = []
            counts = {"pending": 0, "yes": 0, "no": 0, "maybe": 0}
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not any(c not in (None, "") for c in r):
                    continue
                row = {k: ("" if v is None else str(v)) for k, v in zip(headers, r)}
                decision = (row.get("decision") or "").lower()
                counts[decision] = counts.get(decision, 0) + 1
                rows.append(row)
            self._send_json(200, {"rows": rows, "stats": counts})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_decide(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body) if body else {}
            job_id = int(data["id"])
            decision = str(data["decision"]).strip().lower()
            if decision not in {"pending", "yes", "no", "maybe"}:
                self._send_json(400, {"error": "decision must be pending/yes/no/maybe"})
                return
            try:
                wb = load_workbook(XLSX_PATH)
            except PermissionError:
                self._send_json(423, {"error": "jobs.xlsx is locked — close Excel first"})
                return
            ws = wb["jobs"]
            headers = [c.value for c in ws[1]]
            if "decision" not in headers:
                self._send_json(500, {"error": "no 'decision' column"})
                return
            decision_idx = headers.index("decision")
            rv_idx = headers.index("resume_version") if "resume_version" in headers else None

            # ONE-AT-A-TIME: if another job is currently tailoring, refuse to spawn a second one.
            if decision == "yes" and rv_idx is not None:
                for r in ws.iter_rows(min_row=2):
                    other_id = r[0].value
                    if other_id is None or other_id == job_id:
                        continue
                    if (r[rv_idx].value or "") == "tailoring":
                        self._send_json(409, {
                            "error": (
                                f"Already tailoring #{other_id}. Cancel that one first, "
                                f"or wait for it to finish."
                            ),
                            "active_tailor_id": other_id,
                        })
                        return

            found = False
            prev_resume_version = ""
            should_tailor = False
            for r in ws.iter_rows(min_row=2):
                if r[0].value == job_id:
                    r[decision_idx].value = decision
                    if rv_idx is not None:
                        prev_resume_version = (r[rv_idx].value or "")
                        # Only trigger tailoring when transitioning to yes from a non-yes / un-tailored state
                        if decision == "yes" and (not prev_resume_version or prev_resume_version.startswith("error:")):
                            r[rv_idx].value = "tailoring"
                            should_tailor = True
                    found = True
                    break
            if not found:
                self._send_json(404, {"error": f"id {job_id} not found"})
                return
            wb.save(XLSX_PATH)

            # Spawn Claude Code tailor pass AFTER the xlsx is saved
            log_path = None
            if should_tailor:
                log_path = spawn_claude_tailor(job_id)

            self._send_json(200, {
                "ok": True,
                "id": job_id,
                "decision": decision,
                "tailoring_started": should_tailor,
                "tailor_log": str(log_path) if log_path else None,
            })
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    def _handle_cancel(self):
        """Cancel an in-flight tailoring: clear resume_version, revert decision to pending.

        The spawned Claude Code process (and its Terminal window) is NOT killed —
        the user closes that manually. This endpoint just unblocks the UI so the
        user can re-trigger or pick a different job.
        """
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body) if body else {}
            job_id = int(data["id"])
            try:
                wb = load_workbook(XLSX_PATH)
            except PermissionError:
                self._send_json(423, {"error": "jobs.xlsx is locked — close Excel first"})
                return
            ws = wb["jobs"]
            headers = [c.value for c in ws[1]]
            decision_idx = headers.index("decision") if "decision" in headers else None
            rv_idx = headers.index("resume_version") if "resume_version" in headers else None
            found = False
            for r in ws.iter_rows(min_row=2):
                if r[0].value == job_id:
                    if decision_idx is not None:
                        r[decision_idx].value = "pending"
                    if rv_idx is not None:
                        r[rv_idx].value = ""
                    found = True
                    break
            if not found:
                self._send_json(404, {"error": f"id {job_id} not found"})
                return
            wb.save(XLSX_PATH)
            self._send_json(200, {"ok": True, "id": job_id, "decision": "pending"})
        except Exception as e:
            self._send_json(400, {"error": str(e)})


def open_browser_soon():
    def _open():
        try:
            webbrowser.open(f"http://localhost:{PORT}/")
        except Exception:
            pass
    t = threading.Timer(0.8, _open)
    t.daemon = True
    t.start()


def main():
    print("=" * 60)
    print(f"  Jobs Triage Server")
    print("=" * 60)
    print(f"  xlsx file : {XLSX_PATH}")
    print(f"  url       : http://localhost:{PORT}/")
    print(f"  stop      : Ctrl+C")
    print("=" * 60)
    if not XLSX_PATH.exists():
        print(f"⚠️  WARNING: {XLSX_PATH} does not exist yet.")
        print("   Run the daily job sourcing pipeline first.\n")
    open_browser_soon()
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
