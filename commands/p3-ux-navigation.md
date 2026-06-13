# /p3-ux-navigation – Sitemap & Information Architecture

Creates the navigation structure, sitemap and identifies critical flows.

## Argument: $ARGUMENTS = [Focus, e.g. "Onboarding", "Dashboard", "Mobile"]

If provided: Focus the navigation analysis on the named area.
If not provided: Create complete sitemap for the MVP scope.

## Prerequisites
- USER_JOURNEYS.md and FEATURES.md exist

## Agent
- **Type**: ux-designer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From USER_JOURNEYS.md: Personas and journeys (short version)
- From FEATURES.md: Must-Have features with screens
- From ARCHITECTURE.md: Technical constraints for navigation (if relevant)

## Prompt Template
> **Goal**: Create sitemap and navigation structure. Focus: $ARGUMENTS
>
> **Context**:
> [inline from USER_JOURNEYS.md, FEATURES.md]
>
> **Output Format**:
> 1. Sitemap as ASCII tree (hierarchy of screens)
> 2. Navigation pattern: Tab Bar / Sidebar / Breadcrumb – with justification
> 3. Critical flows: Table | Flow | Steps | Friction Points |
>
> **Constraints**:
> - ONLY navigation and information architecture
> - NO wireframes, NO dark mode, NO accessibility
> - Max. 15 screens in the sitemap
> - Max. 5 critical flows

## Orchestrator Checkpoint
- [ ] All must-have features have at least one screen?
- [ ] Critical flows cover the most important user journeys?

## Write Detail File
Write the result to `docs/architecture/NAVIGATION.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: ux-navigation
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Sitemap` (ASCII tree), `## Navigation Pattern` (with justification), `## Critical Flows` (the table flow / steps / friction points).

## Update Sub-Index
Update `docs/architecture/UX_CONCEPT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[NAVIGATION.md](NAVIGATION.md)` with status `complete`.
- Lift the navigation pattern decision into **Key Decisions** of the sub-index (e.g. `- Bottom tab bar with 4 tabs → see NAVIGATION.md`).
- Do not edit `ARCHITECTURE.md` directly.

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
