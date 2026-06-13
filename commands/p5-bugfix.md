# /p5-bugfix – Analyze & Fix Bug

Systematically analyzes a found bug, identifies the root cause and fixes it with an accompanying regression test. Goal: the bug is fixed, secured by a test, and cannot be silently reintroduced.

## Argument: $ARGUMENTS = [Bug description/ticket ID]

If provided: Analyze and fix the described bug or the bug with the named ID.
If not provided: Read SPRINT.md or the latest review/acceptance protocols and ask which bug should be fixed. Do not make assumptions.

## Execution

### 1. Read Context
Read the following files (if available):
- **SPRINT.md** (sprint context, known open bugs)
- **reviews/** or **tests/** (review or acceptance test protocol with bug description)
- Relevant source code files (derive from bug description)
- **ARCHITECTURE.md** (to understand the affected area)

### 2. Delegation to Debugger Agent (Lead)
Delegate root cause analysis to the **debugger** agent:

> Analyze the following bug: **$ARGUMENTS**
> Context: [Insert bug description from review/acceptance protocol, name affected files]
>
> **A. Reproduction**
> - Describe the exact steps to reproduce the bug
> - What is the expected behavior? What happens instead?
> - Under which conditions does the bug occur? Under which does it not?
>
> **B. Root Cause Analysis**
> - Identify the exact cause in the code (file, line, function)
> - Why does the error occur? (Logic error, missing validation, race condition, etc.)
> - Was there a missing test that could have prevented this bug?
> - Is this bug possibly present in multiple places in the code?
>
> **C. Fix Strategy**
> - What change is the minimal, correct fix?
> - Are there risks with the fix – could it affect other areas?
> - What regression test must be written?

### 3. Delegation to Senior-Developer Agent (Support)
Delegate fix implementation to the **senior-developer** agent:

> Implement the fix for the following bug, based on the debugger's analysis: **$ARGUMENTS**
> Root cause from debugger analysis: [Insert root cause]
> Fix strategy: [Insert fix strategy]
>
> 1. **Regression test first**: Write a test that reproduces the bug and fails (Red)
> 2. **Implement fix**: Fix the bug with the minimal, correct fix (Green)
> 3. **All tests green**: Ensure all existing tests continue to pass
> 4. **Brief fix description**: What was changed and why?

### 4. Commit & Document Result
Commit after fix: `fix: [Bug-ID] [Description]` (build + tests must be green).
Supplement the original review or acceptance test protocol with the fix status.
Update **SPRINT.md**: mark bug as "Fixed".
If the bug has a broader impact, add a note to **RISKS.md**.

## Result

- Bug fix code with regression test
- **SPRINT.md** updated (bug status "Fixed")
- Next step: back to `/p5-acceptance` (re-run acceptance test for the affected feature) or `/p5-review` (if the fix was extensive)

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
