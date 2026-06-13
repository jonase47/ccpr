# /p2-assumptions – Identify & Prioritise Critical Assumptions

Systematically lists all critical Assumptions from the conception phase and prioritises them by risk and validatability. The result is an Assumptions register that serves as the working basis for all further validation steps.

## Argument: $ARGUMENTS = [Focus area, e.g. "market", "technology", "regulatory"]

If provided: Focus the Assumptions register on the specified area.
If not provided: Read all conception documents and create a complete, cross-area Assumptions register. If any context is missing, ask for the project background.

## Execution

### 1. Read Context
Read the following files (if available):
- **CONCEPT.md** (consolidated Concept)
- **FEATURES.md** / **MVP.md**
- **BUSINESS_MODEL.md** / **FINANCIAL_PLAN.md**
- **DSGVO_INITIAL_ASSESSMENT.md**
- **DISCOVERY.md**

### 2. Delegate to konzeptor Agent (Lead)
Delegate the Assumptions analysis to the **konzeptor** agent:

> Read all conception documents and extract all Assumptions from them – everything that was treated as fact but has not yet been proven. Focus (if provided): **$ARGUMENTS**
>
> Create an **Assumptions Register** with the following structure per assumption:
>
> | ID | Assumption | Area | Consequence if wrong | Validatability | Priority |
> |---|---|---|---|---|---|
>
> - **Area**: Market / Technology / Regulatory / User / Finance
> - **Consequence if wrong**: What happens to the project if this assumption is not correct? (Low / High / K.O.)
> - **Validatability**: How difficult is this assumption to validate? (Easy / Medium / Hard)
> - **Priority**: Combination of consequence and validatability → Which Assumptions must be checked first?
>
> Explicitly mark the **Top 3 most critical Assumptions** – these must be validated in Phase 2 without fail.
>
> Also suggest a concrete validation method for each assumption:
> - Desk research / market research
> - Technical Proof of Concept
> - User conversations / interviews
> - Numbers / data / statistics
> - Regulatory inquiry / lawyer

### 3. Delegate to business-analyst Agent (Support)
Delegate the review of financial and market Assumptions to the **business-analyst** agent:

> Supplement the konzeptor's Assumptions register with:
> 1. Missing financial and market Assumptions from FINANCIAL_PLAN.md and BUSINESS_MODEL.md
> 2. Assessment of the financial consequence if the top Assumptions do not hold
> 3. Recommendation: In what order should the Assumptions be validated (quick wins first)?

### 4. Write Detail File
Write the result to `docs/validation/ASSUMPTIONS.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P2
subskill: assumptions
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Assumptions Register` (with risk level + consequence), `## Top-3 Risk Assumptions`, `## Validation Method per Assumption`, `## Recommended Order`.

### 5. Update Phase Index
Update `docs/validation/VALIDATION.md` (create from index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[ASSUMPTIONS.md](ASSUMPTIONS.md)` with status `complete`.
- Lift the Top-3 risk assumptions into **Open Risks / Open Questions** of the index (each one a 1-liner referencing `ASSUMPTIONS.md`).

## Result

- **`docs/validation/ASSUMPTIONS.md`** (complete Assumptions register with prioritisation and validation methods)
- **`docs/validation/VALIDATION.md`** (phase index updated)
- Clear list of Top-3 risk Assumptions as a mandatory task for Phase 2
- Basis for `/p2-market-validation`, `/p2-poc` and `/p2-regulatory-check`

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
