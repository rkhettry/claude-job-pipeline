# claude-job-pipeline

A daily AI-powered job-hunt pipeline you run on your own Mac. Every day at noon it (1) polls **hundreds of company job boards directly** via their public ATS APIs for fresh new-grad roles, then (2) has **Claude Code** scrape the major new-grad SWE aggregators, drops candidates into a spreadsheet, emails you a digest, lets you triage through a tiny local web UI, and — when you say ✓ Yes — spawns a fresh Claude Code session that tailors a 1-page LaTeX resume for that specific role. A live viewer streams every Claude run in real time.

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
| `triage_server.py` | Localhost Python web UI (port 8765). Two pages: `/` for triaging the spreadsheet, `/runs` for a 📡 live viewer that streams **every** Claude run (sourcing, tailor, outreach, verify-date) in real time. |
| `watchlist_poller.py` | Polls hundreds of company job boards directly via their public ATS APIs (Greenhouse / Lever / Ashby / SmartRecruiters) for fresh, explicitly-new-grad roles. Pure Python, no Claude tokens, ~60s. Runs first each day so its hits land before the Claude aggregator pass. |
| `watchlist_discover.py` | One-time helper that resolves each company in `config/watchlist.json` to its ATS + board slug. Run it after editing the watchlist. |
| `config/watchlist.json` | The company watchlist (name → ATS + slug). Ships with a large curated starter list; edit it to match the companies you'd actually take an offer from. |
| `send_digest.py` | Emails the daily digest via Gmail SMTP — fully headless, **no Chrome needed**. Reads `config/smtp.json` (gitignored). |
| `config/smtp.example.json` | Template for SMTP credentials. Copy to `config/smtp.json` and add a Gmail App Password. |
| `config/user.example.yaml` | Single source of truth for your identity, job preferences, prestige bar, and resume settings. Copy to `config/user.yaml` and fill in. |
| `prompts/daily-sourcing.txt` | Thin prompt the cron feeds into `claude`. Just says "follow `job-sourcing-spec.md`." Don't edit to change behavior — edit the spec. |
| `scripts/launch_daily_sourcing.sh` | Bash + AppleScript wrapper. Runs the watchlist poll, opens Terminal.app, runs Claude Code, then emails the digest via SMTP. |
| `launchd/daily-sourcing.plist.template` | macOS LaunchAgent — fires the launcher daily at 12:00 local time. Fill in placeholders before installing. |
| `job-sourcing-spec.md` | Source of truth for the Claude aggregator pass. Targeting rules, sources (SimplifyJobs, jobright-ai repo + minisite, Hacker News "Who's hiring"), dedup logic, digest. **Customize this for your hunt** (see "Customizing" below). |
| `resume-tailoring-spec.md` | Source of truth for the tailoring pass. 1-page quality rules, the "perfect-fit dial" (JD keyword extraction + honest re-framing), and the visual-verification loop. **Customize for your roles + killer metrics.** |

## Prerequisites

- **macOS** (the launcher uses AppleScript / Terminal.app / launchd).
- **Claude Code CLI** — install: <https://claude.ai/code>. The launcher expects `claude` at `~/.local/bin/claude` (the default install location) or anywhere on your `PATH`.
- **Claude in Chrome extension** + a logged-in Chrome session for LinkedIn and Gmail. Install: <https://claude.ai/chrome>. The spec uses `mcp__Claude_in_Chrome__*` tools to drive the browser sources.
- **Python 3** with `openpyxl` (auto-installed on first run of `triage_server.py`).
- **LaTeX** — required by the resume-tailoring half. Install MacTeX or BasicTeX, or use `tectonic` as a drop-in alternative.
- **A Gmail App Password** (optional but recommended) — for the headless SMTP digest email. Generate one at <https://myaccount.google.com/apppasswords> (requires 2-Step Verification), then `cp config/smtp.example.json config/smtp.json` and fill it in. Without this, the digest is still written to `digest-YYYY-MM-DD.md` each run; you just won't get the email.

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

You'll see the run appear in the 📡 live viewer's sidebar with a pulsing **LIVE** badge; click it to stream Claude's reasoning, every tool call, every Chrome page it opens, and the final summary as they happen.

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

## Watchlist (direct-from-ATS sourcing)

`config/watchlist.json` is a list of companies you'd actually take an offer from. Each day `watchlist_poller.py` hits each company's public job-board API directly (Greenhouse / Lever / Ashby / SmartRecruiters — the same feed the careers page renders), filters for **explicitly** new-grad software roles posted in the **last 2 days**, and appends fresh hits straight into `jobs.xlsx`. This catches roles the hour they go live — often before the aggregators have them.

To customize:
1. Edit `config/watchlist.json` — add/remove companies (name + `hints` slug guesses).
2. Run `python3 watchlist_discover.py` to resolve each company's ATS + board slug.
3. `python3 watchlist_poller.py --test` to preview matches without writing anything.

It's deliberately strict: a role only lands in the sheet if the title or JD literally says new grad / entry level / 0–1 years and it's CA-or-US-remote and freshly posted. Quiet days are expected — explicit new-grad reqs cluster around fall recruiting.

## Daily digest email (SMTP)

After each run, `send_digest.py` emails you the digest via Gmail SMTP — no Chrome required, works fully headless. The sourcing run always writes `digest-YYYY-MM-DD.md`; the SMTP step sends it. Set it up once: `cp config/smtp.example.json config/smtp.json` and add a Gmail [App Password](https://myaccount.google.com/apppasswords). Recipient comes from `config/user.yaml` → `digest_email`.

## Live run viewer

`http://localhost:8765/runs` (the 📡 button in the triage top bar) lists **every** Claude run from the last 48h — sourcing, resume tailors, outreach, verify-date — each with a pulsing **LIVE** badge while running. Click one to watch a console-style feed that updates every 2s: Claude's reasoning, every command and Chrome page it opens, tool results, and a final summary card with duration + cost. This works because every spawn runs with `--output-format stream-json`, so the log fills in event-by-event as the run happens (not buffered until the end).

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
- `jobs.xlsx`, `logs/`, `versions/`, `digest-*.md`, `config/user.yaml`, `config/smtp.json`, and your resume materials are all `.gitignore`d. **Don't commit them.**
- The one secret on disk is `config/smtp.json` (your Gmail App Password). It's gitignored, used only by `send_digest.py` to send mail to yourself, and revocable anytime from your Google account. Never commit it. An App Password is not your Google login password and only grants mail-send.

## Acknowledgments

- [Claude Code](https://claude.ai/code) — Anthropic's CLI agent.
- [Claude in Chrome](https://claude.ai/chrome) — MCP browser tooling that lets Claude drive a logged-in browser.
- [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) and [jobright-ai/2026-Software-Engineer-New-Grad](https://github.com/jobright-ai/2026-Software-Engineer-New-Grad) — community-maintained new-grad sources.

## License

MIT — see [LICENSE](./LICENSE).
