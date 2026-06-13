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
Orchestrator reads in advance and delivers inline:
- From USER_JOURNEYS.md: The journey to be tested (exact steps)
- From TEST_STRATEGY.md: Defined critical E2E paths

## Prompt Template
> **Goal**: Run E2E tests for: [journey/feature]
>
> **User Journey**:
> [inline from USER_JOURNEYS.md]
>
> **Output Format**:
> A step-by-step table per journey:
> | Step | Action | Expected | Actual | Status |
> |---|---|---|---|---|
>
> Overall result: PASSED / FAILED
>
> **Constraints**:
> - E2E tests ONLY (no unit, no integration tests)
> - Test from the user's perspective, not from the code perspective
> - Max. 5 journeys per run

## Orchestrator Checkpoint
- [ ] All critical paths from TEST_STRATEGY.md covered?
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
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
