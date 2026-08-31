---
disable-model-invocation: true
---
# /p5-review – Code Review

Conducts a structured code review: first code quality, then security. Each dimension is its own sub-skill.

## Argument: $ARGUMENTS = [File/module/feature name]

If provided: Review the named code area.
If not provided: resolve the story via the work-item adoption guard below (falls back to reading
SPRINT.md and asking, if the project is still on prose).

## 0. Work-item adoption guard (ADR-0002 §8)

Run `python3 ~/.claude/scripts/workitems.py list` **and** explicitly check whether the
`docs/workitems/` directory exists (e.g. `ls docs/workitems/`). Both signals are required — `list`
returns the identical `[]` for an adopted-but-empty store and a never-adopted project; only the
directory's existence tells them apart.
- **Non-empty list** → the project uses the structured store. Use the CLI for all item state below:
  - No `$ARGUMENTS`: resolve the story via `workitems list --status "In Review"`, pick the first
    item in the returned array, ask for confirmation.
  - `$ARGUMENTS` provided: resolve `<id>` by matching `$ARGUMENTS` against a story's title, or
    directly if it looks like a `Work-Item` id (`WI-NNNN`) from BACKLOG.md/SPRINT.md, then confirm
    the resolved item with the user before proceeding.
- **Empty list, but `docs/workitems/` exists** → the store is adopted; an empty `In Review` list is
  a real result — nothing is currently awaiting code review (not an error, not a reason to search
  prose instead). If no `$ARGUMENTS` was given either, say so explicitly and ask the user which
  story to review, rather than silently falling back to SPRINT.md.
- **Empty list and no `docs/workitems/` directory** → not adopted, still on prose. Read SPRINT.md to
  find/ask which story is next, as before. Emit one line: *"Tip: run `lift` to adopt the structured
  work-item store."*

See Manual/WORKITEMS.md §8 for the full guard rationale, the directory-check requirement, and the
status-verb mapping.

## Flow

### 1. Check code quality
`/p5-review-code $ARGUMENTS` – Checks clean code, logic, tests, architecture conformity.

### 2. Check security
`/p5-review-security $ARGUMENTS` – Checks security checklist, OWASP, injection risks.

### 3. Consolidation by Wingman

Start the **wingman** agent with the review results:
> Consolidate the results from code review and security review.

Use the wingman summary as the basis for presenting results to the user.

## Notes
- Both reviews can run in parallel (no dependency)
- For CRITICAL findings from either review: `/p5-bugfix` before acceptance
- On completion, using the same guard result from step 0:
  - Structured store: approved → `workitems set-status <id> "Waiting for Approval"` (acceptance
    pending); back to Dev → `workitems set-status <id> "In Progress"`.
  - Prose fallback: update SPRINT.md — mark story as "Approved" or "Back to Dev".
- Once wired, item status is never hand-edited in SPRINT.md/BACKLOG.md — those are planning views
  (Manual/WORKITEMS.md §8).
- Document review results in reviews/ or SPRINT.md

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
