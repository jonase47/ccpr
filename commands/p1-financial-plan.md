# /p1-financial-plan – Cost Structure, Revenue Forecast & Break-Even

Creates a first financial plan with Cost Structure, Revenue Forecast, and break-even analysis. The goal is not exact bookkeeping but a plausible set of numbers that demonstrates the economic viability of the venture.

## Argument: $ARGUMENTS = [Planning horizon, e.g. "3 years", "18 months"]

If provided: Create the financial plan for the specified period.
If not provided: Ask for the desired planning horizon. The default would be 3 years – confirm this suggestion or allow it to be adjusted.

## Execution

### 1. Read Context
Read the following files (if available):
- **DISCOVERY.md** (market assessment, willingness to pay)
- **BUSINESS_MODEL.md** (revenue streams, pricing, Cost Structure from Canvas)
- **MVP.md** (scope – influences development costs)
- **FEATURES.md** (scope – influences Operating Costs)

### 2. Delegate to business-analyst Agent (Lead)
Delegate the entire financial planning to the **business-analyst** agent:

> Create a financial plan for the horizon: **$ARGUMENTS**
> Context from BUSINESS_MODEL.md: [Insert revenue streams, pricing, Cost Structure]
>
> The financial plan must include:
>
> **A. Cost Structure (one-time & ongoing)**
> - Development costs (person-months × day rate or hourly rate)
> - Infrastructure/hosting per month (minimum, growth)
> - Tools, licences, software
> - Marketing/sales
> - Overhead (accounting, legal, etc.)
>
> **B. Revenue Forecast (3 scenarios)**
> - 🐻 Bear Case: What if things go worse than expected?
> - 📊 Base Case: Realistic expectation
> - 🚀 Bull Case: What if things go significantly better?
> - For each scenario: number of customers/users per month + revenue
>
> **C. Break-Even Analysis**
> - When is the monthly break-even reached (Base Case)?
> - How many paying customers/users are needed for this?
>
> **D. Capital Requirements**
> - How much capital is needed until break-even?
> - Recommendation: self-financing / debt / funding?
>
> Use plausible Assumptions and explicitly flag them as Assumptions. Use simple tables.

### 3. Write Detail File
Write the result to `docs/concept/FINANCIAL_PLAN.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P1
subskill: financial-plan
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Cost Structure`, `## Revenue Forecast` (3 scenarios), `## Break-Even`, `## Capital Requirements`, `## Assumptions Register` (every assumption explicitly listed as such).

### 4. Update Phase Index
Update `docs/concept/CONCEPT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[FINANCIAL_PLAN.md](FINANCIAL_PLAN.md)` with status `complete`.
- Lift the break-even point and capital requirements into **Key Decisions**.
- Add critical financing assumptions under **Open Risks / Open Questions** for `/p2-market-validation` to test.

## Result

- **`docs/concept/FINANCIAL_PLAN.md`** (Cost Structure, Revenue Forecast 3 scenarios, break-even, capital requirements)
- **`docs/concept/CONCEPT.md`** (phase index updated)
- All Assumptions explicitly marked as such
- Basis for Gate 1 and later validation in `/p2-market-validation`

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
