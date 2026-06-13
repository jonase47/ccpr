# /gate-p1 – Quality Gate 1: Conception → Validation

Checks whether all results of the conception phase are complete and robust, and prepares the transition to the validation phase. No argument – this gate always checks the complete checklist.

## No Argument ($ARGUMENTS not applicable)

Gate commands do not accept arguments. They always check the complete current project status.

## Execution

### 1. Read Preflight Report

Read `docs/.gate-preflight-p1.md` as the primary source of information. This report contains:
- Artefact existence and mandatory sections (mechanically checked)
- Content check (regex-based: personas, journeys, MoSCoW, Canvas, break-even, DSGVO)
- Document summaries (via Ollama, if available)

If the preflight report does not exist or is older than 10 minutes, read the conception documents directly instead — **always start with the phase index**:

1. **`docs/concept/CONCEPT.md`** (phase index) — gives you the detail-file table, key decisions, open risks.
2. From the index's detail-file table, load only the detail files you need to confirm content:
   - **`docs/concept/USER_JOURNEYS.md`** (personas, journeys, scenarios)
   - **`docs/concept/FEATURES.md`** (feature catalogue + MVP Scope Boundary section — `MVP.md` no longer exists)
   - **`docs/concept/BUSINESS_MODEL.md`** (Canvas, value proposition, pricing)
   - **`docs/concept/FINANCIAL_PLAN.md`** (cost structure, revenue forecast, break-even, assumptions register)
   - **`docs/concept/DSGVO_INITIAL_ASSESSMENT.md`** (data classification, legal bases, obligations)
3. P0 reference: `docs/discovery/DISCOVERY.md` (phase index) for problem statement / target audience continuity.

### 1a. Constitution Inviolables (mandatory pre-gate)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p1.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for the gate:
- Include the Inviolable bullets verbatim in the agent prompt (Step 2 below).
- The agent must check each evaluated phase-decision against the Inviolables.
- Any violation is an **"Inviolable breach"** — surface it explicitly in the verdict and treat it as a No-Go signal (Conditional Go only if the user explicitly waives; document the waiver).

If `docs/CONSTITUTION.md` is missing on a Full-Track project, recommend `/constitution` before proceeding (or document an explicit waiver in the gate verdict).

### 2. Delegate to konzeptor Agent

Delegate the gate check to the **konzeptor** agent with a focused prompt:

> Gate P1 check. Preflight report (with summaries):
> [Insert preflight content here]
>
> Mechanical checks are done (file existence, sections, content patterns).
> Evaluate the content:
> 1. **Personas & Journeys**: Specific enough? Pain points genuine? Critical path covered?
> 2. **Feature Prioritisation**: MoSCoW comprehensible? MVP delivers genuine user value?
> 3. **Value Proposition**: Understandable at a glance? Differentiation clear?
> 4. **Business Model**: Canvas complete? Pricing justified?
> 5. **Financial Planning**: Assumptions plausible? Break-even realistic?
> 6. **DSGVO**: Data categories complete? Legal bases named?
> 7. **Assumptions Register**: All Assumptions flagged as such?
>
> If unclear: load the relevant detail file selectively (the phase index already points you there).
> Format: Per point assessment (Met/Partially/Not met) + 1-2 sentences.
>
> Overall recommendation: Go / Conditional Go / No-Go.

### 3. Create Gate Protocol

Create **`docs/concept/GATE_P1.md`** with:
- Result of the mechanical preflight checks (table taken from report)
- Content evaluation by the konzeptor (7 points)
- List of open points with concrete next steps
- Go/Conditional Go/No-Go recommendation

Also update **`docs/concept/CONCEPT.md`** (phase index):
- Set `**Status:** Gate Passed (DD.MM.YYYY)` (or `Conditional Go` / `No-Go`).
- Append the verdict and any Conditional-Go conditions under the **Gate Notes** section.
- Add a row in the detail-file table for `[GATE_P1.md](GATE_P1.md)` with the verdict.

The phase index is the consolidated concept document — no separate "summary CONCEPT.md" needs to be regenerated; the index already aggregates Key Decisions and Open Risks from all five subskills.

---

## Quality Gate 1 – Reference Checklist

The following points are covered by preflight (mechanical) and agent (content):

**Mechanical (Preflight):**
- Phase index `docs/concept/CONCEPT.md` exists with the standard sections (Status, Detail Files)
- All five detail files exist with frontmatter `status: active`: `USER_JOURNEYS.md`, `FEATURES.md` (with MVP Scope Boundary section), `BUSINESS_MODEL.md`, `FINANCIAL_PLAN.md`, `DSGVO_INITIAL_ASSESSMENT.md`
- Content patterns inside the detail files: personas, journeys, MoSCoW, MVP scope, Canvas, pricing, break-even, DSGVO data categories

**Content (Agent):**
- Personas & Journeys: specific, genuine pain points, critical path
- Feature Prioritisation: MoSCoW comprehensible, MVP delivers user value
- Value Proposition: understandable, differentiated
- Business Model: Canvas complete, pricing justified
- Financial Planning: Assumptions plausible, break-even realistic
- DSGVO: data categories complete, legal bases named
- Assumptions flagged as such

---

## Result

- **`docs/concept/GATE_P1.md`** (gate protocol with checklist, evaluation, recommendation)
- **`docs/concept/CONCEPT.md`** (phase index updated: status, gate notes)
- Clear Decision as a prerequisite for starting Phase 2

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Go** | All criteria met | Start with `/p2-assumptions` |
| **Conditional Go** | Minor gaps present | Close gaps, then Go |
| **No-Go** | Significant Concept gaps | Back to Phase 1 |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Write **`docs/concept/GATE_P1.md`** (gate protocol from §3 above)
2. Update **`docs/concept/CONCEPT.md`** phase index with gate result (status + gate notes, per §3 above)
3. **On Go only** — freeze Phase-P1 detail files: `bash ~/.claude/scripts/freeze-phase-docs.sh P1` (skipped on Conditional Go / No-Go)
4. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
5. **Cleanup**: `rm -f docs/.gate-preflight-p1.md` (last operation)

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
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p1.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
