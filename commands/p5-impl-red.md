# /p5-impl-red – Write Failing Tests (RED)

Writes unit tests for a feature BEFORE production code exists. Tests must fail.

## Argument: $ARGUMENTS = [Feature name/Story ID]

If provided: Write tests for the named feature.
If not provided: Ask which feature should be tested.

## Prerequisites
- Story identified in SPRINT.md
- Acceptance criteria from BACKLOG.md known

## Agent
- **Type**: senior-developer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and provides inline:
- From BACKLOG.md: acceptance criteria of the story (exact lines)
- From ARCHITECTURE.md: affected modules/files (relevant section only)
- From TEST_STRATEGY.md: test naming convention and framework

## Prompt Template
> **Goal**: Write failing unit tests for Story [ID]: [Title]
>
> **Acceptance Criteria**:
> [inline from BACKLOG.md]
>
> **Affected Modules**:
> [inline from ARCHITECTURE.md]
>
> **Output Format**:
> - Test file(s) in the tests/ directory
> - Naming scheme: "should [behavior] when [condition]"
> - 1 test per acceptance criterion + most important edge cases
>
> **Constraints**:
> - Write ONLY tests, NO production code
> - Tests MUST fail (assert against not-yet-existing code)
> - Max. 15 test cases

## Orchestrator Checkpoint
- [ ] Tests cover all acceptance criteria?
- [ ] Tests actually fail (not due to syntax errors)?
- [ ] Test file is in the correct directory?

## Output
- Test file(s) in tests/

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
