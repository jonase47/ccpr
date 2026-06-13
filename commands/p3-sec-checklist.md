# /p3-sec-checklist – Developer Security Checklist

Creates a concrete checklist that every feature in phase 5 must fulfill.

## Argument: $ARGUMENTS = not applicable

Always creates the complete checklist based on the security architecture.

## Prerequisites
- SECURITY.md with threat model, auth concept, data security and API security

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From SECURITY.md: All previous sections (threat model, auth, data, API) – short version
- From TECH_STACK.md: Technologies in use (for tech-specific rules)

## Prompt Template
> **Goal**: Create developer security checklist for phase 5.
>
> **Security Architecture**:
> [short version from SECURITY.md]
>
> **Output Format**:
> Checklist with max. 15 items, grouped by:
> - [ ] Input & Output (validation, encoding, sanitization)
> - [ ] Auth & Session (if relevant)
> - [ ] Data & Secrets (encryption, no plain text)
> - [ ] Logging & Error Handling (do not log sensitive data)
> - [ ] Forbidden Practices (eval, innerHTML, secrets in code, etc.)
>
> **Constraints**:
> - ONLY checklist, NO new analyses
> - Every item must be concretely verifiable (yes/no)
> - Adapted to the actual tech stack

## Orchestrator Checkpoint
- [ ] Checklist covers all SECURITY.md sections?
- [ ] Items are verifiable (not vague)?

## Write Detail File
Write the result to `docs/architecture/CHECKLIST.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: sec-checklist
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Input & Output`, `## Auth & Session`, `## Data & Secrets`, `## Logging & Error Handling`, `## Forbidden Practices`.

## Update Sub-Index
Update `docs/architecture/SECURITY.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[CHECKLIST.md](CHECKLIST.md)` with status `complete`.
- Lift the existence of the checklist into **Key Decisions** of the sub-index (e.g. `- Developer security checklist ready for P5 → see CHECKLIST.md`).
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
