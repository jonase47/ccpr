# /p4-sprint – Plan Sprint

Plans the current sprint: pulls matching stories from the backlog, defines the sprint goal, identifies risks, and creates the sprint document. Called repeatedly at the start of each new sprint.

## Argument: $ARGUMENTS = [Sprint goal, e.g. "Complete auth flow", "MVP core running"]

If provided: Use as the sprint goal and select matching stories from the backlog that support this goal.
If not provided: Read BACKLOG.md and PROJECT_PLAN.md and derive a sensible sprint goal. If BACKLOG.md is missing, point this out and recommend running `/p4-backlog` first.

## Execution

### 1. Read Context
Read the following files (if available):
- **BACKLOG.md** (prioritized backlog – source of sprint stories)
- **PROJECT_PLAN.md** (milestones – where does the project stand?)
- **SPRINT.md** (if available: last sprint as reference for velocity)
- **RISKS.md** (consider known risks)
- **POLISH.md** or `polish/POLISH-SPRINT-NN.md` of the previous sprint (if `/p5-polish` ran – check for archive-pending state)

### 1b. Archive Previous Sprint's Polish File (if present)
Before planning the new sprint, archive the previous sprint's polish artefact so the new sprint starts clean:
- If `docs/planning/polish/POLISH-SPRINT-<prev>.md` exists with `status: living` → move it to `docs/planning/.handover-archive/sprint-<prev>/POLISH-SPRINT-<prev>.md` and set `status: active`, update `last_updated`.
- If flat `docs/planning/POLISH.md` exists with `status: living` → move it to `docs/planning/.handover-archive/sprint-<prev>/POLISH.md` and set `status: active`.
- If `status: empty` → archive identically (record that no polish was needed).
- Update `PROJECT_PLAN.md`: remove or update the POLISH row in the Detail Files table to reflect archival.
- If no polish file exists (skill was not run): proceed silently, no error.

Create `.handover-archive/sprint-<prev>/` if it does not yet exist.

### 1c. Capture Sprint Base Commit (anchors the end-of-sprint review)
Record the current `HEAD` as this sprint's base, so `/p5-review-sprint` and `/gate-p5` can resolve **exactly** which commits belong to the sprint — regardless of how many commits or pushes happen mid-sprint:
- At the start of planning (before writing the sprint docs), run `git rev-parse HEAD` and capture the SHA.
- Write it into the sprint frontmatter as `base_commit: <sha>` (see 4b / 4c). The end-of-sprint review then scopes itself to `git diff <base_commit>..HEAD`.
- Edge case — brand-new repo with no commits yet: leave `base_commit` empty and let the review fall back to reviewing all of `HEAD`.

### 2. Delegation to Project-Planner Agent (Lead)
Delegate sprint planning to the **project-planner** agent:

> Plan the next sprint. Sprint goal (if provided): **$ARGUMENTS**
> Context from BACKLOG.md and PROJECT_PLAN.md: [Insert backlog status, milestones, last sprint velocity]
>
> **A. Formulate Sprint Goal**
> - 1–2 sentences describing what should be achieved by the end of the sprint
> - The goal must be achievable through the selected stories
>
> **B. Select Stories**
> - Choose stories from the backlog that support the sprint goal
> - Note: dependencies must be resolved before a story can be pulled
> - Capacity: estimate realistically (no more than 80% of available story points)
> - Sort stories by implementation order within the sprint
>
> **C. Sprint Table**
> | Story ID | Title | Epic | Story Points | Type | Dependency |
> |---|---|---|---|---|---|
>
> **D. Identify Risks**
> - Which stories in the sprint have the highest uncertainty?
> - Which external dependencies could block the sprint?
> - What is the fallback if the sprint goal is not fully reached?
>
> **E. Definition of Done for This Sprint**
> - What must be fulfilled for a story to count as "Done"?
> - (Typically: code written + unit tests green + code review + acceptance test passed + CI green)

### 3. Delegation to Senior-Developer Agent (Support)
Delegate technical planning review to the **senior-developer** agent:

> Review the project-planner's sprint plan from a developer perspective:
> 1. Are the selected stories implementable within one sprint (effort realistic)?
> 2. Are there technical prerequisites that are not yet met?
> 3. In what order should the stories be implemented (technical dependencies)?
> 4. Where do you see the greatest risk in this sprint?

### 4. Write Detail Files
This subskill writes **two** living file groups in `docs/planning/`. Both stay alive across sprints — `SPRINT.md` reflects the current sprint, `RISKS.md` is the cumulative register. Each group can be **flat** or **sub-index**, depending on size.

#### 4a. Choose Layout — Sprint

| Condition | Layout |
|---|---|
| Current sprint plan fits in <10 KB | **Flat**: single `SPRINT.md` (overwrite each sprint) |
| Sprint plan ≥10 KB OR you want history of prior sprints preserved | **Sub-Index**: lean `SPRINT.md` + `sprint/SPRINT-NN.md` per sprint |

#### 4b. Flat Layout — Sprint (small sprints)

Write `docs/planning/SPRINT.md` (overwrite — sprint plan reflects the current sprint only). Frontmatter:

```yaml
---
phase: P4
subskill: sprint
kind: detail
status: living   # current sprint plan, replaced each call
last_updated: <DD.MM.YYYY>
base_commit: <sha>   # HEAD at sprint start — anchors the /p5-review-sprint diff
---
```

Body sections: `## Sprint Goal`, `## Selected Stories` (with order), `## Definition of Done`, `## Risks Identified This Sprint`.

#### 4c. Sub-Index Layout — Sprint (recommended for non-trivial sprints / when history matters)

Write a lean **sub-index** `docs/planning/SPRINT.md`:

```yaml
---
phase: P4
subskill: sprint
kind: sub-index
status: living
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~6 KB):
- `## Current Sprint` — name, goal (1 line), link to `sprint/SPRINT-NN.md`
- `## Sprint History` — table: `Sprint | Goal (1 line) | Status | Detail-File`
- `## Velocity` — story points completed per sprint (rolling)
- `## Detail Files` — link list

Per sprint (current and previous), write one detail file `docs/planning/sprint/SPRINT-NN.md` (NN = two-digit sprint number):

```yaml
---
phase: P4
subskill: sprint
kind: sprint-detail
sprint: NN
base_commit: <sha>   # HEAD at sprint start — anchors the /p5-review-sprint diff
status: living | complete   # complete after sprint end
last_updated: <DD.MM.YYYY>
---
```

Body: `## Sprint Goal`, `## Selected Stories` (with order, story-point estimates), `## Definition of Done`, `## Risks Identified This Sprint`, `## Sprint Review` (filled at sprint end).

#### 4d. Choose Layout — Risks

| Condition | Layout |
|---|---|
| ≤6 risks AND register fits in <8 KB | **Flat**: single `RISKS.md` |
| ≥7 risks OR register ≥8 KB | **Sub-Index**: lean `RISKS.md` + `risks/R-NN-<slug>.md` per risk |

#### 4e. Flat Layout — Risks (small register)

Write `docs/planning/RISKS.md` (create with frontmatter on first run, append on later runs). Frontmatter:

```yaml
---
phase: P4
subskill: sprint
kind: detail
status: living   # risk register grows across sprints
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Risk Register` table with columns `ID | Risk | Severity | Status | Countermeasure | Sprint Identified`. Each `/p4-sprint` run appends new rows; existing rows get status updates as risks materialise or are mitigated.

#### 4f. Sub-Index Layout — Risks (recommended for ≥7 risks)

Write a lean **sub-index** `docs/planning/RISKS.md`:

```yaml
---
phase: P4
subskill: sprint
kind: sub-index
status: living
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~6 KB):
- `## Risk Matrix` — table: `ID | Risk (1 line) | Severity | Status | Detail-File`
- `## High / Critical Risks` — quick list with one-liners + links
- `## Detail Files` — link list

Per risk, write one detail file `docs/planning/risks/R-NN-<slug>.md` (NN = two-digit risk number, slug = kebab-case short name):

```yaml
---
phase: P4
subskill: sprint
kind: risk-detail
risk_id: R-NN
severity: low | medium | high | critical
status: open | mitigated | accepted | closed
sprint_identified: NN
last_updated: <DD.MM.YYYY>
---
```

Body: `## Description`, `## Impact`, `## Likelihood`, `## Countermeasure`, `## Trigger / Indicator` (when does this risk become real?), `## Owner`, `## History` (status changes over time).

### 5. Update Phase Index
Update `docs/planning/PROJECT_PLAN.md` (the P4 phase index, created by `/p4-backlog` if missing):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure rows for `[SPRINT.md](SPRINT.md)` (status `living`) and `[RISKS.md](RISKS.md)` (status `living`).
- Lift the current sprint goal into **Key Decisions** (e.g. `- Sprint <N>: <goal> → see SPRINT.md`).
- Lift any newly identified High/Critical risk into **Open Risks / Open Questions**.

## Result

- **`docs/planning/SPRINT.md`** (current sprint plan)
- **`docs/planning/RISKS.md`** (cumulative risk register)
- **`docs/planning/PROJECT_PLAN.md`** (phase index updated)
- Direct entry point into `/p5-implement` for the first story of the sprint

## Note on Sprint Numbers
The sprint number is managed in SPRINT.md and incremented with each new sprint call. The command itself does not manage numbering.

## Ticket ID Formats in Sprint
Bugs and findings that arise during the sprint follow the schema from `/p4-backlog`:
- **Bugs:** `BUG-{NN}` (sequentially numbered per project, sprint assignment in the sprint table)
- **Findings:** `{AREA}-{NN}` (e.g. SAST-01, DSGVO-03, PT-07)

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
