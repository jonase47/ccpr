# /guide – Project Guide (Status, Skill Recommendation, Disambiguation)

Invokes the `project-guide` agent as the entry point for the current project:
structured status snapshot, prioritised next steps with skill/agent
recommendation, and disambiguation for unclear requests.

## Argument: $ARGUMENTS = [optional: concrete question / request]

- Without argument: status snapshot + 3 prioritised next steps.
- With argument: disambiguate the request and hand off to the matching domain
  agent, with 1–2 clarifying questions first if needed.

## Execution

1. Start the `project-guide` agent via the Task tool.
2. Pass the argument (if present) as the request.
3. The guide operates read-only on:
   - `.claude/CLAUDE.md`
   - `docs/HANDOVER.md`
   - `docs/.session-context.md` (if <10 min old)
   - `docs/memory/MEMORY.md`
   - `docs/BASELINE.md` (if Baseline mode is active)
   - Phase-specific files (SPRINT.md, phase indexes) if needed
   - `~/.claude/docs/NEXT_STEPS_REFERENCE.md` as the phase-sequence reference
4. Write permissions for the guide are limited to `docs/memory/project-guide/`
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
