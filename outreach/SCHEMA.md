# Outreach sidecar JSON schema

One file per applied job: `automation/outreach/<job_id>.json`

Created by `outreach-lead-finder-spec.md` (Stage 1). Read + mutated by the triage UI when the user reviews/edits/approves leads. Read again by `outreach-sender-spec.md` (Stage 2) which writes back send-status.

> **Message templates live in `outreach/message-templates.md`** (the editable surface). The lead-finder copies them into the sidecar's `templates` field verbatim. The strings below are illustrative; the live values come from that file.

```json
{
  "job_id": 42,
  "company": "Palantir",
  "role": "Forward Deployed Software Engineer, New Grad",
  "apply_url": "https://jobs.palantir.com/...",
  "brief_reason": "FDE program working with ontology / mission-critical deployments",
  "stage": "leads-ready",
  "lead_count_requested": 10,
  "found_at": "2026-06-05T14:23:00",
  "sent_at": null,
  "templates": {
    "recruiter": "Hey {first_name}, just applied to the {role_short} role{job_id_suffix} at {company}. Been following your work on {brief_reason} for a while. Would mean a lot if you could give my resume a quick look.",
    "founder": "Hey {first_name}, applied to the {role_short} role{job_id_suffix} at {company}. Really like what you're building in {brief_reason}. Would love a few seconds of your time on my resume if you have a sec.",
    "engineer": "Hey {first_name}, just put in an app for the {role_short} role{job_id_suffix} on your team. Big fan of what your team's doing on {brief_reason}. Would love a quick look at my resume if you have a sec."
  },
  "leads": [
    {
      "lead_id": "lead-001",
      "name": "Jane Smith",
      "first_name": "Jane",
      "title": "University Recruiter, New Grad SWE",
      "company": "Palantir",
      "profile_url": "https://www.linkedin.com/in/janesmith/",
      "summary": "4 yrs at Palantir, focused on new-grad / university hiring. Connected with the user (1st-degree).",
      "connection_degree": "1st",
      "lead_type": "recruiter",
      "qualified_reason": "1st-degree connection, new-grad recruiting focus, same org",
      "approved": true,
      "message": "Hey Jane, just applied to the FDE role at Palantir. Been following your work on ontology infra for a while. Would mean a lot if you could give my resume a quick look.",
      "send_status": "pending",
      "send_error": null,
      "sent_at": null,
      "note_used": false
    }
  ]
}
```

## Fields

- **stage**: `finding` → `leads-ready` → `sending` → `sent` (or `error`)
- **lead_type**: `recruiter` | `founder` | `engineer` — determines which template seeds the message
- **connection_degree**: `1st` (can DM directly) | `2nd` (must connect + add note) | `3rd+` (skip unless user explicitly approves)
- **approved**: `true` | `false` | `null` (null = user hasn't reviewed yet; defaults to true if `connection_degree == 1st` and lead_type == recruiter at find-time)
- **message**: pre-hydrated from `templates[lead_type]` with `{first_name}`, `{role_short}`, `{job_id_suffix}`, `{company}`, `{brief_reason}` filled. User can override per-lead in the modal.
- **send_status**: `pending` | `sent` | `failed` | `skipped` | `limit_reached`
- **note_used**: `true` if a personalized note was attached to a connection request (counts toward LinkedIn's monthly cap)

## Stage 1 (lead-finder) writes
- Everything except `send_status` ≠ `pending`, `sent_at`, `note_used: true`

## UI mutates (via /api/outreach-leads-update)
- `templates`, `brief_reason`, `leads[].approved`, `leads[].message`

## Stage 2 (sender) writes
- `stage` → `sending` → `sent` (or stays at `sending` partial if mixed outcome)
- per-lead `send_status`, `send_error`, `sent_at`, `note_used`
- `sent_at` (top-level) when batch is done
