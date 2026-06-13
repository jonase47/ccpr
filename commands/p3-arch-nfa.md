# /p3-arch-nfa – Define Non-Functional Requirements

Defines the non-functional requirements (scalability, performance, availability, maintainability).

## Argument: $ARGUMENTS = [Focus, e.g. "Performance", "Scalability"]

If provided: Deep-dive the named NFR area.
If not provided: Create complete NFR overview.

## Prerequisites
- ARCHITECTURE.md and TECH_STACK.md exist

## Agent
- **Type**: system-architekt
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: Component diagram (short version)
- From CONCEPT.md: Target Audience and usage context
- From CLAUDE.md: Project frame (budget, timeline, hosting)

## Prompt Template
> **Goal**: Define non-functional requirements for the project.
>
> **Architecture Context**:
> [inline from ARCHITECTURE.md, CONCEPT.md]
>
> **Output Format**:
> Table: | NFR Area | Requirement | Metric | Target Value |
> Areas: Scalability, Availability, Performance, Maintainability, Security
>
> **Constraints**:
> - ONLY measurable requirements (no vague statements)
> - Max. 10 NFRs
> - Target values realistic to project frame (hobby vs. enterprise)

## Orchestrator Checkpoint
- [ ] Every NFR has a concrete metric and target value?
- [ ] NFRs appropriate to the project frame (not over-engineered)?

## Write Detail File
Write the result to `docs/architecture/NFR.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: arch-nfa
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Non-Functional Requirements` (the table NFR Area / Requirement / Metric / Target Value), optional `## Trade-offs` (which NFRs conflict and how the trade-off was resolved).

## Update Phase Index
Update `docs/architecture/ARCHITECTURE.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[NFR.md](NFR.md)` with status `complete`.
- Lift the most restrictive NFRs into **Open Risks / Open Questions** if any are flagged as hard (e.g. `- Availability: 99.9% target — single Hetzner node is the SPOF → see NFR.md`).

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
