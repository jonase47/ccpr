# /p6-audit-dsgvo – DSGVO (GDPR) Compliance Check

Compares the implementation against the DSGVO initial assessment: data subject rights, data minimisation, deletion deadlines, data processing agreements.

## Argument: $ARGUMENTS = [data category/area]

If provided: Focus on the specified area.
If not provided: Check full DSGVO compliance.

## Prerequisites
- DSGVO_INITIAL_ASSESSMENT.md present
- Implementation complete

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads in advance and delivers inline:
- From DSGVO_INITIAL_ASSESSMENT.md: Data protection obligations, data categories
- From src/: Code that processes personal data (relevant sections only)
- From ARCHITECTURE.md: Data flow diagram (relevant section only)

## Prompt Template
> **Goal**: DSGVO compliance check against DSGVO_INITIAL_ASSESSMENT.md
>
> **DSGVO Requirements**:
> [inline from DSGVO_INITIAL_ASSESSMENT.md]
>
> **Data-processing Code**:
> [inline from src/]
>
> **Output Format**:
> Checklist:
> | # | DSGVO Requirement | Implemented? | Finding |
> |---|---|---|---|
>
> Overall assessment: COMPLIANT / FINDINGS / NON-COMPLIANT
>
> **Constraints**:
> - DSGVO check ONLY – no technical security
> - For projects without personal data: brief confirmation is sufficient
> - Focus on actual data processing, not theoretical

## Orchestrator Checkpoint
- [ ] All points from DSGVO_INITIAL_ASSESSMENT.md checked?
- [ ] Findings correctly classified from a legal perspective?

## Write Detail File
Write the result to `docs/quality/audit_dsgvo.md` (overwrite). Frontmatter:

```yaml
---
phase: P6
subskill: audit-dsgvo
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Scope`, `## Findings` (DSGVO compliance checklist), `## Severity Summary`.

## Update Sub-Index
Update `docs/quality/AUDIT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[audit_dsgvo.md](audit_dsgvo.md)` with status `complete`.
- Lift any unmitigated Art. 6 / Art. 9 / Art. 13 finding into **Open Risks**.

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
