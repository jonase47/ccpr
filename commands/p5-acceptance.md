---
disable-model-invocation: true
---
# /p5-acceptance – Acceptance Tests

Tests an implemented feature against its requirements from a user perspective: are all acceptance criteria met? Are edge cases handled correctly? The result is test findings that determine whether the feature counts as "Done".

## Argument: $ARGUMENTS = [Feature name/Story ID]

If provided: Test the named feature against its acceptance criteria.
If not provided: resolve the story via the work-item adoption guard below (falls back to reading
SPRINT.md and asking, if the project is still on prose). If context is missing, ask for the feature
name or story ID.

## 0. Work-item adoption guard (ADR-0002 §8)

Run `python3 ~/.claude/scripts/workitems.py list`.
- **Non-empty array** → the project uses the structured store. Use the CLI for all item state below:
  - No `$ARGUMENTS`: resolve the story via `workitems list --status "Waiting for Approval"`, pick
    the first item in the returned array, ask for confirmation. Acceptance criteria come from
    `workitems get <id>` (`description` field) instead of BACKLOG.md prose.
  - `$ARGUMENTS` provided: resolve `<id>` by matching `$ARGUMENTS` against a story's title, or
    directly if it looks like a `Work-Item` id (`WI-NNNN`) from BACKLOG.md/SPRINT.md, then confirm
    the resolved item with the user before proceeding.
- **`[]` and no `docs/workitems/` directory** → still on prose. Read SPRINT.md/BACKLOG.md to
  find/ask which story is next, as before. Emit one line: *"Tip: run `lift` to adopt the structured
  work-item store."*
- **`[]` but `docs/workitems/` exists** → adopted store, just empty right now (e.g. between
  sprints). Treat as adopted: use the CLI, not the prose fallback.

See `docs/adr/ADR-0002-workitem-backend-contract.md` for the adoption-guard rationale and the status vocabulary.

## Execution

### 1. Read Context
Read the following files (if available):
- **BACKLOG.md** (acceptance criteria of the story – this is the test standard)
- **SPRINT.md** (sprint context and Definition of Done)
- **USER_JOURNEYS.md** (persona and journey context for realistic test scenarios)
- **UX_CONCEPT.md** (UI specifications for visual checks)
- **TEST_STRATEGY.md** (test levels and methods)

The **qa-tester** agent has no `Bash` (`agents/qa-tester.md`) — it cannot execute the automated
suite itself. If the story's implementation carries automated tests (from P5's TDD cycle), run
`~/.claude/scripts/run-tests.sh [story scope] [projectdir]` and capture the JSON result before
delegating below; where no automated test covers a criterion, the agent verifies it by reading the
code and UX_CONCEPT.md instead (its own charter: "derived from user stories", never invented either
way).

### 2. Delegation to QA-Tester Agent (Lead)
Delegate acceptance verification to the **qa-tester** agent:

> Verify the following feature against its acceptance criteria: **$ARGUMENTS**
> Acceptance criteria from BACKLOG.md: [Insert all acceptance criteria of the story]
> Persona context from USER_JOURNEYS.md: [Insert relevant persona]
> Automated results (from `scripts/run-tests.sh`, already executed by the orchestrator, if any exist
> for this scope): [inline JSON, or "no automated coverage for this story"]
>
> **No-summary fallback**: if the results carry no `summary` field (`run-tests.sh`'s `npm test`
> path returns `{"framework":"npm-test","raw_output":…}`, and an undetected framework returns
> `{"framework":"unknown","error":…}`) — treat that criterion as if no automated coverage exists;
> do not produce a pass/fail count from it.
>
> **A. Acceptance Criteria Check**
> Check each acceptance criterion individually:
> | Criterion | Test Result | Finding |
> |---|---|---|
> | [Criterion 1] | Passed / Failed / Manually Verified / No parseable automated result | [Description] |
> Where an automated result with a `summary` exists for a criterion, transcribe Passed/Failed from
> it — never estimate. Where none exists (no coverage, or the no-summary fallback above), mark
> Manually Verified (or Failed) from your own code/UX review, or "No parseable automated result" if
> you cannot verify it manually either.
>
> **B. Happy Path Tests**
> - Test the standard flow from a user perspective completely
> - Use the relevant persona from USER_JOURNEYS.md as test context
> - Document each step and the expected vs. actual result
>
> **C. Edge Case Tests**
> Test edge cases and boundary values systematically:
> - Empty inputs / no data available
> - Maximum input lengths / boundary values
> - Invalid inputs / wrong format
> - Concurrent actions / race conditions (if relevant)
> - Behavior after network errors or timeouts (if relevant)
>
> **D. Error Case Tests**
> - Are errors communicated in an understandable way?
> - Does the application recover correctly from errors?
> - Are no technical error messages passed through to the user?
>
> **E. Overall Evaluation**
> - Done: All acceptance criteria passed, no critical bugs
> - Conditionally Done: Minor issues, but core function works correctly
> - Not Done: Acceptance criteria not met or critical bug found

### 3. Delegation to Senior-Developer Agent (Support)
Delegate the technical assessment of found issues to the **senior-developer** agent:

> Evaluate the QA tester's findings:
> 1. Are the bugs found reproducible? (Brief technical assessment)
> 2. How severe are they technically (surface-level cause or deep in the code)?
> 3. Prioritization: what must be fixed immediately, what can wait?

### 4. Document Result
Create **ACCEPTANCE_[Feature-Name].md** in the `tests/` directory (or supplement SPRINT.md):
- Test results per acceptance criterion
- List of found bugs with severity
- Overall evaluation: Done / Conditionally Done / Not Done

On completion, using the same guard result from step 0:
- Structured store: accepted → `workitems set-status <id> "Done"`; rejected →
  `workitems set-status <id> "In Progress"`.
- Prose fallback: update SPRINT.md — story status to "Done" or back to "In Dev".

Once wired, item status is never hand-edited in SPRINT.md/BACKLOG.md — those are planning views
(`docs/adr/ADR-0002-workitem-backend-contract.md`).

## Result

- **tests/ACCEPTANCE_[Feature].md** (test results per acceptance criterion)
- Work item status updated (structured store) or **SPRINT.md** updated (prose fallback)
- If bugs found: next step is `/p5-bugfix`
- If Done: story is complete, take next story from `workitems list --status "Ready"` (or SPRINT.md
  in prose fallback)

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-command status
4. If the current phase appears complete: recommend the gate
