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
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
