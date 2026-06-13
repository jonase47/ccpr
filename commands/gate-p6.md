# /gate-p6 – Release Gate: QA & Security Approval

Checks whether the system is ready for launch. Both QA and Security must explicitly grant approval. No go-live without dual approval.

## No Argument ($ARGUMENTS not applicable)

Gate commands accept no arguments. They always check the complete current project status.

## Pre-Flight
If `docs/.gate-preflight-p6.md` exists and is less than 10 minutes old, read it as a starting point. Mechanical checks (file existence, sections) are already done – focus on content evaluation.

## Constitution Inviolables (mandatory pre-gate, applies to both sub-gates)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p6.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for **both** sub-gates (`/gate-p6-qa` and `/gate-p6-security`):
- When invoking each sub-gate, pass the Inviolable bullets verbatim in the agent prompt.
- Both QA and Security must check their evaluation against the Inviolables (e.g. „A11y-Inviolable forces WCAG 2.2 AA verification", „Security-Inviolable forces dependency-audit").
- Any violation is an **"Inviolable breach"** — surface it explicitly in the sub-gate verdict and treat it as a No-Go signal for release.

If `docs/CONSTITUTION.md` is missing on a Full-Track project: stop the gate and recommend `/constitution` before proceeding (release without Constitution check is not advisable in Full-Track).

## Flow

### 1. QA Approval
`/gate-p6-qa` – Evaluates all QA-relevant points (tests, accessibility, performance, bugs) and grants QA approval.

### 2. Security Approval
`/gate-p6-security` – Evaluates all security-relevant points (audit, pentest, DSGVO) and grants Security approval.

### 3. Consolidation (Orchestrator)
Read `docs/quality/QA.md` (phase index) first to get the status of all sub-indexes (`A11Y.md`, `AUDIT.md`, `FUNCTIONAL.md`, `PENTEST.md`) and direct detail files (`EXPLORATORY.md`, `BUGFIX.md`). Open the sub-indexes only when their status row indicates `needs-rework` or open Critical risks.

Create **`docs/quality/GATE_P6.md`** with:
- QA approval section (consumes the GATE_P6_QA result from `gate-p6-qa`)
- Security approval section (consumes the GATE_P6_SECURITY result from `gate-p6-security`)
- **Release tag set?** (`git tag vX.Y.Z` + `chore: release vX.Y.Z`)
- Overall decision: Go-live only when BOTH approvals are positive (Approved or Conditional Approval)

Also update **`docs/quality/QA.md`** (phase index):
- Set `**Status:** Gate Passed (DD.MM.YYYY)` (or `Conditional Go-Live` / `No Go-Live`).
- Append the verdict and any Conditional-Go conditions under the **Gate Notes** section.
- Add a row in the detail-file table for `[GATE_P6.md](GATE_P6.md)` with the verdict.

## Notes
- Steps 1 and 2 can run in parallel
- Step 3 is handled by the Orchestrator itself (no agent delegation)
- The complete Gate-P6 checklist remains in the sub-skills

## Possible Outcomes

| Decision | Prerequisite | Next Step |
|---|---|---|
| **Go-Live** | QA + Security Approved | `/p7-prepare` |
| **Conditional Go-Live** | Conditional approval(s), no rejection | Fulfil conditions, then `/p7-prepare` |
| **No Go-Live** | QA or Security Not Approved | Fix findings with `/p6-bugfix` |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Write **`docs/quality/GATE_P6.md`** (gate protocol from §3 above — consumes QA + Security approval results)
2. Update **`docs/quality/QA.md`** phase index with gate result (status + gate notes, per §3 above)
3. **On Go-Live only** — freeze Phase-P6 detail files: `bash ~/.claude/scripts/freeze-phase-docs.sh P6` (skipped on Conditional Go-Live / No Go-Live)
4. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
5. **Cleanup**: `rm -f docs/.gate-preflight-p6.md` (last operation)

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

### Cleanup
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p6.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
