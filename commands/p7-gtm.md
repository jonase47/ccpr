# /p7-gtm – Launch Go-to-Market & Set Up KPI Tracking

Launches the go-to-market activities and sets up KPI tracking. The result is active marketing measures and a working tracking setup that delivers meaningful data from day one.

## Argument: $ARGUMENTS = [Channel/measure, e.g. "Email Launch", "Social Media", "PR", "all channels"]

If provided: Focus the GTM activities on the specified channel or measure.
If not provided: Read BUSINESS_MODEL.md and FINANCIAL_PLAN.md and plan all defined go-to-market channels. If any context is missing, ask about the GTM strategy.

## Execution

### 1. Read Context
Read the following files (if available):
- **BUSINESS_MODEL.md** (channels, customer segments, value proposition)
- **FINANCIAL_PLAN.md** (KPI targets, break-even plans, budget)
- **USER_JOURNEYS.md** (target audiences for communication)
- **RELEASE_NOTES.md** (launch content foundation)
- **USER_GUIDE.md** (onboarding material for first users)

### 2. Delegation to Business Analyst Agent (Lead)
Delegate GTM coordination to the **business-analyst** agent:

> Coordinate the go-to-market launch. Channel/measure (if specified): **$ARGUMENTS**
> Context from BUSINESS_MODEL.md and FINANCIAL_PLAN.md: [Apply channels, target audience, KPI targets]
>
> **A. Set Up KPI Tracking**
> Define and set up the most important KPIs:
> - **Acquisition KPIs**: New users/customers per week, conversion rate (visitor → registration → paying customer)
> - **Activation KPIs**: What percentage of new users reach the "aha moment"?
> - **Retention KPIs**: Weekly / monthly active users (WAU/MAU), churn rate
> - **Revenue KPIs**: MRR (Monthly Recurring Revenue), ARPU (Average Revenue Per User)
> - **Business KPIs**: Progress towards break-even (current MRR vs. break-even MRR)
>
> For each KPI: definition, measurement method, target value (from FINANCIAL_PLAN.md), measurement frequency
>
> **B. Analytics Setup**
> - Web analytics set up (e.g. Plausible, Matomo, Google Analytics – privacy-compliant!)
> - Conversion funnels configured (visitor → registration → activation → payment)
> - Important events tracked (sign-up, feature usage, upgrade, churn)
> - UTM parameter strategy defined for campaigns
>
> **C. Launch Go-to-Market Measures**
> Launch the defined measures for: **$ARGUMENTS**
>
> Depending on channel:
> - **Email**: Launch email to waitlist / existing contacts (create draft)
> - **Social Media**: Launch posts for relevant platforms (create drafts)
> - **PR/Content**: Launch press release or blog post (create draft)
> - **Community**: Announcement in relevant communities (Reddit, Slack groups, forums)
> - **Direct sales**: List of first target customers, outreach drafts
>
> For each channel: create launch content draft based on value proposition from BUSINESS_MODEL.md.
>
> **D. Go Live with Pricing**
> - Is the pricing from BUSINESS_MODEL.md correctly implemented in the application and on the website?
> - Are payment processes fully tested (test payments in staging)?
> - Are invoices / receipts correctly configured?

### 3. Delegation to Konzeptor Agent (Support)
Delegate content quality review to the **konzeptor** agent:

> Review the GTM measures from the business analyst from a product and communication perspective:
> 1. Does the launch content communicate the value proposition clearly and convincingly?
> 2. Does the tone fit the product and target audience?
> 3. Are there important communication points that were missed?

### 4. Write Detail File
Write the result to `docs/launch/GTM.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P7
subskill: gtm
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## KPI Dashboard` (which KPIs are tracked where), `## KPI Targets 30/60/90 Days`, `## Launch Measures` (links / drafts), `## Launch Content per Channel`.

(File replaces the legacy `GTM_LAUNCH.md` name — keep `GTM.md` going forward.)

### 5. Update Phase Index
Update `docs/launch/LAUNCH.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[GTM.md](GTM.md)` with status `complete`.
- Lift the headline KPI targets (30/60/90 days) into **Key Decisions** (e.g. `- 30-day target: 100 active users → see GTM.md`).

## Result

- **`docs/launch/GTM.md`** (KPIs, tracking setup, launch measures)
- **`docs/launch/LAUNCH.md`** (phase index updated)
- Active KPI tracking in production
- Launch content drafts per channel (ready for publication)
- Foundation for `/gate-p7` and `/p8-business`

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
