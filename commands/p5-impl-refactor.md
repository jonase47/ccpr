# /p5-impl-refactor – Clean Up Code (REFACTOR)

Improves code quality without changing behavior. All tests must continue to pass.

## Argument: $ARGUMENTS = [Feature name/Story ID]

If provided: Refactor the code of the named feature.
If not provided: Ask which feature should be refactored.

## Prerequisites
- `/p5-impl-green` completed (all tests green)

## Agent
- **Type**: senior-developer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and provides inline:
- From src/: the production code written in GREEN (affected files only)
- From tests/: the corresponding tests (affected files only)

## Prompt Template
> **Goal**: Refactor the production code for Story [ID]: [Title] – improve quality, preserve behavior
>
> **Current Code**:
> [inline from src/]
>
> **Corresponding Tests**:
> [inline from tests/]
>
> **Output Format**:
> - Changed file(s) in src/
> - At the end: list of refactoring measures (max. 10 lines)
>
> **Constraints**:
> - Do NOT introduce new behavior
> - All tests MUST continue to pass
> - Check: DRY, clear naming, no magic numbers, no unnecessary complexity
> - Inline comments only for non-obvious decisions

## Orchestrator Checkpoint
- [ ] All tests still green?
- [ ] No new behavior introduced?
- [ ] Code actually more readable/maintainable than before?
- [ ] Commit after REFACTOR: `refactor: [Description]`

## Output
- Refactored code in src/

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
