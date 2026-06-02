# claude-job-pipeline

A daily AI-powered job-hunt pipeline you run on your own Mac. **Claude Code** scrapes the four major new-grad SWE job sources every day at noon, drops candidates into a spreadsheet, lets you triage them through a tiny local web UI, and — when you say ✓ Yes — spawns a fresh Claude Code session that tailors a 1-page LaTeX resume for that specific role.

Built on top of [Claude Code](https://claude.ai/code), [Claude in Chrome](https://claude.ai/chrome) (MCP browser tooling), and macOS `launchd`.

```
┌────────────┐    ┌─────────────────┐    ┌──────────────┐    ┌──────────────────┐
│ launchd    │ -> │ launch script   │ -> │ Claude Code  │ -> │ jobs.xlsx        │
│ noon daily │    │ (Terminal.app)  │    │ + Chrome MCP │    │ + email digest   │
└────────────┘    └─────────────────┘    └──────────────┘    └──────────────────┘
                                                                       │
                                                                       v
                                                              ┌─────────────────┐
                                                              │ Triage web UI   │
                                                              │ localhost:8765  │
                                                              │ + live pipeline │
                                                              │ view at /runs   │
                                                              └─────────┬───────┘
                                                                        │  ✓ Yes
                                                                        v
                                                              ┌────────────────────┐
                                                              │ Claude Code tailors │
                                                              │ 1-page LaTeX resume │
                                                              │ → versions/<co>.pdf │
                                                              └────────────────────┘
```

## What's inside

| Path | Purpose |
|---|---|
| `triage_server.py` | Localhost Python web UI (port 8765). Two pages: `/` for triaging the spreadsheet, `/runs` for an n8n-style live view of the daily sourcing pipeline. |
| `prompts/daily-sourcing.txt` | Thin prompt the cron feeds into `claude`. Just says "follow `job-sourcing-spec.md`." Don't edit to change behavior — edit the spec. |
| `scripts/launch_daily_sourcing.sh` | Bash + AppleScript wrapper. Kills lingering claude zombies, opens Terminal.app, runs Claude Code with the prompt as a CLI arg. |
| `launchd/daily-sourcing.plist.template` | macOS LaunchAgent — fires the launcher daily at 12:00 local time. Fill in placeholders before installing. |
| `job-sourcing-spec.md` | Source of truth for the daily sourcing pass. Targeting rules, sources (SimplifyJobs, jobright-ai, jobright minisite, LinkedIn), dedup logic, digest email. **Customize this for your hunt** (see "Customizing" below). |
| `resume-tailoring-spec.md` | Source of truth for the tailoring pass. 1-page quality rules, the "perfect-fit dial" (JD keyword extraction + honest re-framing), and the visual-verification loop. **Customize for your roles + killer metrics.** |

## Prerequisites

- **macOS** (the launcher uses AppleScript / Terminal.app / launchd).
- **Claude Code CLI** — install: <https://claude.ai/code>. The launcher expects `claude` at `~/.local/bin/claude` (the default install location) or anywhere on your `PATH`.
- **Claude in Chrome extension** + a logged-in Chrome session for LinkedIn and Gmail. Install: <https://claude.ai/chrome>. The spec uses `mcp__Claude_in_Chrome__*` tools to drive the browser sources.
- **Python 3** with `openpyxl` (auto-installed on first run of `triage_server.py`).
- **LaTeX** — required by the resume-tailoring half. Install MacTeX or BasicTeX, or use `tectonic` as a drop-in alternative.

## Install

```bash
# 1) Clone into wherever you like (the README assumes ~/Desktop/claude-job-pipeline,
#    but anywhere works — the scripts are path-relative).
cd ~/Desktop
git clone https://github.com/<YOUR_GITHUB_USER>/claude-job-pipeline.git
cd claude-job-pipeline

# 2) Make scripts executable.
chmod +x scripts/launch_daily_sourcing.sh triage_server.py

# 3) Add your resume materials (see "Resume materials layout" below) into this same directory
#    OR set RESUME_ROOT env var to point at a separate private directory.

# 4) Set up the LaunchAgent (the daily cron).
cp launchd/daily-sourcing.plist.template launchd/daily-sourcing.plist
# Open launchd/daily-sourcing.plist and replace the three placeholders:
#   {{USERNAME}}   -> your macOS short username  (run: whoami)
#   {{HOME}}       -> /Users/$(whoami)
#   {{REPO_PATH}}  -> absolute path to your clone (e.g. /Users/you/Desktop/claude-job-pipeline)

# 5) Symlink the plist into ~/Library/LaunchAgents/ and load it.
ln -sf "$(pwd)/launchd/daily-sourcing.plist" \
       ~/Library/LaunchAgents/com.$(whoami).daily-sourcing.plist
launchctl load ~/Library/LaunchAgents/com.$(whoami).daily-sourcing.plist
launchctl list | grep daily-sourcing   # should print a line — you're scheduled.
```

## First-run sanity test

Before trusting the noon schedule, fire the launcher manually:

```bash
bash scripts/launch_daily_sourcing.sh
```

A Terminal.app window should pop with Claude Code running. The log mirrors to `logs/sourcing-<timestamp>.log`. To watch it visually, in another shell:

```bash
python3 triage_server.py
# then open http://localhost:8765/runs
```

You'll see a pipeline diagram (Pre-flight → SimplifyJobs → jobright-ai repo → jobright minisite → LinkedIn → Filter → Dedupe → Append → Email → DONE) with the current stage pulsing.

## Daily workflow

1. **Noon** — `launchd` fires the sourcing run. If your laptop is asleep at noon, the missed run fires when you open the lid. (Reboot across noon = run is skipped; launchd doesn't replay across boots.)
2. **You open the triage UI** — `python3 triage_server.py` (or leave it running in the background). Browse to `http://localhost:8765/`.
3. **Triage** — each new row is a card with company, role, location, comp, source, and reasoning. Click ✓ Yes / ○ Maybe / ✗ No.
4. **Yes → tailoring auto-kicks off** — a new Terminal window opens with Claude Code tailoring a 1-page resume for that specific JD. The pipeline runs up to 4 verification iterations (compile → read PDF visually → check word count / widows / no whitespace gaps / killer metrics present → fix or finalize). When done, the card flips from "Tailoring…" to "✓ Resume ready · Open PDF ↗".
5. **One tailoring at a time.** Clicking ✓ on a second job while one is in flight returns a 409 and a toast. Use the **Cancel** button on the in-flight card to abort first.

## Resume materials layout

By default the tailoring spec expects your resume sources alongside the pipeline scripts:

```
claude-job-pipeline/
├── triage_server.py
├── job-sourcing-spec.md
├── resume-tailoring-spec.md
├── profile.md                # contact info, education (never tailored)
├── skills.md                 # broader skill inventory
├── experiences/              # one .md per role, bullets + narratives
│   ├── <company-a>.md
│   ├── <company-b>.md
│   └── ...
├── master/
│   ├── resume.tex            # 1-page LaTeX template (your master)
│   └── resume.md             # current shipping bullets, for reference
└── research/
    ├── findings.md           # per-target-company notes
    └── action-plan.md
```

These are **never committed** to this public template — they live only in your clone. The `.gitignore` excludes them.

If you'd rather keep resume sources in a separate private repo, set `RESUME_ROOT` and the triage server will look there:

```bash
RESUME_ROOT=~/private-resume python3 triage_server.py
```

## Customizing (start here when you clone)

The spec files are the source of truth. Search them for `[CUSTOMIZE]` markers:

```bash
grep -n '\[CUSTOMIZE\]' *.md
```

The high-value spots to edit:

**`job-sourcing-spec.md` §1 (Targeting)**
- Geo / metros you care about
- Comp floor
- Visa situation
- Prestige bar (your Tier-A list + wedge themes that match your background)
- Hard avoids (companies you've already interviewed at, products you don't believe in, locations that don't work)

**`resume-tailoring-spec.md`**
- §1 rule 5 — list your top 4–8 killer metrics so Claude knows to preserve them
- §3 Reordering rule — encode your role ordering rules (e.g. "current shipping role first, offer-in-hand second")
- §3 Bullet selection per role — list which bullets to feature for which JD themes
- §3 Projects + Organizations — your specifics

Don't edit `prompts/daily-sourcing.txt` to change targeting behavior — it's intentionally thin. Edit the spec.

## Live pipeline view

`http://localhost:8765/runs` shows the sourcing run as a 10-node n8n-style diagram with the active step pulsing and a live log tail underneath (auto-scrolling, refreshes every 2.5s). Use it during/after the noon run to see exactly where Claude is, what tool it's calling, and whether it got stuck.

## Operational tips

- **Logs:** every run writes `logs/sourcing-YYYYMMDD-HHMMSS.log`. `logs/launchd-stdout.log` / `launchd-stderr.log` capture the launcher itself.
- **Skip a day:** `launchctl unload ~/Library/LaunchAgents/com.$(whoami).daily-sourcing.plist`. Reload to resume.
- **Change the time:** edit `Hour`/`Minute` in the plist, then `unload` + `load`.
- **Zombie killer:** the launcher kills any prior `claude --chrome ... job-sourcing-spec.md` process before spawning a new one. Sleep cycles can leave Claude stuck on dead Chrome/API sockets indefinitely; the killer prevents pile-up.
- **Stuck tailor in the UI:** click **Cancel** on the spinning card. It clears the `tailoring` state and the decision; the Terminal window stays open (close it manually).
- **xlsx locked:** close Excel before clicking ✓ Yes (openpyxl can't write while Excel has the file open).

## Security & privacy

- All scraping runs in **your** local Chrome via Claude in Chrome — your existing LinkedIn / Gmail sessions, not credentials we ever see.
- The triage server binds to `127.0.0.1` only (not network-exposed).
- `jobs.xlsx`, `logs/`, `versions/`, and your resume materials are `.gitignore`d. **Don't commit them.**
- No secrets are read from disk by any script in this repo. If you fork and add a CI / hosted variant, you're on your own for secret handling.

## Acknowledgments

- [Claude Code](https://claude.ai/code) — Anthropic's CLI agent.
- [Claude in Chrome](https://claude.ai/chrome) — MCP browser tooling that lets Claude drive a logged-in browser.
- [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) and [jobright-ai/2026-Software-Engineer-New-Grad](https://github.com/jobright-ai/2026-Software-Engineer-New-Grad) — community-maintained new-grad sources.

## License

MIT — see [LICENSE](./LICENSE).
