---
disable-model-invocation: true
---
# /p4-sprint – Plan Sprint

Plans the current sprint: pulls matching stories from the backlog, defines the sprint goal, identifies risks, and creates the sprint document. Called repeatedly at the start of each new sprint.

## Argument: $ARGUMENTS = [Sprint goal, e.g. "Complete auth flow", "MVP core running"]

If provided: Use as the sprint goal and select matching stories that support this goal, resolved via
the work-item adoption guard below (falls back to reading BACKLOG.md prose, if the project is still
on prose).
If not provided: Read PROJECT_PLAN.md and derive a sensible sprint goal from the available story
candidates (guard below). If no candidate stories exist, point this out and recommend running
`/p4-backlog` first.

## 0. Work-item adoption guard (ADR-0002 §8)

`/p4-backlog` creates every story at `Backlog` (unstarted, re-selectable). `Ready` means
"committed to a sprint" — nothing sets it except this command, when it actually pulls a story into
the Sprint Table (step 2B). So the candidate POOL is `Backlog`, not `Ready`; `/p5-implement`
correctly resolves its own selection from `Ready`, because this command is what populates it.

Run `python3 ~/.claude/scripts/workitems.py list`.
- **Non-empty array** → the project uses the structured store. Select candidate stories via
  `workitems list --status "Backlog"` (step 2B) instead of reading BACKLOG.md prose for candidates —
  BACKLOG.md/`backlog/E-0X-*.md` remain readable for the full story text (title, description,
  acceptance criteria) once a candidate's id is known, but the candidate SET itself comes from the
  CLI, not from re-parsing prose.
- **`[]` and no `docs/workitems/` directory** → still on prose. Read BACKLOG.md for candidate
  stories, as before. Emit one line: *"Tip: run `lift` to adopt the structured work-item store."*
- **`[]` but `docs/workitems/` exists** → adopted store, just empty right now (e.g. everything
  already committed to a sprint or done). Treat as adopted: use the CLI — an empty `Backlog` list
  means no candidate stories, not "fall back to prose".

See Manual/WORKITEMS.md §8 for the full guard rationale and the status-verb mapping.

## Execution

### 1. Read Context
Read the following files (if available):
- **BACKLOG.md** / `backlog/E-0X-*.md` (story text: title, description, acceptance criteria — the
  candidate set itself comes from `workitems list --status "Backlog"` per the §8 guard above, on a
  structured-store project)
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

### 1c. Determine the Current Sprint Number
Read the previous sprint's `sprint:` frontmatter value — from `docs/planning/SPRINT.md` (flat layout) or the most recent `docs/planning/sprint/SPRINT-NN.md` (sub-index layout). Increment it by 1 for the new sprint (start at `1` if no previous sprint carries this field yet, e.g. the project's first `/p4-sprint` run). Call this `N`. It is used for:
- the new sprint's frontmatter (`sprint: <N>`, see 4b/4c)
- the per-story `workitems set-sprint <id> <N>` call in step 2B below

`sprint: <N>` in SPRINT.md's frontmatter (or the active `sprint/SPRINT-NN.md`'s, for the sub-index layout) is the **single source of truth** for "what is the current sprint number" — `/guide` and `/gate-p5` read it from there, not from filenames or prose.

### 1d. Capture Sprint Base Commit (anchors the end-of-sprint review)
Record the current `HEAD` as this sprint's base, so `/p5-review-sprint` and `/gate-p5` can resolve **exactly** which commits belong to the sprint — regardless of how many commits or pushes happen mid-sprint:
- At the start of planning (before writing the sprint docs), run `git rev-parse HEAD` and capture the SHA.
- Write it into the sprint frontmatter as `base_commit: <sha>` (see 4b / 4c). The end-of-sprint review then scopes itself to `git diff <base_commit>..HEAD`.
- Edge case — brand-new repo with no commits yet: leave `base_commit` empty and let the review fall back to reviewing all of `HEAD`.

### 2. Delegation to Project-Planner Agent (Lead)
Delegate sprint planning to the **project-planner** agent:

> Plan the next sprint. Sprint goal (if provided): **$ARGUMENTS**
> Context: [Insert PROJECT_PLAN.md milestones, last sprint velocity, and the candidate stories from
> the §0 guard: `workitems list --status "Backlog"` (structured store) or BACKLOG.md prose (fallback)]
>
> **A. Formulate Sprint Goal**
> - 1–2 sentences describing what should be achieved by the end of the sprint
> - The goal must be achievable through the selected stories
>
> **B. Select Stories**
> - Structured store: choose from the `Backlog` candidates (§0 guard) that support the sprint goal —
>   read each candidate's full story text (title, description, acceptance criteria) from
>   BACKLOG.md/`backlog/E-0X-*.md` via its `**Work-Item:** WI-NNNN` reference. Prose fallback:
>   choose stories directly from BACKLOG.md, as before.
> - Note: dependencies must be resolved before a story can be pulled
> - Capacity: estimate realistically (no more than 80% of available story points)
> - Sort stories by implementation order within the sprint
> - For each selected story, carry forward its `Work-Item` id — on the structured store it's already
>   known from the `Backlog` list (§0); on prose fallback, read it from the story's `**Work-Item:**`
>   line in BACKLOG.md if the project has partially adopted the store, otherwise there is none yet.
>   This is the same id `/p5-implement`, `/p5-review`, `/p5-acceptance`, and `gate-p5` resolve
>   `set-status` against, so it must be carried into the Sprint Table below, not dropped.
> - **Promote each selected story to `Ready` and stamp it with the sprint** (structured store only):
>   `workitems set-status <id> "Ready"` **and** `workitems set-sprint <id> <N>` (N from step 1c) —
>   being pulled into this sprint's Sprint Table IS the commitment event; `Ready` is what
>   `/p5-implement` resolves its own selection from, and the `sprint` field is what `/guide` and
>   `/gate-p5` resolve sprint *membership* from (`list --sprint <N>`) — the Sprint Table below is a
>   human-readable view from here on, not the machine source of membership. Do this for every story
>   written into the Sprint Table, not just a subset — an item left without both `Ready` and
>   `sprint: <N>` would be invisible to `/p5-implement` and/or `/gate-p5`/`/guide`'s sprint scoping.
>
> **C. Sprint Table**
> | Story ID | Work-Item | Title | Epic | Story Points | Type | Dependency |
> |---|---|---|---|---|---|---|
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
sprint: <N>   # current sprint number (step 1c) — the source /guide and /gate-p5 read for sprint scoping
---
```

Body sections: `## Sprint Goal`, `## Selected Stories` (the Sprint Table from step 2C, including each
story's Work-Item id, in order), `## Definition of Done`, `## Risks Identified This Sprint`.

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
sprint: NN   # this sprint's number (step 1c) — the source /guide and /gate-p5 read for sprint scoping
base_commit: <sha>   # HEAD at sprint start — anchors the /p5-review-sprint diff
status: living | frozen   # frozen after sprint end
last_updated: <DD.MM.YYYY>
---
```

Body: `## Sprint Goal`, `## Selected Stories` (the Sprint Table from step 2C, including each story's
Work-Item id, with order and story-point estimates), `## Definition of Done`, `## Risks Identified
This Sprint`, `## Sprint Review` (filled at sprint end).

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
status: living   # detail file keeps growing via ## History as the risk evolves
risk_status: open | mitigated | accepted | closed
sprint_identified: NN
last_updated: <DD.MM.YYYY>
---
```

`status` is the document-schema field (`phase`/`subskill`/`status`/`last_updated`, required by `phase-docs-lint.sh`) — a risk detail file is always `living`, it is designed to be appended to via `## History` for as long as the risk is tracked. `risk_status` is a separate field for the RISK lifecycle itself; the two must not share a name, or `phase-docs-lint.sh` validates the risk lifecycle value against the document-status enum and rejects it.

Body: `## Description`, `## Impact`, `## Likelihood`, `## Countermeasure`, `## Trigger / Indicator` (when does this risk become real?), `## Owner`, `## History` (risk_status changes over time).

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
The sprint number `N` is determined by this command (step 1c): previous sprint's `sprint:` frontmatter value + 1, starting at `1` if none exists yet. It is written into SPRINT.md's (or the active `sprint/SPRINT-NN.md`'s) frontmatter as `sprint: <N>` — the single source of truth `/guide` and `/gate-p5` read for sprint scoping — and stamped onto every committed story via `workitems set-sprint <id> <N>`.

## Ticket ID Formats in Sprint
Bugs and findings that arise during the sprint follow the schema from `/p4-backlog`:
- **Bugs:** `BUG-{NN}` (sequentially numbered per project, sprint assignment in the sprint table)
- **Findings:** `{AREA}-{NN}` (e.g. SAST-01, DSGVO-03, PT-07)

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
