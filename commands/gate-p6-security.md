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
