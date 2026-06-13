# /p1-business-model – Business Model Canvas & Value Proposition

Develops the Business Model with Business Model Canvas, sharpens the value proposition, and defines a first pricing approach. The result is BUSINESS_MODEL.md as the economic foundation of the project.

## Argument: $ARGUMENTS = [Business Model type, e.g. "SaaS", "service", "marketplace"]

If provided: Focus the development on the specified Business Model type and its typical mechanics.
If not provided: Read DISCOVERY.md, FEATURES.md and MVP.md and derive the most sensible Business Model type. If any context is missing, ask for the desired model.

## Execution

### 1. Read Context
Read the following files (if available):
- **DISCOVERY.md** (problem statement, Target Audience, market assessment incl. willingness to pay)
- **FEATURES.md** / **MVP.md** (What is being built?)
- **USER_JOURNEYS.md** (Who are the users?)

### 2. Delegate to konzeptor Agent (Lead)
Delegate the conceptual development to the **konzeptor** agent:

> Develop the Business Model for this project. Business Model type (if provided): **$ARGUMENTS**
> Context: [Insert problem statement, Target Audience, MVP scope]
>
> Create a complete **Business Model Canvas** with all 9 building blocks:
> 1. **Customer Segments**: Who are our most important customers?
> 2. **Value Propositions**: What value do we create for each segment?
> 3. **Channels**: How do we reach customers and deliver the value?
> 4. **Customer Relationships**: What relationships do we have with customers?
> 5. **Revenue Streams**: What do customers pay for? How much?
> 6. **Key Resources**: What do we need to operate the model?
> 7. **Key Activities**: What must we do?
> 8. **Key Partnerships**: Who do we depend on?
> 9. **Cost Structure**: What are the biggest cost drivers?
>
> Also add:
> - **Value Proposition Statement** (1 concise sentence: For [Target Audience] who have [problem], [product] offers [solution], unlike [alternative])
> - **Pricing Approach**: Concrete recommendation with rationale (e.g. freemium from X€/month, one-time payment Y€, etc.)

### 3. Delegate to business-analyst Agent (Support)
Delegate the economic plausibility check to the **business-analyst** agent:

> Check the konzeptor's Business Model Canvas for economic plausibility:
> 1. **Weaknesses**: Which building blocks are unrealistic or not thought through?
> 2. **Pricing Validation**: Is the proposed price in line with the market? Compare with competitors from DISCOVERY.md.
> 3. **Unit Economics**: Are there early indications of positive unit economics (Customer Lifetime Value > Customer Acquisition Cost)?
> 4. **Recommendation**: What should be adjusted in the model?

### 4. Write Detail File
Write the result to `docs/concept/BUSINESS_MODEL.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P1
subskill: business-model
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Business Model Canvas` (the 9 fields), `## Value Proposition`, `## Pricing Approach`, `## Unit Economics Outlook`.

### 5. Update Phase Index
Update `docs/concept/CONCEPT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[BUSINESS_MODEL.md](BUSINESS_MODEL.md)` with status `complete`.
- Lift the value proposition + pricing approach into **Key Decisions**.

## Result

- **`docs/concept/BUSINESS_MODEL.md`** (Business Model Canvas, value proposition, pricing approach)
- **`docs/concept/CONCEPT.md`** (phase index updated)
- Basis for `/p1-financial-plan` and Gate 1

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
