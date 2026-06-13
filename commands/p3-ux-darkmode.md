# /p3-ux-darkmode – Dark Mode Color Strategy

Defines the color strategy for dark mode with semantic colors and toggle mechanism.

## Argument: $ARGUMENTS = [Toggle mechanism, e.g. "System Preference", "Toggle", "both"]

If provided: Use the mechanism as the specification.
If not provided: Recommend the most suitable mechanism.

## Prerequisites
- Wireframes from `/p3-ux-wireframes` available

## Agent
- **Type**: ux-designer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From UX_CONCEPT.md: Wireframes (short list of screens and elements)
- Dark mode requirement and color blindness note

## Prompt Template
> **Goal**: Define dark mode color strategy. Toggle: $ARGUMENTS
>
> **Context**:
> [inline from UX_CONCEPT.md, CLAUDE.md]
>
> **Output Format**:
> 1. Semantic colors: Table | Token | Light | Dark | Usage |
> 2. Critical components: which ones need special dark mode treatment?
> 3. Toggle mechanism: description (1-2 sentences)
>
> **Constraints**:
> - ONLY color strategy and toggle mechanism
> - NO wireframes, NO accessibility analysis
> - Semantic tokens instead of hex values in design
> - Max. 12 color tokens
> - Color-blindness-friendly (blue/orange instead of red/green)

## Orchestrator Checkpoint
- [ ] All wireframe elements covered by tokens?
- [ ] Color blindness requirement considered?

## Write Detail File
Write the result to `docs/architecture/DARKMODE.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: ux-darkmode
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Semantic Colors` (the token/light/dark/usage table), `## Critical Components`, `## Toggle Mechanism`.

## Update Sub-Index
Update `docs/architecture/UX_CONCEPT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[DARKMODE.md](DARKMODE.md)` with status `complete`.
- Lift the toggle decision into **Key Decisions** of the sub-index.
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
