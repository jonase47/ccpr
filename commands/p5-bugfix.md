# /p5-bugfix – Analyze & Fix Bug

Systematically analyzes a found bug, identifies the root cause and fixes it with an accompanying regression test. Goal: the bug is fixed, secured by a test, and cannot be silently reintroduced.

## Argument: $ARGUMENTS = [Bug description/ticket ID]

If provided: Analyze and fix the described bug or the bug with the named ID.
If not provided: resolve the bug via the work-item adoption guard below (falls back to reading
SPRINT.md or the latest review/acceptance protocols and asking, if the project is still on prose).
Do not make assumptions.

## 0. Work-item adoption guard (ADR-0002 §8)

A bug is a work item too (`--type fix`) — whether it was found during `/p5-review`/`/p5-acceptance`
(the story itself is already `In Progress`, sent back by the reviewing gate) or reported standalone
(no existing item yet).

Run `python3 ~/.claude/scripts/workitems.py list`.
- **Non-empty array** → the project uses the structured store. Use the CLI for all item state below:
  - No `$ARGUMENTS`: resolve the bug via `workitems list --status "In Progress"` (items sent back to
    dev by a review/acceptance rejection land here); if more than one, ask which to fix — do not
    assume.
  - `$ARGUMENTS` provided: resolve `<id>` by matching `$ARGUMENTS` against a story's title, or
    directly if it looks like a `Work-Item` id (`WI-NNNN`) from BACKLOG.md/SPRINT.md, then confirm
    with the user. If it matches no existing item (a standalone bug report, not yet tracked),
    create it first: `workitems create --title "<bug summary>" --type fix --description
    "$ARGUMENTS"` (unfiltered `list` duplicate-title check first — trim + casefold — so a re-run
    never recreates the same bug item).
- **`[]` and no `docs/workitems/` directory** → still on prose. Read SPRINT.md to find/ask which
  bug is next, as before. Emit one line: *"Tip: run `lift` to adopt the structured work-item store."*
- **`[]` but `docs/workitems/` exists** → adopted store, just empty right now. Treat as adopted: use
  the CLI, not the prose fallback.

See Manual/WORKITEMS.md §8 for the full guard rationale and the status-verb mapping.

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
Using the same guard result from step 0:
- Structured store: **default to `workitems set-status <id> "In Review"`** — bugs get code review
  like any other story, and this project ships no designated no-review hotfix path today. Only use
  `workitems set-status <id> "Waiting for Approval"` instead if a documented hotfix procedure
  explicitly exempts this fix from code review (e.g. a project-specific emergency-patch policy
  recorded in RUNBOOK.md/CONTRIBUTING.md) — absent such a documented exemption, always `"In
  Review"`, never guess "this one looks minor enough to skip".
- Prose fallback: update SPRINT.md — mark bug as "Fixed".
If the bug has a broader impact, add a note to **RISKS.md**.
Once wired, item status is never hand-edited in SPRINT.md/BACKLOG.md — those are planning views
(Manual/WORKITEMS.md §8).

## Result

- Bug fix code with regression test
- Work item status updated (structured store) or **SPRINT.md** updated (bug status "Fixed", prose fallback)
- Next step: back to `/p5-acceptance` (re-run acceptance test for the affected feature) or `/p5-review` (if the fix was extensive)

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
