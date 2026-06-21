# Buyer setup guide

Goal: get this pipeline running on your Mac in under an hour.

## Prerequisites (REQUIRED, install BEFORE you do anything else)

- **macOS** (the launchd scheduler + AppleScript window management is Mac-only)
- **Claude Code subscription** (Pro $20/mo or Max $100/mo). Install from [claude.ai/code](https://claude.ai/code), then run `claude login` once to OAuth.
- **LinkedIn Premium Career** ($40/mo). Required for the outreach DMs to work without monthly note caps. Free tier is capped at 3 personalized notes/month, which kills the outreach loop after the first day.
- **Chrome browser** with the **Claude in Chrome** extension installed and the LinkedIn account you'll use logged in.
- **Python 3.10+** (macOS ships with this) and **tectonic** for LaTeX compilation:
  ```bash
  brew install tectonic
  ```

If you don't have all of the above, stop and install them first.

## Setup — 5 steps

### 1. Clone the repo + cd in

```bash
git clone <repo-url> ~/job-pipeline
cd ~/job-pipeline
```

### 2. Fill in `config/user.yaml`

This is the single source of truth for your identity, job preferences, and prestige bar. Every spec reads from it.

```bash
cp config/user.example.yaml config/user.yaml
$EDITOR config/user.yaml
```

Fields you must fill in:
- `identity.full_name`, `email`, `phone`, `linkedin_url`, `github_url`
- `job_preferences.level` (new-grad / internship / early-career / senior)
- `job_preferences.target_role_types` (the titles you'd apply to)
- `job_preferences.preferred_locations.primary` (your top cities)
- `job_preferences.comp_floor_k` (your minimum comp)
- `prestige.tier_a_companies` (your dream-company list — customize this carefully, it's how the sourcer prioritizes)
- `prestige.hard_avoid` (companies you'd never work at)
- `resume.filename_pattern` (e.g. `"Jane Doe SWE {company}"`)
- `resume.killer_metrics` (your strongest quantified wins)
- `resume.hard_facts.education`, `gpa`, `graduation`
- `digest_email` (where the daily digest goes)

The file is heavily commented. Read the comments as you go.

### 3. Fill in `master/resume.tex`

This is your actual LaTeX resume. The tailoring spec reads this and rewrites bullets per-job.

```bash
cp master/resume.example.tex master/resume.tex
$EDITOR master/resume.tex
```

The template has TODO markers. Fill in:
- **Heading**: your name, contact info (must match `config/user.yaml`)
- **Education**: school, degree, GPA, graduation
- **Experience**: one `\resumeSubheading` block per past job, with 2-3 `\resumeItem` bullets each
- **Projects**: 1-2 strong personal projects
- **Technical Skills**: customize the categories to your stack
- **Organizations**: optional, 1-2 lines of leadership

**Do NOT change the macros** (`\resumeSubheading`, `\resumeItem`, etc.). The tailoring spec depends on parsing those.

Test the compile:
```bash
cd master && tectonic resume.tex && open resume.pdf
```

If the PDF looks like a clean one-pager, you're good.

### 4. Set up the digest email (SMTP)

The daily digest emails itself to you via Gmail SMTP — no Chrome needed. Set it up once:

```bash
cp config/smtp.example.json config/smtp.json
$EDITOR config/smtp.json
```

Fill in `sender_email` (your Gmail) and `app_password` — a Gmail **App Password**, NOT your login password. Generate at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification on). The recipient is `digest_email` from `config/user.yaml`. Skip this and you'll still get `digest-YYYY-MM-DD.md` written each run — just no email.

### 5. (Optional) Customize the company watchlist

`config/watchlist.json` ships with a large curated company list that polls each board directly for fresh new-grad roles. To make it yours: edit the list, then `python3 automation/watchlist_discover.py` to resolve each board. The starter list works out of the box.

### 6. Run the triage server

```bash
python3 automation/triage_server.py
```

Opens at [http://localhost:8765](http://localhost:8765). You should see an empty triage UI (no jobs sourced yet). The 📡 **Live** button in the top bar opens the run viewer that streams every Claude run.

### 7. Test end-to-end

In the triage UI:
1. Click **+ Add JD** in the top right
2. Paste a real job-posting URL or the JD text
3. Watch Claude open a Terminal window, tailor your resume, and write a PDF to `versions/<slug>/`
4. Click the **Open PDF** link in the UI to view the result

If the PDF has YOUR name, YOUR experience reframed for the JD, and looks like a clean one-pager — you're set.

## Daily sourcing (optional — sets up the noon-PT scheduled run)

Edit `scripts/launch_daily_sourcing.sh` to point at your repo path, then install the launchd plist (see `launchd/` directory for the template).

## How the pipeline works (mental model)

- **`config/user.yaml`** → your identity + preferences. Source of truth.
- **`master/resume.tex`** → your actual resume content. Source of truth.
- **`automation/job-sourcing-spec.md`** → tells Claude how to find jobs that fit you (reads user.yaml).
- **`automation/resume-tailoring-spec.md`** → tells Claude how to rewrite your resume per JD (reads user.yaml + master/resume.tex).
- **`automation/outreach-lead-finder-spec.md`** → tells Claude how to find LinkedIn recruiters at the target company.
- **`automation/outreach-sender-spec.md`** → tells Claude how to send messages to approved leads.
- **`automation/verify-date-spec.md`** → tells Claude how to verify the actual posted date of a job.
- **`automation/watchlist_poller.py`** + **`config/watchlist.json`** → polls company job boards directly (no Claude) for fresh new-grad roles, runs first each day.
- **`automation/send_digest.py`** + **`config/smtp.json`** → emails you the daily digest via SMTP, headless.
- **`automation/triage_server.py`** → the local web UI you use to triage jobs + trigger tailoring + manage outreach, plus the 📡 live run viewer at `/runs`.

Edit `config/user.yaml` when your preferences change. Edit `master/resume.tex` when your work history changes. You almost never need to edit the specs — the specs read from your config.

## Troubleshooting

**"unable to connect to the API" in a spawned terminal**
Your Claude Code OAuth token expired. In any working terminal, run `claude login` and re-auth. New task spawns will use the refreshed token.

**Stuck Claude terminals piling up**
Click the **🧹** button in the top bar of the triage UI to close all stuck task terminals (Terminal.app only, never touches iTerm2). For one job's spawn, use the **⋯** per-row menu.

**LaTeX won't compile**
Make sure tectonic is installed (`brew install tectonic`). The `master/resume.example.tex` should compile out of the box; if it doesn't, something's off with your tectonic install.

**Outreach hits a limit immediately**
You're probably on free LinkedIn. Premium Career is required for unlimited personalized notes. Confirm at [linkedin.com/premium](https://linkedin.com/premium).

**Daily sourcing doesn't fire**
Check the launchd job is loaded: `launchctl list | grep daily-sourcing`. The plist needs absolute paths matching your repo location.

## Support

- 7 days of Discord DM support from purchase
- After that: community-supported via the buyer Discord channel
- Future updates are bonus, not guaranteed

## License

Personal use only. Do not resell or share the repo. The price is below the cost of building this yourself; respect the work.
