---
disable-model-invocation: true
---
# /p6-func-integration – Run Integration Tests

Tests the interaction between system components: API against DB, middleware chains, external services against mocks.

## Argument: $ARGUMENTS = [test area/feature]

If provided: Focus on the specified area.
If not provided: Ask about the test scope.

## Prerequisites
- Implementation complete (P5 done)
- TEST_STRATEGY.md present

## Agent
- **Type**: qa-tester
- **Model**: sonnet

## Context (Orchestrator prepares)
The **qa-tester** agent has no `Bash` (`agents/qa-tester.md`) — it can design and write integration
test files (it has `Write`/`Edit`) but cannot execute them. That splits this command into two steps:
the agent designs the tests first, then the orchestrator runs them and hands the results back for
analysis. Prepared before step 1:
- From TEST_STRATEGY.md: Integration test level, tools, scope
- From ARCHITECTURE.md: Component diagram, interfaces (relevant section only)
- From API_SPEC.md: Endpoints to be tested

## Prompt Template

### Step 1: Design & write the tests (qa-tester)
> **Goal**: Design and write integration tests for: [area]. Do not claim any test has passed or
> failed at this stage — results come from step 2 below, run by the orchestrator.
>
> **Components and Interfaces**:
> [inline from ARCHITECTURE.md / API_SPEC.md]
>
> **Output Format**:
> Table with max. 20 test cases:
> | # | Test Case | Components | Expected |
> |---|---|---|---|
> Plus the path(s) of the test file(s) written.
>
> **Constraints**:
> - Integration tests ONLY (no unit, no E2E)
> - Focus on interfaces between components
> - Test external services against mocks

### Step 2: Execute (orchestrator, not the agent)
Run `~/.claude/scripts/run-tests.sh [new integration test path] [projectdir]` against the file(s)
step 1 wrote and capture the JSON result.

### Step 3: Report (qa-tester analyzes the results)
> **Goal**: Fill in the Actual/Status columns for the table from step 1, using only the results
> below — transcribed, never estimated.
>
> **Results** (from `scripts/run-tests.sh`, already executed by the orchestrator):
> [inline JSON: framework, summary.total/passed/failed, failures[]]
>
> **Output Format**:
> The step 1 table, extended:
> | # | Test Case | Components | Expected | Actual | Status |
> |---|---|---|---|---|---|
>
> Summary (derived from the results' `summary`): X passed, Y failed

## Orchestrator Checkpoint
- [ ] All critical interfaces tested?
- [ ] Step 2 actually ran before step 3 was delegated?
- [ ] Failed tests are reproducible?

## Write Detail File
Write the result to `docs/quality/func_integration.md` (overwrite). Frontmatter:

```yaml
---
phase: P6
subskill: func-integration
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Test Results` (table), `## Failures Summary`.

## Update Sub-Index
Update `docs/quality/FUNCTIONAL.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[func_integration.md](func_integration.md)` with status `complete`.
- Lift any blocking integration failure into **Open Risks**.

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one command run has been measured adding 1021 B, ~20 % of the cap.
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
3. Only suggest commands that fit the current phase/sub-command status
4. If the current phase appears complete: recommend the gate
