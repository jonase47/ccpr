# /p1-features – Feature Definition & MVP Scope Boundary

Defines the feature scope of the project, prioritises using MoSCoW, and clearly defines the MVP scope. The result is FEATURES.md and MVP.md as the binding basis for architecture and planning.

## Argument: $ARGUMENTS = [Feature area]

If provided: Focus the feature definition on a specific area (e.g. "authentication", "booking process", "admin area").
If not provided: Read USER_JOURNEYS.md and DISCOVERY.md and develop the complete feature list for the entire project. If any context is missing, ask for the project scope.

## Execution

### 1. Read Context
Read the following files (if available):
- **DISCOVERY.md** (problem statement, Target Audience, market assessment)
- **USER_JOURNEYS.md** (personas, user journeys – basis for feature derivation)
- **CONCEPT.md** (if already available)

### 2. Delegate to konzeptor Agent (Lead)
Delegate the feature work to the **konzeptor** agent:

> Derive a complete feature catalogue from the user journeys and the problem statement. Context: [Insert DISCOVERY.md and USER_JOURNEYS.md content]. Focus (if provided): **$ARGUMENTS**
>
> Create:
> 1. **Feature Catalogue**: All identified features with a short description (1–2 sentences per feature)
> 2. **MoSCoW Prioritisation**: Assign each feature:
>    - **Must Have**: Without this feature the product is worthless
>    - **Should Have**: Important, but dispensable in the short term
>    - **Could Have**: Nice to have if time permits
>    - **Won't Have (this time)**: Deliberately excluded from the MVP
> 3. **Rationale**: Why is a feature a Must Have? Which user journey does it cover?
> 4. **Dependencies**: Which features build on each other?

### 3. Delegate to ux-designer Agent (Support)
Delegate the MVP scope definition to the **ux-designer** agent:

> Review the konzeptor's feature catalogue from a UX perspective:
> 1. **MVP Scope Recommendation**: What is the minimum that enables a genuine user experience?
> 2. **Missing Features**: What has the konzeptor overlooked that is indispensable for good UX?
> 3. **Out-of-Scope Risks**: Which excluded features could directly frustrate users?

### 3b. Consolidation by Wingman

Start the **wingman** agent with the results from konzeptor and ux-designer:
> Consolidate the feature analysis and MVP scope recommendation.

Use the Wingman summary as the basis for documentation.

### 4. Write Detail File
Write the result to `docs/concept/FEATURES.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P1
subskill: features
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Feature Catalogue` (with MoSCoW prioritisation and rationale per item), `## MVP Scope Boundary` (what is included in the MVP, what is explicitly excluded, value proposition of the MVP).

The legacy `MVP.md` is **not** created — its content lives as the `## MVP Scope Boundary` section inside `FEATURES.md`. Migration of existing projects keeps the old `MVP.md` until manually merged.

### 5. Update Phase Index
Update `docs/concept/CONCEPT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[FEATURES.md](FEATURES.md)` with status `complete`.
- Lift the MVP value proposition into **Key Decisions** (e.g. `- MVP value proposition: <one-liner> → see FEATURES.md`).

## Result

- **`docs/concept/FEATURES.md`** (prioritised feature catalogue with MVP Scope Boundary section)
- **`docs/concept/CONCEPT.md`** (phase index updated)
- Basis for `/p1-business-model`, `/p3-architecture` and `/p4-backlog`

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
