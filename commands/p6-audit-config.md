---
disable-model-invocation: true
---
# /p6-audit-config – Review Infrastructure & Configuration

Checks security headers, CORS, DB access, secrets management, and server configuration.

## Argument: $ARGUMENTS = [configuration area]

If provided: Focus on the specified area.
If not provided: Check the entire configuration.

## Prerequisites
- Deployment configuration present
- SECURITY.md with infrastructure requirements

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- Configuration files: .env.example, Docker config, server config, etc.
- From src/: Security header configuration, CORS setup
- From SECURITY.md: Infrastructure requirements

## Prompt Template
> **Goal**: Check infrastructure and configuration security
>
> **Configuration**:
> [inline from config files]
>
> **Output Format**:
> Checklist:
> | # | Check Point | Status | Finding |
> |---|---|---|---|
> | 1 | Security Headers (CSP, HSTS, X-Frame) | OK/FINDING/N/A | ... |
> | 2 | CORS configuration | OK/FINDING/N/A | ... |
> | 3 | DB access (least privilege) | OK/FINDING/N/A | ... |
> | 4 | Secrets management | OK/FINDING/N/A | ... |
>
> **Constraints**:
> - Configuration check ONLY – no code review, no dependencies
> - For static sites without a server: brief confirmation "N/A" is sufficient
> - Focus on production configuration

## Orchestrator Checkpoint
- [ ] All infrastructure points from SECURITY.md checked?
- [ ] Findings with concrete fix recommendation?

## Write Detail File
Write the result to `docs/quality/audit_config.md` (overwrite). Frontmatter:

```yaml
---
phase: P6
subskill: audit-config
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Findings`, `## Severity Summary`.

## Update Sub-Index
Update `docs/quality/AUDIT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[audit_config.md](audit_config.md)` with status `complete`.
- Lift any High/Critical config finding into **Open Risks** of the sub-index.

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
