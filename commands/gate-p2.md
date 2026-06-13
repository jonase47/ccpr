# /gate-p2 – Quality Gate 2: Validation → Architecture

Checks whether all critical Assumptions have been validated and a well-founded Go/No-Go/Pivot Decision can be made. This is the most important gate in the model – here it is decided whether to invest in the cost- and time-intensive architecture and implementation phase. No argument – this gate always checks the complete checklist.

## No Argument ($ARGUMENTS not applicable)

Gate commands do not accept arguments. They always check the complete current project status.

## Execution

### 1. Read Preflight Report

Read `docs/.gate-preflight-p2.md` as the primary source of information. This report contains:
- Artefact existence and mandatory sections (mechanically checked)
- Content check (regex-based: risk assessments, validation status, results, PoC)
- Document summaries (via Ollama, if available)

If the preflight report does not exist or is older than 10 minutes, read the validation documents directly instead — **always start with the phase index**:

1. **`docs/validation/VALIDATION.md`** (phase index) — gives you the detail-file table, key decisions, open risks.
2. From the index's detail-file table, load only the detail files you need:
   - **`docs/validation/ASSUMPTIONS.md`** (register with validation status)
   - **`docs/validation/MARKET_VALIDATION.md`**
   - **`docs/validation/POC.md`** (plus `poc/` code directory if relevant)
   - **`docs/validation/REGULATORY_CHECK.md`**
3. P1 reference (only when validation findings impact concept/financials): `docs/concept/CONCEPT.md` (index), then `BUSINESS_MODEL.md` / `FINANCIAL_PLAN.md` / `DSGVO_INITIAL_ASSESSMENT.md` selectively.

### 1a. Constitution Inviolables (mandatory pre-gate)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p2.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for the gate:
- Include the Inviolable bullets verbatim in the agent prompt (Step 2 below).
- The agent must check each evaluated phase-decision against the Inviolables.
- Any violation is an **"Inviolable breach"** — surface it explicitly in the verdict and treat it as a No-Go signal (Conditional Go only if the user explicitly waives; document the waiver).

If `docs/CONSTITUTION.md` is missing on a Full-Track project, recommend `/constitution` before proceeding (or document an explicit waiver in the gate verdict).

### 2. Delegate to konzeptor Agent

Delegate the gate check to the **konzeptor** agent with a focused prompt:

> Gate P2 check. Preflight report (with summaries):
> [Insert preflight content here]
>
> Mechanical checks are done (file existence, sections, content patterns).
> Evaluate the content:
> 1. **Assumptions Register**: Top-3 risks validated or consciously accepted?
> 2. **Technical Feasibility**: PoC successful (if needed)?
> 3. **Regulatory**: Knock-out criteria resolved?
> 4. **Pricing**: Validated through market data/competitors?
> 5. **Financial Plan**: Still viable after validation? Break-even shifted?
> 6. **Concept Update**: Refuted Assumptions incorporated?
> 7. **Go/No-Go/Pivot**: Clear recommendation with rationale?
>
> If unclear: read specific original file directly.
> Format: Per point assessment (Met/Partially/Not met) + 1-2 sentences.
> Overall recommendation: Go / Conditional Go / No-Go / Pivot.

### 3. Create Gate Protocol

Create **`docs/validation/GATE_P2.md`** with:
- Result of the mechanical preflight checks (table taken from report)
- Content evaluation by the konzeptor (7 points)
- Summary of the most important validation results
- Go/No-Go/Pivot Decision with rationale
- For Pivot: first directional recommendation

Also update **`docs/validation/VALIDATION.md`** (phase index):
- Set `**Status:** Gate Passed (DD.MM.YYYY)` (or `Conditional Go` / `Pivot` / `No-Go`).
- Append the verdict, validation summary and any Conditional-Go conditions under the **Gate Notes** section.
- Add a row in the detail-file table for `[GATE_P2.md](GATE_P2.md)` with the verdict.

---

## Quality Gate 2 – Reference Checklist

The following points are covered by preflight (mechanical) and agent (content):

**Mechanical (Preflight):**
- Phase index `docs/validation/VALIDATION.md` exists with the standard sections
- All four detail files exist with frontmatter `status: active`: `ASSUMPTIONS.md`, `MARKET_VALIDATION.md`, `POC.md`, `REGULATORY_CHECK.md`
- Content patterns inside the detail files: risk assessments, validation status, results, PoC reference

**Content (Agent):**
- Assumptions register: Top-3 risks validated or consciously accepted
- Technical Feasibility: PoC successful (if needed)
- Regulatory: knock-out criteria resolved
- Pricing: validated through market data
- Financial plan: still viable after validation
- Concept: refuted Assumptions incorporated
- Go/No-Go/Pivot: clear recommendation

---

## Result

- **`docs/validation/GATE_P2.md`** (gate protocol with checklist, validation summary, Decision)
- **`docs/validation/VALIDATION.md`** (phase index updated: status, gate notes)

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Go** | All critical Assumptions validated, Concept viable | Start with `/p3-architecture` |
| **Conditional Go** | Minor open points, but bridgeable | Resolve open points, then Go |
| **Pivot** | Key Assumptions refuted – realignment needed | Back to `/p1-features` or `/p0-problem` |
| **No-Go** | Knock-out criterion or not economically viable | Stop project |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Write **`docs/validation/GATE_P2.md`** (gate protocol from §3 above)
2. Update **`docs/validation/VALIDATION.md`** phase index with gate result (status + gate notes, per §3 above)
3. **On Go only** — freeze Phase-P2 detail files: `bash ~/.claude/scripts/freeze-phase-docs.sh P2` (skipped on Conditional Go / Pivot / No-Go)
4. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
5. **Cleanup**: `rm -f docs/.gate-preflight-p2.md` (last operation)

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
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p2.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
