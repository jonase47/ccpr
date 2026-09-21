---
disable-model-invocation: true
---
# /p6-func-e2e – E2E Tests for Critical Paths

Tests critical user journeys end-to-end – from start to the expected final result.

## Argument: $ARGUMENTS = [journey/feature]

If provided: Test the specified journey.
If not provided: Ask about the paths to be tested.

## Prerequisites
- Integration tests passed (`/p6-func-integration`)
- USER_JOURNEYS.md and TEST_STRATEGY.md present

## Agent
- **Type**: qa-tester
- **Model**: sonnet

## Context (Orchestrator prepares)
The **qa-tester** agent has no `Bash` (`agents/qa-tester.md`) — it can design and write E2E test
files (it has `Write`/`Edit`) but cannot execute them. That splits this command into two steps: the
agent designs the tests first, then the orchestrator runs them and hands the results back for
analysis. Prepared before step 1:
- From USER_JOURNEYS.md: The journey to be tested (exact steps)
- From TEST_STRATEGY.md: Defined critical E2E paths

## Prompt Template

### Step 1: Design & write the tests (qa-tester)
> **Goal**: Design and write E2E tests for: [journey/feature]. Do not claim any test has passed or
> failed at this stage — results come from step 2 below, run by the orchestrator.
>
> **User Journey**:
> [inline from USER_JOURNEYS.md]
>
> **Output Format**:
> A step-by-step table per journey:
> | Step | Action | Expected |
> |---|---|---|
> Plus the path(s) of the test file(s) written.
>
> **Constraints**:
> - E2E tests ONLY (no unit, no integration tests)
> - Test from the user's perspective, not from the code perspective
> - Max. 5 journeys per run

### Step 2: Execute (orchestrator, not the agent)
Run `~/.claude/scripts/run-tests.sh [new E2E test path] [projectdir]` against the file(s) step 1
wrote and capture the JSON result.

### Step 3: Report (qa-tester analyzes the results)
> **Goal**: Fill in the Actual/Status columns for the journey table from step 1, using only the
> results below — transcribed, never estimated.
>
> **Results** (from `scripts/run-tests.sh`, already executed by the orchestrator):
> [inline JSON: framework, summary.total/passed/failed, failures[]]
>
> **Output Format**:
> The step 1 table, extended:
> | Step | Action | Expected | Actual | Status |
> |---|---|---|---|---|
>
> Overall result: PASSED / FAILED (derived from the results' `summary.failed` count)

## Orchestrator Checkpoint
- [ ] All critical paths from TEST_STRATEGY.md covered?
- [ ] Step 2 actually ran before step 3 was delegated?
- [ ] Failed steps clearly documented?

## Write Detail File
Write the result to `docs/quality/func_e2e.md` (overwrite). Frontmatter:

```yaml
---
phase: P6
subskill: func-e2e
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Test Results` (table per journey), `## Failures Summary`.

## Update Sub-Index
Update `docs/quality/FUNCTIONAL.md` (the functional-testing sub-index, created by `/p6-functional` if missing):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[func_e2e.md](func_e2e.md)` with status `complete` (or `needs-rework` if blocking failures exist).
- Lift any blocking journey failure into **Open Risks** of the sub-index.
- Do not edit `QA.md` directly.

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
