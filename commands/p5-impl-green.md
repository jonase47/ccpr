# /p5-impl-green – Minimal Code for Green Tests (GREEN)

Writes the minimal production code that makes the existing tests green. No over-engineering.

## Argument: $ARGUMENTS = [Feature name/Story ID]

If provided: Implement code for the named feature.
If not provided: Ask which feature should be implemented.

## Prerequisites
- `/p5-impl-red` completed (failing tests exist)

## Agent
- **Type**: senior-developer
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and provides inline:
- From tests/: the failing test files (complete)
- From ARCHITECTURE.md: affected modules, file structure (relevant section only)
- From SECURITY.md: security checklist (affected points only)

## Prompt Template
> **Goal**: Write minimal production code that makes all tests green for Story [ID]: [Title]
>
> **Failing Tests**:
> [inline from tests/]
>
> **Architecture Guidelines**:
> [inline from ARCHITECTURE.md]
>
> **Output Format**:
> - Production code file(s) in the src/ directory
> - At the end: summary of which files were created/changed
>
> **Constraints**:
> - ONLY as much code as needed to make tests green
> - No over-engineering, no anticipatory abstractions
> - Follow security checklist from SECURITY.md
> - All tests must be green after implementation

## Orchestrator Checkpoint
- [ ] All tests green?
- [ ] No unnecessary code written?
- [ ] Security checklist followed?
- [ ] Commit after GREEN: `feat: [Story-ID] [Description]`

## Output
- Production code file(s) in src/

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
