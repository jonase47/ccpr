# /p3-arch-adr – Write Architecture Decision Records

Documents all significant architectural decisions as ADRs.

## Argument: $ARGUMENTS = [Specific decision, e.g. "ADR-001 Monolith"]

If provided: Write ADR for the named decision.
If not provided: Create ADRs for all open decisions from architecture and tech stack.

## Prerequisites
- ARCHITECTURE.md and TECH_STACK.md exist

## Agent
- **Type**: system-architekt
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: Architectural decisions made (short list)
- From TECH_STACK.md: Technology decisions with alternatives

## Prompt Template
> **Goal**: Write ADRs for all significant architectural decisions.
>
> **Decisions**:
> [inline from ARCHITECTURE.md + TECH_STACK.md]
>
> **Output Format**:
> One file per ADR with:
> - Title, date, status (accepted)
> - Context (1-2 sentences)
> - Options (enumeration)
> - Decision (1 sentence)
> - Justification (1-2 sentences)
> - Consequences (pros/cons as list)
>
> **Constraints**:
> - Max. 6 ADRs
> - Only decisions with real alternatives (no trivial decisions)
> - Numbering: ADR-001, ADR-002, etc.

## Orchestrator Checkpoint
- [ ] Every ADR has context, options and justification?
- [ ] No redundant ADRs?

## Output
- ADR/ directory with one file per ADR

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
