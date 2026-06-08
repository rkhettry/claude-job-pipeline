# Job Sourcing Spec — Daily Pipeline

> **Read me first.** This file is the source of truth for the scheduled job-sourcing task. The task prompt just says "follow this spec." Edit the rules here — do not edit the scheduled task prompt.

## §0 Configuration (READ BEFORE EVERYTHING ELSE)

**Before anything else, read `<REPO_ROOT>/automation/config/user.yaml`.** That file contains:

- `identity` — the owner's name, email, work-auth status
- `job_preferences` — level, target roles, locations, comp floor, years-experience drop rule
- `prestige` — tier-A companies, wedge categories, hard-avoid list, current-offers floor
- `digest_email` — where the run summary email goes

Throughout this spec, when a section mentions a specific value (e.g. "$150k comp floor", "the user's hard-avoid list", "Bay Area focus"), **use the value from user.yaml**, not the inline value. The inline values are illustrative defaults for the template owner; they may not apply to the current user.

If `config/user.yaml` is missing, halt immediately with `ERROR — missing config/user.yaml; copy user.example.yaml to user.yaml and fill in your values`.

---

**Owner:** see `config/user.yaml` → `identity.full_name` / `identity.email`
**Last updated:** 2026-05-27
**Runs:** daily at 12:00 PT via `daily-job-sourcing` scheduled task
**Reads from:** the four sources listed below + `config/user.yaml`
**Writes to:** `<REPO_ROOT>/automation/jobs.xlsx`
**Notifies via:** email to `digest_email` (from config) after each run (Claude in Chrome → Gmail web)

---

## 1. Targeting (what makes the cut)

A job goes in the sheet only if **every** rule below is true. When in doubt, mark `prestige=unsure` and let Raj triage — bias toward a tight, high-quality list rather than recall.

- **Role:** SWE / Software Engineer / Software Developer / SDE / Backend / Full-stack / ML Engineer / AI Engineer / Applied AI. **ALSO include FDE-flavored roles** (high-priority for this hunt): Forward Deployed Engineer, Forward Deployed Software Engineer, Deployment Engineer, Implementation Engineer, Solutions Engineer *(only if the JD is engineering-heavy, NOT sales-flavored — Solutions Engineer at some places is pre-sales; read the JD)*, Member of Technical Staff (MTS — Anthropic / OpenAI / Inflection's catch-all SWE title). Known new-grad-friendly FDE programs: **Palantir** (flagship FDE track), **Anduril / Vannevar Labs / Saronic / Castelion** (defense-tech rotational), and occasionally **Decagon / Sierra / Harvey / Glean**. PM/APM is included **only** if it's an exceptional fit (top-tier company AND clearly elite program).
- **Level — HARD: new-grad only.** **Include:** "new-grad", "entry-level", "university", "2026 grad", "0 years experience", "no prior experience required", "Software Engineer I" / "L3" / "SDE I" at FAANG-equivalent companies (those tiers default to new-grad intake). **DROP if the JD requires 1+ years of post-grad / non-internship experience** — phrases like "1+ years experience", "2+ years", "minimum 1 year of professional experience", "early career (1-2 yrs)", or a "Required Qualifications" section listing any years of full-time SWE experience. Even if the title says "Software Engineer I" or "Early Career", if the JD body asks for ≥1 year non-internship → drop. Internships count as 0 years (i.e. "0 years professional experience" is fine; "0-2 years" is a yellow flag — read the JD to confirm internships qualify). Also drop: senior, staff, principal, manager, lead.
- **Geo:** California (any city). Other US metros (NYC, Seattle, Austin, Boston, Chicago) **only** if the company is clearly top-tier. Remote-US is OK if comp + company clear the bar.
- **Visa:** Raj is a US citizen — don't filter on sponsorship.
- **Comp floor:** ~$150K base or higher. If comp isn't listed, infer from company tier + Levels.fyi norms; if you can't infer, mark `comp=unknown` and include only if the company is clearly tier-A.
- **Freshness:** trust the source's stated timestamp. Include rows the source labels **≤3 days old** (widened 2026-06-01 to evaluate lead quality at a broader window).
  - Rows ≤1 day → `freshness=fresh`. Rows 1–3 days → `freshness=recent`. Older → drop unless Tier-A/wedge override applies.
  - **Tier-A/wedge override:** if the source timestamp says >3 days but the company is clearly Tier-A or strong-wedge fit, include it with `freshness=older`. An older posting at a top company is still worth pursuing.
  - **NO API verification step.** Do NOT call Greenhouse/Lever/Ashby/Workday APIs to cross-check post dates. Removed 2026-06-01 because it caused multi-hour stalls when an API rate-limited or a Chrome extension hiccup happened mid-run. Accept some false-fresh rows in exchange for a pipeline that completes reliably. (Raj sees the company name in triage and can spot obviously-old reposts manually.)
- **Prestige bar:** must be **strictly better than the user's current offers (Dell SWE new-grad, Capital One EPTech SWE new-grad).** That means one of:
  - **Tier A** (auto-include): FAANG, Anthropic, OpenAI, Google DeepMind, xAI, Meta GenAI, Apple ML, Microsoft AI; AI unicorns with $1B+ valuation; YC unicorns; Stripe, Ramp, Notion, Figma, Databricks, Snowflake; Vercel, Replit, Cursor/Anysphere, Modal, Sierra, Decagon, Glean, Harvey, Perplexity, Cohere, Scale, Hugging Face, Mistral, AI21.
  - **Strong wedge fit for Raj** (auto-include): multimodal AI, agentic AI, voice AI, RAG infra, dev tools, healthcare AI, wellness/nutrition AI (his PlateMax + Loop + Dell stack maps onto these directly). See `<REPO_ROOT>/research/findings.md` for the curated wedge list.
  - **Borderline** → `prestige=unsure`: Series A AI startups with notable founders/investors but low brand recognition. Surface them but flag.
- **Hard avoids** (always drop, no exceptions): Forward Health, Carbon Health, Olive AI, Cerebral, Innovaccer, Cognition / Windsurf, Pinecone, Sourcegraph, Hippocratic AI, Suki, DeepScribe, Augmedix, Limitless / Rewind, Bee, Mem.ai, Cal AI (standalone), Granola, Whoop (Boston, unless Raj wants to relocate), Tabnine, Adept, Magic.dev, Imbue. Also drop: consulting firms (Accenture, Deloitte, etc.), traditional enterprise IT, defense/intel primes, anything tagged "junior" inside a non-tech-first company (banks, retailers, insurance — unless tier-A like Capital One+, and Capital One is already the floor).
- **Volume cap:** **soft target ~3–8 new rows per run, quality-first** (hard cap 20). Raj wants a small list of teams actively hiring new grads, not 30 recycled reqs. Prioritize `freshness=fresh` rows, then `older` (active Tier-A/wedge). If you have more than the cap after filtering, keep the best by (freshness: fresh > older) then tier (Tier-A > wedge > unsure). It's totally fine to surface only 1–3 on a slow day — quality over recall.

---

## 2. Sources & how to parse each

### 2.1 SimplifyJobs/New-Grad-Positions

- URL: https://github.com/SimplifyJobs/New-Grad-Positions
- Raw README: https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md
- Format: a markdown table inside the README. Columns vary slightly but typically: `Company | Role | Location | Application/Link | Date Posted` (sometimes shown as "Age" like `1d`, `2d`).
- Parsing strategy: `web_fetch` the raw README. If it exceeds the token limit (it usually does), save to disk and grep + read in chunks. Look for lines starting with `| ` and the section under the table that lists open positions. Closed/expired roles are marked with 🔒 or strikethrough — skip them.
- **web_fetch provenance gotcha:** scheduled runs sometimes get "URL not in provenance set" on the raw README. Workaround: first `web_fetch` the HTML page (`https://github.com/SimplifyJobs/New-Grad-Positions`) — that seeds provenance — then re-fetch the raw URL.
- Freshness: use the `Date Posted` / `Age` column. Include ≤3 days. Anything older → drop (unless Tier-A/wedge override per §1).
- Dedupe key: canonical apply URL (strip tracking params like `?utm_*`, `?gh_src=*`).

### 2.2 jobright-ai/2026-Software-Engineer-New-Grad

- URL: https://github.com/jobright-ai/2026-Software-Engineer-New-Grad
- Raw README: https://raw.githubusercontent.com/jobright-ai/2026-Software-Engineer-New-Grad/main/README.md
- Format: same general shape as SimplifyJobs — markdown table with date column. Sometimes includes salary band.
- **Maintenance warning:** as of 2026-05-27 dry run, this repo appeared to have a stale top row (dated Mar 27). The maintainer may pause updates for stretches. If the most-recent row is >7 days old, treat the source as stale for this run — log it, contribute 0 rows, and continue. Don't fail the pipeline.
- Parsing strategy: same as 2.1 (web_fetch raw, chunk if needed). Same provenance workaround applies — fetch HTML page first if raw URL is blocked.
- Freshness: use the listed date column; include ≤3 days, drop older (unless Tier-A/wedge override per §1).

### 2.3 jobright.ai new-grad SWE minisite (the real source behind newgrad-jobs.com)

- **Use this URL directly:** https://jobright.ai/minisites-jobs/newgrad/us/swe?embed=true
- Investigation on 2026-05-27 found that `newgrad-jobs.com` is a thin wrapper around this jobright.ai minisite (loaded as an iframe). The previously-cited Airtable embed (`appzSWTM1QA543oU/shrpvJsQjbhk8l9pi`) is a hidden 0×0 abandoned iframe — ignore it.
- **Note: same company as §2.2** (jobright-ai), but a different surface. The GitHub repo is stale; this minisite is live and updates hourly. If only one is healthy, prefer this one.
- **Parsing strategy:** use Claude in Chrome.
  1. Navigate to the URL above. Wait ~5 seconds for the table to render.
  2. Read text via `mcp__Claude_in_Chrome__javascript_tool` evaluating `document.body.innerText`. The table is structured as repeated row blocks with columns: row number, Position Title, Date ("X hour(s) ago" / "X day(s) ago"), Apply, Work Model (Remote/Hybrid/Onsite), Location, Company, Salary, Company Size, Company Industry, Qualifications, H1B Sponsored, Is New Grad.
  3. Parse by splitting on the row-number boundary or by regex on the time-ago column.
  4. Avoid `document.querySelectorAll('a[href]')` introspection — Claude in Chrome's safety rails block iterating hrefs with query strings, which kills the JS call entirely. Use only `innerText` for extraction. To get an actual apply URL, click the "Apply" link/button for a specific row and capture the destination in the new tab.
- **Capture per row:** company, role title, location, posted-time-ago, salary band, company size, industry, H1B flag, is-new-grad flag, apply URL.
- **Freshness:** the site shows "X hours ago" / "X days ago" inline — include ≤3 days, drop older (unless Tier-A/wedge override per §1).
- **Quality boost:** this source surfaces salary inline (rare elsewhere). Use the salary band to enforce the $150K+ floor directly here — drop rows with `comp_top < 150000` if expressed as a yearly band. Hourly bands need conversion (multiply hourly_top × 2080).
- **PRESTIGE: this is a high-volume aggregator.** A typical run will see 20+ fresh entries here, of which most are mid-tier companies that don't clear the user's bar. Apply §1's prestige rules **strictly** — when in doubt, drop rather than mark `unsure`. Only pull rows where the company is clearly Tier-A (FAANG, top AI labs, named AI unicorns) or a strong wedge fit (multimodal / agents / voice AI / RAG infra / dev tools / healthcare AI from the curated list in `<REPO_ROOT>/research/findings.md`). The volume cap (§1) still applies — 20 hard max across all sources.
- **Fallback:** if the embed URL is blocked, fall back to navigating https://www.newgrad-jobs.com/ in Chrome, then find and click into the visible (non-zero-size) `iframe[src*="jobright.ai"]` to re-derive the current minisite URL.
- If the page won't render the list at all, skip this source for the run and note it in the digest. Don't fail the pipeline.

### 2.4 ~~LinkedIn~~ — REMOVED 2026-06-01

**LinkedIn search is DISABLED.** Reasons: (a) LinkedIn's "posted X ago" is unreliable (reposts get fresh timestamps, captcha risk on scheduled runs), (b) most genuinely-fresh roles surface in §2.1 / §2.3 anyway, (c) anti-bot friction was eating run time.

Do not navigate to linkedin.com during a sourcing run. Skip this section entirely.

### 2.6 Hacker News "Who is hiring?" monthly thread (NEW 2026-06-01)

High-signal founder-posted hiring thread, refreshed on the 1st of every month. Better for finding cool / impactful / different early-stage roles than aggregator boards. No login required; uses HN's public Algolia API (no Chrome MCP needed).

- **Discovery:** find the current month's thread via Algolia search:
  ```
  GET https://hn.algolia.com/api/v1/search?query=Ask%20HN%20Who%20is%20hiring&tags=story&hitsPerPage=5
  ```
  Pick the most recent result whose `title` matches `Ask HN: Who is hiring? (<Month> <Year>)`. The `objectID` is the thread ID.
- **Fetch the full thread + comments:**
  ```
  GET https://hn.algolia.com/api/v1/items/<thread_id>
  ```
  Returns nested JSON. The `children` array holds top-level posts, one per company. Each comment has `id`, `author`, `created_at` (ISO timestamp), and `text` (HTML — strip tags or convert to plain text).
- **Comment format (convention, not enforced):** `Company | Role(s) | Location | Remote? | Comp? | Visa? | <description>`. Posters often deviate — accept any hiring-flavored comment.
- **Freshness:** use `created_at` per comment. Include comments posted within the last 3 days (matches §1). The thread itself is monthly, but individual posts span the full month — filter by per-comment timestamp.
- **Per-row capture:**
  - `company` — usually first token before the `|`. If the comment is unstructured, parse from the first 1–2 lines.
  - `role` — extract every distinct role title mentioned (one row per (company, role) pair if a comment lists multiple).
  - `location` — look for `San Francisco`, `Bay Area`, `Palo Alto`, `Remote (US)`, `Remote (global)`, `California`. Drop rows with no location-fit per §1 Geo rule.
  - `comp` — only if mentioned inline; else `unknown`.
  - `apply_url` — the **HN comment permalink**: `https://news.ycombinator.com/item?id=<comment_id>`. This is the canonical URL for dedup. If the comment also links to a job page, capture that in `notes`.
  - `source` — `hn-hiring`.
  - `reasoning` — one line, e.g. `"founder-posted on HN, <vibe>"` or `"YC-backed, Series A, <wedge>"`.
- **Filters:**
  - Skip non-hiring comments (recruiter spam, "how to apply" meta-posts, off-topic). A comment is hiring-flavored if it contains `hiring`, `join`, `we're looking`, `we are looking`, `engineer`, or `apply` in the first ~200 chars.
  - Apply all §1 rules: new-grad role match, geo, freshness, prestige, hard-avoids.
  - **§5 step 5 JD verification is lightweight here** because the JD IS the comment body. Re-check the years-of-experience gate directly from the comment text (don't navigate elsewhere unless the comment links to a longer JD).
- **Volume expectation:** typical thread has 60-150 top-level posts. After the 3-day freshness window + §1 prestige/level filters, expect ~5-15 candidates per run that warrant JD verify, and ~1-4 to actually land in the sheet.
- **Failure modes:**
  - Algolia returns the wrong thread → search the title for the current month name + year before accepting.
  - Comment text is HTML — Algolia's `text` field includes `<p>`, `<i>`, etc. Strip with a regex or parser; don't naive-string-match across tags.
  - Some comments are top-rated but old (posted Day 1 of the month). Filter by `created_at` strictly — don't sort by score.

---

### 2.5 ~~Freshness verification~~ — REMOVED 2026-06-01

**This step is DISABLED.** Do not call any ATS API (Greenhouse, Lever, Ashby, Workday, amazon.jobs) to cross-check dates. The verification loop caused multi-hour stalls when an API rate-limited or the Chrome extension hiccuped mid-run.

Trust the source's stated `X hours/days ago` timestamp per §1. If a row turns out to be an old repost, Raj catches it manually during triage — the cost of one bad row in the digest is much lower than the cost of the whole pipeline hanging.

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
| 9 | `source` | str | one of: `simplify` / `jobright` / `newgrad-jobs` / `hn-hiring` |
| 10 | `apply_url` | str | direct apply URL (NOT the source page) |
| 11 | `tier` | str | `A` / `wedge` / `unsure` |
| 12 | `reasoning` | str | 1 line: why this passed the prestige bar (e.g. "Anthropic — auto-include tier-A") |
| 13 | `decision` | str | always `pending` on insert. Raj edits to `yes` / `no` / `maybe`. |
| 14 | `applied_date` | YYYY-MM-DD or empty | Raj fills when applied |
| 15 | `resume_version` | str | path to tailored resume folder if applicable, else empty |
| 16 | `notes` | str | freeform; any per-row caveats (e.g. "salary band from jobright minisite — verify on apply page") |

If the file doesn't exist when the task runs, **create it** with these headers in row 1 (bold), then append.

---

## 5. Workflow (the actual loop the task runs)

1. **Pre-flight:** `Read` this spec file. `Read` the current `<REPO_ROOT>/automation/jobs.xlsx` to build a set of existing canonical URLs and (company, role) tuples for dedup.
2. **Pull sources in parallel where possible:**
   - `web_fetch` SimplifyJobs raw README (§2.1)
   - `web_fetch` jobright-ai raw README (§2.2)
   - Claude in Chrome → newgrad-jobs / jobright minisite WITH the **Is New Grad = Yes** filter applied (§2.3)
   - `web_fetch` HN Algolia API → current "Who is hiring?" thread + comments (§2.6) — no Chrome needed
   - (LinkedIn is disabled per §2.4 — skip it.)
3. **Normalize each candidate into the schema in §4.**
4. **Apply cheap pre-filters from §1**: role → geo → hard-avoid → prestige. Drop early — these are free.
5. **JD verification (MANDATORY, per-candidate).** For every surviving candidate, open the `apply_url` (`web_fetch` for static pages; Claude in Chrome if it's a JS-driven ATS like Workday/Lever/Greenhouse/Ashby). Read the actual job description body, then verify:
   - **(a) Level matches §1 Level rule.** If the JD's Required Qualifications or Minimum Qualifications section requires **1+ years of non-internship / post-graduation experience**, DROP — regardless of the title. Phrases that trigger an automatic drop: "1+ years experience", "2+ years experience", "minimum 1 year of professional", "early career (1-2 yrs)", "must have N years of full-time SWE". Internships always count as zero, so "experience including internships" is fine. If the JD never mentions years of experience at all, treat as new-grad-eligible.
   - **(b) Realistic for a new-grad SWE.** Skip roles that require specialization beyond a new grad's reach: explicitly-required PhD, "publications in NeurIPS/ICML required", 5+ year tech-lead expectations, deep-domain specialization (compiler internals, low-level kernel, security research) with no broader SWE framing. Generalist SWE / AI engineer / applied-ML / backend / full-stack roles all pass — a new grad can realistically apply.
   - **(c) Cheap stop-loss.** Spend at most ~20 seconds per JD. If the page won't load after one retry, mark `notes="JD unverified — page didn't load"` and KEEP the row (don't drop on infra flakiness). If you got the JD body, log a one-line verdict to the digest: `<company> / <role> → pass | drop:1+yrs | drop:specialist`.
   - Track per-run counters: `jd_verified=N`, `jd_dropped_1plus_yrs=N`, `jd_dropped_specialist=N`, `jd_unverified=N`.
6. **Apply remaining §1 filters** that need post-JD context: level (re-check after JD read), freshness override. Drop early; cheaper.
7. **Dedup against existing rows** per §3.
8. **Apply volume cap** (≤20 hard, ~10 soft preference).
9. **Append surviving rows to `jobs.xlsx`** with `decision=pending`.
10. **Send the daily digest email** per §6 (include the JD-verification counters in the body).
11. **Print a 1-paragraph summary to the run log** so Raj sees it as a notification: total scanned per source, total kept, JD-verification counters, list of company names added.

If zero new rows survive, still send the email (subject "No new jobs today, here's why") with a one-paragraph note on what was scanned + filter counts, so Raj knows the pipeline ran.

---

## 6. Daily digest email

**To:** <your-email> (Raj emails himself from his own Gmail)
**From:** <your-email> (his logged-in session)
**Subject:** `Daily jobs digest — YYYY-MM-DD — N new` (e.g. `Daily jobs digest — 2026-05-28 — 4 new`)

**Body (HTML, simple):**

```
Hey Raj — daily sourcing pass complete.

NEW JOBS ADDED (N):

1. <company> — <role>
   Location: <location> · Comp: <comp> · Tier: <tier>
   Why it passed: <reasoning>
   Apply: <apply_url>
   Posted: <posted_date> · Source: <source>

2. ...

---
Open jobs.xlsx to triage: <REPO_ROOT>/automation/jobs.xlsx
Spec: <REPO_ROOT>/automation/job-sourcing-spec.md
```

If `N == 0`, body is:
```
Hey Raj — daily sourcing pass complete. No new jobs cleared the bar today.

Scanned: Simplify (X candidates → Y after filters), jobright (X → Y),
newgrad-jobs / jobright-minisite (X → Y), HN Who's Hiring (X → Y).

Top filter drops: <stale: N> <wrong role: N> <below prestige bar: N> <hard avoid: N> <duplicates: N>
```

**How to send (no Gmail MCP available — use Claude in Chrome):**

Gmail's compose body is a `contenteditable` div, NOT a textarea. Naive typing tools silently no-op on it. Follow this sequence precisely — the 2026-05-27 dry run hit a blank-body failure and the procedure below is the verified fix.

1. `mcp__Claude_in_Chrome__navigate` to https://mail.google.com. Wait for inbox.
2. Click the **Compose** button (upper-left). Wait for compose modal.
3. **To field:** find the To input, set value via the native value setter, dispatch `input` event, then dispatch synthetic `Enter` keydown to commit the chip. After committing, verify by querying `dialog.querySelector('[email="<your-email>"]')` — the input's `.value` is cleared once the chip exists, so don't read the input.
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
   - Confirm the textContent contains a sentinel: at least one company name from the digest (e.g. the first company in §6 body). If sentinel missing → retry the body fill (max 2 retries). If still failing after 2 retries → STOP, write the digest to `<REPO_ROOT>/automation/digest-YYYY-MM-DD.md`, do NOT send a blank email.
7. **Send:** the Send button is `div[role="dialog"] div[role="button"][data-tooltip^="Send"]` (the `aria-label` contains a directional-formatting char — match by `startsWith("Send")` or `data-tooltip` prefix, not equality).
8. Wait for the "Message sent" toast text to appear before closing/navigating away. If toast doesn't appear within 5s, do not assume success.

**Fallback:** if Gmail is not logged in, or the body-fill verification gate fails twice, write the formatted digest to `<REPO_ROOT>/automation/digest-YYYY-MM-DD.md` and log "email skipped — see digest md fallback" in the run summary. Do NOT send a blank-body email.

---

## 7. Error handling

- **Source down / fetch fails:** log it, skip that source, continue with the others. Don't block the whole run on one source.
- **Token-limit on raw README:** save to disk, grep + read in chunks (this is normal, not an error).
- **xlsx locked (file open in Excel):** log it, write to `jobs-pending-merge-YYYY-MM-DD.xlsx` instead, and mention in the email digest that Raj should close Excel + merge manually.
- **No new rows:** still send the email (per §6).

---

## 8. Things Raj may want to tweak over time

These are the dials. Search-replace these strings if you want to change behavior without rewriting the spec:

- Comp floor: `$150K base or higher`
- Volume hard cap: `hard cap 20`
- Geo: `California (any city). Other US metros...`
- Run time: lives in the scheduled task, not here — update via `update_scheduled_task` for `daily-job-sourcing`.
- Hard-avoid list: §1, "Hard avoids" bullet.
- Tier-A allowlist: §1, "Tier A" bullet.
