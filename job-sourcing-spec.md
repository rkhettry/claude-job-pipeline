# Job Sourcing Spec — Daily Pipeline

> **Read me first.** This file is the source of truth for the scheduled job-sourcing task. The launcher prompt is intentionally thin — it just says "follow this spec." Edit the rules here, not the prompt.
>
> 🧰 **This is a template.** Search the file for `[CUSTOMIZE]` to find the spots most users will want to change. Defaults reflect one specific job hunt (Bay Area new-grad SWE/AI, 2026) — adapt them to yours.

**Owner:** <Your Name> (<your-email@example.com>)
**Runs:** daily at 12:00 local time via the LaunchAgent defined in `launchd/daily-sourcing.plist.template`
**Reads from:** the four sources listed below
**Writes to:** `./jobs.xlsx` (in the cloned repo root)
**Notifies via:** email to <your-email@example.com> after each run (Claude in Chrome → Gmail web)

---

## 1. Targeting (what makes the cut)

A job goes in the sheet only if **every** rule below is true. When in doubt, mark `prestige=unsure` and let the user triage in the web UI — bias toward a tight, high-quality list rather than recall.

- **[CUSTOMIZE] Role:** SWE / Software Engineer / Software Developer / SDE / Backend / Full-stack / ML Engineer / AI Engineer / Applied AI. PM/APM included **only** if it's an exceptional fit (top-tier company AND clearly elite program).
- **[CUSTOMIZE] Level:** new-grad / entry-level / university / 2026 grad / "0–2 years" / SWE I / L3. Drop anything labeled senior, staff, principal, manager, lead.
- **[CUSTOMIZE] Geo:** the metro(s) you care about (default: California any city; other US metros only if top-tier; Remote-US OK if comp + company clear the bar).
- **[CUSTOMIZE] Visa:** state your situation (e.g. "candidate is a US citizen — don't filter on sponsorship", or "candidate needs sponsorship — drop roles that explicitly say no").
- **[CUSTOMIZE] Comp floor:** ~$150K base or higher (default). If comp isn't listed, infer from company tier + Levels.fyi norms; if you can't infer, mark `comp=unknown` and include only if clearly tier-A.
- **Freshness:** trust the source's stated timestamp. Include rows the source labels ≤1 day old.
  - All kept rows get `freshness=fresh`. We no longer distinguish verified vs unverified.
  - **Tier-A/wedge override:** if the source timestamp says >1 day but the company is clearly Tier-A or strong-wedge fit, include it anyway with `freshness=older`. An older posting at a top company is still worth pursuing.
  - **NO API verification step.** Do NOT call Greenhouse/Lever/Ashby/Workday APIs to cross-check post dates. (This step caused multi-hour stalls in earlier versions when an API rate-limited or the Chrome extension hiccuped mid-run.) Accept some false-fresh rows in exchange for a pipeline that completes reliably — the human triages obviously-old reposts in the web UI.
- **[CUSTOMIZE] Prestige bar:** must be **strictly better than the candidate's current best offer** (or whatever floor matters to them). One of:
  - **Tier A** (auto-include) — example list, edit to taste: FAANG, Anthropic, OpenAI, Google DeepMind, xAI, Meta GenAI, Apple ML, Microsoft AI; AI unicorns with $1B+ valuation; YC unicorns; Stripe, Ramp, Notion, Figma, Databricks, Snowflake; Vercel, Replit, Cursor/Anysphere, Modal, Sierra, Decagon, Glean, Harvey, Perplexity, Cohere, Scale, Hugging Face, Mistral, AI21.
  - **Strong wedge fit** (auto-include) — example wedges: multimodal AI, agentic AI, voice AI, RAG infra, dev tools, healthcare AI. Customize per your background — pick wedges where your projects/experience map directly onto the company's stack.
  - **Borderline** → `prestige=unsure`: Series A AI startups with notable founders/investors but low brand recognition. Surface them but flag.
- **[CUSTOMIZE] Hard avoids** (always drop) — your personal "no thanks" list. Example starter set: consulting firms (Accenture, Deloitte), traditional enterprise IT, defense/intel primes, "junior" roles inside non-tech-first companies (banks, retailers, insurance). Edit this list for companies you've already interviewed at, products you don't believe in, locations that don't work, etc.
- **Volume cap:** **soft target ~3–8 new rows per run, quality-first** (hard cap 20). You want a small list of teams actively hiring, not 30 recycled reqs. Prioritize `freshness=fresh` rows, then `older` (active Tier-A/wedge). If over the cap after filtering, keep the best by (freshness: fresh > older) then tier (Tier-A > wedge > unsure). It's fine to surface only 1–3 on a slow day — quality over recall.

---

## 2. Sources & how to parse each

### 2.1 SimplifyJobs/New-Grad-Positions

- URL: https://github.com/SimplifyJobs/New-Grad-Positions
- Raw README: https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md
- Format: a markdown table inside the README. Columns vary slightly but typically: `Company | Role | Location | Application/Link | Date Posted` (sometimes shown as "Age" like `1d`, `2d`).
- Parsing strategy: `web_fetch` the raw README. If it exceeds the token limit (it usually does), save to disk and grep + read in chunks. Look for lines starting with `| ` and the section under the table that lists open positions. Closed/expired roles are marked with 🔒 or strikethrough — skip them.
- **web_fetch provenance gotcha:** scheduled runs sometimes get "URL not in provenance set" on the raw README. Workaround: first `web_fetch` the HTML page (`https://github.com/SimplifyJobs/New-Grad-Positions`) — that seeds provenance — then re-fetch the raw URL.
- Freshness: use the `Date Posted` / `Age` column. Anything older than 1 day → drop.
- Dedupe key: canonical apply URL (strip tracking params like `?utm_*`, `?gh_src=*`).

### 2.2 jobright-ai/2026-Software-Engineer-New-Grad

- URL: https://github.com/jobright-ai/2026-Software-Engineer-New-Grad
- Raw README: https://raw.githubusercontent.com/jobright-ai/2026-Software-Engineer-New-Grad/main/README.md
- Format: same general shape as SimplifyJobs — markdown table with date column. Sometimes includes salary band.
- **Maintenance warning:** as of 2026-05-27 dry run, this repo appeared to have a stale top row (dated Mar 27). The maintainer may pause updates for stretches. If the most-recent row is >7 days old, treat the source as stale for this run — log it, contribute 0 rows, and continue. Don't fail the pipeline.
- Parsing strategy: same as 2.1 (web_fetch raw, chunk if needed). Same provenance workaround applies — fetch HTML page first if raw URL is blocked.
- Freshness: use the listed date column; drop >1 day old.

### 2.3 jobright.ai new-grad SWE minisite (the real source behind newgrad-jobs.com)

- **Use this URL directly:** https://jobright.ai/minisites-jobs/newgrad/us/swe?embed=true
- Investigation on 2026-05-27 found that `newgrad-jobs.com` is a thin wrapper around this jobright.ai minisite (loaded as an iframe). The previously-cited Airtable embed (`appzSWTM1QA543oU/shrpvJsQjbhk8l9pi`) is a hidden 0×0 abandoned iframe — ignore it.
- **Note: same company as §2.2** (jobright-ai), but a different surface. The GitHub repo is stale; this minisite is live and updates hourly. If only one is healthy, prefer this one.
- **Parsing strategy:** use Claude in Chrome.
  1. Navigate to the URL above. Wait ~5 seconds for the table to render.
  2. **MANDATORY filter step — set "Is New Grad" dropdown to "Yes" before extracting any data.** The unfiltered table contains many non-new-grad SWE postings that pollute results. The page has a column-header dropdown labeled "Is New Grad" with options Yes / No / All. Click that dropdown, select **Yes**, and wait ~3 more seconds for the filtered table to re-render. Verify the filter applied by checking the visible row count dropped (typically from 100+ to <40) before continuing. If you cannot find or interact with the filter, log it and continue with the unfiltered table — but flag in the digest: "⚠️ Could not apply Is New Grad=Yes filter to jobright minisite — results may include non-new-grad roles."
  3. Read text via `mcp__Claude_in_Chrome__javascript_tool` evaluating `document.body.innerText`. The table is structured as repeated row blocks with columns: row number, Position Title, Date ("X hour(s) ago" / "X day(s) ago"), Apply, Work Model (Remote/Hybrid/Onsite), Location, Company, Salary, Company Size, Company Industry, Qualifications, H1B Sponsored, Is New Grad.
  4. Parse by splitting on the row-number boundary or by regex on the time-ago column.
  5. Avoid `document.querySelectorAll('a[href]')` introspection — Claude in Chrome's safety rails block iterating hrefs with query strings, which kills the JS call entirely. Use only `innerText` for extraction. To get an actual apply URL, click the "Apply" link/button for a specific row and capture the destination in the new tab.
- **Capture per row:** company, role title, location, posted-time-ago, salary band, company size, industry, H1B flag, is-new-grad flag, apply URL.
- **Freshness:** the site shows "X hours ago" / "X days ago" inline — drop anything ≥2 days.
- **Quality boost:** this source surfaces salary inline (rare elsewhere). Use the salary band to enforce the $150K+ floor directly here — drop rows with `comp_top < 150000` if expressed as a yearly band. Hourly bands need conversion (multiply hourly_top × 2080).
- **PRESTIGE: this is a high-volume aggregator.** A typical run will see 20+ fresh entries here, of which most are mid-tier companies that don't clear your bar. Apply §1's prestige rules **strictly** — when in doubt, drop rather than mark `unsure`. Only pull rows where the company is clearly Tier-A (FAANG, top AI labs, named AI unicorns) or a strong wedge fit (multimodal / agents / voice AI / RAG infra / dev tools / healthcare AI from the curated list in `~/your-resume/research/findings.md`). The volume cap (§1) still applies — 20 hard max across all sources.
- **Fallback:** if the embed URL is blocked, fall back to navigating https://www.newgrad-jobs.com/ in Chrome, then find and click into the visible (non-zero-size) `iframe[src*="jobright.ai"]` to re-derive the current minisite URL.
- If the page won't render the list at all, skip this source for the run and note it in the digest. Don't fail the pipeline.

### 2.4 LinkedIn — fresh new-grad SWE search

- Use Claude in Chrome with your existing logged-in LinkedIn session.
- Run **three** searches (open each in a tab, scrape first page only):
  1. `https://www.linkedin.com/jobs/search/?keywords=software%20engineer%20new%20grad%202026&location=California%2C%20United%20States&f_TPR=r86400&f_E=2`
  2. `https://www.linkedin.com/jobs/search/?keywords=new%20grad%20software%20engineer&location=San%20Francisco%20Bay%20Area&f_TPR=r86400&f_E=2`
  3. `https://www.linkedin.com/jobs/search/?keywords=AI%20engineer%20new%20grad&location=California%2C%20United%20States&f_TPR=r86400&f_E=2`
- `f_TPR=r86400` = past 24 hours. `f_E=2` = entry-level.
- For each result, capture company, title, location, posted time, job URL. Click into a listing only if you need salary or to confirm new-grad fit.
- Tip: LinkedIn's anti-bot is sensitive. Random 3–6s waits between scrolls/clicks. Bail gracefully if you hit a captcha — don't retry in a tight loop.

---

### 2.5 ~~Freshness verification~~ — REMOVED 2026-06-01

**This step is DISABLED.** Do not call any ATS API (Greenhouse, Lever, Ashby, Workday, amazon.jobs) to cross-check dates. The verification loop caused multi-hour stalls when an API rate-limited or the Chrome extension hiccuped mid-run.

Trust the source's stated `X hours/days ago` timestamp per §1. If a row turns out to be an old repost, you catch it manually during triage — the cost of one bad row in the digest is much lower than the cost of the whole pipeline hanging.

If this section ever needs to be re-enabled, restore from git history and add a hard per-API timeout (e.g., 10s) and a max-total-budget for the verification phase (e.g., 5 minutes), then bail with `unverified` on timeout rather than retrying forever.

---

## 3. Dedup (don't re-add what's already in the sheet)

Before appending a row, check the existing `jobs.xlsx`:

1. **Canonical URL match:** strip query params (`?utm_*`, `?gh_src=*`, `?lever-source=*`, `?source=linkedin`), trailing slashes, and `www.` from both the new and existing URLs. If a normalized URL matches an existing row → skip.
2. **Company + role fuzzy match:** if `(company.lower(), role.lower())` matches an existing pending/applied row → skip even if URL differs (often the same posting on different boards).

Don't update existing rows. Only append new ones.

---

## 4. Spreadsheet schema (`jobs.xlsx`, sheet `jobs`)

Columns, in order:

| # | column | type | notes |
|---|---|---|---|
| 1 | `id` | int | auto-increment, 1-based |
| 2 | `date_sourced` | YYYY-MM-DD | the day this row was added |
| 3 | `posted_date` | YYYY-MM-DD or `unknown` | **verified real post/maintenance date** where obtainable (§2.5), else the source's claimed date |
| 4 | `freshness` | str | `fresh` (verified ≤2d, not reposted) / `older` (Tier-A/wedge, active ≤30d or recently reposted) / `stale` (>30d) / `unverified` (no date obtainable). Simplify rows = `fresh`. |
| 5 | `company` | str | clean name (e.g. "OpenAI", not "OpenAI Inc.") |
| 6 | `role` | str | title as listed |
| 7 | `location` | str | "San Francisco, CA" / "Remote (US)" / "New York, NY" |
| 8 | `comp` | str | e.g. "$180K base" / "$200–250K TC" / "unknown" |
| 9 | `source` | str | one of: `simplify` / `jobright` / `newgrad-jobs` / `linkedin` |
| 10 | `apply_url` | str | direct apply URL (NOT the source page) |
| 11 | `tier` | str | `A` / `wedge` / `unsure` |
| 12 | `reasoning` | str | 1 line: why this passed the prestige bar (e.g. "Anthropic — auto-include tier-A") |
| 13 | `decision` | str | always `pending` on insert. you edit to `yes` / `no` / `maybe`. |
| 14 | `applied_date` | YYYY-MM-DD or empty | you fill when applied |
| 15 | `resume_version` | str | path to tailored resume folder if applicable, else empty |
| 16 | `notes` | str | freeform; verification evidence (e.g. "LinkedIn 'Reposted 6h ago'") goes here |

If the file doesn't exist when the task runs, **create it** with these headers in row 1 (bold), then append.

---

## 5. Workflow (the actual loop the task runs)

1. **Pre-flight:** `Read` this spec file. `Read` the current `~/claude-job-pipeline/jobs.xlsx` to build a set of existing canonical URLs and (company, role) tuples for dedup.
2. **Pull sources in parallel where possible:**
   - `web_fetch` SimplifyJobs raw README (§2.1)
   - `web_fetch` jobright-ai raw README (§2.2)
   - Claude in Chrome → newgrad-jobs Airtable (§2.3)
   - Claude in Chrome → LinkedIn × 3 searches (§2.4)
3. **Normalize each candidate into the schema in §4.**
4. **Apply targeting filters from §1** in this order: role → level → geo → freshness → hard-avoid → prestige. Drop early; cheaper.
5. **Dedup against existing rows** per §3.
6. **Apply volume cap** (≤20 hard, ~10 soft preference).
7. **Append surviving rows to `jobs.xlsx`** with `decision=pending`.
8. **Send the daily digest email** per §6.
9. **Print a 1-paragraph summary to the run log** so you see it as a notification: total scanned per source, total kept, list of company names added.

If zero new rows survive, still send the email (subject "No new jobs today, here's why") with a one-paragraph note on what was scanned + filter counts, so you know the pipeline ran.

---

## 6. Daily digest email

**To:** <your-email@example.com> (you email yourself from his own Gmail)
**From:** <your-email@example.com> (his logged-in session)
**Subject:** `Daily jobs digest — YYYY-MM-DD — N new` (e.g. `Daily jobs digest — 2026-05-28 — 4 new`)

**Body (HTML, simple):**

```
Hey there — daily sourcing pass complete.

NEW JOBS ADDED (N):

1. <company> — <role>
   Location: <location> · Comp: <comp> · Tier: <tier>
   Why it passed: <reasoning>
   Apply: <apply_url>
   Posted: <posted_date> · Source: <source>

2. ...

---
Open jobs.xlsx to triage: ~/claude-job-pipeline/jobs.xlsx
Spec: ~/claude-job-pipeline/job-sourcing-spec.md
```

If `N == 0`, body is:
```
Hey there — daily sourcing pass complete. No new jobs cleared the bar today.

Scanned: Simplify (X candidates → Y after filters), jobright (X → Y),
newgrad-jobs (X → Y), LinkedIn (X → Y).

Top filter drops: <stale: N> <wrong role: N> <below prestige bar: N> <hard avoid: N> <duplicates: N>
```

**How to send (no Gmail MCP available — use Claude in Chrome):**

Gmail's compose body is a `contenteditable` div, NOT a textarea. Naive typing tools silently no-op on it. Follow this sequence precisely — the 2026-05-27 dry run hit a blank-body failure and the procedure below is the verified fix.

1. `mcp__Claude_in_Chrome__navigate` to https://mail.google.com. Wait for inbox.
2. Click the **Compose** button (upper-left). Wait for compose modal.
3. **To field:** find the To input, set value via the native value setter, dispatch `input` event, then dispatch synthetic `Enter` keydown to commit the chip. After committing, verify by querying `dialog.querySelector('[email="<your-email@example.com>"]')` — the input's `.value` is cleared once the chip exists, so don't read the input.
4. **Subject:** click the Subject input, type the subject string.
5. **Body — this is the tricky part. Use the DOM-node method as PRIMARY (it's focus-independent and Trusted-Types-safe); fall back to `execCommand` only if needed.**
   - Selector: `div[role="dialog"] div[aria-label="Message Body"]` (class chain `Am aiL Al editable`, `contenteditable=true`).
   - **Why not `execCommand`/`innerHTML` first:** verified 2026-05-28 — `document.execCommand('insertText', …)` **silently returns `false` and inserts nothing when the browser window doesn't hold OS focus** (i.e. every headless/cron run, and any time the window is backgrounded). And `body.innerHTML = …` throws `This document requires 'TrustedHTML' assignment` (Gmail enforces Trusted Types). The earlier `execCommand` recipe only worked when the window happened to be foregrounded.
   - **PRIMARY recipe — build DOM nodes (no focus, no innerHTML):**
     ```js
     const body = document.querySelector('div[role="dialog"] div[aria-label="Message Body"]');
     while (body.firstChild) body.removeChild(body.firstChild);
     BODY_TEXT.split('\n').forEach(line => {
       const div = document.createElement('div');
       if (line === '') div.appendChild(document.createElement('br'));
       else div.appendChild(document.createTextNode(line));   // textNode = no HTML injection, dodges Trusted Types
       body.appendChild(div);
     });
     body.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }));
     ```
     Each line becomes its own `<div>`, blank lines get a `<br>` — Gmail renders the paragraph breaks correctly and reads this DOM when sending.
   - **Fallback recipe** (only if the DOM-node method ever leaves `textContent.length` short): focus the div, place a collapsed `Range`/`Selection` at end, then `document.execCommand('insertText', false, BODY_TEXT)`. This needs the window foregrounded, so it's the backup, not the default.
6. **VERIFY before sending** (mandatory gate, do not skip):
   - Read back `body.textContent.length` — must be > 200.
   - Confirm the textContent contains a sentinel: at least one company name from the digest (e.g. the first company in §6 body). If sentinel missing → retry the body fill (max 2 retries). If still failing after 2 retries → STOP, write the digest to `~/claude-job-pipeline/digest-YYYY-MM-DD.md`, do NOT send a blank email.
7. **Send:** the Send button is `div[role="dialog"] div[role="button"][data-tooltip^="Send"]` (the `aria-label` contains a directional-formatting char — match by `startsWith("Send")` or `data-tooltip` prefix, not equality).
8. Wait for the "Message sent" toast text to appear before closing/navigating away. If toast doesn't appear within 5s, do not assume success.

**Fallback:** if Gmail is not logged in, or the body-fill verification gate fails twice, write the formatted digest to `~/claude-job-pipeline/digest-YYYY-MM-DD.md` and log "email skipped — see digest md fallback" in the run summary. Do NOT send a blank-body email.

---

## 7. Error handling

- **Source down / fetch fails:** log it, skip that source, continue with the others. Don't block the whole run on one source.
- **Token-limit on raw README:** save to disk, grep + read in chunks (this is normal, not an error).
- **LinkedIn captcha:** stop scraping LinkedIn, continue with whatever was already captured, note "LinkedIn skipped — captcha" in the email digest.
- **xlsx locked (file open in Excel):** log it, write to `jobs-pending-merge-YYYY-MM-DD.xlsx` instead, and mention in the email digest that you should close Excel + merge manually.
- **No new rows:** still send the email (per §6).

---

## 8. Things you may want to tweak over time

These are the dials. Search-replace these strings if you want to change behavior without rewriting the spec:

- Comp floor: `$150K base or higher`
- Volume hard cap: `hard cap 20`
- Geo: `California (any city). Other US metros...`
- Run time: lives in the scheduled task, not here — update via `update_scheduled_task` for `daily-job-sourcing`.
- Hard-avoid list: §1, "Hard avoids" bullet.
- Tier-A allowlist: §1, "Tier A" bullet.
