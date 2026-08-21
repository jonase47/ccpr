# /p3-infra-teststrategy – Define Test Strategy

Defines test levels, test tools, coverage targets and critical test paths.

## Argument: $ARGUMENTS = [Focus, e.g. "E2E", "Unit Tests", "Coverage"]

If provided: Deep-dive the named area.
If not provided: Create complete test strategy.

## Prerequisites
- ARCHITECTURE.md and TECH_STACK.md exist
- FEATURES.md with user journeys known

## Agent
- **Type**: qa-tester
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From FEATURES.md: Must-Have features (short list)
- From ARCHITECTURE.md: Modules and layers
- From TECH_STACK.md: Technologies in use (for tool recommendations)
- From USER_JOURNEYS.md: Critical flows (short list)

## Prompt Template
> **Goal**: Define test strategy for the project. Focus: $ARGUMENTS
>
> **Context**:
> [inline from FEATURES.md, ARCHITECTURE.md, TECH_STACK.md]
>
> **Output Format**:
> 1. Test levels: Table | Level | What is tested | Who executes |
> 2. Test tools: Table | Level | Tool | Justification |
> 3. Coverage target: unit test coverage in % with justification (1 sentence)
> 4. Critical test paths: Table | Flow | Test Level | Priority |
> 5. Definition of Done for tests (max. 5 items)
>
> **Constraints**:
> - ONLY test strategy, NO infrastructure, NO monitoring
> - Max. 4 test levels
> - Max. 6 critical test paths
> - Tools must be compatible with the tech stack

## Orchestrator Checkpoint
- [ ] All test levels (unit, integration, E2E, exploratory) covered?
- [ ] Tools compatible with the tech stack?

## Write Detail File
Write the result to `docs/architecture/TESTSTRATEGY.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: infra-teststrategy
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Test Levels`, `## Test Tools`, `## Coverage Target`, `## Critical Test Paths`, `## Definition of Done for Tests`.

(File replaces the legacy `TEST_STRATEGY.md` name — keep the new `TESTSTRATEGY.md` going forward.)

## Update Sub-Index
Update `docs/architecture/INFRA.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[TESTSTRATEGY.md](TESTSTRATEGY.md)` with status `complete`.
- Lift the coverage target and any chosen test tool into **Key Decisions** of the sub-index.
- Do not edit `ARCHITECTURE.md` directly.

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
