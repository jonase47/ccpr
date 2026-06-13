# /p5-implement – Implement Feature (TDD Cycle)

Implements a feature in the TDD cycle: Red → Green → Refactor. Each phase is its own sub-skill with a focused agent call.

## Argument: $ARGUMENTS = [Feature name/Story ID]

If provided: Implement the named feature.
If not provided: Read SPRINT.md and ask which feature should be implemented next.

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
- Update SPRINT.md after completion: mark story as "In Review"

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
