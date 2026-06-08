---
description: Verify a job posting's actual posted date from the source ATS page (not the aggregator). Usage — /verify-date <job_id>
---

Run the verify-date check for the job_id in `$ARGUMENTS`. If no job_id is given, ask the user.

**Source of truth for behavior:** `<REPO_ROOT>/automation/verify-date-spec.md`. Read that file first and follow it exactly. The triage server normally spawns this via the row's 🔍 Verify date button; this slash command is for manual / ad-hoc runs.

**Input from $ARGUMENTS:**
- JOB_ID — single integer

Goal: navigate to the direct ATS page (greenhouse, lever, ashby, workday, company careers — NOT jobright / SimplifyJobs / HN), find the real posted date, write it to the `posted_date_verified` column in jobs.xlsx.

Output value:
- `YYYY-MM-DD` if found with high confidence
- `unknown` if you tried everything

NEVER fabricate. `unknown` is the right answer when you don't know.

Print the one-line DONE summary from §5 of the spec and exit.
