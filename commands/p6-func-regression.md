---
disable-model-invocation: true
---
# /p6-func-regression – Run Regression Tests

Ensures that existing functionality has not been broken by new changes.

## Argument: $ARGUMENTS = [area/sprint]

If provided: Focus regression on the specified area.
If not provided: Test all areas affected by the latest changes.

## Prerequisites
- Existing automated tests present
- SPRINT.md with latest changes

## Agent
- **Type**: qa-tester
- **Model**: sonnet

## Context (Orchestrator prepares)
The **qa-tester** agent has no `Bash` (`agents/qa-tester.md`) — it cannot run the suite itself. The
orchestrator runs it first and hands the agent the result to analyze:
- From SPRINT.md: Which features/modules were changed most recently
- From tests/: Existing test files (file names + test case overview only)
- **Test-run output**: run `~/.claude/scripts/run-tests.sh [area] [projectdir]` scoped to the areas
  affected by recent changes (or the full suite if `$ARGUMENTS` was not given) and capture its JSON
  output — this is the agent's sole source for pass/fail counts below

## Prompt Template
> **Goal**: Analyze the results below – identify whether recent changes have broken existing
> functionality. Every number in your report must be transcribed from the provided results, never
> invented or estimated.
>
> **Recent Changes**:
> [inline from SPRINT.md]
>
> **Results** (already produced by the orchestrator, via `scripts/run-tests.sh`):
> [inline JSON: framework, summary.total/passed/failed, failures[]]
>
> **No-summary fallback**: if the results carry no `summary` field (`run-tests.sh`'s `npm test`
> path returns `{"framework":"npm-test","raw_output":…}`, and an undetected framework returns
> `{"framework":"unknown","error":…}`) — do not produce any pass/fail count. Mark every row
> "Manually Verified" / "No parseable automated result" instead, and say so explicitly in the
> summary.
>
> **Output Format**:
> | # | Test Area | Total Tests | Passed | Failed | Regressions |
> |---|---|---|---|---|---|
> (Total/Passed/Failed transcribed from the results' `summary` — never estimated. No `summary`
> present → "Manually Verified" / "No parseable automated result" per the fallback above, not a
> number)
>
> New regressions (if any, derived from the `failures[]` entries):
> | # | Regression | Affected Feature | Suspected Cause |
> |---|---|---|---|
>
> **Constraints**:
> - Analyze the provided results ONLY — no new test files, no independent suite execution
> - Focus on areas affected by recent changes
> - Assign each regression clearly to a change

## Orchestrator Checkpoint
- [ ] Test-run output captured and passed to the agent before delegation?
- [ ] Regressions clearly documented and assigned?

## Write Detail File
Write the result to `docs/quality/func_regression.md` (overwrite). Frontmatter:

```yaml
---
phase: P6
subskill: func-regression
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Test Results` (table), `## Regressions Detected`.

## Update Sub-Index
Update `docs/quality/FUNCTIONAL.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[func_regression.md](func_regression.md)` with status `complete`.
- Lift any newly detected regression into **Open Risks** with assignment.

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
