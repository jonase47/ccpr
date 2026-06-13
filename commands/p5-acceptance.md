# /p5-acceptance – Acceptance Tests

Tests an implemented feature against its requirements from a user perspective: are all acceptance criteria met? Are edge cases handled correctly? The result is test findings that determine whether the feature counts as "Done".

## Argument: $ARGUMENTS = [Feature name/Story ID]

If provided: Test the named feature against its acceptance criteria.
If not provided: Read SPRINT.md and ask which feature should be tested. If context is missing, ask for the feature name or story ID.

## Execution

### 1. Read Context
Read the following files (if available):
- **BACKLOG.md** (acceptance criteria of the story – this is the test standard)
- **SPRINT.md** (sprint context and Definition of Done)
- **USER_JOURNEYS.md** (persona and journey context for realistic test scenarios)
- **UX_CONCEPT.md** (UI specifications for visual checks)
- **TEST_STRATEGY.md** (test levels and methods)

### 2. Delegation to QA-Tester Agent (Lead)
Delegate acceptance tests to the **qa-tester** agent:

> Run acceptance tests for the following feature: **$ARGUMENTS**
> Acceptance criteria from BACKLOG.md: [Insert all acceptance criteria of the story]
> Persona context from USER_JOURNEYS.md: [Insert relevant persona]
>
> **A. Acceptance Criteria Check**
> Check each acceptance criterion individually:
> | Criterion | Test Result | Finding |
> |---|---|---|
> | [Criterion 1] | Passed / Failed | [Description] |
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

Update **SPRINT.md**: story status to "Done" or back to "In Dev".

## Result

- **tests/ACCEPTANCE_[Feature].md** (test results per acceptance criterion)
- **SPRINT.md** updated (story status)
- If bugs found: next step is `/p5-bugfix`
- If Done: story is complete, take next story from SPRINT.md

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
