# Resume Tailoring Spec — Agentic Loop

> **Read me first.** This file is the source of truth for the resume tailoring pipeline. The triage server (`triage_server.py`) invokes Claude Code with a prompt that says "read this spec and execute it for job_id N." Edit this file to change tailoring behavior — never modify the invocation command.

## §0 Configuration (READ BEFORE EVERYTHING ELSE)

**Before anything else, read `<REPO_ROOT>/automation/config/user.yaml`.** That file contains:

- `identity` — the owner's name (used in resume header + output filename pattern)
- `resume.filename_pattern` — e.g. `"Your Full Name SWE {company}"`. Replace `{company}` with the target company name when writing the output `.md` / `.tex` / `.pdf` files.
- `resume.killer_metrics` — the list of quantified wins that MUST stay visible across every tailored version (see §1 / §3 rules)
- `resume.hard_facts` — education, GPA, graduation date (use as-is, never invent variations)
- `resume.projects_always_include` — projects to keep on every resume
- `resume.organizations_always_include` — organizations / leadership lines

Throughout this spec, when a section mentions a specific value (e.g. "Your Full Name SWE", "(a top quantified metric)", "your flagship project"), **use the values from user.yaml**, not the inline ones. The inline values are illustrative defaults for the template owner.

If `config/user.yaml` is missing, halt immediately with `ERROR — missing config/user.yaml`.

---

**Owner:** see `config/user.yaml` → `identity.full_name`
**Triggered by:** Clicking ✓ Yes on a job card in `http://localhost:8765/`
**Runs as:** `claude -p "..." --dangerously-skip-permissions` subprocess
**Working dir:** `<REPO_ROOT>/`
**Input:** `job_id` (1-based row in `<REPO_ROOT>/automation/jobs.xlsx`)
**Output:** `<REPO_ROOT>/versions/<slug>/` containing files matching `resume.filename_pattern` from config (e.g. `Your Full Name SWE <Company>.md`, `.tex`, `.pdf`)

---

## 1. Hard quality rules (non-negotiable)

These are what the user means by "no white space" and "good 1 page resume." Verification step in §5 enforces them.

1. **Exactly 1 page.** Page count > 1 = automatic rejection, revise and recompile. Page count = 1 with > 20% empty bottom = also reject (looks sparse).
2. **Every bullet fills its line in the PDF — NO trailing whitespace after the bullet text on any rendered line.** Each `\resumeItem{}` should render as one nearly-full line. If a bullet wraps to a second line, that second line must ALSO be visually full (no half-empty trailing line). Target word count: **17–22 words per bullet** (matches density of existing bullets in `master/resume.tex`). Bullets with < 14 words = too short, rewrite. Bullets with > 26 words = will wrap, rewrite tighter. Word count is a proxy — **the PDF render is the ground truth**. If the visual inspection (§5) shows trailing whitespace on any line, expand the bullet to fill it OR tighten so it fits on one line.
3. **No widow lines.** A bullet that wraps to a 1-or-2-word second line is a widow — rewrite to fit one line or expand to fill the second.
4. **Every bullet follows the Google XYZ formula**: `Accomplished [X] as measured by [Y] by doing [Z]`. In practice this means each bullet must have (a) the action verb / what was built, (b) the metric / impact (`(top $ metric)`, `(latency metric)`, `(scale metric)`, `(throughput metric)`, `(outcome metric)`), and (c) the technical specifics (named technologies, architecture details). The master resume's existing bullets already follow this pattern — match the density. Bullets missing any of (X, Y, Z) = rewrite using the source bullet from `experiences/`.
5. **Preserve the killer metrics from the master.** These numbers are the user's strongest signals and must stay visible across every tailored version unless the role genuinely doesn't care: **(killer metric #1 from user.yaml)**, **(killer metric #2 from user.yaml)**, **(latency metric from user.yaml)**, **(throughput + outcome metric from user.yaml)**, **(scale metric from user.yaml)**, **(infra-scale metric from user.yaml)**. Tailoring = re-emphasizing, never silently dropping these.
6. **Tailored content only from `experiences/`, `skills.md`, `profile.md`, and the master resume.** Do NOT fabricate metrics, projects, or accomplishments. If a job calls for something the user doesn't have, leave it out — never invent.
7. **Section order is fixed**: Education → Experience → Projects → Technical Skills → Organizations. Don't reorder unless the company specifically calls for something different (e.g. research-heavy roles can promote Projects above Experience).
8. **Header (name + contact) is identical to master** — same email, phone, LinkedIn, GitHub. Don't touch it.

---

## 2. Inputs (read in this order)

1. **`<REPO_ROOT>/automation/jobs.xlsx`** — find the row where `id` matches the input `job_id`. Pull: `company`, `role`, `location`, `comp`, `apply_url`, `reasoning`, `tier`, `source`. Use openpyxl via Python.
2. **`<REPO_ROOT>/profile.md`** — contact info, education facts. Never change.
3. **`<REPO_ROOT>/skills.md`** — broader skill inventory; pick from this when tailoring the Technical Skills section.
4. **`<REPO_ROOT>/experiences/*.md`** — narrative + bullet candidates for each role. Read every file. These are the source for all experience bullets.
5. **`<REPO_ROOT>/master/resume.tex`** — the LaTeX template. **Copy this verbatim as the starting point**, then mutate the bullet contents + skills section per the rules below.
6. **`<REPO_ROOT>/master/resume.md`** — current shipping bullets, for reference.
7. **`<REPO_ROOT>/research/findings.md`** and **`research/action-plan.md`** — the user's research on target companies. If the target company is mentioned, use those notes to inform what to lead with.
8. **(Optional but recommended)** — `web_fetch` the job's `apply_url` if it loads. Look for keywords in the JD (e.g. "agentic", "multimodal", "platform", "Kubernetes", "voice"). These guide which bullets to feature.

---

## 3. Tailoring decisions — which bullets to feature

The master already has the strongest bullets per role. Tailoring = picking the **right 2–3 bullets per role** to lead with based on the job's signal, tightening the skills section, AND re-phrasing bullets within their own facts to surface the JD's exact vocabulary (per §3.1). You are **curating + re-framing** existing source material — never inventing.

**Reordering rule:** Your current role stays first by default. Your strongest "offer-in-hand" or highest-signal role stays second. But lead differently depending on the target's archetype — generalize these to your own roles in `experiences/`:
- **Voice AI / agentic companies** → promote the role with your strongest voice/agent/customer story.
- **Multimodal / vision** → lead with the role that has your strongest multimodal/ML headline.
- **Dev tools / infra / platform** → lead with your strongest infrastructure/scale role.
- **Healthcare / domain-specific** → lead with the role whose domain best matches.
- **Frontier labs** → keep your current shipping role first.

**Bullet selection per role (pick the strongest 2–3 for the target):** for each role in `experiences/`, tag its bullets by theme (e.g. RAG/retrieval, infra/cost, scale/throughput, customer/deployment, product/users) and select the 2–3 whose themes match the JD's archetype. Lead every role with its single strongest quantified bullet. The specifics live in `experiences/*.md` and `config/user.yaml` → `resume.killer_metrics`; this spec only decides *which* to feature, never invents content.

**Skills section tailoring:**
- Show ~4 categories (e.g. AI/ML, ML Infrastructure, Languages, Backend/Cloud — adapt to your stack). Keep them all.
- Reorder if relevant: for ML platform roles, move ML Infrastructure ABOVE AI/ML.
- Drop/add specific items from `skills.md` based on JD keywords. Don't add anything the user hasn't actually done.

**Projects section:**
- Keep the projects in `config/user.yaml` → `resume.projects_always_include`. A strong flagship project (real users / real outcomes) is universally valuable; its description line may be re-framed per role (consumer vs ML-powered vs infra lens) — same project, different lens.

**Organizations section:**
- Keep the lines in `config/user.yaml` → `resume.organizations_always_include`. They take ~2 lines and prove leadership.

---

## 3.1 Aggressive but honest re-framing (the "perfect fit" dial)

The goal: every tailored resume should read like it was **written for** the JD, not **picked for** the JD. But every claim must trace back to `experiences/*.md`. The hard rules below are non-negotiable.

### Step A — extract JD keywords first
Before drafting bullets, `web_fetch` the `apply_url`. Pull **8–12 high-signal phrases** from the JD: technologies (e.g., "LangGraph", "gRPC", "Kafka"), domain terms (e.g., "agentic", "retrieval-augmented", "distributed systems"), and verbs (e.g., "shipped", "owned", "architected"). Save these in `tailor.log` and surface them in the rationale at the bottom of the `.md`. These are your **re-framing targets**.

### Step A.5 — classify the JD's archetype
After extracting keywords, **classify the JD into ONE archetype** (or two if mixed). This drives the lead verbs, the skills-section reshape, and which existing bullet framings to lean into. Log the classification in `tailor.log` AND in the `Why this version` rationale.

| Archetype | JD signals | Lead verbs to use | Skills emphasis | your flagship project framing |
|---|---|---|---|---|
| **FDE / Forward Deployed** | "customer", "deployment", "pilot", "field", "onsite travel", "delivery", "client-facing"; Palantir, Anduril, Decagon, Sierra, Glean, Harvey | **Deployed, Shipped, Owned (end-to-end), Embedded, Drove adoption, Closed (pilots)** | Promote a "Customer Delivery" line surfacing real pilot/deployment numbers from `experiences/` (e.g. closed B2B pilots, hires placed, customer-discovery interviews) | "Owned full product → deployment → customer-feedback loop; shipped to App Store with X daily users" |
| **Platform / Infra / ML Infra** | "scale", "platform", "distributed", "throughput", "latency", "cost", "Kubernetes", "GPU", "inference"; Modal, Databricks, Snowflake (eng-flavored), Vercel | **Architected, Scaled, Engineered, Optimized, Cut (latency/cost), Built (at scale)** | Promote ML Infrastructure category ABOVE AI/ML; surface specific platform tech that maps to the JD | "iOS app with on-device LLM inference at the edge" |
| **Research / Applied ML / Frontier Lab (research roles)** | "research", "investigate", "novel", "publish", "evaluations", "benchmarks", "model behavior", "fine-tuning"; Anthropic Research, OpenAI Research, DeepMind | **Demonstrated, Investigated, Modeled, Evaluated, Designed (experiments)** | Lead with AI/ML; surface eval frameworks, fine-tuning, model evaluation, training tools | "LLM photo-and-text macro extraction with multimodal vision pipeline; X-shot prompting + structured output evals" |
| **Frontier Lab — engineering** (not research) | "Member of Technical Staff", "ship at the frontier", "production AI systems", "applied"; Anthropic Eng, OpenAI Eng, xAI Eng | **Shipped, Owned, Architected, Built (in production)** | Balance AI/ML + ML Infra; emphasize production AI shipping | "Production iOS app shipping LLM features end-to-end" |
| **Consumer / Product** | "user", "product", "growth", "consumer", "mobile", "DAU/MAU", "engagement", "App Store"; consumer AI apps | **Shipped, Launched, Drove (DAU/retention), Iterated (with users)** | Add a "Product Impact" line surfacing user metrics; lead bullets with user-facing outcomes | "Consumer iOS app, X daily users, Y collective outcome (e.g. fat loss / hours saved)" |
| **Defense / Hard-tech** | "ITAR", "clearance", "mission-critical", "field deployment", "harden"; Anduril, Vannevar, Saronic, Castelion | **Deployed (in field), Owned, Engineered (mission-critical), Hardened** | Emphasize reliability, low-level, production systems; surface any deployment-resilience work | "iOS app with on-device inference, no server-side dependencies" |
| **Hybrid / Unclear** | Mixed signals (e.g. "Forward Deployed AI Engineer at a research lab"). | Blend lead verbs from the dominant + secondary archetype. | Pick the dominant archetype's skills reshape. | Pick the framing that matches the dominant archetype. |

**Important — be smart, not robotic.** The archetype is a *default lean*, not a forced template. If a JD is genuinely a Platform role, don't jam FDE verbs into it. If the candidate doesn't have a strong customer-deployment story in `experiences/`, don't fabricate a "Customer Delivery" skills line — fall back to the honest framing. The archetype tells you where to push when the underlying facts already support it.

### Step B — what you CAN do (allowed re-phrasing)
Combining Step A's keywords with Step A.5's archetype, aggressively re-frame within the candidate's real facts:

- **Lead-verb swap per archetype.** Every Experience bullet should open with a verb from the archetype's lead-verb list. Master says "Built K8s pipeline…" → FDE-archetype: "Deployed K8s pipeline…"; Platform-archetype: "Architected K8s pipeline…"; Research-archetype: stays "Built" since investigation isn't the action. Same fact, archetype-leading verb.
- **Reorder words to lead with the JD's emphasis.** Source: "Built K8s pipeline ingesting (scale metric)". JD says "distributed systems" → "Built distributed K8s pipeline ingesting (scale metric)". Same fact, JD-leading.
- **Substitute synonyms that match the JD's exact phrasing.** "retrieval-augmented generation" → "RAG" if JD uses "RAG". "containerized service" → "microservice" if JD says microservice.
- **Promote sub-mentions to the lead.** Source: "...integrated Stripe, Twilio, and gRPC". JD is gRPC-heavy → "Built gRPC service integrating Stripe and Twilio".
- **Reframe the same work with a different domain lens.** A single infra/data pipeline from your experience IS, simultaneously and truthfully: "distributed systems work" / "ML infrastructure" / "platform engineering" / "data pipeline at scale" / "customer deployment infra". Pick the lens that matches the archetype.
- **Re-frame project description lines per archetype.** your flagship project has multiple honest framings (see the table above) — pick the archetype-matching one.
- **Restructure the skills section per archetype.** Not just adding 2-3 words — actually move categories around or add an archetype-specific line backed by real source-data:
  - **FDE:** add a "Customer Delivery" line (e.g. "3 B2B pilots closed, 6 hires placed, 50+ customer-discovery interviews") **only if those numbers are real and in `experiences/`**.
  - **Platform/Infra:** lift ML Infrastructure above AI/ML.
  - **Research:** lead with AI/ML; surface eval frameworks and fine-tuning if present.
  - **Consumer:** add a "Product Impact" line with user-facing metrics from the source.
- **Reorder Experience entries within the archetype.** FDE → promote the role with the strongest customer-deployment story to lead. Research → promote the role with the strongest investigative work. (Still respect the §3 default reordering rule as the starting point.)

### Step C — what you CANNOT do (lying)
**Hard rules. Violating any of these = automatic rejection, even if the visual layout is perfect. These rails are stronger than the archetype dial — when in conflict, honesty wins.**

- ❌ **No new metrics.** Every `$`, `%`, multiplier, latency number, user count, and dollar figure must come from `experiences/*.md`. Do not invent. Do not extrapolate. Do not "round up".
- ❌ **No new accomplishments.** Don't claim ownership, leadership, or scope that isn't in the source files.
- ❌ **No new tools/technologies.** If the user didn't actually use Kafka, don't mention Kafka — even if the JD demands it. Leave it for the cover letter as a learning interest.
- ❌ **Killer metrics stay visible** ((top $ metric), (2nd $ metric), (latency metric), (throughput metric), (scale metric), (infra metric)). Re-frame them — never silently drop them.
- ❌ **Google XYZ format stays on every bullet.** (X) action verb / what built, (Y) metric / impact, (Z) technical specifics. Re-framing only changes the order/vocabulary, never the presence of all three.
- ❌ **Magnitudes/units never change.** A "$120k/yr" saving never becomes "$150k/yr" or "$120k/month".
- ❌ **Don't force an archetype that doesn't fit the facts.** If the JD is FDE-flavored but the candidate has no real customer-deployment story → don't invent one. Use the archetype's lead verbs only where they're truthful (e.g. "Deployed" is fine for a bullet about a real customer deployment, but NOT for an internal-only pipeline bullet). When the archetype reframe would distort a fact, fall back to honest framing — even if it costs you JD-keyword coverage.
- ❌ **Don't pad the skills section with archetype-shaped lines you can't back up.** A "Customer Delivery: 3 B2B pilots closed" line is only OK if the 3 pilots are documented in `experiences/`. A "Customer Delivery: experience with customers" line is hand-waving — don't ship it.

### Step D — coverage check during verification
After drafting, count how many of the 8–12 JD keywords appear somewhere in the tailored resume. **Target: ≥ 60% coverage.** Below 50% → loop back and find more honest re-framing opportunities. Below 30% → flag in the rationale ("⚠️ low keyword coverage — role may not be a strong fit").

---

## 4. Output layout

For `job_id=N` with company `Upstart` and role `Software Engineer, Agentic Tooling`:

```
<REPO_ROOT>/versions/upstart-software-engineer-agentic-tooling/
├── Your Full Name SWE Upstart.md     # markdown source + tailoring rationale at bottom
├── Your Full Name SWE Upstart.tex    # LaTeX (copy of master.tex with bullets/skills swapped)
├── Your Full Name SWE Upstart.pdf    # compiled output — THIS is what the user sends
├── job-context.json                       # snapshot of the job row from jobs.xlsx for traceability
└── tailor.log                             # debug log of the agentic verification loop
```

**Filename convention** (THE deliverable filename, used for .md/.tex/.pdf so they all match if the user forwards the source). **Never name the deliverable files `tailored.*` — always use this pattern:**

```
Your Full Name SWE <Company>.<ext>
```

Where `<Company>` is the clean company name from the xlsx row (e.g. `Upstart`, `NVIDIA`, `Anthropic`). Spaces in the filename are allowed and intentional. Strip any LaTeX-unfriendly chars (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) and trim trailing whitespace. Examples:
- Company `OpenAI` → `Your Full Name SWE OpenAI.pdf`
- Company `Anthropic` → `Your Full Name SWE Anthropic.pdf`
- Company `Meta` → `Your Full Name SWE Meta.pdf`

**Folder slug rule** (the containing directory — the user never sees this, it's just for filesystem tidiness): `<company-lowercase-hyphenated>-<role-lowercase-hyphenated-trimmed-to-40-chars>`. Strip punctuation. Examples:
- `Upstart` + `Software Engineer, Agentic Tooling` → `upstart-software-engineer-agentic-tooling`
- `NVIDIA` + `Machine Learning Applications and Compiler Engineer, LPX - New College Grad 2026` → `nvidia-machine-learning-applications-and-comp` (truncated)

If the folder already exists, append `-v2`, `-v3`, etc. Don't overwrite previous tailorings.

**`Your Full Name SWE <Company>.md` body structure:**
```markdown
# Your Full Name — Tailored for <Company> — <Role>

<resume content as markdown — same bullets that go in the .tex>

---

## Why this version
- **Archetype:** <one of FDE / Platform / Research / Frontier-Lab-Eng / Consumer / Defense / Hybrid — and a one-line signal that drove the call>
- **Lead-verb defaults applied:** <list the archetype verbs used, e.g. "Deployed, Shipped, Owned (end-to-end)">
- **Reordering:** <e.g. "promoted Role A above Role B because the JD is FDE-flavored and A has the strongest customer-deployment story">
- **Bullet picks:** <which bullets, why>
- **Skills emphasis:** <what was promoted / restructured per the archetype>
- **JD keywords matched:** <comma-separated keywords from the JD>
- **Coverage:** <N of M JD keywords appear in the rendered resume — Step D target ≥60%>
- **Honest archetype caveats:** <any spots where the archetype reframe would have distorted facts, so honest framing was kept instead>
- **Gaps to flag in cover letter:** <things the candidate doesn't have that the JD wants>
```

---

## 5. The agentic verification loop (max 4 iterations)

This is what makes the output actually good — don't skip it.

```
iteration = 1
while iteration <= 4:
    1. Compile: cd <REPO_ROOT>/versions/<slug>/ && pdflatex -interaction=nonstopmode "Your Full Name SWE <Company>.tex"
       (If pdflatex is unavailable, `tectonic "Your Full Name SWE <Company>.tex"` is an accepted drop-in engine.)
       - On compile error, fix the .tex and retry. Compile errors don't count as an iteration.
    2. Read the resulting "Your Full Name SWE <Company>.pdf" (use the Read tool with the PDF path — Claude can view PDFs visually).
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
open "<REPO_ROOT>/versions/<slug>/Your Full Name SWE <Company>.pdf"
```
This opens the PDF in macOS Preview so the user can eyeball it. Skip on headless / errored runs.

---

## 7. Finalize — update jobs.xlsx

When the verified PDF is in place, write the **full absolute path to the PDF** to the resume_version column for this job_id. The UI uses this exact value to build its "Open PDF ↗" link.

```python
from openpyxl import load_workbook
xlsx = "<REPO_ROOT>/automation/jobs.xlsx"
pdf_path = "<REPO_ROOT>/versions/<slug>/Your Full Name SWE <Company>.pdf"
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

## 9. Dials the user may want to tweak over time

- Bullets-per-role count (currently: 2–3 per top role, 1–2 per supporting)
- Word target per bullet (currently 17–22)
- Iteration cap (currently 4)
- Whether to auto-`open` the PDF on success
- Section ordering rules
- The default "current-role-first" lead

Search-replace these strings to change behavior. The trigger script (`triage_server.py`) doesn't care — it just invokes Claude Code with the prompt "read this spec and execute it."
