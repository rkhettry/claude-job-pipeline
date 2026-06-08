# Outreach message templates

**Edit this file to change how outreach messages sound.** These are the *defaults* that get hydrated into the per-job sidecar JSON. You can override per-company in the View Leads modal.

## Hard rules for ALL templates

1. **No em dashes (—).** They read as AI-generated. Use commas or periods.
2. **No double dashes (--).** Same reason.
3. **Hard cap: 290 characters after placeholder hydration.** LinkedIn shows 300 but cuts off oddly.
4. **No fabricated specifics.** Never invent a recent post / project / team name.
5. **Casual but not sloppy.** New-grad voice. Avoid corporate-speak ("following your work on", "deeply impressed by", "thrilled to").
6. **Don't force a context line.** If you don't have something genuinely concrete to say about the lead or company, OMIT the context line. Empty `{context}` is the preferred default. Only fill it when you have real signal.

## Placeholders

| Placeholder | Source | Example |
|---|---|---|
| `{first_name}` | First word of lead's LinkedIn name | `Jane` |
| `{role_short}` | 2-4 word version of role | `FDE`, `new grad SWE`, `MTS` |
| `{job_id_suffix}` | Visible req id with leading space if present, else empty | ` (#R-12345)` or `` |
| `{company}` | Company name | `Palantir` |
| `{context}` | Optional context line, see rules below | ` Big fan of what you're building.` or `` (empty) |

## `{context}` rules — IMPORTANT

The `{context}` placeholder is the most-misused part of these templates. Default behavior: leave it empty (`""`). Only fill it when you have one of these concrete signals:

| Signal | Fill `{context}` with | Example |
|---|---|---|
| Recent visible post by the lead about a product/feature | ` Loved your recent post on {topic}.` | ` Loved your recent post on the AIP rollout.` |
| Concrete, real product/team Raj cares about | ` Big fan of {company}'s work on {topic}.` | ` Big fan of Palantir's work on the FDE program.` |
| You know nothing specific but want flow (founder/engineer only, NEVER recruiter) | ` Big fan of what you're building.` or ` Genuinely excited about what y'all are doing.` | (use sparingly) |
| Anything else | `""` (empty) — DEFAULT | |

**Never** invent a topic that isn't backed by something visible on the lead's profile, a recent post, or the actual JD. "Following your work on live governance" when `brief_reason="live governance"` was guessed from a tagline is a LIE and reads spammy. If unsure, leave `{context}` empty.

## Templates

### Recruiter (always omit `{context}`)

```
Hey {first_name}, applied to the {role_short} role{job_id_suffix} at {company}. Wanted to flag it directly in case my app gets buried. Would mean a lot if you had a sec to look at my resume.
```

Recruiters don't have personal "work" on a product. They recruit. Don't pretend otherwise. The template has no `{context}` placeholder because there isn't one for this lead type.

### Founder (context optional, prefer empty)

```
Hey {first_name}, applied to the {role_short} role{job_id_suffix} at {company}.{context} Would love if you had a sec to look at my resume.
```

### Engineer (context optional, prefer empty)

```
Hey {first_name}, applied to the {role_short} role{job_id_suffix} on your team.{context} Would love a quick look at my resume.
```

## Examples of hydrated messages

**Recruiter, 1st-degree:**
> Hey Jane, applied to the FDE role (#R-12345) at Palantir. Wanted to flag it directly in case my app gets buried. Would mean a lot if you had a sec to look at my resume.

**Founder, no concrete context (preferred default):**
> Hey Sarah, applied to the FDE role at Palantir. Would love if you had a sec to look at my resume.

**Founder, with concrete context (recent post):**
> Hey Sarah, applied to the FDE role at Palantir. Loved your recent post on the AIP launch. Would love if you had a sec to look at my resume.

**Engineer, with vague-but-honest context:**
> Hey Alex, applied to the FDE role on your team. Big fan of what you're building. Would love a quick look at my resume.

## How to edit

1. Open this file.
2. Change the text inside the three code fences above (recruiter / founder / engineer).
3. Save.
4. New `/api/outreach-find` runs pick up the new defaults. Existing sidecars are untouched.
