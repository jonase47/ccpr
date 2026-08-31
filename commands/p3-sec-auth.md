---
disable-model-invocation: true
---
# /p3-sec-auth – Auth & Authorization Concept

Defines the authentication and authorization concept including session management.

## Argument: $ARGUMENTS = [Auth method, e.g. "JWT", "Session", "OAuth", "none"]

If provided: Use the method as a starting point.
If not provided: Recommend based on architecture and requirements.

## Prerequisites
- ARCHITECTURE.md and threat model exist

## Agent
- **Type**: system-architekt
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: Components with access control
- From SECURITY.md: Threat model (spoofing/elevation rows)
- From CONCEPT.md: User roles and permissions (if defined)

## Prompt Template
> **Goal**: Design auth & authorization concept. Method: $ARGUMENTS
>
> **Context**:
> [inline from ARCHITECTURE.md, SECURITY.md]
>
> **Output Format**:
> 1. Auth method with justification (1-2 sentences)
> 2. Roles table: | Role | Description | Access Rights |
> 3. Session management: timeout, token rotation, logout
> 4. Password policy (if password-based)
>
> **Constraints**:
> - ONLY auth concept, NO threat model, NO API security
> - If no auth needed: explicitly justify and leave section empty
> - MFA only if relevant for the project type

## Orchestrator Checkpoint
- [ ] Auth method justified?
- [ ] Roles cover all user types mentioned in the concept?

## Write Detail File
Write the result to `docs/architecture/AUTH.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: sec-auth
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Auth Method` (with justification), `## Roles` (the table Role / Description / Access Rights), `## Session Management` (timeout, token rotation, logout), `## Password Policy` (if password-based), `## MFA` (if relevant).

## Update Sub-Index
Update `docs/architecture/SECURITY.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[AUTH.md](AUTH.md)` with status `complete`.
- Lift the headline auth decision into **Key Decisions** of the sub-index (e.g. `- Auth: JWT with 15-min access + 7-day refresh → see AUTH.md`).
- Do not edit `ARCHITECTURE.md` directly — `/p3-security` rolls the sub-index up.

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
