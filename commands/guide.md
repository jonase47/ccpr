# /guide – Project Guide (Status, Skill Recommendation, Disambiguation)

Invokes the `project-guide` agent as the entry point for the current project:
structured status snapshot, prioritised next steps with skill/agent
recommendation, and disambiguation for unclear requests.

## Argument: $ARGUMENTS = [optional: concrete question / request]

- Without argument: status snapshot + 3 prioritised next steps.
- With argument: disambiguate the request and hand off to the matching domain
  agent, with 1–2 clarifying questions first if needed.

## Execution

1. **Work-item adoption guard (ADR-0002 §8)** — `project-guide` has no Bash access (by design, it's
   read-only via Read/Grep/Glob/Edit), so if the active phase is P4/P5, the orchestrator resolves
   this beforehand and passes the result in: run `python3 ~/.claude/scripts/workitems.py list`.
   - **Non-empty array** → the project uses the structured store. Also run `workitems list --status
     "Ready"` / `"In Progress"` / `"Done"` for the current sprint's item counts (e.g. "6/10 Done, 2
     In Progress, 2 Ready") — this is the SOURCE OF TRUTH for phase status, not SPRINT.md prose,
     which is only a generated view and can lag behind CLI-driven status changes made outside a
     `/p4-sprint`/`gate-p5` run.
   - **`[]` and no `docs/workitems/` directory** → still on prose. Derive sprint status from
     SPRINT.md as before.
   - **`[]` but `docs/workitems/` exists** → adopted store, just empty right now. Report it as such
     (e.g. "0 items in the current sprint"), don't fall back to prose.
2. Start the `project-guide` agent via the Task tool, passing the resolved item counts (if any) as
   part of its context alongside the request.
3. Pass the argument (if present) as the request.
4. The guide operates read-only on:
   - `.claude/CLAUDE.md`
   - `docs/HANDOVER.md`
   - `docs/.session-context.md` (if <10 min old)
   - `docs/memory/MEMORY.md`
   - `docs/BASELINE.md` (if Baseline mode is active)
   - Phase-specific files (SPRINT.md, phase indexes) if needed
   - `~/.claude/docs/NEXT_STEPS_REFERENCE.md` as the phase-sequence reference
   - Work-item counts prepared by the orchestrator in step 1 (structured-store projects)
5. Write permissions for the guide are limited to `docs/memory/project-guide/`
   and its HANDOVER section.

## Expected Output

**For a status request (no argument):**

```markdown
# Status <DD.MM.YYYY>

**Phase:** <PX [subtitle]> — <current state>
**Last action:** <Skill + date>
**Open decisions:** <count + top 1-3>
**Cleanup notes:** <if present, otherwise _none_>

## Recommended next steps

1. **`/skill-1`** — <rationale>
2. `/skill-2` — <rationale>
3. `/skill-3` — <rationale>

**Recommendation:** (N) `<skill>` with rationale.
```

**For a request argument:**

- If the domain is clear: hand off with context bundle to the responsible agent.
- If unclear: 1–2 clarifying questions.

## When not to invoke

- When you already know which skill/agent you need — trigger it directly,
  saves tokens.
- In the middle of an active skill workflow (e.g. between RED/GREEN/REFACTOR) —
  status aggregation is overhead there.
- For domain work itself (concept, code, review) — the guide mediates only,
  it does not execute.
