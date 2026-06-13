# /p5-polish – Sprint Polish: Collect & Resolve Small Carry-Over TODOs

Collects small clean-up TODOs accumulated during the sprint (from `/p5-review`, `/p5-acceptance`, `/p5-bugfix`, TODO/FIXME comments) that do not justify a full story but make the next sprint easier. Triages each item into `polish-now`, `backlog`, `handover`, or `drop`. Optionally executes `polish-now` items directly (TDD mini-cycle, one commit per item). Runs **between `/gate-p5` (Sprint Done) and the next `/p4-sprint`**.

This is **not** a retrospective – `/gate-p5` keeps the 3-point retro. This skill is the cleanup step before the next sprint begins.

## Argument: $ARGUMENTS = [mode | POL-ID]

- *empty* → Hybrid mode (collect + triage + execute small items)
- `collect-only` → Collect & document only, no code changes
- `execute` → Execute previously-triaged `polish-now` items from existing POLISH file
- `<POL-ID>` (e.g. `POL-03-02`) → Work on a single polish item

## Preconditions (Hard Block on Violation)

Before doing anything else, verify:
1. **Gate-p5 passed**: Last `gate-p5` entry in `SPRINT.md` shows `Sprint Done` or `Conditionally Done`. If not → stop, recommend `/gate-p5` first.
2. **CI green**: No failing tests or build errors on current commit. If red → stop, recommend `/p5-bugfix`.
3. **Working tree clean**: No uncommitted changes. If dirty → stop, ask user to commit or stash.

If any precondition fails, write the reason and the recommended next command, then exit. Do not collect, do not execute.

## Execution

### 1. Read Context
Read the following files (if available):
- **SPRINT.md** and current `sprint/SPRINT-NN.md` (deferred items, "Conditionally Done" notes, retrospective points)
- **BACKLOG.md** (for deduplication – do not re-capture items already in the backlog)
- **HANDOVER.md** (existing "Open Points")
- **reviews/** and **tests/ACCEPTANCE_*.md** files with mtime ≥ sprint start (review/acceptance findings)
- Latest `gate-p5` block in SPRINT.md (retrospective points marked as "improvement")
- **BASELINE.md** (if present – frozen-docs rules apply, see Edge Cases)

### 2. Code Scan for In-Sprint TODOs
Run a focused scan on files changed during the current sprint:

```
git log --name-only --since="<sprint-start-date>" --pretty=format: | sort -u
grep -nE "TODO|FIXME|XXX|HACK" <those-files>
```

Capture file:line and the marker comment. Skip files outside `src/`.

### 3. Delegation to Project-Planner Agent (Lead) – Collect & Triage

Delegate aggregation and triage to the **project-planner** agent:

> Collect and triage sprint-end polish TODOs.
> Sources gathered (insert findings from steps 1–2): [list with origin per item]
>
> **A. Deduplicate**
> - Remove items already tracked as stories in BACKLOG.md
> - Merge near-duplicates from different sources
>
> **B. Assign Polish IDs**
> Schema: `POL-NN-MM` (NN = current sprint number, MM = sequential item number).
>
> **C. Triage each item**
> Apply this heuristic strictly:
>
> | Criterion | polish-now | backlog | handover | drop |
> |---|---|---|---|---|
> | Effort | ≤30 min, ≤2 files | >30 min OR new test needed | unclear / blocked | irrelevant / duplicate |
> | New test required? | No (or trivial, ≤5 LOC) | Yes | — | — |
> | Touches architecture / API? | No | Yes (even small) | — | — |
> | Examples | Typo, JSDoc gap, magic number → const, unused import, one-liner refactor | Refactor with test changes, new feature detail | needs external clarification | duplicate of existing story |
>
> **D. Hard limit: max 5 `polish-now` items per run.**
> If more candidates qualify: keep the top 5 (highest impact on next sprint), move the rest to `backlog`. Warn the user: "Polish debt is high → consider a dedicated tech-debt sprint."
>
> **E. Output**
> Triage table with columns: `ID | Source | Item | Size estimate | Decision | Reason`.

### 4. User Confirmation (interactive)

Present the triage table to the user. Ask for confirmation or overrides per item. **Never silently modify the triage** – the user must accept it explicitly. If `$ARGUMENTS = collect-only`, skip to step 7 after confirmation.

### 5. Delegation to Senior-Developer Agent (Support) – Execute `polish-now` Items

For each `polish-now` item, delegate to the **senior-developer** agent:

> Execute polish item **POL-NN-MM**: [item description, file:line]
>
> 1. **Test first** if a regression test is missing for this area (RED). For trivial items (typo, comment update, import cleanup), no new test is required – existing test suite must stay green.
> 2. **Apply the fix** (GREEN). Minimal change, no scope creep.
> 3. **Refactor** if it improves clarity (optional).
> 4. **Run full test suite** – must be green.
> 5. **Commit**: one item = one commit. Type matches the change:
>    - `docs: POL-NN-MM <desc>` for doc/comment changes
>    - `refactor: POL-NN-MM <desc>` for non-behavioural code changes
>    - `chore: POL-NN-MM <desc>` for tooling / cleanup
>    - `fix: POL-NN-MM <desc>` for tiny defect fixes (rare here – usually `/p5-bugfix` territory)
> 6. Record the commit hash for the POLISH file.

### 6. Transfer Non-Executed Items

- `backlog` items: append to `BACKLOG.md` as mini-stories with effort estimate, reference to POL-ID.
- `handover` items: add to `docs/HANDOVER.md` under "Open Points" with POL-ID and reason for blocking.
- `drop` items: record in the POLISH file under "Dropped" with reason.

### 7. Write POLISH Detail File

**Choose layout:**

| Condition | Layout |
|---|---|
| `SPRINT.md` uses sub-index layout (sprint/SPRINT-NN.md exists) | **Sub-Index**: `docs/planning/polish/POLISH-SPRINT-NN.md` |
| `SPRINT.md` is flat | **Flat**: `docs/planning/POLISH.md` (overwrite each sprint) |

**Frontmatter:**

```yaml
---
phase: P5
subskill: polish
kind: sprint-detail   # or `detail` for flat layout
sprint: NN
status: living        # → complete on archive (set by /p4-sprint)
last_updated: <DD.MM.YYYY>
parent_index: ../PROJECT_PLAN.md
---
```

**Body sections:**
- `## Polish Sources` – brief list of what was scanned (SPRINT.md, reviews/, code TODOs, etc.)
- `## Triage Table` – columns: `ID | Source | Item | Size | Decision | Status | Commit/Ref`
- `## Done (this run)` – list of `polish-now` items completed with commit hash
- `## Moved to Backlog` – list with backlog story IDs (linkable)
- `## Moved to Handover` – list with reason
- `## Dropped` – list with reason

**Special case: no items found.** Write the file with `status: empty`, leave triage table empty, single line in body: "No polish items found this sprint." No commits.

### 8. Update Phase Index

Update `docs/planning/PROJECT_PLAN.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: add or refresh row for `[POLISH-SPRINT-NN.md](polish/POLISH-SPRINT-NN.md)` (status `living`) or `[POLISH.md](POLISH.md)` for flat layout.
- If `polish-now` items affected architecture-adjacent code (rare – usually filtered out by triage): lift a one-liner into **Key Decisions**.

## Result

- `docs/planning/polish/POLISH-SPRINT-NN.md` (or flat `POLISH.md`) with triage outcome
- 0–5 small commits for executed `polish-now` items
- `BACKLOG.md` updated (mini-stories for `backlog` items)
- `HANDOVER.md` updated (open points for `handover` items)
- `PROJECT_PLAN.md` updated (phase index)

## Possible Outcomes

| Result | Meaning | Next Step |
|---|---|---|
| **Items executed** | One or more polish items committed | `/p4-sprint` (start next sprint) |
| **Empty** | Nothing to polish this sprint | `/p4-sprint` directly |
| **Backlog-heavy** | Polish debt too high – warning issued | Consider dedicated tech-debt sprint via `/p4-sprint` with explicit goal |

## Edge Cases

- **No polish TODOs found**: Write empty POLISH file (`status: empty`), recommend `/p4-sprint` directly. No commit.
- **More than 10 candidate items**: Warn user. Force-split to max 5 `polish-now`, rest goes to backlog. Suggest planning a dedicated tech-debt sprint.
- **Baseline mode active** (`BASELINE.md` present + project CLAUDE.md has Baseline section): Skip reading frozen docs. Items that would modify frozen docs → auto-`drop` or `backlog` with reason "would modify frozen baseline".
- **Uncommitted changes at start**: Hard block (see Preconditions).
- **CI red at start**: Hard block – recommend `/p5-bugfix`.
- **Gate-p5 not yet passed**: Hard block – recommend `/gate-p5`.

## Note on Archiving

The POLISH detail file stays `living` until `/p4-sprint` is called for the next sprint. At that point `/p4-sprint` moves the file to `docs/planning/.handover-archive/sprint-NN/` and sets `status: active`. Do not archive within this skill.

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. After polish: recommend `/p4-sprint` to start the next sprint (or `/p6-functional` if all sprints are done)
