# /p3-arch-techstack – Tech Stack Decision

Selects the tech stack and justifies each technology decision.

## Argument: $ARGUMENTS = [Preference, e.g. "Vanilla JS", "React", "Single-File"]

If provided: Consider the preference and check its suitability.
If not provided: Recommend based on architecture and project requirements.

## Prerequisites
- Component diagram from `/p3-arch-components` available

## Agent
- **Type**: system-architekt
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: Component diagram (overview only)
- From CLAUDE.md: Briefing preference for tech stack
- From VALIDATION.md: PoC tech findings (if available)

## Prompt Template
> **Goal**: Select tech stack for the project. Preference: $ARGUMENTS
>
> **Architecture**:
> [inline component diagram]
>
> **Output Format**:
> Table: | Area | Technology | Justification | Alternatives |
> Areas: Frontend, Backend, Database, Build Tool, Hosting, External Services
>
> **Constraints**:
> - ONLY tech stack, NO architecture changes
> - Justification max. 1 sentence per technology
> - Max. 8 rows

## Orchestrator Checkpoint
- [ ] Every technology has a justification?
- [ ] Briefing preference considered or explicitly rejected with reasoning?

## Write Detail File
Write the result to `docs/architecture/TECH_STACK.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: arch-techstack
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Stack Overview` (the table Area / Technology / Justification / Alternatives), `## Open Trade-offs` (decisions still to confirm in implementation).

## Update Phase Index
Update `docs/architecture/ARCHITECTURE.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[TECH_STACK.md](TECH_STACK.md)` with status `complete`.
- Lift load-bearing tech-stack decisions into **Key Decisions** (1 line each, e.g. `- Frontend: SwiftUI → see TECH_STACK.md`).

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
