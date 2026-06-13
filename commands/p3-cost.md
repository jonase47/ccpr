# /p3-cost – Operating Costs of the Architecture

Estimates the ongoing Operating Costs of the chosen architecture for various usage scenarios. The goal is realistic cost planning that feeds back into the financial plan – no surprises after launch.

## Argument: $ARGUMENTS = [Scenario, e.g. "100 users", "10k users", "100k requests/day"]

If provided: Calculate the Operating Costs for the named scenario. Multiple scenarios can be provided as a comma-separated list (e.g. "100 users, 1k users, 10k users").
If not provided: Read ARCHITECTURE.md, INFRASTRUCTURE.md and FINANCIAL_PLAN.md and select sensible scenarios based on growth projections. If any context is missing, ask for the expected user numbers.

## Execution

### 1. Read Context
Read the following files (if available):
- **ARCHITECTURE.md** (system components – what runs where?)
- **INFRASTRUCTURE.md** (hosting decisions, concrete services)
- **TECH_STACK.md** (technologies and external services with cost implications)
- **FINANCIAL_PLAN.md** (previous infrastructure cost estimates for comparison)

### 2. Delegation to Business Analyst Agent (Lead)
Delegate the cost calculation to the **business-analyst** agent:

> Calculate the monthly Operating Costs for the following scenarios: **$ARGUMENTS**
> Context from ARCHITECTURE.md and INFRASTRUCTURE.md: [insert components, services, hosting decisions]
>
> **A. Cost Categories (per scenario)**
> Calculate monthly costs for each category:
>
> | Category | Service/Component | Cost/Month (Scenario 1) | Cost/Month (Scenario 2) | ... |
> |---|---|---|---|---|
> | Server / Compute | (e.g. Hetzner CX21) | X€ | X€ | |
> | Database | (e.g. managed PostgreSQL) | X€ | X€ | |
> | Object Storage | (e.g. S3, Hetzner Object Storage) | X€ | X€ | |
> | CDN / Bandwidth | | X€ | X€ | |
> | Email Delivery | (e.g. Postmark, SendGrid) | X€ | X€ | |
> | Monitoring / Logging | (e.g. Sentry, Grafana Cloud) | X€ | X€ | |
> | Auth Service | (if external, e.g. Auth0) | X€ | X€ | |
> | Other External APIs | | X€ | X€ | |
> | **Total** | | **X€** | **X€** | |
>
> **B. Scaling Behavior**
> - How do costs develop between scenarios?
> - Are there cost tiers (e.g. tier upgrades at external services)?
> - At what user count does an architecture change become economically sensible?
>
> **C. Cost Optimization Potential**
> - Which cost items are largest and could be reduced?
> - Are there cheaper alternatives to individual services?
> - Reserved instances / annual subscriptions: where does early commitment pay off?
>
> **D. Comparison with Financial Plan**
> - Do the calculated costs deviate from FINANCIAL_PLAN.md?
> - If yes: how does the financial plan need to be adjusted?

### 3. Delegation to System Architect Agent (Support)
Delegate the technical plausibility check to the **system-architekt** agent:

> Check the business analyst's cost estimate for technical plausibility:
> 1. Are the assumed resources (CPU, RAM, storage) realistic for the named user numbers?
> 2. Are there cost items missing that will arise with the chosen architecture?
> 3. Are there architecture adjustments that would significantly reduce costs?

### 4. Write Detail File
Write the result to `docs/architecture/COST_ESTIMATION.md` (overwrite if it exists). Start with:

```yaml
---
phase: P3
subskill: cost
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Cost Table per Scenario`, `## Scaling Behavior`, `## Cost Optimization Potential`, `## Comparison with Financial Plan`.

Update **`docs/concept/FINANCIAL_PLAN.md`** (P1 detail file) with the corrected infrastructure costs if deviations exist — this is a cross-phase update; refresh the `last_updated` frontmatter there too and note the change in `docs/concept/CONCEPT.md` index.

### 5. Update Phase Index
Update `docs/architecture/ARCHITECTURE.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[COST_ESTIMATION.md](COST_ESTIMATION.md)` with status `complete`.
- Lift the headline cost figure into **Key Decisions** (e.g. `- Operating cost ~30 €/month at 1k users → see COST_ESTIMATION.md`).
- If costs deviate substantially from FINANCIAL_PLAN.md, add a 1-liner under **Open Risks** flagging the gap.

## Result

- **`docs/architecture/COST_ESTIMATION.md`** (Operating Costs per scenario, scaling behavior, optimizations)
- Updated **`docs/concept/FINANCIAL_PLAN.md`** if applicable (cross-phase touch)
- **`docs/architecture/ARCHITECTURE.md`** (phase index updated)
- Complete foundation for `/gate-p3`

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for permitted transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
