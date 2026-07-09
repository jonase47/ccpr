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
   this beforehand and passes the result in. Run `python3 ~/.claude/scripts/workitems.py list`
   **and** explicitly check whether the `docs/workitems/` directory exists (e.g. `ls
   docs/workitems/`) — both signals are required, `list` returns the identical `[]` for an
   adopted-but-empty store and a never-adopted project.
   - **Non-empty list** → the project uses the structured store. **A bare `list
     --status "Ready"/"In Progress"/"Done"` returns PROJECT-WIDE totals across every sprint, not
     this sprint's.** Scope it: read the current sprint number `<N>` from `docs/planning/SPRINT.md`'s
     frontmatter `sprint: <N>` (or the active `docs/planning/sprint/SPRINT-NN.md`'s `sprint: NN`
     field, for the sub-index layout), then run `workitems list --sprint <N>` and count status
     directly among that result. Report the scoped counts as "this sprint" (e.g. "6/10 Done, 2 In
     Progress, 2 Ready — this sprint"). If SPRINT.md (or the active sprint detail file) carries no
     `sprint:` frontmatter yet (a sprint plan predating this convention, or before the project's
     first `/p4-sprint` run under it), scoping isn't possible — report the unscoped `list`/`--status`
     counts but label them explicitly **"project-wide"**, never "this sprint".
   - **Empty list, but `docs/workitems/` exists** → the store is adopted, just empty right now (or
     genuinely zero items). Report it as such (e.g. "0 items adopted yet" or "0 in this sprint"),
     don't fall back to prose.
   - **Empty list and no `docs/workitems/` directory** → not adopted, still on prose. Derive sprint
     status from SPRINT.md as before.
2. Start the `project-guide` agent via the Task tool, passing the resolved item counts (if any,
   labeled "this sprint" or "project-wide" per the scoping above) as part of its context.
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
