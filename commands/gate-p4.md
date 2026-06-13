# /gate-p4 – Quality Gate 4: Planning → Implementation

Checks whether all organizational and technical prerequisites are met to begin implementation. This is a readiness gate – all participants must know what to do first. No argument – this gate always checks the complete checklist.

## No Argument ($ARGUMENTS not applicable)

Gate commands do not accept arguments. They always check the complete current project status.

## Execution

### 1. Read Preflight Report

Read `docs/.gate-preflight-p4.md` as the primary source of information. This report contains:
- Artifact existence and mandatory sections (mechanically checked)
- Content checks (regex-based: estimates, acceptance criteria, DoD, etc.)
- Document summaries (via Ollama, if available)

If the preflight report does not exist or is older than 10 minutes, read the planning documents directly instead — **always start with the phase index**:

1. **`docs/planning/PROJECT_PLAN.md`** (phase index) — gives you the detail-file table, key decisions, milestones, open risks.
2. From the index's detail-file table, load only the detail files you need:
   - **`docs/planning/BACKLOG.md`** (living)
   - **`docs/planning/SPRINT.md`** (living, current sprint)
   - **`docs/planning/RISKS.md`** (living, cumulative risk register)
   - **`docs/planning/SETUP.md`** (CI/CD + dev-env status)
   - **`docs/planning/DOCS.md`** (summary of README/CONTRIBUTING)
3. Repo-root files when content checks demand them: `README.md`, `CONTRIBUTING.md`.

### 1a. Constitution Inviolables (mandatory pre-gate)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p4.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for the gate:
- Include the Inviolable bullets verbatim in the agent prompt (Step 2 below).
- The agent must check the sprint plan and backlog against the Inviolables (e.g. „each story respects A11y baseline", „no story violates DSGVO defaults").
- Any violation is an **"Inviolable breach"** — surface it explicitly in the verdict and treat it as a No-Go signal.

If `docs/CONSTITUTION.md` is missing on a Full-Track project, recommend `/constitution` before proceeding.

### 2. Delegation to Project-Planner Agent

Delegate the gate check to the **project-planner** agent with a focused prompt:

> Gate P4 check. Preflight report (with summaries):
> [Insert preflight content here]
>
> Mechanical checks are done (file existence, sections, content patterns).
> Evaluate the content:
> 1. **Backlog quality**: Are stories precise enough for developers? Are estimates plausible?
> 2. **Sprint planning**: Is capacity realistic, order sensible, sprint goal clear?
> 3. **Milestones**: Are success criteria measurable and achievable?
> 4. **Risks**: Are countermeasures concrete or just placeholders?
> 5. **Technical readiness**: CI/CD, dev environment, secrets – can work start tomorrow?
> 6. **First story**: Can the developer start without asking questions?
>
> If unclear: read the original file selectively (not all of them).
> Format: Per point a rating (Met/Partially/Not met) + 1-2 sentences.
> Overall recommendation: Go / Conditional Go / No-Go.

### 3. Create Gate Protocol

Create **`docs/planning/GATE_P4.md`** with:
- Result of the mechanical preflight checks (copy table from report)
- Content evaluation by the project-planner (6 points)
- List of open points with concrete next steps
- Go/Conditional Go/No-Go recommendation

Also update **`docs/planning/PROJECT_PLAN.md`** (phase index):
- Set `**Status:** Gate Passed (DD.MM.YYYY)` (or `Conditional Go` / `No-Go`).
- Append the verdict and any Conditional-Go conditions under the **Gate Notes** section.
- Add a row in the detail-file table for `[GATE_P4.md](GATE_P4.md)` with the verdict.

---

## Quality Gate 4 – Reference Checklist

The following points are covered by preflight (mechanically) and agent (content):

**Mechanical (Preflight):**
- Phase index `docs/planning/PROJECT_PLAN.md` exists with the standard sections plus a `## Milestones & Release Planning` body section
- Living detail files exist with frontmatter `status: living`: `BACKLOG.md`, `SPRINT.md`, `RISKS.md`
- Setup detail files exist with frontmatter `status: active`: `SETUP.md`, `DOCS.md`
- Repo-root files exist: `README.md` with quick-start, `CONTRIBUTING.md`

**Content (Agent):**
- Backlog: stories precise, estimates plausible, acceptance criteria clear
- Sprint: capacity realistic, order sensible
- Milestones: success criteria measurable
- Risks: countermeasures concrete
- Technical readiness: CI/CD, dev environment, secrets
- First story: developer can start without asking questions

---

## Result

- **`docs/planning/GATE_P4.md`** (gate protocol with checklist, evaluation, recommendation)
- **`docs/planning/PROJECT_PLAN.md`** (phase index updated: status, gate notes)

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Go** | Team is ready, infrastructure is in place | Start with `/p5-implement` |
| **Conditional Go** | Minor gaps, but not blocking | Close gaps in parallel with the start |
| **No-Go** | Blocking gaps – starting would fail | Fix blockers, then re-check |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Write **`docs/planning/GATE_P4.md`** (gate protocol from §3 above)
2. Update **`docs/planning/PROJECT_PLAN.md`** phase index with gate result (status + gate notes, per §3 above)
3. **On Go only** — freeze Phase-P4 detail files: `bash ~/.claude/scripts/freeze-phase-docs.sh P4` (skipped on Conditional Go / No-Go)
4. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
5. **Cleanup**: `rm -f docs/.gate-preflight-p4.md` (last operation)

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate

### Cleanup
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p4.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
