# /p5-review-security – Check Security Checklist

Checks code against the security checklist. Focus on OWASP Top 10, injection, auth and data handling.

## Argument: $ARGUMENTS = [File/module/feature name]

If provided: Check the named code area.
If not provided: Ask which code should be checked.

## Prerequisites
- Feature implemented
- SECURITY.md with developer checklist available

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and provides inline:
- From src/: the code to be checked (affected files/functions only)
- From SECURITY.md: developer security checklist (relevant points only)

## Prompt Template
> **Goal**: Security review for: [Feature/Module]
>
> **Code**:
> [inline from src/]
>
> **Security Checklist**:
> [inline from SECURITY.md]
>
> **Output Format**:
> Table with max. 10 findings:
> | # | Severity | OWASP Category | Finding | Recommendation |
> |---|---|---|---|---|
> | 1 | CRITICAL/HIGH/NOTE | e.g. A03:Injection | Description | Fix |
>
> Checklist status:
> | Checklist Item | Status |
> |---|---|
> | [Item from SECURITY.md] | OK / FINDING / N/A |
>
> **Constraints**:
> - Only check security – NO code quality (separate sub-skill)
> - For minimal scope (no user input, no backend): brief confirmation is sufficient
> - Focus on actual risks, not theoretical scenarios

## Orchestrator Checkpoint
- [ ] All checklist items evaluated?
- [ ] CRITICAL findings are actually exploitable?
- [ ] Recommendations are actionable?

## Output
- Security findings as table (documented in SPRINT.md or reviews/)

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
