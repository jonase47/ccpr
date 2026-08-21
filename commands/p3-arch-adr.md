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
