# /p6-a11y-visual – Contrast, Colours & Dark Mode

Checks colour contrast (WCAG AA), colour-independence of information presentation, and dark mode conformance.

## Argument: $ARGUMENTS = [page/component]

If provided: Check the specified page/component.
If not provided: Check all critical screens.

## Prerequisites
- UI implemented
- ACCESSIBILITY.md with WCAG target present

## Agent
- **Type**: ux-designer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- From src/: CSS/styles (colour definitions, dark mode variables)
- From ACCESSIBILITY.md: WCAG target and colour requirements
- From UX_CONCEPT.md: Colour palette, dark mode concept

## Prompt Template
> **Goal**: Check visual accessibility for: [page/component]
>
> **Styles/Colours**:
> [inline from CSS]
>
> **WCAG Requirements**:
> [inline from ACCESSIBILITY.md]
>
> **Output Format**:
> Contrast table:
> | # | Element | Foreground | Background | Ratio | WCAG | Status |
> |---|---|---|---|---|---|---|
>
> Colour independence:
> | # | Element | Colour-only info? | Alternative present? | Status |
> |---|---|---|---|---|
>
> Dark mode checks:
> | # | Element | Light OK? | Dark OK? | Finding |
> |---|---|---|---|---|
>
> **Constraints**:
> - Visual check ONLY – no keyboard, no screen reader
> - WCAG 2.1 AA: text >= 4.5:1, large text >= 3:1, UI elements >= 3:1
> - Account for red-green colour blindness (blue/orange instead of red/green)

## Orchestrator Checkpoint
- [ ] All colour combinations checked (light + dark)?
- [ ] Red-green colour blindness accounted for?
- [ ] Contrast ratios correctly calculated?

## Write Detail File
Write the result to `docs/quality/a11y_visual.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P6
subskill: a11y-visual
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Contrast Checks` (the contrast-ratio table), `## Colour Independence`, `## Dark Mode Checks`, `## Severity Summary`.

## Update Sub-Index
Update `docs/quality/A11Y.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[a11y_visual.md](a11y_visual.md)` with status `complete` (or `needs-rework`).
- Lift any contrast or colour-blindness blocker into **Open Risks** of the sub-index.
- Do not edit `QA.md` directly.

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
