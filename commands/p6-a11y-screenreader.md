# /p6-a11y-screenreader – ARIA, Semantics & Alt Texts

Checks screen reader compatibility: semantic HTML, ARIA attributes, alt texts, live regions.

## Argument: $ARGUMENTS = [page/component]

If provided: Check the specified page/component.
If not provided: Check all screens.

## Prerequisites
- UI implemented

## Agent
- **Type**: ux-designer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- From src/: HTML structure (semantics, ARIA attributes, images, forms)
- From ACCESSIBILITY.md: Screen reader requirements

## Prompt Template
> **Goal**: Check screen reader compatibility for: [page/component]
>
> **HTML Structure**:
> [inline from src/]
>
> **Output Format**:
> Checklist:
> | # | Check Point | Status | Finding |
> |---|---|---|---|
> | 1 | Images have alt texts (or aria-hidden) | OK/FINDING | ... |
> | 2 | Form inputs have labels | OK/FINDING | ... |
> | 3 | Interactive elements: role/aria-label | OK/FINDING | ... |
> | 4 | Status changes via aria-live | OK/FINDING | ... |
> | 5 | Icons without text have aria-label | OK/FINDING | ... |
> | 6 | Semantic HTML (header, nav, main) | OK/FINDING | ... |
> | 7 | Heading hierarchy correct | OK/FINDING | ... |
>
> **Constraints**:
> - Screen reader compatibility ONLY – no colours, no keyboard
> - Focus on semantic correctness and ARIA completeness

## Orchestrator Checkpoint
- [ ] All images, forms, buttons checked?
- [ ] aria-live present for dynamic content?

## Write Detail File
Write the result to `docs/quality/a11y_screenreader.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P6
subskill: a11y-screenreader
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Findings` (ARIA + semantics checklist), `## Severity Summary`.

## Update Sub-Index
Update `docs/quality/A11Y.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[a11y_screenreader.md](a11y_screenreader.md)` with status `complete` (or `needs-rework`).
- Lift any blocking screen-reader finding into **Open Risks** of the sub-index.
- Do not edit `QA.md` directly.

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
