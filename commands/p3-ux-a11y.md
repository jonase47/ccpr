# /p3-ux-a11y – Accessibility Concept

Defines WCAG target, contrast requirements, keyboard navigation, screen reader requirements and testing methods.

## Argument: $ARGUMENTS = [WCAG level, e.g. "AA", "AAA"]

If provided: Use the level as the specification.
If not provided: Recommend the appropriate level with justification.

## Prerequisites
- UX_CONCEPT.md with wireframes and dark mode strategy

## Agent
- **Type**: konzeptor
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From UX_CONCEPT.md: Wireframe elements (short list) and dark mode tokens
- Accessibility requirements (e.g. red-green color blindness)
- From FEATURES.md: Interactive elements (short list)

## Prompt Template
> **Goal**: Create accessibility concept. WCAG target: $ARGUMENTS
>
> **Context**:
> [inline from UX_CONCEPT.md, CLAUDE.md]
>
> **Output Format**:
> 1. WCAG level with justification (1 sentence)
> 2. Color contrasts: minimum ratios text (4.5:1), UI (3:1)
> 3. Keyboard navigation: Table | Flow | Tab Order | Focus Indicator |
> 4. Screen reader: Table | Element | ARIA Label | Role |
> 5. Color blindness: concrete examples where non-color indicators are needed
> 6. Testing methods: list of tools for phase 6
>
> **Constraints**:
> - ONLY accessibility, NO wireframes, NO dark mode (contrast reference only)
> - Max. 5 flows for keyboard navigation
> - Max. 10 ARIA elements
> - Testing methods must name concrete tool names

## Orchestrator Checkpoint
- [ ] WCAG level justified?
- [ ] Color blindness requirement considered?

## Write Detail File
Write the result to `docs/architecture/A11Y.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: ux-a11y
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## WCAG Target` (with justification), `## Color Contrasts`, `## Keyboard Navigation`, `## Screen Reader`, `## Color Blindness`, `## Testing Methods`.

(File replaces the legacy `ACCESSIBILITY.md` name — keep the new `A11Y.md` going forward.)

## Update Sub-Index
Update `docs/architecture/UX_CONCEPT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[A11Y.md](A11Y.md)` with status `complete`.
- Lift the WCAG target into **Key Decisions** of the sub-index (e.g. `- WCAG AA + colour-blind-safe palette → see A11Y.md`).
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
