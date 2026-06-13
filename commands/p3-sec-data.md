# /p3-sec-data – Data Security Concept

Defines encryption (transit/rest), secrets management and backup security.

## Argument: $ARGUMENTS = [Focus, e.g. "Encryption", "Secrets", "Backup"]

If provided: Deep-dive the named area.
If not provided: Create complete data security concept.

## Prerequisites
- ARCHITECTURE.md and threat model exist
- DATA_MODEL.md exists (if database is present)

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From SECURITY.md: Threat model (information disclosure rows)
- From DATA_MODEL.md: Data fields requiring protection (if available)
- From TECH_STACK.md: Database/hosting in use

## Prompt Template
> **Goal**: Define data security measures for the project.
>
> **Context**:
> [inline from SECURITY.md, DATA_MODEL.md]
>
> **Output Format**:
> 1. Encryption in transit: TLS version, HSTS (1-2 sentences)
> 2. Encryption at rest: Table | Data Field | Encryption | Method |
> 3. Secrets management: where are secrets stored, how are they rotated?
> 4. Backup security: encryption, retention
>
> **Constraints**:
> - ONLY data security, NO auth concept, NO API security
> - Measures proportional to project risk
> - Max. 8 encrypted fields in the table

## Orchestrator Checkpoint
- [ ] All sensitive fields from DATA_MODEL.md covered?
- [ ] Secrets strategy concrete (not just "use a vault")?

## Write Detail File
Write the result to `docs/architecture/DATA_SECURITY.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: sec-data
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Encryption in Transit`, `## Encryption at Rest` (the field/encryption/method table), `## Secrets Management`, `## Backup Security`.

## Update Sub-Index
Update `docs/architecture/SECURITY.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[DATA_SECURITY.md](DATA_SECURITY.md)` with status `complete`.
- Lift the secrets-management decision and any field that is *not* encrypted-at-rest despite being sensitive into **Key Decisions** / **Open Risks** of the sub-index.
- Do not edit `ARCHITECTURE.md` directly.

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for permitted transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
