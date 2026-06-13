# /p0-market – Market Assessment & Competition Overview

Delivers a first market assessment: Is there demand? Who are the competitors? Is the idea roughly viable economically? The result is an overview needed for the Go/No-Go Decision at Gate 0.

## Argument: $ARGUMENTS = [Industry / market segment]

If provided: Use as the focus for the market research (e.g. "E-Health", "B2B-SaaS", "local trades").
If not provided: Read DISCOVERY.md (problem statement and Target Audience) and derive the industry from it. If DISCOVERY.md is also missing, ask for the market segment.

## Execution

### 1. Read Context
Read `docs/discovery/DISCOVERY.md` (phase index) and `docs/discovery/PROBLEM.md` (detail file from `/p0-problem`) to understand the problem statement and Target Audience. This information is essential for a meaningful market assessment.

### 2. Delegate to konzeptor Agent (Lead)
Delegate the structuring and evaluation to the **konzeptor** agent:

> Create a first market assessment for the segment: **$ARGUMENTS**
> Context from PROBLEM.md: [Insert problem statement, Target Audience]
>
> Work out:
> 1. **Market Size** (Rough estimate: How many potential customers/users are there?)
> 2. **Demand Indicators** (Are there signs of genuine need? Search volume, forums, existing solutions?)
> 3. **Competition Overview** (3–5 direct or indirect competitors with a brief assessment)
> 4. **Differentiation Potential** (Where could a new solution do better?)
> 5. **First Economic Assessment** (Is there a business here? Rough willingness to pay?)

### 3. Delegate to business-analyst Agent (Support)
Delegate the economic assessment in parallel or afterwards to the **business-analyst** agent:

> Supplement the konzeptor's market assessment with:
> 1. Rough market size in euros (TAM/SAM if possible, otherwise qualitative estimate)
> 2. Typical willingness to pay in this segment
> 3. First assessment: Is this economically worthwhile – why yes/no?

### 4. Write Detail File
Write the result to `docs/discovery/MARKET.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P0
subskill: market
status: active   # skeleton | draft | active | frozen | archived | living
last_updated: <DD.MM.YYYY>
---
```

Below the frontmatter, structure the body with the headings: `## Market Size`, `## Demand Indicators`, `## Competition Overview`, `## Differentiation Potential`, `## Economic Assessment`.

### 5. Update Phase Index
Update `docs/discovery/DISCOVERY.md` (create from the index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In the **Detail Files** table: ensure a row for `[MARKET.md](MARKET.md)` with status `complete`.
- Lift a 1-line summary into **Key Decisions** (e.g. `- Market: ~<TAM>, top competitors <X, Y> → see MARKET.md`).
- If the economic assessment is critical/marginal, add a 1-liner under **Open Risks / Open Questions** referencing `MARKET.md`.

## Result

- **`docs/discovery/MARKET.md`** (detail file with frontmatter and structured body)
- **`docs/discovery/DISCOVERY.md`** (phase index updated)
- Basis for the Go/No-Go discussion in `/gate-p0`

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
