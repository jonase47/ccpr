# /p3-ux-wireframes – Wireframes for Key Screens

Creates wireframes (ASCII art) for the most important screens with interaction descriptions.

## Argument: $ARGUMENTS = [Screen name, e.g. "Start Page", "Core Screen", "Error State"]

If provided: Create wireframe for the named screen.
If not provided: Create wireframes for all key screens.

## Prerequisites
- Sitemap from `/p3-ux-navigation` available

## Agent
- **Type**: ux-designer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From UX_CONCEPT.md: Sitemap and critical flows
- From FEATURES.md: Feature details for the affected screens
- From USER_JOURNEYS.md: Relevant persona and journey

## Prompt Template
> **Goal**: Create wireframes for: $ARGUMENTS
>
> **Context**:
> [inline from UX_CONCEPT.md, FEATURES.md]
>
> **Output Format**:
> Per screen:
> 1. ASCII art wireframe (approx. 20-30 lines)
> 2. Element description: Table | Element | Type | Interaction |
> 3. UX decision (1 sentence why this layout)
>
> Required screens: Start Page, Core Screen, Empty State, Error State
>
> **Constraints**:
> - ONLY wireframes and interaction descriptions
> - NO color specifications, NO dark mode
> - Max. 5 screens per call
> - ASCII art must be readable in monospace

## Orchestrator Checkpoint
- [ ] All required screens covered (or skipped with justification)?
- [ ] Every element has an interaction description?

## Write Detail Files

The result can be written **flat** (single `WIREFRAMES.md`) or **as sub-index with per-screen detail files**, depending on size. ASCII wireframes are large per screen; once you have several screens, the flat layout blows past read-budgets.

### Choose Layout

| Condition | Layout |
|---|---|
| ≤5 screens AND result fits in <25 KB | **Flat**: single `WIREFRAMES.md` |
| ≥6 screens OR result ≥25 KB | **Sub-Index**: lean `WIREFRAMES.md` + `wireframes/` subfolder with one detail file per screen |

### Flat Layout (small wireframe sets)

Write `docs/architecture/WIREFRAMES.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P3
subskill: ux-wireframes
kind: detail
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: per screen one `## <Screen Name>` heading, each with the ASCII wireframe, element/interaction table, and 1-sentence UX rationale.

### Sub-Index Layout (recommended for ≥6 screens)

Write a lean **sub-index** `docs/architecture/WIREFRAMES.md`:

```yaml
---
phase: P3
subskill: ux-wireframes
kind: sub-index
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~10 KB):
- `## Status`
- `## Screen Overview` — table: `Screen | Type (Start/Core/Empty/Error/...) | Persona | Detail-File`
- `## Navigation Map` — how screens connect (cross-screen flow, links to detail files)
- `## Shared Patterns` — common elements / interactions used across screens (one place to define them, referenced from details)
- `## Detail Files` — link list

Per screen, write one detail file `docs/architecture/wireframes/<SCREEN-SLUG>.md` (slug = kebab-case screen name):

```yaml
---
phase: P3
subskill: ux-wireframes
kind: wireframe-detail
screen: <Screen Name>
status: active
last_updated: <DD.MM.YYYY>
---
```

Body: `## Wireframe` (ASCII art, ~20–30 lines), `## Elements` (table: Element | Type | Interaction), `## UX Rationale` (1 sentence), `## States` (loading/empty/error variants if relevant), `## Notes`.

## Update Sub-Index
Update `docs/architecture/UX_CONCEPT.md` (the UX sub-index, created by `/p3-ux` if missing):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[WIREFRAMES.md](WIREFRAMES.md)` with status `complete`.
- If a screen had to be skipped or carries an open UX question, note it in **Open Risks / Open Questions** of the sub-index.
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
