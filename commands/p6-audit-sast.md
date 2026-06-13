# /p6-audit-sast – Static Code Analysis

Checks source code for injection vulnerabilities, insecure cryptography, secrets in code, and insecure error handling.

## Argument: $ARGUMENTS = [module/file/entire codebase]

If provided: Focus SAST on the specified area.
If not provided: Check the entire source code.

## Prerequisites
- Source code present in src/

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- From src/: The code to be checked (affected files only)
- From SECURITY.md: Developer checklist (security-relevant points)

## Prompt Template
> **Goal**: Static code analysis (SAST) for: [area]
>
> **Code**:
> [inline from src/]
>
> **Output Format**:
> Table with max. 15 findings:
> | # | Severity | Category | File:Line | Finding | Recommendation |
> |---|---|---|---|---|---|
>
> Categories: Injection, Cryptography, Secrets, Error Handling, Logging
>
> **Constraints**:
> - Static analysis ONLY – no runtime test, no pentest
> - Focus on OWASP Top 10
> - No style findings, security-relevant issues only

## Orchestrator Checkpoint
- [ ] All source code files checked?
- [ ] Findings are specific (file + line)?

## Write Detail File
Write the result to `docs/quality/audit_sast.md` (overwrite). Frontmatter:

```yaml
---
phase: P6
subskill: audit-sast
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Findings` (SAST table with file/line/severity), `## Severity Summary`.

## Update Sub-Index
Update `docs/quality/AUDIT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[audit_sast.md](audit_sast.md)` with status `complete`.
- Lift any High/Critical SAST finding into **Open Risks**.

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
