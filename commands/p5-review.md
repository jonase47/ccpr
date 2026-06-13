# /p5-review – Code Review

Conducts a structured code review: first code quality, then security. Each dimension is its own sub-skill.

## Argument: $ARGUMENTS = [File/module/feature name]

If provided: Review the named code area.
If not provided: Read SPRINT.md and ask which code should be reviewed.

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
- Update SPRINT.md after completion: mark story as "Approved" or "Back to Dev"
- Document review results in reviews/ or SPRINT.md

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
