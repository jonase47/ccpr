# /p6-audit – Security Audit, Dependency Check & DSGVO (GDPR) Compliance

Conducts a defensive security audit. Each audit area is a separate sub-skill.

## Argument: $ARGUMENTS = [focus/area]

If provided: Focus the audit on the specified area.
If not provided: Run all audit areas.

## Flow

### 0. Ensure Sub-Index Exists
Make sure `docs/quality/AUDIT.md` exists as a **sub-index** with the standard header (Status / Last Updated / Key Decisions / Open Risks / Detail Files / Gate Notes — see `~/.claude/docs/PROJECT_PHASES.md`). If missing, create it with empty placeholders. The five `p6-audit-*` sub-skills below each refresh their own row in this sub-index's **Detail Files** table.

### 1. Static Code Analysis
`/p6-audit-sast $ARGUMENTS` – Checks code for injection, cryptography, secrets.

### 2. Auth Implementation
`/p6-audit-auth $ARGUMENTS` – Compares auth code against SECURITY.md.

### 3. Dependency Check
`/p6-audit-deps $ARGUMENTS` – Checks dependencies for CVEs.

### 4. Configuration
`/p6-audit-config $ARGUMENTS` – Checks security headers, CORS, secrets management.

### 5. DSGVO Compliance
`/p6-audit-dsgvo $ARGUMENTS` – Compares against DSGVO_INITIAL_ASSESSMENT.md.

### 6. Roll Up Sub-Index to Phase Index
After all `p6-audit-*` sub-skills have run, summarise the AUDIT sub-index into the phase index `docs/quality/QA.md`:
- Add an entry in the phase-index **Detail Files** table for `[AUDIT.md](AUDIT.md)` (the sub-index itself), status `complete` once all five sub-skill rows are `complete` (or `needs-rework`).
- Lift any High/Critical audit finding into the phase-index **Open Risks**.

## Notes
- Sub-skills 1–4 can run in parallel (no dependencies)
- DSGVO (5) can also run in parallel
- Detail files: `audit_sast.md`, `audit_auth.md`, `audit_deps.md`, `audit_config.md`, `audit_dsgvo.md` under the `AUDIT.md` sub-index
- For minimal scope (no auth, no deps, no PII): abbreviate affected sub-skills with `status: active` and a body note stating "N/A — out of scope for <reason>"

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
