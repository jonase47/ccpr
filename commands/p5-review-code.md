# /p5-review-code – Check Code Quality

Checks code for quality, clean code, logic errors and test coverage. Delivers review findings with severity level.

## Argument: $ARGUMENTS = [File/module/feature name]

If provided: Review the named code area.
If not provided: Ask which code should be reviewed.

## Prerequisites
- Feature implemented (after `/p5-impl-refactor` or directly after implementation)

## Agent
- **Type**: code-reviewer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and provides inline:
- From src/: the code to be reviewed (affected files/functions only)
- From tests/: the corresponding tests
- From ARCHITECTURE.md: relevant architecture guidelines (affected section only)

## Prompt Template
> **Goal**: Code review for: [Feature/Module]
>
> **Code**:
> [inline from src/]
>
> **Tests**:
> [inline from tests/]
>
> **Output Format**:
> Table with max. 15 findings:
> | # | Severity | Area | Finding | Suggestion |
> |---|---|---|---|---|
> | 1 | CRITICAL/HIGH/NOTE | File:Line | Description | Fix suggestion |
>
> Overall rating: MERGE-READY | MERGE-AFTER-FIXES | REWORK
>
> **Constraints**:
> - Only check code quality, logic, tests – NO security analysis (separate sub-skill)
> - Severity levels: CRITICAL (merge blocker), HIGH (should be fixed), NOTE (optional)
> - No style nitpicks if code conventions are followed

## Orchestrator Checkpoint
- [ ] Findings are concrete and traceable?
- [ ] Severity levels assigned consistently?
- [ ] Overall rating matches the findings?

## Output
- Review findings as table (documented in SPRINT.md or reviews/)

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
