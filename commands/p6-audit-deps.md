# /p6-audit-deps – Dependency Check

Checks all dependencies for known vulnerabilities (CVEs), outdated packages, and maintenance status.

## Argument: $ARGUMENTS = [package manager/area]

If provided: Focus on the specified area.
If not provided: Check all dependency files.

## Prerequisites
- Dependency files present (package.json, requirements.txt, go.mod, etc.)

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- Dependency files: package.json, lock files (direct dependencies only)
- From TECH_STACK.md: Technologies in use

## Prompt Template
> **Goal**: Dependency check – identify known vulnerabilities and outdated packages
>
> **Dependencies**:
> [inline from package.json / requirements.txt / etc.]
>
> **Output Format**:
> Table with max. 15 findings:
> | # | Package | Version | CVE/Issue | CVSS | Recommendation |
> |---|---|---|---|---|---|
>
> Summary: X critical, Y high, Z outdated
>
> **Constraints**:
> - Dependency analysis ONLY – no code review
> - Priority: CVSS >= 7.0
> - Also report outdated packages without active maintenance
> - For zero dependencies: a brief confirmation is sufficient

## Orchestrator Checkpoint
- [ ] All dependency files checked?
- [ ] Critical CVEs with concrete update recommendation?

## Write Detail File
Write the result to `docs/quality/audit_deps.md` (overwrite). Frontmatter:

```yaml
---
phase: P6
subskill: audit-deps
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Findings` (CVE table), `## Severity Summary`.

## Update Sub-Index
Update `docs/quality/AUDIT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[audit_deps.md](audit_deps.md)` with status `complete`.
- Lift any unpatched Critical CVE into **Open Risks**.

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
