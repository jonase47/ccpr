# /p2-market-validation – Validate Market, Pricing & Demand Assumptions

Checks critical market, pricing, and demand Assumptions from the Assumptions register using concrete research, data, and competitive analyses. The result is confirmed or refuted Assumptions as the basis for informed Concept decisions.

## Argument: $ARGUMENTS = [Specific assumption or assumption ID from ASSUMPTIONS.md]

If provided: Validate the named assumption or assumption ID specifically (e.g. "A-03", "B2B willingness to pay").
If not provided: Read ASSUMPTIONS.md and validate the highest-priority market and financial Assumptions. If ASSUMPTIONS.md is missing in an autonomous pipeline run, infer the top-3 market/financial assumptions from CONCEPT.md / FEATURES.md, log this fallback in HANDOVER.md ("validated without ASSUMPTIONS.md, basis = MVP scope"), and continue. Only halt and recommend running `/p2-assumptions` first when running interactively.

## Execution

### 1. Read Context
Read the following files (if available):
- **ASSUMPTIONS.md** (Assumptions register – which Assumptions should be validated?)
- **DISCOVERY.md** (market assessment from Phase 0 as starting point)
- **BUSINESS_MODEL.md** / **FINANCIAL_PLAN.md** (pricing Assumptions)

### 2. Delegate to business-analyst Agent (Lead)
Delegate the market validation to the **business-analyst** agent:

> Validate the following assumption(s): **$ARGUMENTS**
> Context from ASSUMPTIONS.md and DISCOVERY.md: [Insert relevant Assumptions and market context]
>
> For each assumption to be validated, conduct:
>
> **A. Demand Validation**
> - Are there measurable demand signals? (search volume, forums, communities, waitlists)
> - Are comparable products/services successful in the market?
> - Back up with concrete data sources or examples
>
> **B. Pricing Validation**
> - What do customers pay for comparable solutions? (competitor pricing research)
> - Is there public data on willingness to pay in this segment?
> - Is the own pricing approach from BUSINESS_MODEL.md in line with the market?
>
> **C. Competitive Validation**
> - Have competitors changed since DISCOVERY.md?
> - Are there new market participants or product changes?
> - Differentiation potential still valid?
>
> **D. Result per Assumption**
> - ✅ Confirmed: Assumption holds, evidence available
> - ⚠️ Partially confirmed: Assumption must be adjusted
> - ❌ Refuted: Assumption is wrong – consequence for the Concept?
> - ❓ Not validatable with available means: What approach is recommended?

### 3. Delegate to konzeptor Agent (Support)
Delegate the impact on the Concept to the **konzeptor** agent:

> Evaluate the business analyst's validation results:
> 1. Which Concept decisions must be adjusted?
> 2. Does the MVP scope need to change?
> 3. Does the financial plan need to be revised?
> 4. Recommendation: Continue / Pivot / Adjust Concept?

### 4. Write Detail File
Write the result to `docs/validation/MARKET_VALIDATION.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P2
subskill: market-validation
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Validation Method`, `## Findings`, `## Impact on Concept`, `## Impact on Financial Plan`, `## Recommendation` (Continue / Pivot / Adjust).

Cross-file updates:
- Update `docs/validation/ASSUMPTIONS.md`: refresh validation status per affected assumption (do not rewrite the file, just update status fields and bump `last_updated`).
- If concept or financial plan need adjustment: update `docs/concept/BUSINESS_MODEL.md` or `docs/concept/FINANCIAL_PLAN.md` and bump their `last_updated`.

### 5. Update Phase Index
Update `docs/validation/VALIDATION.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[MARKET_VALIDATION.md](MARKET_VALIDATION.md)` with status `complete`.
- Lift the recommendation (Continue / Pivot / Adjust) into **Key Decisions** with 1-line rationale.
- Reduce the corresponding `ASSUMPTIONS.md` rows in **Open Risks** when the assumption is validated or disproved.

## Result

- **`docs/validation/MARKET_VALIDATION.md`** (validation method, findings, recommendation)
- Updated **`docs/validation/ASSUMPTIONS.md`** (status per assumption)
- Possibly updated **`docs/concept/BUSINESS_MODEL.md`** or **`docs/concept/FINANCIAL_PLAN.md`**
- **`docs/validation/VALIDATION.md`** (phase index updated)
- Basis for `/gate-p2`

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
