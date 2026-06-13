# /gate-p7-tech – Technical Go-Live Check

Checks technical go-live readiness: deployment, monitoring, rollback, smoke tests.

## Argument: $ARGUMENTS = not applicable

Gate commands do not accept arguments.

## Prerequisites
- `docs/launch/LAUNCH.md` (phase index) exists
- `docs/launch/PREPARE.md` (pre-launch checklist) with frontmatter `status: active`
- `docs/launch/DEPLOYMENT.md` (deployment log) with frontmatter `status: active`
- `docs/launch/MONITORING.md` (monitoring & runbook) with frontmatter `status: active`
- `docs/quality/GATE_P6.md` (P6 approval) exists

## Agent
- **Type**: devops
- **Model**: sonnet

## Pre-Flight
If `docs/.gate-preflight-p7.md` exists and is less than 10 minutes old, read it as a starting point. Mechanical checks (file existence, sections) are already done – focus on content evaluation.

## Context (Orchestrator prepares)
**Read the phase index first**, then load detail files only when their status row signals an open issue:
- From `docs/launch/LAUNCH.md`: status, key decisions, open risks (entry point)
- From `docs/launch/DEPLOYMENT.md`: deployment status, smoke test results
- From `docs/launch/MONITORING.md`: monitoring status, rollback plan, alerting rules
- From `docs/launch/PREPARE.md`: any unfinished checklist items
- From `docs/quality/GATE_P6.md`: QA and security approval status

## Prompt Template
> **Goal**: Technical go-live check for Gate P7.
>
> **Technical Reports**:
> [inline summaries]
>
> **Output Format**:
> 1. Checklist (max. 6 items):
> | # | Check | Status | Reason |
> Status: Fulfilled / Partially / Not fulfilled
>
> 2. Technical go-live approval:
> - Approval / Conditional approval / No approval
> - Reason (2-3 sentences)
> - Conditions (if conditional, as numbered list)
>
> **Constraints**:
> - ONLY technical check, NO business evaluation
> - Focus: deployment, monitoring, rollback, smoke tests
> - No approval if deployment failed or no rollback plan exists

## Orchestrator Checkpoint
- [ ] Deployment status checked?
- [ ] Rollback plan present and tested?

## Output
- Technical approval section consumed by `gate-p7.md` to compose `docs/launch/GATE_P7.md`. This sub-gate does not write its own file; it returns its evaluation as agent output that the orchestrator-level `gate-p7` aggregates.

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
