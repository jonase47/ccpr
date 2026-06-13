# /release-baseline – Set project state as baseline

Makes a "cut" after a release: project state is documented as given,
HANDOVER is archived and summarized, docs are split into Frozen/Active.

## Argument: $ARGUMENTS = [Release version, e.g. "v1.0.0"]

## Prerequisites
- Gate-P7 Go or explicit user request

## Execution

### 1. Read prep report
Read `docs/.baseline-prep.md` (created via baseline.sh).
If not present or older than 10 min: inform the user that
`~/.claude/scripts/baseline.sh [version] [projectdir]` should be run first.

### 2. Create BASELINE.md
Create `docs/BASELINE.md`:

```markdown
# Baseline: [Version]

**Release**: [Version]
**Date**: [DD.MM.YYYY]
**Status**: [e.g. MVP completed, all gates P0-P7 passed]

## Project State Summary
[Take HANDOVER summary from prep report. If not available: summarize from HANDOVER.md yourself (max. 10 sentences)]

## Core Architecture
[3-5 sentences from docs/architecture/ARCHITECTURE.md – architecture style, main components, deployment model]

## Tech Stack
[Bullet points from .claude/CLAUDE.md or docs/architecture/TECH_STACK.md]

## Completed Milestones
[Table from docs/planning/PROJECT_PLAN.md – completed milestones only]

## Important Decisions
[Take from .claude/CLAUDE.md "Important Decisions" table]
```

### 3. Update project CLAUDE.md
Add a "Baseline" section after "Current Phase" (before "Project goals"):

```markdown
## Baseline
**Release**: [Version] ([Date])
**Status**: [e.g. MVP completed, all gates P0-P7 passed]

### Frozen Docs (read only when needed)
- docs/discovery/ (P0)
- docs/concept/ (P1)
- docs/validation/ (P2)
- docs/architecture/ (P3)
- docs/planning/PROJECT_PLAN.md (milestones)

### Active Docs (at every session start)
- docs/HANDOVER.md (Handover)
- docs/BASELINE.md (reference)
- docs/planning/BACKLOG.md (current work)
- docs/planning/SPRINT.md (current sprint)
```

If a Baseline section already exists: update it (version, date, status).

### 4. Reset HANDOVER.md
Create a fresh HANDOVER.md according to the template (`~/.claude/templates/HANDOVER_TEMPLATE.md`):

- **Current phase**: P8 – Operations & Evolution
- **Status**: Baseline [Version] set, ready for post-release iterations
- **What was achieved**: Take HANDOVER summary from prep report (compact)
- **Next steps**: `/p8-ops` or `/p8-iteration` depending on context
- **Context for next session**: Take HANDOVER summary from prep report

### 5. Present result
Show the user:
- Archived HANDOVER file (path)
- Created BASELINE.md (brief summary)
- Changed CLAUDE.md (Frozen/Active Docs)
- Reset HANDOVER.md

## Handover Epilogue
Update `docs/HANDOVER.md` with the result of this command.
Set "Last Agent / Command" to `/release-baseline`.

## Next Steps
- `/p8-ops` – Start production operations
- `/p8-iteration [topic]` – Plan next feature
