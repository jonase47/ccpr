# /p6-a11y-keyboard – Keyboard Navigation & Focus

Checks full keyboard operability: tab order, focus indicator, Enter/Space, Escape, focus trap.

## Argument: $ARGUMENTS = [page/component]

If provided: Check the specified page/component.
If not provided: Check all interactive areas.

## Prerequisites
- UI implemented with interactive elements

## Agent
- **Type**: ux-designer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- From src/: HTML structure (interactive elements, tabindex, event handlers)
- From ACCESSIBILITY.md: Keyboard requirements

## Prompt Template
> **Goal**: Check keyboard navigation for: [page/component]
>
> **HTML Structure**:
> [inline from src/]
>
> **Output Format**:
> Checklist:
> | # | Check Point | Status | Finding |
> |---|---|---|---|
> | 1 | All elements reachable via Tab | OK/FINDING | ... |
> | 2 | Tab order is logical | OK/FINDING | ... |
> | 3 | Focus indicator visible | OK/FINDING | ... |
> | 4 | Enter/Space activates elements | OK/FINDING | ... |
> | 5 | Escape closes overlays | OK/FINDING | ... |
> | 6 | Focus trap in modals | OK/FINDING | ... |
> | 7 | Touch targets >= 44x44px | OK/FINDING | ... |
>
> **Constraints**:
> - Keyboard navigation ONLY – no colours, no screen reader
> - Focus on interactive elements (buttons, links, inputs, modals)

## Orchestrator Checkpoint
- [ ] All interactive elements checked?
- [ ] Focus management for dynamic content tested?

## Write Detail File
Write the result to `docs/quality/a11y_keyboard.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P6
subskill: a11y-keyboard
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope` (which pages/components were checked), `## Findings` (the checklist table), `## Severity Summary` (counts of OK / minor / major findings).

## Update Sub-Index
Update `docs/quality/A11Y.md` (the accessibility sub-index, created by `/p6-a11y` if missing):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[a11y_keyboard.md](a11y_keyboard.md)` with status `complete` (or `needs-rework` if blocking findings exist).
- Lift any blocking finding into **Open Risks / Open Questions** of the sub-index.
- Do not edit the phase-level `QA.md` directly — `/p6-a11y` rolls the sub-index up.

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
