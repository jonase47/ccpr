# /p8-business – Evaluate KPIs & Optimise Business Model

Evaluates the KPIs from ongoing operations, compares them with the plans from FINANCIAL_PLAN.md, and derives optimisation measures for the business model. Called regularly (recommended: monthly) or on an ad-hoc basis.

## Argument: $ARGUMENTS = [KPI/metric or period, e.g. "MRR", "Churn", "last month", "Q1"]

If provided: Focus the evaluation on the specified metric or period.
If not provided: Read GTM_LAUNCH.md and FINANCIAL_PLAN.md and perform a complete KPI evaluation for the current month. If any context is missing, ask about the evaluation period.

## Execution

### 1. Read Context
Read the following files (if available):
- **GTM_LAUNCH.md** (defined KPIs and target values for 30/60/90 days)
- **FINANCIAL_PLAN.md** (revenue forecast and break-even as comparison basis)
- **BUSINESS_MODEL.md** (business model – which levers can be optimised?)
- Previous KPI reports (if available, for trend analysis)

### 2. Delegation to Business Analyst Agent (Lead)
Delegate KPI evaluation to the **business-analyst** agent:

> Evaluate the KPIs for: **$ARGUMENTS**
> Target values from GTM_LAUNCH.md: [Apply KPI targets]
> Financial plan from FINANCIAL_PLAN.md: [Apply revenue forecast, break-even]
>
> **A. KPI Evaluation**
> Create a clear KPI table:
>
> | KPI | Target | Actual | Deviation | Trend |
> |---|---|---|---|---|
> | MRR | X€ | Y€ | +/- Z% | ↑/↓/→ |
> | New users (month) | X | Y | | |
> | Conversion rate | X% | Y% | | |
> | Churn rate | X% | Y% | | |
> | Break-even progress | X% | Y% | | |
>
> **B. Root Cause Analysis for Deviations**
> For every significant negative deviation (> 20% below target):
> - What are the probable causes?
> - Is the deviation structural (the model is wrong) or temporary (seasonal effect, one-off event)?
> - What data would be needed to confirm the cause?
>
> **C. Business Model Optimisation**
> Evaluate current optimisation levers:
> - **Pricing**: Are adjustments upward or downward warranted? Are there indications of price sensitivity?
> - **Acquisition channels**: Which channel delivers the best results (CAC vs. LTV)?
> - **Retention**: Where are we losing users? Are there patterns in churn?
> - **Upsell/Expansion**: Is there growth potential with existing customers?
> - **Operating Costs**: Are there cost positions that have grown disproportionately?
>
> **D. Financial Plan Update**
> - Does FINANCIAL_PLAN.md need to be adjusted based on actual numbers?
> - Has the projected break-even shifted?
> - How much capital runway remains?
>
> **E. Recommendations**
> - Top 3 measures for the next month (concrete, prioritised, with expected impact)
> - Recommendation for the evolution loop: back to P1 (new features), P3 (architecture), or P5 (improvements)?

### 3. Delegation to Konzeptor Agent (Support)
Delegate product implications to the **konzeptor** agent:

> Evaluate the KPI analysis and business recommendations from the business analyst from a product perspective:
> 1. Which user feedback signals explain the KPI trends?
> 2. Which feature adjustments or new features would have the greatest impact on the KPIs?
> 3. Recommendation for the evolution loop: what should be prioritised next?

### 4. Write Detail File
This subskill maintains a **living** detail file `docs/operations/BUSINESS.md`. It is overwritten on each call with the latest KPI snapshot — historical reports can optionally be archived as `docs/operations/snapshots/KPI_REPORT_<Month-Quarter>.md` if you want to keep history (the index never tracks individual snapshots, only the latest summary).

Write `docs/operations/BUSINESS.md` (overwrite). Frontmatter:

```yaml
---
phase: P8
subskill: business
status: living
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Reporting Period`, `## KPI Table` (actual vs. target with trends), `## Root Cause Analysis`, `## Top-3 Optimisation Recommendations`, `## Updated Break-Even Outlook`.

Cross-file update: refresh `docs/concept/FINANCIAL_PLAN.md` (P1 detail file) with the corrected actual numbers if a meaningful deviation exists, and bump its `last_updated`.

### 5. Update Phase Index
Update `docs/operations/OPS.md` (create from index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[BUSINESS.md](BUSINESS.md)` with status `living`.
- Lift the headline KPI verdict (on track / off track) into **Key Decisions**.
- Add the most significant negative deviation under **Open Risks / Open Questions**.

## Result

- **`docs/operations/BUSINESS.md`** (latest KPI report with recommendations)
- Updated **`docs/concept/FINANCIAL_PLAN.md`** if applicable
- **`docs/operations/OPS.md`** (phase index updated)
- Prioritised optimisation measures as input for `/p8-iteration`

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open items
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
