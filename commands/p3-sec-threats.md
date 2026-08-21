# /p3-sec-threats – Create STRIDE Threat Model

Analyzes the system according to the STRIDE model and identifies threats with countermeasures.

## Argument: $ARGUMENTS = [Focus area, e.g. "API", "Database", "Frontend"]

If provided: Focus STRIDE on the named area.
If not provided: Analyze the entire system.

## Prerequisites
- ARCHITECTURE.md with component diagram exists
- TECH_STACK.md exists

## Agent
- **Type**: security-master
- **Model**: opus

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: Component diagram and data flows
- From TECH_STACK.md: Technologies in use (short list)

## Prompt Template
> **Goal**: STRIDE threat model for: $ARGUMENTS
>
> **Architecture**:
> [inline from ARCHITECTURE.md]
>
> **Output Format**:
> Table: | STRIDE Category | Threat | Affected Component | Severity | Countermeasure | Status |
> Severity: Critical / High / Medium / Low
> Status: open / addressed
>
> **Constraints**:
> - ONLY threat model, NO auth concept, NO checklists
> - Max. 12 threats
> - Focus on realistic threats for the project type

## Orchestrator Checkpoint
- [ ] All 6 STRIDE categories covered?
- [ ] Severity levels plausible?

## Write Detail File
Write the result to `docs/architecture/THREATS.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: sec-threats
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## STRIDE Threat Model` (the table STRIDE Category / Threat / Component / Severity / Countermeasure / Status), `## Critical Threats Summary` (the open Critical/High items called out for the gate).

## Update Sub-Index
Update `docs/architecture/SECURITY.md` (the security sub-index, created by `/p3-security` if missing):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[THREATS.md](THREATS.md)` with status `complete`.
- Lift any open Critical threat into **Open Risks / Open Questions** of the sub-index (e.g. `- Critical: <threat> still open → see THREATS.md`).
- Do not edit the phase-level `ARCHITECTURE.md` directly — `/p3-security` rolls the sub-index summary up to the phase index.

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
