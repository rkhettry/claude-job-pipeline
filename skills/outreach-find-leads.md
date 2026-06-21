---
description: Find LinkedIn recruiters/founders/engineers for a specific applied job. Usage — /outreach-find-leads <job_id> <count>
---

Run the outreach lead-finder for the job_id and lead count the user provided in `$ARGUMENTS` (typically two whitespace-separated integers, e.g. `42 10`). If only one number is given, treat it as job_id with default count=10. If neither is given, ask the user to provide the job_id.

**Source of truth for behavior:** `<REPO_ROOT>/automation/outreach-lead-finder-spec.md`. Read that file first and follow it exactly, then read `<REPO_ROOT>/automation/outreach/message-templates.md` for the message text. The triage server normally spawns this via the UI's 🎯 Outreach button; this slash command is for manual / ad-hoc runs.

**Inputs from $ARGUMENTS:**
- JOB_ID — first integer
- LEAD_COUNT — second integer (default 10)
- APPEND — false unless the user explicitly says "append" in $ARGUMENTS

Use Chrome MCP (the user is authenticated on LinkedIn). Write the sidecar JSON at `<REPO_ROOT>/automation/outreach/<JOB_ID>.json`.

Do NOT send any messages or connection requests — this is find-only. The user reviews in the triage UI, then runs `/outreach-send` or clicks 📨 Send approved.

When done, print the one-line DONE summary from §7 of the spec and exit.
