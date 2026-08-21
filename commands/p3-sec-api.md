# /p3-sec-api – API Security Requirements

Defines input validation, rate limiting, CORS and security headers.

## Argument: $ARGUMENTS = [Focus, e.g. "CORS", "Rate Limiting", "Headers"]

If provided: Deep-dive the named area.
If not provided: Create complete API security requirements.

## Prerequisites
- ARCHITECTURE.md exists
- API endpoints known (from DATA_MODEL.md or API_SPEC.md)

## Agent
- **Type**: security-master
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: API components and data flows
- From DATA_MODEL.md: API endpoints (if available)
- From TECH_STACK.md: Backend framework

## Prompt Template
> **Goal**: Define API security requirements.
>
> **Context**:
> [inline from ARCHITECTURE.md, DATA_MODEL.md]
>
> **Output Format**:
> 1. Input validation: strategy (whitelist/blacklist), sanitization
> 2. Rate limiting: Table | Endpoint Type | Limit | Time Window |
> 3. CORS: allowed origins, methods, headers
> 4. Security headers: Table | Header | Value | Purpose |
>
> **Constraints**:
> - ONLY API security, NO auth concept, NO data encryption
> - Max. 6 rate limit rules
> - Max. 8 security headers
> - If no API present: explicitly justify and keep section minimal

## Orchestrator Checkpoint
- [ ] OWASP Top 10 API risks considered?
- [ ] Security headers complete (CSP, X-Frame-Options, etc.)?

## Write Detail File
Write the result to `docs/architecture/API_SECURITY.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: sec-api
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Input Validation`, `## Rate Limiting`, `## CORS`, `## Security Headers`.

## Update Sub-Index
Update `docs/architecture/SECURITY.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[API_SECURITY.md](API_SECURITY.md)` with status `complete`.
- Note any OWASP Top-10-API risk that is NOT yet mitigated under **Open Risks** of the sub-index.
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
