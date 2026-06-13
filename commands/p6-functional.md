# /p6-functional – Integration, E2E & Regression Tests

Runs systematic functional tests at the system level. Each test level is a separate sub-skill.

## Argument: $ARGUMENTS = [test area/feature]

If provided: Test the specified area.
If not provided: Read TEST_STRATEGY.md and ask about the test scope.

## Flow

### 0. Ensure Sub-Index Exists
Make sure `docs/quality/FUNCTIONAL.md` exists as a **sub-index** with the standard header (Status / Last Updated / Key Decisions / Open Risks / Detail Files / Gate Notes — see `~/.claude/docs/PROJECT_PHASES.md`). If missing, create it with empty placeholders. The three `p6-func-*` sub-skills below each refresh their own row in this sub-index's **Detail Files** table.

### 1. Integration Tests
`/p6-func-integration $ARGUMENTS` – Tests the interaction between system components.

### 2. E2E Tests
`/p6-func-e2e $ARGUMENTS` – Tests critical user journeys end-to-end.

### 3. Regression Tests
`/p6-func-regression $ARGUMENTS` – Ensures that existing functionality has not been broken.

### 4. Roll Up Sub-Index to Phase Index
After all `p6-func-*` sub-skills have run, summarise the FUNCTIONAL sub-index into the phase index `docs/quality/QA.md`:
- Add an entry in the phase-index **Detail Files** table for `[FUNCTIONAL.md](FUNCTIONAL.md)` (the sub-index itself), status `complete` once all three sub-skill rows are `complete` (or `needs-rework`).
- Lift any blocking functional failure into the phase-index **Open Risks**.

## Notes
- Maintain order: Integration → E2E → Regression
- On integration failures: Fix first before starting E2E
- Detail files: `func_integration.md`, `func_e2e.md`, `func_regression.md` under the `FUNCTIONAL.md` sub-index

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
