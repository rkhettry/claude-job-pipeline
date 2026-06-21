---
description: Send LinkedIn messages for approved leads for a specific applied job. Usage — /outreach-send <job_id>
---

Run the outreach sender for the job_id in `$ARGUMENTS`. If no job_id is given, ask the user.

**Source of truth for behavior:** `<REPO_ROOT>/automation/outreach-sender-spec.md`. Read that file first and follow it exactly. The triage server normally spawns this via the UI's 📨 Send approved button; this slash command is for manual / ad-hoc runs.

**Inputs from $ARGUMENTS:**
- JOB_ID — single integer

Sidecar JSON path: `<REPO_ROOT>/automation/outreach/<JOB_ID>.json`. Read it, send to every lead where `approved == true` AND `send_status` is `pending` (or `failed` for retries).

Use Chrome MCP (the user is authenticated on LinkedIn). Per-lead flow:
- 1st-degree: direct DM via Message button
- 2nd-degree: Connect → Add a note → paste message → Send invitation
- 3rd+ degree: skip (mark `send_status: skipped`)

**Critical rules** (also in the spec):
- 45-90s random jitter between EVERY send, success or failure
- NEVER send blank connection requests; always add the note
- If LinkedIn says "you've reached your monthly limit for personalized invitations", mark that lead and all subsequent leads as `limit_reached` / `skipped`, save, exit cleanly
- NEVER use InMail credits; stay on the free message tab
- If 3 consecutive failures, halt batch, mark remaining as skipped
- NEVER edit a lead's message at send-time (user finalized it in the UI). Only exception: trimming overflow at sentence boundary.
- NEVER use em dashes (—) or double dashes (--) in any message text

When done, print the one-line DONE summary from §4 of the spec and exit.
