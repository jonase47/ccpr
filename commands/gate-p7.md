# /gate-p7 – Go-Live Gate: Technical Readiness & Business Readiness

Checks whether the system is fully ready for production operation. Last gate before the official go-live status.

## No Argument ($ARGUMENTS not applicable)

Gate commands do not accept arguments. They always check the complete current project status.

## Pre-Flight
If `docs/.gate-preflight-p7.md` exists and is less than 10 minutes old, read it as a starting point. Mechanical checks (file existence, sections) are already done – focus on content evaluation.

## Constitution Inviolables (mandatory pre-gate, applies to both sub-gates)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p7.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for **both** sub-gates (`/gate-p7-tech` and `/gate-p7-business`):
- When invoking each sub-gate, pass the Inviolable bullets verbatim in the agent prompt.
- Tech must verify deployment, monitoring, rollback respect the Inviolables (no telemetry-leak, no secret-in-code, A11y-baseline live).
- Business must verify GTM, Pricing, Release-Docs respect the Inviolables (e.g. plain-language privacy statements in marketing copy, A11y mention in store listing).
- Any violation is an **"Inviolable breach"** — block go-live until resolved or explicitly waived (waiver documented in `GATE_P7.md`).

If `docs/CONSTITUTION.md` is missing on a Full-Track project: stop the gate and require `/constitution` before go-live.

## Flow

### 1. Technical Go-Live Check
`/gate-p7-tech` – Checks deployment, monitoring, rollback, and smoke tests.

### 2. Business Readiness Check
`/gate-p7-business` – Checks documentation, GTM, KPIs, and mandatory documents.

### 3. Consolidation (Orchestrator)
Read `docs/launch/LAUNCH.md` (phase index) first to get the status of all detail files (`PREPARE.md`, `DEPLOYMENT.md`, `MONITORING.md`, `RELEASE_DOCS.md`, `GTM.md`). Open detail files only when their row indicates `needs-rework` or open Critical risks.

Create **`docs/launch/GATE_P7.md`** with:
- Technical approval section (consumes the GATE_P7_TECH result from `gate-p7-tech`)
- Business approval section (consumes the GATE_P7_BUSINESS result from `gate-p7-business`)
- Overall go-live decision

Also update **`docs/launch/LAUNCH.md`** (phase index):
- Set `**Status:** Go-live confirmed (DD.MM.YYYY)` (or `Conditional` / `No Go-Live`).
- Append the verdict and any conditions under the **Gate Notes** section.
- Add a row in the detail-file table for `[GATE_P7.md](GATE_P7.md)` with the verdict.

## Notes
- Steps 1 and 2 can run in parallel
- Step 3 is done by the Orchestrator itself (no agent delegation)
- For hobby projects: business evaluation carries less weight

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Go-live confirmed** | Technically stable, business ready | `/p8-ops` (Operations) |
| **Conditional go-live** | Minor open items | Fulfil conditions, then proceed to operations |
| **No go-live** | Critical prerequisites missing | Resolve blockers, then gate again |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Write **`docs/launch/GATE_P7.md`** (gate protocol from §3 above — consumes Technical + Business approval results)
2. Update **`docs/launch/LAUNCH.md`** phase index with gate result (status + gate notes, per §3 above)
3. **On Go-live confirmed only** — freeze Phase-P7 detail files: `bash ~/.claude/scripts/freeze-phase-docs.sh P7` (skipped on Conditional / No go-live)
4. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
5. **Cleanup**: `rm -f docs/.gate-preflight-p7.md` (last operation)

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open items
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate

### Cleanup
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p7.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
