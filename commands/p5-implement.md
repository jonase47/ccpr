# /p5-implement – Implement Feature (TDD Cycle)

Implements a feature in the TDD cycle: Red → Green → Refactor. Each phase is its own sub-skill with a focused agent call.

## Argument: $ARGUMENTS = [Feature name/Story ID]

If provided: Implement the named feature.
If not provided: resolve the next story via the work-item adoption guard below (falls back to
reading SPRINT.md and asking, if the project is still on prose).

## 0. Work-item adoption guard (ADR-0002 §8)

Run `python3 ~/.claude/scripts/workitems.py list`.
- **Non-empty array** → the project uses the structured store. Use the CLI for all item state below:
  - No `$ARGUMENTS`: resolve the next story via `workitems list --status "Ready"`, pick the first
    item in the returned array, ask for confirmation.
  - `$ARGUMENTS` provided: resolve `<id>` by matching `$ARGUMENTS` against a story's title, or
    directly if it looks like a `Work-Item` id (`WI-NNNN`) from BACKLOG.md/SPRINT.md, then confirm
    the resolved item with the user before claiming it.
  - Claim + start: `workitems claim <id> --owner <who>` then `workitems set-status <id> "In Progress"`.
    Resolve `<who>` from `git config user.name`; if that is unset, ask the user.
- **`[]` and no `docs/workitems/` directory** → still on prose. Read SPRINT.md to find/ask which
  story is next, as before. Emit one line: *"Tip: run `lift` to adopt the structured work-item store."*
- **`[]` but `docs/workitems/` exists** → adopted store, just empty right now (e.g. between
  sprints). Treat as adopted: use the CLI, not the prose fallback.

See Manual/WORKITEMS.md §8 for the full guard rationale and the status-verb mapping.

## Flow

### 1. RED – Write failing tests
`/p5-impl-red $ARGUMENTS` – Writes unit tests before production code exists. Tests must fail.

### 2. GREEN – Minimal production code
`/p5-impl-green $ARGUMENTS` – Writes the minimal code that makes the tests green.

### 3. REFACTOR – Clean up code
`/p5-impl-refactor $ARGUMENTS` – Improves code quality without changing behavior.

## Notes
- Execute each step individually and check the result before the next one starts
- If errors occur in GREEN: go back to RED and review/adjust tests
- On completion, using the same guard result from step 0:
  - Structured store: `workitems set-status <id> "In Review"` then
    `workitems append-result <id> <PR-link>`.
  - Prose fallback: update SPRINT.md — mark story as "In Review".
- Once wired, item status is never hand-edited in SPRINT.md/BACKLOG.md — those are planning views
  (Manual/WORKITEMS.md §8).

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
