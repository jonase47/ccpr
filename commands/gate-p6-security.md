# /gate-p6-security – Security Approval Evaluation

Evaluates all security-relevant points of the Gate-P6 checklist and grants Security approval.

## Argument: $ARGUMENTS = not applicable

Gate commands accept no arguments.

## Prerequisites
- `docs/quality/QA.md` (phase index) exists
- `docs/quality/AUDIT.md` (sub-index) and its detail files (`audit_auth.md`, `audit_config.md`, `audit_deps.md`, `audit_dsgvo.md`, `audit_sast.md`)
- `docs/quality/PENTEST.md` (sub-index) and its detail files (`pentest_recon.md`, `pentest_auth.md`, `pentest_authz.md`, `pentest_injection.md`, `pentest_logic.md`)
- `docs/architecture/SECURITY.md` (P3 sub-index) as reference for the security architecture
- `docs/concept/DSGVO_INITIAL_ASSESSMENT.md` (P1 detail file) as compliance benchmark

## Agent
- **Type**: security-master
- **Model**: opus

## Pre-Flight
If `docs/.gate-preflight-p6.md` exists and is less than 10 minutes old, read it as a starting point. Mechanical checks (file existence, sections) are already done – focus on content evaluation.

## Context (Orchestrator prepares)
**Read the phase and sub-indexes first**, then load detail files only when their status row signals an open issue:
- From `docs/quality/QA.md`: status, key decisions, open risks (entry point)
- From `docs/quality/AUDIT.md` (sub-index): row status of each `audit_*.md`
- From `docs/quality/PENTEST.md` (sub-index): row status of each `pentest_*.md`
- From `docs/architecture/SECURITY.md`: P3 threat model summary (key decisions, open risks)
- From `docs/concept/DSGVO_INITIAL_ASSESSMENT.md`: DSGVO requirements (short list)
- Detail files (`audit_dsgvo.md`, `pentest_authz.md`, ...) only when a sub-index row is `needs-rework` or has an open Critical risk

## Prompt Template
> **Goal**: Security approval evaluation for Gate P6.
>
> **Security Reports**:
> [inline summaries]
>
> **Output Format**:
> 1. Checklist (max. 6 points):
> | # | Check Point | Status | Justification |
> Status: Met / Partial / Not Met
>
> 2. Security Approval:
> - Approved / Conditional Approval / Not Approved
> - Justification (2–3 sentences)
> - Conditions (if conditional, as numbered list)
>
> **Constraints**:
> - Security evaluation ONLY, NO QA evaluation
> - Evaluation based exclusively on available reports
> - No approval if critical or high security findings are open

## Orchestrator Checkpoint
- [ ] Audit and pentest considered?
- [ ] DSGVO compliance checked?

## Output
- Security approval section consumed by `gate-p6.md` to compose `docs/quality/GATE_P6.md`. This sub-gate does not write its own file; it returns its evaluation as agent output that the orchestrator-level `gate-p6` aggregates.

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
