---
disable-model-invocation: true
---
# /p6-audit-auth – Review Auth Implementation

Compares the auth implementation against the requirements in SECURITY.md: JWT, sessions, RBAC, password hashing.

## Argument: $ARGUMENTS = [auth module/area]

If provided: Focus on the specified auth area.
If not provided: Check the entire auth implementation.

## Prerequisites
- Auth code implemented
- SECURITY.md with auth requirements

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- From src/: Auth-relevant code (login, session, middleware, token handling)
- From SECURITY.md: Auth requirements and specification

## Prompt Template
> **Goal**: Check auth implementation against SECURITY.md for: [area]
>
> **Auth Code**:
> [inline from src/]
>
> **Auth Requirements**:
> [inline from SECURITY.md]
>
> **Output Format**:
> Checklist table:
> | # | Requirement | Implemented? | Finding |
> |---|---|---|---|
>
> Overall assessment: OK / FINDINGS / CRITICAL
>
> **Constraints**:
> - Auth check ONLY – no SAST, no dependencies
> - Compare target (SECURITY.md) vs. actual (code)
> - For missing auth system: brief confirmation "N/A" is sufficient

## Orchestrator Checkpoint
- [ ] All auth requirements from SECURITY.md checked?
- [ ] Findings are actionable?

## Write Detail File
Write the result to `docs/quality/audit_auth.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P6
subskill: audit-auth
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Findings` (the checklist), `## Severity Summary`.

## Update Sub-Index
Update `docs/quality/AUDIT.md` (the security-audit sub-index, created by `/p6-audit` if missing):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[audit_auth.md](audit_auth.md)` with status `complete` (or `needs-rework`).
- Lift any High/Critical auth finding into **Open Risks** of the sub-index.
- Do not edit `QA.md` directly.

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
