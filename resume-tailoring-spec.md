# Resume Tailoring Spec — Agentic Loop

> **Read me first.** This file is the source of truth for the resume tailoring pipeline. The triage server (`triage_server.py`) invokes Claude Code with a prompt that says "read this spec and execute it for job_id N." Edit this file to change tailoring behavior — never modify the invocation command.

**Owner:** <Your Name> (<your-email@example.com>)
**Triggered by:** Clicking ✓ Yes on a job card in `http://localhost:8765/`
**Runs as:** `claude -p "..." --dangerously-skip-permissions` subprocess
**Working dir:** `~/your-resume/`
**Input:** `job_id` (1-based row in `~/claude-job-pipeline/jobs.xlsx`)
**Output:** `~/your-resume/versions/<slug>/` containing `<Your Name> SWE Newgrad <Company>.md`, `.tex`, `.pdf`

---

## 1. Hard quality rules (non-negotiable)

These are what "no white space" and "a good 1-page resume" mean. The verification step in §5 enforces them.

1. **Exactly 1 page.** Page count > 1 = automatic rejection, revise and recompile. Page count = 1 with > 20% empty bottom = also reject (looks sparse).
2. **Every bullet fills its line in the PDF — NO trailing whitespace after the bullet text on any rendered line.** Each `\resumeItem{}` should render as one nearly-full line. If a bullet wraps to a second line, that second line must ALSO be visually full (no half-empty trailing line). Target word count: **17–22 words per bullet** (matches density of existing bullets in `master/resume.tex`). Bullets with < 14 words = too short, rewrite. Bullets with > 26 words = will wrap, rewrite tighter. Word count is a proxy — **the PDF render is the ground truth**. If the visual inspection (§5) shows trailing whitespace on any line, expand the bullet to fill it OR tighten so it fits on one line.
3. **No widow lines.** A bullet that wraps to a 1-or-2-word second line is a widow — rewrite to fit one line or expand to fill the second.
4. **Every bullet follows the Google XYZ formula**: `Accomplished [X] as measured by [Y] by doing [Z]`. In practice this means each bullet must have (a) the action verb / what was built, (b) the metric / impact (e.g. `$X/yr saved`, `N% latency drop`, `Nk users/day`, `placed N hires`), and (c) the technical specifics (named technologies, architecture details). The master resume's existing bullets already follow this pattern — match the density. Bullets missing any of (X, Y, Z) = rewrite using the source bullet from `experiences/`.
5. **[CUSTOMIZE] Preserve the killer metrics from the master.** These are the candidate's strongest signals and must stay visible across every tailored version unless the role genuinely doesn't care. **List your top 4–8 numerical wins here so Claude can prioritize them** — e.g. *"$X/yr cost saving at <Company A>", "N% latency reduction at <Company B>", "Nk users/day at <Company C>"*. Tailoring = re-emphasizing these, never silently dropping them.
6. **Tailored content only from `experiences/`, `skills.md`, `profile.md`, and the master resume.** Do NOT fabricate metrics, projects, or accomplishments. If a job calls for something the candidate doesn't have, leave it out — never invent.
7. **Section order is fixed**: Education → Experience → Projects → Technical Skills → Organizations. Don't reorder unless the company specifically calls for something different (e.g. research-heavy roles can promote Projects above Experience).
8. **Header (name + contact) is identical to master** — same email, phone, LinkedIn, GitHub. Don't touch it.

---

## 2. Inputs (read in this order)

1. **`~/claude-job-pipeline/jobs.xlsx`** — find the row where `id` matches the input `job_id`. Pull: `company`, `role`, `location`, `comp`, `apply_url`, `reasoning`, `tier`, `source`. Use openpyxl via Python.
2. **`~/your-resume/profile.md`** — contact info, education facts. Never change.
3. **`~/your-resume/skills.md`** — broader skill inventory; pick from this when tailoring the Technical Skills section.
4. **`~/your-resume/experiences/*.md`** — narrative + bullet candidates for each role. Read every file. These are the source for all experience bullets.
5. **`~/your-resume/master/resume.tex`** — the LaTeX template. **Copy this verbatim as the starting point**, then mutate the bullet contents + skills section per the rules below.
6. **`~/your-resume/master/resume.md`** — current shipping bullets, for reference.
7. **`~/your-resume/research/findings.md`** and **`research/action-plan.md`** — your research on target companies. If the target company is mentioned, use those notes to inform what to lead with.
8. **(Optional but recommended)** — `web_fetch` the job's `apply_url` if it loads. Look for keywords in the JD (e.g. "agentic", "multimodal", "platform", "Kubernetes", "voice"). These guide which bullets to feature.

---

## 3. Tailoring decisions — which bullets to feature

The master already has the strongest bullets per role. Tailoring = picking the **right 2–3 bullets per role** to lead with based on the job's signal, tightening the skills section, AND re-phrasing bullets within their own facts to surface the JD's exact vocabulary (per §3.1). You are **curating + re-framing** existing source material — never inventing.

### [CUSTOMIZE] Reordering rule
Define a default lead role and a fallback. Example template:
> - Default lead: `<your most-current shipping role>` (always first — it's the freshest signal).
> - Secondary lead: `<your strongest prior role / best brand>` (second by default).
> - Override per JD theme — e.g. *Voice AI / agentic roles → promote your voice-AI role above secondary*; *Multimodal / vision → lead with whichever role had the most multimodal work*; *Frontier labs (Anthropic, OpenAI, etc.) → keep most-current first*.

Edit the bullet list above to encode your actual roles and the JD themes you commonly see.

### [CUSTOMIZE] Bullet selection per role
For each role in your experience, list which bullet(s) to feature for which JD themes. Example template:
> - **`<Role A>`:** always include the `<flagship bullet>`. Optionally add `<secondary bullet>` for `<JD theme>`.
> - **`<Role B>`:** at least the `<core bullet>`. Add the `<cost/efficiency bullet>` for infra/cost-conscious shops. Add the `<platform bullet>` for platform roles.
> - …

The point: every (role, JD-theme) combo should have a default. Claude reads this to know which bullets to lead with.

### Skills section tailoring
- Keep the 4 categories from your master (AI/ML, ML Infrastructure, Languages, Backend/Cloud — or whatever your master defines).
- Reorder if relevant: for ML-platform roles, move ML Infrastructure ABOVE AI/ML.
- Drop/add specific items from `skills.md` based on JD keywords. **Don't add anything the candidate hasn't actually done.**

### [CUSTOMIZE] Projects section
List the projects to always include and how their description lines may be re-framed per role lens. Example:
> - `<Your flagship project>` stays. Universally strong (real users, real outcomes). Description line may be re-framed per role (consumer iOS vs ML-powered vs multimodal inference) — same project, different lens.

### [CUSTOMIZE] Organizations section
List groups/leadership roles that should stay. Example:
> - Keep both `<Group A>` and `<Group B>`. They take 2 lines and prove leadership.

---

## 3.1 Aggressive but honest re-framing (the "perfect fit" dial)

The goal: every tailored resume should read like it was **written for** the JD, not **picked for** the JD. But every claim must trace back to `experiences/*.md`. The hard rules below are non-negotiable.

### Step A — extract JD keywords first
Before drafting bullets, `web_fetch` the `apply_url`. Pull **8–12 high-signal phrases** from the JD: technologies (e.g., "LangGraph", "gRPC", "Kafka"), domain terms (e.g., "agentic", "retrieval-augmented", "distributed systems"), and verbs (e.g., "shipped", "owned", "architected"). Save these in `tailor.log` and surface them in the rationale at the bottom of the `.md`. These are your **re-framing targets**.

### Step B — what you CAN do (allowed re-phrasing)
The same X / Y / Z facts can be reframed multiple honest ways. Pick the framing that resonates with the JD:

- **Reorder words to lead with the JD's emphasis.** Source: "Built K8s pipeline ingesting 10k+ emails/day". JD says "distributed systems" → "Built distributed K8s pipeline ingesting 10k+ emails/day". Same fact, JD-leading.
- **Substitute synonyms that match the JD's exact phrasing.** Source: "retrieval-augmented generation". JD uses "RAG" → use "RAG". Source: "containerized service". JD says "microservice" → use "microservice".
- **Promote sub-mentions to the lead.** Source: "...integrated Stripe, Twilio, and gRPC". JD is gRPC-heavy → "Built gRPC service integrating Stripe and Twilio".
- **Reframe the same work with a different domain lens.** A Kubernetes data pipeline IS, simultaneously and truthfully: "distributed systems work" / "ML infrastructure" / "platform engineering" / "data pipeline at scale". Pick the lens that matches the role.
- **Re-frame project description lines** (e.g., your flagship side project) per role lens.

### Step C — what you CANNOT do (lying)
**Hard rules. Violating any of these = automatic rejection, even if the visual layout is perfect.**

- ❌ **No new metrics.** Every `$`, `%`, multiplier, latency number, user count, and dollar figure must come from `experiences/*.md`. Do not invent. Do not extrapolate. Do not "round up".
- ❌ **No new accomplishments.** Don't claim ownership, leadership, or scope that isn't in the source files.
- ❌ **No new tools/technologies.** If you didn't actually use Kafka, don't mention Kafka — even if the JD demands it. Leave it for the cover letter as a learning interest.
- ❌ **Killer metrics stay visible.** Re-frame them — never silently drop them. (Define the killer-metrics list in §1.5 for this candidate.)
- ❌ **Google XYZ format stays on every bullet.** (X) action verb / what built, (Y) metric / impact, (Z) technical specifics. Re-framing only changes the order/vocabulary, never the presence of all three.
- ❌ **Magnitudes/units never change.** "$134k/yr" never becomes "$150k/yr" or "$134k/month".

### Step D — coverage check during verification
After drafting, count how many of the 8–12 JD keywords appear somewhere in the tailored resume. **Target: ≥ 60% coverage.** Below 50% → loop back and find more honest re-framing opportunities. Below 30% → flag in the rationale ("⚠️ low keyword coverage — role may not be a strong fit").

---

## 4. Output layout

For `job_id=N` with company `Upstart` and role `Software Engineer, Agentic Tooling`:

```
~/your-resume/versions/upstart-software-engineer-agentic-tooling/
├── <Your Name> SWE Newgrad Upstart.md     # markdown source + tailoring rationale at bottom
├── <Your Name> SWE Newgrad Upstart.tex    # LaTeX (copy of master.tex with bullets/skills swapped)
├── <Your Name> SWE Newgrad Upstart.pdf    # compiled output — THIS is what you send
├── job-context.json                       # snapshot of the job row from jobs.xlsx for traceability
└── tailor.log                             # debug log of the agentic verification loop
```

**Filename convention** (THE deliverable filename, used for .md/.tex/.pdf so they all match if you forward the source). **Never name the deliverable files `tailored.*` — always use this pattern:**

```
<Your Name> SWE Newgrad <Company>.<ext>
```

Where `<Company>` is the clean company name from the xlsx row (e.g. `Upstart`, `NVIDIA`, `Anthropic`). Spaces in the filename are allowed and intentional. Strip any LaTeX-unfriendly chars (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) and trim trailing whitespace. Examples:
- Company `OpenAI` → `<Your Name> SWE Newgrad OpenAI.pdf`
- Company `Anthropic` → `<Your Name> SWE Newgrad Anthropic.pdf`
- Company `Meta` → `<Your Name> SWE Newgrad Meta.pdf`

**Folder slug rule** (the containing directory — you never see this, it's just for filesystem tidiness): `<company-lowercase-hyphenated>-<role-lowercase-hyphenated-trimmed-to-40-chars>`. Strip punctuation. Examples:
- `Upstart` + `Software Engineer, Agentic Tooling` → `upstart-software-engineer-agentic-tooling`
- `NVIDIA` + `Machine Learning Applications and Compiler Engineer, LPX - New College Grad 2026` → `nvidia-machine-learning-applications-and-comp` (truncated)

If the folder already exists, append `-v2`, `-v3`, etc. Don't overwrite previous tailorings.

**`<Your Name> SWE Newgrad <Company>.md` body structure:**
```markdown
# <Your Name> — Tailored for <Company> — <Role>

<resume content as markdown — same bullets that go in the .tex>

---

## Why this version
- **Reordering:** <e.g. "promoted Role A above Role B because the JD is voice-AI-first">
- **Bullet picks:** <which bullets, why>
- **Skills emphasis:** <what was promoted, what was dropped>
- **JD keywords matched:** <comma-separated keywords from the JD>
- **Gaps to flag in cover letter:** <things you don't have that the JD wants>
```

---

## 5. The agentic verification loop (max 4 iterations)

This is what makes the output actually good — don't skip it.

```
iteration = 1
while iteration <= 4:
    1. Compile: cd ~/your-resume/versions/<slug>/ && pdflatex -interaction=nonstopmode "<Your Name> SWE Newgrad <Company>.tex"
       (If pdflatex is unavailable, `tectonic "<Your Name> SWE Newgrad <Company>.tex"` is an accepted drop-in engine.)
       - On compile error, fix the .tex and retry. Compile errors don't count as an iteration.
    2. Read the resulting "<Your Name> SWE Newgrad <Company>.pdf" (use the Read tool with the PDF path — Claude can view PDFs visually).
    3. Verify against §1 hard rules:
       a. Exactly 1 page? Look at the page count or estimate by content overflow markers.
       b. Bottom of page < ~20% empty? If too sparse, content needs to expand.
       c. Every bullet fills its line (no widows)? Visually scan.
       d. Word counts: each \resumeItem{} body between 14 and 26 words?
       e. Metrics in every bullet? Check for $, %, numerals, named tech.
    4. If all checks pass → DONE. Break the loop.
    5. If checks fail → identify the specific problem:
       - "Too long (overflows 1 page)" → trim a bullet, drop a less-relevant one, or compact the skills section
       - "Too sparse (huge blank at bottom)" → add a bullet from a less-featured role, or restore a dropped category in skills
       - "Bullet #3 has a widow" → tighten or expand bullet to fit one line cleanly
       - "Bullet has no metric" → rewrite using a stronger source bullet from experiences/
       - Edit the .tex accordingly. Increment iteration.
    6. Log decisions to tailor.log: "iteration N: <observation>, <action taken>".
```

After 4 iterations, if still imperfect, save what you have (don't loop forever) and add to the rationale section: "⚠️ Reached iteration cap with remaining issue: <description>. Manual review needed."

### Mandatory visual inspection before finalizing

**You MUST `Read` the compiled PDF visually as the final gate before writing the resume_version path to xlsx.** Word counts and LaTeX source inspection are not sufficient — Claude can see PDFs as images. On the final pass, before declaring DONE:

1. Open the PDF with the `Read` tool (use the absolute `.pdf` path).
2. Walk through it visually, line by line:
   - **Is it exactly 1 page?** If a second page exists at all, even with one line on it → reject, tighten, recompile.
   - **Is the bottom ≥ 80% filled?** Big white gap at the bottom = sparse, looks bad → expand.
   - **Does every bullet line end with text, not whitespace?** A bullet that wraps to a 2-word second line is a widow — reject and rewrite. A bullet that ends 30% short of the right margin looks half-empty — rewrite to fill OR shorten to fit.
   - **Are the Google XYZ elements visible in every bullet?** Eyeball each bullet: action verb at the start, metric somewhere, technical specifics. Missing any → rewrite.
   - **Do JD keywords from §3.1 Step A actually appear in the rendered text?** Cross-check coverage visually.
3. Only after a clean visual pass → write the PDF path to `resume_version` and exit. If any visual check fails, increment iteration and loop.

**This visual gate is non-negotiable. A resume that compiles cleanly but looks sparse / has widows / has whitespace gaps is worse than no tailoring at all — it signals carelessness to the reader.**

---

## 6. Optional: launch a browser to view it

After successful verification, optionally run:
```
open "~/your-resume/versions/<slug>/<Your Name> SWE Newgrad <Company>.pdf"
```
This opens the PDF in macOS Preview so you can eyeball it. Skip on headless / errored runs.

---

## 7. Finalize — update jobs.xlsx

When the verified PDF is in place, write the **full absolute path to the PDF** to the resume_version column for this job_id. The UI uses this exact value to build its "Open PDF ↗" link.

```python
from openpyxl import load_workbook
xlsx = "~/claude-job-pipeline/jobs.xlsx"
pdf_path = "~/your-resume/versions/<slug>/<Your Name> SWE Newgrad <Company>.pdf"
wb = load_workbook(xlsx)
ws = wb["jobs"]
headers = [c.value for c in ws[1]]
rv_idx = headers.index("resume_version")
for r in ws.iter_rows(min_row=2):
    if r[0].value == JOB_ID:
        r[rv_idx].value = pdf_path
        break
wb.save(xlsx)
```

The UI at `localhost:8765` polls every 8s — once the cell is populated, the card flips from "Tailoring…" to "✓ Resume ready · Open PDF ↗".

If the run fails for any reason, write `error: <one-line reason>` to that cell instead so the UI shows the failure state.

---

## 8. Things that frequently trip this up

- **pdflatex not on PATH** — install MacTeX or Basictex. Check with `which pdflatex` from the spawned shell. If missing, write `error: pdflatex not installed` to resume_version and exit.
- **Special chars in company/role for the slug** — sanitize: lowercase, replace non-alphanumeric with `-`, collapse repeats, trim.
- **LaTeX escape characters in tailored content** — `&` → `\&`, `%` → `\%`, `$` → `\$`, `#` → `\#`, `_` → `\_`. Always escape when copying user-facing strings (company names with `&`, etc.) into the .tex.
- **Bullet rewrites that lose source-grounded specificity** — every claim should be traceable back to an `experiences/*.md` file. Don't generalize away the metrics.
- **Iterating forever** — hard cap at 4. Save and ship after.

---

## 9. Dials you may want to tweak over time

- Bullets-per-role count (currently: 2–3 per top role, 1–2 per supporting)
- Word target per bullet (currently 17–22)
- Iteration cap (currently 4)
- Whether to auto-`open` the PDF on success
- Section ordering rules
- The default lead-role ordering (§3 reordering rule)

Search-replace these strings to change behavior. The trigger script (`triage_server.py`) doesn't care — it just invokes Claude Code with the prompt "read this spec and execute it."
