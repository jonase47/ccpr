# /p4-backlog – Work Breakdown, Backlog & Milestones

Breaks down the features from FEATURES.md into actionable tasks, builds the prioritized backlog, and defines milestones and release planning. The result is BACKLOG.md and PROJECT_PLAN.md as the steering foundation for the entire implementation.

## Argument: $ARGUMENTS = [Focus Epic, e.g. "Authentication", "Booking Process", "Admin Area"]

If provided: Work out the named epic in particular detail – other epics may remain at a higher level.
If not provided: Read FEATURES.md, MVP.md and ARCHITECTURE.md and create a complete backlog for all must-have features. If any context is missing, ask about the MVP scope.

## Execution

### 1. Read Context
Read the following files (if available):
- **FEATURES.md** / **MVP.md** (feature scope and prioritization)
- **ARCHITECTURE.md** / **DATA_MODEL.md** / **API_SPEC.md** (technical foundation)
- **SECURITY.md** (security requirements as mandatory tasks)
- **DSGVO_INITIAL_ASSESSMENT.md** (DSGVO (GDPR) mandatory tasks)
- **FINANCIAL_PLAN.md** (budget constraints influence scheduling)

### 2. Delegation to Project-Planner Agent (Lead)
Delegate the backlog build to the **project-planner** agent:

> Build the project backlog. Focus epic (if provided): **$ARGUMENTS**
> Context: [Insert FEATURES.md, MVP.md, ARCHITECTURE.md key points]
>
> **A. Epic Structure**
> Group all must-have features into meaningful epics (4–8 epics for an MVP).
> Per epic: name, short description, included features, estimated effort (rough story points or days).
>
> **B. User Stories & Tasks**
> Break each epic down into user stories:
> - Format: "As a [Persona] I want to [Action] so that [Benefit]."
> - Acceptance criteria (2–4 points that make it clear when the story is done)
> - Technical tasks per story (concrete implementation steps)
> - Effort estimate (story points: 1 / 2 / 3 / 5 / 8)
> - Dependencies on other stories
> - Labels: Frontend / Backend / Fullstack / DevOps / Design
>
> **C. Backlog Prioritization**
> - Sort stories by priority within each epic
> - Identify the critical path: which stories block others?
> - Mark technical foundation stories (must be implemented first)
>
> **D. Milestones & Release Planning**
> - Define 2–4 milestones on the way to the MVP launch
> - Per milestone: name, included epics/stories, criterion for completion
> - Initial time estimate: how many sprints (2 weeks each) are needed?
>
> **E. Risks & Buffers**
> - Which stories have the highest uncertainty?
> - Where should buffers be planned?

### 3. Delegation to Senior-Developer Agent (Support)
Delegate effort estimation and technical validation to the **senior-developer** agent:

> Review and supplement the project-planner's backlog from a developer perspective:
> 1. Are the story point estimates realistic? Correct any major outliers.
> 2. Are technical tasks missing (e.g. database migrations, test setup, security implementation)?
> 3. Are the acceptance criteria implementable and testable?
> 4. Are there technical dependencies not reflected in the backlog?
> 5. What should be implemented in the first sprint to lay a solid foundation?

### 4. Write Detail Files
This subskill writes the phase index `PROJECT_PLAN.md` plus the backlog. The backlog uses one of two layouts depending on size — both belong in `docs/planning/`.

#### 4a. Choose Backlog Layout

| Condition | Layout |
|---|---|
| Backlog has ≤5 epics AND fits in <20 KB | **Flat**: single `BACKLOG.md` |
| Backlog has ≥6 epics OR ≥20 KB OR many stories per epic | **Sub-Index**: lean `BACKLOG.md` + `backlog/` subfolder with one detail file per epic (recommended for MVPs of any non-trivial size) |

Sub-Index layout follows the generic convention in `~/.claude/docs/PROJECT_PHASES.md` ("Sub-Index for growing detail files").

#### 4b. Flat Layout (small backlogs)

Write `docs/planning/BACKLOG.md` with frontmatter:

```yaml
---
phase: P4
subskill: backlog
kind: detail
status: living   # living | complete (only when project is finished)
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Epics`, `## User Stories` (per epic), `## Estimates & Acceptance Criteria`, `## Dependencies`, `## Labels`.

#### 4c. Sub-Index Layout (recommended for MVP-scale backlogs)

Write a lean **sub-index** `docs/planning/BACKLOG.md`:

```yaml
---
phase: P4
subskill: backlog
kind: sub-index
status: living
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~10 KB):
- `## Status` (one line)
- `## Epics` — overview table: `ID | Title | T-Shirt | Stories | Status | Detail-File`
- `## Epic Dependencies` — DAG (which epic blocks which)
- `## Milestones` — short, links to `PROJECT_PLAN.md` for full breakdown
- `## Detail Files` — link list (epic detail files + cross-reference files)
- `## Risk Register Stub` — only if it stays compact, otherwise extract to `RISKS.md`

Per epic, write one detail file `docs/planning/backlog/E0X-<slug>.md`:

```yaml
---
phase: P4
subskill: backlog
kind: epic-detail
epic_id: E-0X
status: draft
last_updated: <DD.MM.YYYY>
---
```

Body: epic header (Goal, Scope, T-Shirt, Dependencies, Labels, Notes) + all user stories of this epic as H5 (`##### E-0X-S01 · Title`) with their acceptance criteria, estimate, dependencies, labels, notes.

Optional cross-reference files in `docs/planning/backlog/`:
- `STORY_INDEX.md` — table of all stories at a glance: `Story-ID | Epic | Title | T-Shirt | Status | Detail-File`
- `FEATURE_COVERAGE.md` — feature-ID ↔ epic mapping (if Feature-IDs are referenced from stories)

#### 4d. Phase Index `PROJECT_PLAN.md`

Create from index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`. Populate:
- `## Key Decisions`: lift the milestone names + their dates (e.g. `- M1: MVP feature-complete by 30.06.2026 → see PROJECT_PLAN.md (Milestones section)`).
- `## Detail Files` table: add a row for `[BACKLOG.md](BACKLOG.md)` with status `living` and the chosen layout (flat or sub-index). Other P4 detail files (`SPRINT.md`, `RISKS.md`, `SETUP.md`, `DOCS.md`) get added by their respective subskills.
- A new top-level body section in the index titled `## Milestones & Release Planning` with the milestones, their target dates, and risk areas — this stays inside the index because milestones are aggregate planning info, not a per-subskill artefact.

## Ticket ID Schema (Reference)

All IDs follow this consistent schema. Phase is metadata in BACKLOG.md, not part of the ID.

| Type | Format | Example | Note |
|-----|--------|----------|---------|
| Epic | `E-{NN}` | E-01, E-14 | Two digits, sprint-independent |
| Story | `E-{NN}-S{NN}` | E-01-S01, E-14-S03 | Epic reference + story number |
| Bug | `BUG-{NN}` | BUG-01, BUG-12 | Sequentially numbered per project, sprint assignment in SPRINT.md |
| Finding | `{AREA}-{NN}` | SAST-01, DSGVO-03, PT-07 | Areas: SAST, CFG, DSGVO, AUTH, DEP, PT, CR, SEC |
| Milestone | `M{N}` | M1, M2 | Single digit |
| Open Decision | `OE-{NN}` | OE-01 | Optional, not every project needs it |

## Result

- **`docs/planning/BACKLOG.md`** (living, prioritized, estimated backlog with frontmatter `status: living`)
- **`docs/planning/PROJECT_PLAN.md`** (phase index with `## Milestones & Release Planning` body section)
- Foundation for `/p4-sprint` (populate first sprint) and all P5 commands

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
