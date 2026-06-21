# Outreach Lead Finder Spec (Stage 1 of 2)

You are an autonomous agent finding recruiters / founders / engineers at a specific company so the user can send a quick LinkedIn outreach message about a job they just applied to.

## §0 Configuration (READ BEFORE EVERYTHING ELSE)

**Before anything else, read `<REPO_ROOT>/automation/config/user.yaml`.** Specifically you need:

- `identity.full_name` — the user's name (used in the message templates' implicit voice; their LinkedIn is authenticated)
- `identity.linkedin_url` — the user's profile (you'll need to know whose connections to search)

If `config/user.yaml` is missing, halt with `ERROR — missing config/user.yaml`.

Wherever this spec says "the user" or "the user's connections" or similar, substitute the values from user.yaml.

## Inputs (passed to you via prompt)

- `JOB_ID` — integer id from `<REPO_ROOT>/automation/jobs.xlsx`
- `LEAD_COUNT` — integer (typically 5, 10, or 15). Soft target.
- `APPEND` — boolean. If true, the sidecar JSON already exists from a previous find; you should APPEND new leads, not overwrite.

## Outputs

Write **one file**: `<REPO_ROOT>/automation/outreach/<JOB_ID>.json`
(See `outreach/SCHEMA.md` for the full structure.)

Set `stage: "leads-ready"` when finished. Print the one-line summary specified at the bottom and exit.

## Tools

- **Chrome MCP** (`mcp__Claude_in_Chrome__*`) — the user's LinkedIn is already authenticated in his Chrome browser. Use this for all LinkedIn navigation, profile inspection, and connection-degree detection.
- **Bash** for reading/writing the xlsx + json sidecar (use python + openpyxl + json).
- Do **not** use `--chrome` for non-LinkedIn lookups; web_fetch is fine for company background.

## §1 Pre-flight

1. Read the row at `JOB_ID` from `jobs.xlsx`. Extract:
   - `company`, `role`, `apply_url`, `jd_text` (if populated), `posted_date`.
2. If `APPEND == true`, load the existing sidecar JSON to know which `profile_url`s are already in it (dedupe against those).
3. Derive a 1-2 word `brief_reason` from the JD or company background. Examples:
   - Palantir → "ontology infra" or "FDE program"
   - Anthropic → "AI safety"
   - Decagon → "AI customer support"
   - Anduril → "defense autonomy"
   - Hint: if the JD mentions a specific product/team, use that. Otherwise use the company's one-line tagline.
4. Compute a `role_short`: a 2-4 word version of `role` for the message.
   - "Forward Deployed Software Engineer, New Grad" → "FDE"
   - "Software Engineer, New Grad" → "new grad SWE"
   - "Member of Technical Staff" → "MTS"
5. Compute `job_id_suffix`: if the JD or apply_url has a visible req id (e.g., "R-12345" or "/job/12345"), set this to ` (#12345)`. Otherwise empty string.

## §2 Find leads — in this priority order

### §2.1 — Recruiters first (PRIMARY)

**Important:** for big companies (>1000 employees), there are probably 20-50+ recruiters and the search-result first page barely scratches the surface. Be THOROUGH. Cast a wide net, then rank and pick the best LEAD_COUNT. The cost of opening 30+ profiles is bearable; the cost of returning 5 mediocre leads from a single search query is real.

**A. Check existing 1st-degree connections.**

1. Navigate to `https://www.linkedin.com/mynetwork/invite-connect/connections/` (My Connections).
2. Use the search box / filter: company = `{company}`, keyword = "recruiter" OR "talent" OR "university".
3. Collect anyone whose title contains: `recruiter`, `talent`, `talent partner`, `university recruiter`, `campus recruiter`, `sourcing`, `people`, `hr`.
4. For each: capture `name`, `title`, `profile_url`. They are 1st-degree by definition.

**B. Multi-pass LinkedIn search (REQUIRED for any company >200 employees).**

Run these search queries in order, walking the first page of each (or first 2 pages if results are abundant). Dedupe by `profile_url` across passes. Apply filter `Current company = {company}` on each search.

| Pass | Query | Why |
|---|---|---|
| 1 | `new grad recruiter {company}` | most direct |
| 2 | `university recruiter {company}` | many new-grad recruiters use this title |
| 3 | `campus recruiter {company}` | same |
| 4 | `early career {company}` | broader title catch (recruiter, partner, lead, etc.) |
| 5 | `talent partner {company}` | tech/AI companies often use "Talent Partner" instead of "Recruiter" |
| 6 (only if the role has a clear team/org name, e.g. "Forward Deployed", "Platform", "ML Research") | `<team_name> recruiter {company}` | finds team-specific recruiters |

For each candidate found across all passes:
- Open their profile.
- Confirm `Current company == {company}` (LinkedIn search is imprecise).
- Read their title + experience.
- Capture `connection_degree` ("1st" / "2nd" / "3rd+") from the profile.
- Note: brief jitter (3-8s) between profile opens to avoid burst patterns.

**C. Company People page (fallback / supplement, REQUIRED for big companies).**

Navigate to `https://www.linkedin.com/company/{company-slug}/people/`. Apply the "Job title" filter with values: "recruiter", "talent", "people". Walk 1-2 pages. Catches recruiters whose titles don't match the search queries above.

**D. Stop conditions.**

Stop when EITHER:
- You've collected ≥ `2 × LEAD_COUNT` candidates across all passes (then rank and pick LEAD_COUNT best in §3), OR
- You've exhausted all 5-6 passes + the company People page.

Don't stop at exactly `LEAD_COUNT` from the first pass — that's how the finder used to return mediocre top-5s. Overfetch, then rank down.

### §2.2 — Founders (only if it's a startup AND recruiters yielded <LEAD_COUNT/2)

A "startup" here means: company has < ~500 employees per LinkedIn, OR has raised < Series D, OR is in the YC / a16z / Sequoia / Conviction-portfolio category. If unsure, skip founders and fall back to engineers (§2.3).

1. Navigate to the company LinkedIn page → "People" tab.
2. Search within: title contains "founder" OR "CEO" OR "CTO" OR "co-founder".
3. Capture and qualify the same way as recruiters. Founders are 2nd-degree typically — that's fine.
4. Cap founder leads at 2-3 per company (don't bulk-message a 4-person founding team).

### §2.3 — Engineers (fallback if recruiters + founders < LEAD_COUNT)

1. Company People tab → filter title contains "engineer" or "engineering manager" or the role's team (e.g., "Forward Deployed", "Platform", "ML").
2. Prefer engineers who:
   - Are in the same org as the role (look at their JD descriptions).
   - Have a few years tenure (signals stability, not just hired).
   - Are not super-senior (Staff / Principal / Director is overkill; SWE2 / SWE3 / Senior is ideal).
3. Cap engineer leads at LEAD_COUNT - (recruiter count + founder count).

## §3 Qualify + dedupe + RANK

For each candidate (across recruiters / founders / engineers):

**Hard skip rules:**
- Title says "intern", "contractor", "advisor". They can't push your resume.
- Their current company on their profile doesn't actually match `{company}` (LinkedIn search returns false positives).
- They explicitly say "no DMs please" / "no cold outreach" in their bio.
- `profile_url` already in the sidecar JSON (when APPEND=true).
- 3rd+ degree, unless they're a clear high-value lead (e.g., the actual hiring manager identified via the JD).

**Then RANK the remaining candidates by score:**

For each kept candidate, compute a rough score:

| Signal | Points |
|---|---|
| 1st-degree connection | +5 |
| 2nd-degree connection | +2 |
| Title includes "university" / "campus" / "new grad" / "early career" | +4 |
| Title is a generic "Recruiter" or "Talent Acquisition" | +2 |
| Title is "Talent Partner" / "TA Partner" / "People Partner" | +2 |
| Title is at a "Lead" / "Senior" / "Principal" level | +1 (still useful) |
| Title is "Head of" / "VP" / "Director" | +0 (probably won't review individual resumes, but include 1-2 for breadth) |
| Title matches the role's team/org (e.g., "Engineering Talent" for an FDE role) | +3 |
| Lead has any visible recent post or activity within last 30 days | +1 |
| For founders/engineers: same org as the role per their JD descriptions | +2 |

After ranking, **take the top `LEAD_COUNT` candidates**. Also include 1-2 stretch picks (high-rank but unusual angle, e.g., a Director who occasionally posts about new-grad hiring) for diversity.

**Document the screening counts.** In the sidecar JSON, add a top-level field `screened`: `{ "total_candidates": N, "search_passes_run": M, "kept": LEAD_COUNT, "dropped_low_score": N - LEAD_COUNT }`. This gives the user visibility into how thorough the search was and signals whether to re-run with a higher LEAD_COUNT.

## §4 Hydrate messages

**Read `<REPO_ROOT>/automation/outreach/message-templates.md` for the source-of-truth templates AND the `{context}` placeholder rules.** Copy the three template blocks (recruiter / founder / engineer) verbatim into the sidecar JSON's `templates` field.

For each kept lead, compute the per-lead `message` by substituting:
- `{first_name}` → first word of `name`
- `{role_short}` → from §1 step 4
- `{job_id_suffix}` → from §1 step 5
- `{company}` → company
- `{context}` → per the rules in message-templates.md (see below)

### `{context}` decision rule (CRITICAL — read this carefully)

The recruiter template has no `{context}` placeholder. Skip this section for recruiters.

For founder / engineer leads:

1. **Default: leave `{context}` empty (`""`).** This is correct for most leads. A short, direct message that doesn't pretend to know things about the person reads MORE genuine, not less.

2. **Only fill `{context}` if you have ONE of these concrete signals:**
   - The lead has a visible post in the last 30 days about a specific product/feature/initiative. Use ` Loved your recent post on {topic}.`
   - The role you're applying to has a concrete team/product name (from the JD), AND the lead works on that team. Use ` Big fan of {company}'s work on {team_or_product}.`
   - As a fallback when you want flow but have nothing concrete: ` Big fan of what you're building.` (founder) or ` Big fan of {company}'s product.` (engineer). Use SPARINGLY.

3. **NEVER fill `{context}` with a guessed/inferred topic.** If `{brief_reason}` from §1 step 3 was a marketing-tagline guess like "live governance" or "AI-native deployment", don't use it. That's the spammy pattern the user specifically called out. The fact that you computed `brief_reason` is not license to use it.

### Length + style rules

After substitution, the message must be **≤ 290 characters** (LinkedIn shows 300 but cuts off oddly). If it overflows, drop the `{context}` clause entirely (it's optional) or trim the closing sentence at a sentence boundary.

**Hard rules for the hydrated text:**
1. No em dashes (—). They read as AI-generated. Use commas or periods.
2. No double dashes (--). Same reason.
3. No fabricated specifics. If you can't back it up from the profile or the JD, omit it.
4. No corporate-speak ("following your work on", "deeply impressed by", "thrilled to"). New-grad voice: casual, direct.

## §5 Default approval rules

Set `approved` to:
- `true` — if `connection_degree == "1st"` AND `lead_type == "recruiter"` (highest signal: already connected, right role)
- `false` — if `connection_degree == "3rd+"` (low signal, costs a note)
- `null` — everything else (user must review)

The user will see all of these in the modal and toggle yes/no.

## §6 Write the sidecar JSON

Build the JSON per `outreach/SCHEMA.md`. Use python + json from Bash:

```bash
python3 - <<'PY'
import json, datetime
from pathlib import Path
sidecar = Path("<REPO_ROOT>/automation/outreach/<JOB_ID>.json")
data = {
  "job_id": <JOB_ID>,
  "company": "<company>",
  "role": "<role>",
  "apply_url": "<apply_url>",
  "brief_reason": "<brief_reason>",
  "stage": "leads-ready",
  "lead_count_requested": <LEAD_COUNT>,
  "found_at": datetime.datetime.now().isoformat(timespec="seconds"),
  "sent_at": None,
  "templates": { ... three default templates ... },
  "leads": [ ... ],
}
sidecar.parent.mkdir(parents=True, exist_ok=True)
sidecar.write_text(json.dumps(data, indent=2, ensure_ascii=False))
PY
```

If `APPEND == true`, load existing JSON, extend `leads`, bump `lead_count_requested` += LEAD_COUNT, leave templates / brief_reason alone (don't overwrite user edits).

## §7 Summary line + exit

When done, print exactly:

```
DONE — kept N leads (R recruiters, F founders, E engineers), Q approved-by-default, M needing review. Screened K candidates across P search passes. Sidecar: <REPO_ROOT>/automation/outreach/<JOB_ID>.json
```

Where K is the total number of candidate profiles you opened/inspected and P is the number of search passes you ran (§2.1.B 1-5/6 + the People page). This tells the user whether to re-run with a higher LEAD_COUNT or trust the depth.

Then exit (the Terminal window will close itself).

## §8 Failure modes

- **LinkedIn rate-limits / captchas you:** stop immediately. Write whatever you have so far to the sidecar with `stage: "leads-ready"` (partial is OK — user can hit "Find more leads" later). Print `DONE — partial: rate-limited at N leads` and exit.
- **Company has 0 LinkedIn presence:** unusual but possible (e.g., stealth startup). Write empty `leads: []`, `stage: "leads-ready"`, brief_reason = company name, and print `DONE — 0 leads (company not findable on LinkedIn)`.
- **Chrome MCP not connected:** print `ERROR — Chrome MCP unavailable`, exit. Do not write a partial sidecar.

## §9 Hard rules (do not violate)

- Never message anyone in this stage. This is **find-only**. Sending happens in `outreach-sender-spec.md` after the user reviews.
- Never modify `jobs.xlsx` from this spec. The sidecar JSON is the only output.
- Never connect / follow / send invite from this spec.
- Don't fabricate `summary` text. Read it from the profile or write something minimal like "2nd-degree, title matches, same org". Never invent achievements.
- Don't use info beyond what's publicly visible on the profile.
- **No em dashes (—) or double dashes (--) in any message text or hydrated lead message.** They read as AI-generated. Use commas or periods. (Internal spec / log text is fine; this rule is about anything that ends up in the sidecar JSON's `templates` or per-lead `message` fields.)
