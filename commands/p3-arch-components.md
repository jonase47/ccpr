---
disable-model-invocation: true
---
# /p3-arch-components – Component Diagram & Data Flows

Creates the system architecture overview with component diagram, responsibilities and data flows.

## Argument: $ARGUMENTS = [Architecture style, e.g. "Monolith", "Microservices", "Single-File"]

If provided: Use the style as a starting point.
If not provided: Recommend the most suitable style based on the context.

## Prerequisites
- CONCEPT.md and FEATURES.md exist
- MVP.md defines the scope

## Agent
- **Type**: system-architekt
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From CONCEPT.md: Project description, core mechanics
- From FEATURES.md: Must-Have features (short list)
- From VALIDATION.md: PoC findings (if available)

## Prompt Template
> **Goal**: Create component diagram and data flows for: $ARGUMENTS
>
> **Context**:
> [inline from CONCEPT.md, FEATURES.md]
>
> **Output Format**:
> 1. Component diagram (ASCII art or Mermaid)
> 2. Table: | Component | Responsibility | Dependencies |
> 3. Data flows as numbered list
>
> **Constraints**:
> - ONLY architecture overview, NO tech stack, NO ADRs
> - Max. 10 components
> - External integrations only if mentioned in the context

## Orchestrator Checkpoint
- [ ] Diagram covers all must-have features?
- [ ] No component without a clear responsibility?

## Write Detail Files

The result can be written **flat** (single `COMPONENTS.md`) or **as sub-index with per-component detail files**, depending on size.

### Choose Layout

| Condition | Layout |
|---|---|
| ≤6 components AND result fits in <20 KB | **Flat**: single `COMPONENTS.md` |
| ≥7 components OR result ≥20 KB | **Sub-Index**: lean `COMPONENTS.md` + `components/` subfolder with one detail file per component |

### Flat Layout (small architectures)

Write `docs/architecture/COMPONENTS.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P3
subskill: arch-components
kind: detail
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Component Diagram` (ASCII or Mermaid), `## Component Responsibilities` (the responsibilities/dependencies table), `## Data Flows` (numbered list).

### Sub-Index Layout (recommended for ≥7 components)

Write a lean **sub-index** `docs/architecture/COMPONENTS.md`:

```yaml
---
phase: P3
subskill: arch-components
kind: sub-index
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~10 KB):
- `## Component Diagram` (full diagram stays in the index for navigation)
- `## Components` — overview table: `Component | Responsibility (1 line) | Depends On | Detail-File`
- `## Data Flows` (numbered list — cross-cutting flows stay in the index)
- `## Detail Files` — link list

Per component, write one detail file `docs/architecture/components/<COMPONENT>.md`:

```yaml
---
phase: P3
subskill: arch-components
kind: component-detail
component: <ComponentName>
status: active
last_updated: <DD.MM.YYYY>
---
```

Body: `## Responsibility`, `## Interfaces` (in/out APIs), `## Dependencies`, `## Internal Structure` (if non-trivial), `## Notes`.

## Update Phase Index
Update `docs/architecture/ARCHITECTURE.md` (create from index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[COMPONENTS.md](COMPONENTS.md)` with status `complete`.
- Lift the architecture style decision into **Key Decisions** (e.g. `- Architecture style: <style> → see COMPONENTS.md`).

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
