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
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
