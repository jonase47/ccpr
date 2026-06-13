# /gate-p6-qa – QA Approval Evaluation

Evaluates all QA-relevant points of the Gate-P6 checklist and grants QA approval.

## Argument: $ARGUMENTS = not applicable

Gate commands accept no arguments.

## Prerequisites
- `docs/quality/QA.md` (phase index) exists
- `docs/quality/FUNCTIONAL.md` (sub-index) and its detail files (`func_e2e.md`, `func_integration.md`, `func_regression.md`)
- `docs/quality/A11Y.md` (sub-index) and its detail files (`a11y_keyboard.md`, `a11y_screenreader.md`, `a11y_visual.md`)
- `docs/quality/EXPLORATORY.md` (direct detail file)
- `docs/architecture/TESTSTRATEGY.md` exists (as reference for critical paths)

## Agent
- **Type**: qa-tester
- **Model**: sonnet

## Pre-Flight
If `docs/.gate-preflight-p6.md` exists and is less than 10 minutes old, read it as a starting point. Mechanical checks (file existence, sections) are already done – focus on content evaluation.

## Context (Orchestrator prepares)
**Read the phase and sub-indexes first**, then load detail files only when their status row signals an open issue:
- From `docs/quality/QA.md`: status, key decisions, open risks (the entry points)
- From `docs/quality/FUNCTIONAL.md` (sub-index): row status of each `func_*.md`
- From `docs/quality/A11Y.md` (sub-index): row status of each `a11y_*.md`
- From `docs/quality/EXPLORATORY.md`: severity summary
- From `docs/architecture/TESTSTRATEGY.md`: critical test paths (short list)
- Detail files (`func_e2e.md`, `a11y_visual.md`, ...) only when a sub-index row is `needs-rework` or has an open Critical risk

## Prompt Template
> **Goal**: QA approval evaluation for Gate P6.
>
> **Test Protocols**:
> [inline summaries]
>
> **Output Format**:
> 1. Checklist (max. 8 points):
> | # | Check Point | Status | Justification |
> Status: Met / Partial / Not Met
>
> 2. QA Approval:
> - Approved / Conditional Approval / Not Approved
> - Justification (2–3 sentences)
> - Conditions (if conditional, as numbered list)
>
> **Constraints**:
> - QA evaluation ONLY, NO security evaluation
> - Evaluation based exclusively on available protocols
> - No approval if critical bugs are open

## Orchestrator Checkpoint
- [ ] All test protocols considered?
- [ ] Approval status justified comprehensibly?

## Output
- QA approval section consumed by `gate-p6.md` to compose `docs/quality/GATE_P6.md`. This sub-gate does not write its own file; it returns its evaluation as agent output that the orchestrator-level `gate-p6` aggregates.

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
