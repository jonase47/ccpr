# /p3-security – Security Architecture, Threat Model & Auth Concept

Creates the complete security architecture: threat model, auth concept, data security, API security and developer checklist. Each area is its own sub-skill.

## Argument: $ARGUMENTS = [Focus, e.g. "Auth", "API Security", "Data Encryption"]

If provided: Passed through to the sub-skills.
If not provided: All sub-skills run sequentially.

## Flow

### 0. Ensure Sub-Index Exists
Make sure `docs/architecture/SECURITY.md` exists as a **sub-index** with the standard header (Status / Last Updated / Key Decisions / Open Risks / Detail Files / Gate Notes — see `~/.claude/docs/PROJECT_PHASES.md`). If missing, create it with empty placeholders. The five `p3-sec-*` sub-skills below each refresh their own row in this sub-index's **Detail Files** table.

### 1. STRIDE Threat Model
`/p3-sec-threats $ARGUMENTS` – Analyzes the system according to the STRIDE model.

### 2. Auth & Authorization Concept
`/p3-sec-auth $ARGUMENTS` – Defines auth method, roles and session management.

### 3. Data Security
`/p3-sec-data $ARGUMENTS` – Encryption (transit/rest), secrets management, backups.

### 4. API Security
`/p3-sec-api $ARGUMENTS` – Input validation, rate limiting, CORS, security headers.

### 5. Developer Checklist
`/p3-sec-checklist` – Concrete security checklist for phase 5.

### 6. Roll Up Sub-Index to Phase Index
After all `p3-sec-*` sub-skills have run, summarise the security sub-index into the phase index `docs/architecture/ARCHITECTURE.md`:
- Add an entry in the phase-index **Detail Files** table for `[SECURITY.md](SECURITY.md)` (the sub-index itself), status `complete` once all five sub-skill rows in `SECURITY.md` are `complete`.
- Lift the headline security decisions (auth method, encryption strategy, top critical threat) into the phase-index **Key Decisions**.
- Lift any unresolved Critical/High threats from `THREATS.md` into the phase-index **Open Risks**.

### 7. Final HANDOVER Update (Orchestrator-owned)

The orchestrator owns the final `docs/HANDOVER.md` update for this P3 section. Sub-skills (`/p3-sec-*`) also contain a Handover Epilogue — this is intentional, so the sub-skills remain usable on their own. **However, when this orchestrator runs, the orchestrator's HANDOVER update is the authoritative one and supersedes individual sub-skill updates.** Consolidate all `SECURITY.md` sub-sections into a single HANDOVER entry.

## Notes
- Step 1 always first (threat model informs all subsequent steps)
- Steps 2-4 can run in parallel after 1
- Step 5 always last (consolidates all sections)
- Result: SECURITY.md with all sections

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
