# Verify Date Posted Spec

You are an autonomous agent verifying the **actual** posted date of a job by reading the direct source ATS page (NOT the aggregator). Aggregator dates (jobright, SimplifyJobs, HN, newgrad-jobs) are first-seen / repost dates and often lie.

## §0 Configuration

This spec doesn't need personal data. The xlsx path resolves relative to the repo root. No `config/user.yaml` read required for this one.

## Inputs (passed via prompt)

- `JOB_ID` — integer id from `<REPO_ROOT>/automation/jobs.xlsx`

## Output

Write back to the `posted_date_verified` column in `jobs.xlsx`:
- `YYYY-MM-DD` if you found a real posted date on the source page
- `unknown` if you tried everything and couldn't find one

**DO NOT FABRICATE A DATE.** If you can't find it, write `unknown`. Lying is worse than admitting ignorance.

Print one-line summary then exit (Terminal closes itself).

## §1 Read job row + classify the URL

1. Read the row at `JOB_ID` from jobs.xlsx. Extract:
   - `company`, `role`, `apply_url`, `source`, `date_sourced`, `posted_date` (the aggregator-reported one)

2. Classify `apply_url`:

| URL pattern | Type | Action |
|---|---|---|
| `jobright.ai/jobs/info/...` | aggregator | **See §1.1 below — special jobright handling required.** |
| `jobright.ai/minisite/...` | aggregator (minisite) | Same as jobright — follow the "Original Job Post" link |
| `github.com/SimplifyJobs/...` | aggregator (README) | Open the README in Chrome, find the row by company + role, click the apply link |
| `news.ycombinator.com/item?id=...` or `hn.algolia.com/...` | aggregator (HN comment) | Read the HN comment body; the URL inside it is the source. If the source is a company careers page or an apply email, document and stop |
| `boards.greenhouse.io/...`, `jobs.lever.co/...`, `*.ashbyhq.com/...`, `jobs.eu.workday.com/...`, `myworkdayjobs.com/...`, `*.workable.com/...`, `careers.<company>.com/...`, `jobs.<company>.com/...`, `<company>.com/careers/...` | **direct source** | Use it directly |
| Anything else not in the aggregator list | likely direct source | Use it directly |

3. If the URL is an aggregator, navigate through it to get the **direct source ATS URL**. If you can't find a direct source URL (some HN comments only say "email us at X@Y"), write `unknown` to the column and exit.

### §1.1 — Jobright-specific handling (IMPORTANT)

**Never trust jobright's displayed posted date.** Jobright shows a date (sometimes "today", sometimes "2 days ago") that is the first-seen / re-index date in their pipeline, NOT the real posted date on the source ATS. Ignore it completely. Even if the jobright page seems to clearly say "Posted today" or "Posted 1 day ago", do not use that value.

To get the real date, click the **"Original Job Post"** link. It's typically at the **top right** of the jobright posting page (near the company logo / apply button area). Other variations of the link text to watch for:
- "Original Job Post"
- "View Original"
- "Apply on Company Site"
- "Original Posting"
- An external-link icon (↗) next to the job title

Click that link. It will open the actual ATS page (greenhouse / lever / ashby / workday / company careers). **That is the page you read the date from**, per §2 below. The same rule applies to jobright minisites.

If the "Original Job Post" link is missing or broken (rare), write `unknown` and explain in the summary line ("jobright link to original missing").

## §2 Extract the posted date from the direct source page

Open the direct ATS URL in Chrome. Look for the date in this priority order:

### A. Visible text on the rendered page

Common patterns to look for:
- "Posted on June 1, 2026"
- "Posted 3 days ago"
- "Published: 2026-05-28"
- "Created date" / "Listed date"
- "Application opens" / "Posted date"
- Footer date stamps

If you find a "X days ago" style, compute the absolute date using today's date (2026-06-05 or whatever current is, read from `date` command in Bash). Be careful: "3 days ago" today is `2026-06-02`.

### B. JSON-LD structured data (very common, especially Greenhouse / Lever / Ashby)

Many ATS pages embed schema.org JobPosting structured data. View the page source (Chrome dev tools or View Source) and look for:

```html
<script type="application/ld+json">
{
  "@type": "JobPosting",
  "datePosted": "2026-05-28",
  ...
}
</script>
```

Extract `datePosted`. This is the most reliable source.

### C. Meta tags

```html
<meta property="article:published_time" content="2026-05-28T...">
<meta name="DC.date.issued" content="...">
<meta property="og:posted_time" content="...">
```

### D. JS app state / hidden fields

For Workday and similar SPAs, the date is often in:
- A `<script>` tag with initial app state (look for `postingDate`, `datePosted`, `startDate`, `creationDate`)
- An attribute on a hidden element (e.g., `data-posted-date`)

Use Chrome MCP's DOM inspection or View Source to find these. You can use the browser console (`Ctrl+Shift+J`) to run JS like `document.querySelector('[data-job-posted]').textContent`.

### E. URL itself

Some URLs contain the date (e.g., `careers.example.com/jobs/2026/05/...`). Use as a fallback only.

### F. ATS-specific tricks

**Greenhouse:** `<meta property="og:updated_time">` or JSON-LD. Usually clean.

**Lever:** JSON-LD with `datePosted` is standard. Page has "Posted X days ago" in the header.

**Ashby:** API endpoint at `/api/non-user-graphql?op=ApiJobPosting` returns the data including `publishedDate`. If you can call it, do.

**Workday:** Hardest. Look at the network tab for the GraphQL/REST call that fetches job details, or check window state via console: `window.__JOB__` or similar globals.

**Custom careers pages** (Anthropic, OpenAI, Anduril, Palantir): each one is different. Look at the visible date first; if not visible, check JSON-LD; if nothing, write `unknown`.

## §3 Validation

Before writing the date:
- Confirm format is `YYYY-MM-DD`
- Sanity check: the date should be within the last ~6 months and not in the future. If it's older than 6 months, that's suspicious (might be a re-posted listing) — still write it, but flag in the summary line.
- If you found multiple dates on the page (e.g., posted vs updated), prefer **datePosted** / **postedDate**. If only "updated" or "modified" is available, use it but flag in the summary.

## §4 Write back to xlsx

Use python + openpyxl from Bash:

```bash
python3 - <<'PY'
from openpyxl import load_workbook
from pathlib import Path
XLSX = Path("<REPO_ROOT>/automation/jobs.xlsx")
wb = load_workbook(XLSX)
ws = wb["jobs"]
headers = [c.value for c in ws[1]]
# Migrate column if missing
if "posted_date_verified" not in headers:
    ws.cell(row=1, column=len(headers) + 1, value="posted_date_verified")
    headers.append("posted_date_verified")
idx = headers.index("posted_date_verified")
for r in ws.iter_rows(min_row=2):
    if r[0].value == <JOB_ID>:
        r[idx].value = "<YYYY-MM-DD or unknown>"
        break
wb.save(XLSX)
PY
```

## §5 Summary line + exit

Print one of:

```
DONE — verified posted_date=YYYY-MM-DD from <source: JSON-LD | visible text | JS state | meta tag | URL>. Aggregator said: <original posted_date>. Match: yes|no.
```

or

```
DONE — posted_date=unknown. Tried: <list of methods tried>. Source URL: <final direct ATS URL or "could not resolve from aggregator">.
```

Then exit.

## §6 Hard rules

- **NEVER write a fabricated date.** If unsure, write `unknown`.
- **NEVER write the aggregator's date as if it were verified.** That defeats the purpose.
- **NEVER trust jobright's displayed date.** Even if jobright says "Posted today" in big letters, ignore it. Click "Original Job Post" (top right of the jobright page) and read the date from the ATS page that link opens.
- **NEVER skip following aggregator URLs to their source.** A "verify" that just re-reads jobright is not verifying anything.
- Be specific in the summary line about WHERE you found the date (page source, visible text, etc.) so the user can trust it.
- If the page is behind a login or paywall (rare for job postings), write `unknown` and note "behind login" in the summary.
