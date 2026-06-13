# /gate-p7-business – Business Readiness Check

Checks business readiness: documentation, GTM, KPIs, legal mandatory documents.

## Argument: $ARGUMENTS = not applicable

Gate commands do not accept arguments.

## Prerequisites
- `docs/launch/LAUNCH.md` (phase index) exists
- `docs/launch/RELEASE_DOCS.md` (summary + links) with frontmatter `status: active`
- `docs/launch/GTM.md` (or marked as not applicable for hobby projects)
- Repo-root files: `RELEASE_NOTES.md`, `USER_GUIDE.md`, `PRIVACY_POLICY.md`, `LEGAL_NOTICE.md` (latter two only required for public hosting)

## Agent
- **Type**: business-analyst
- **Model**: sonnet

## Pre-Flight
If `docs/.gate-preflight-p7.md` exists and is less than 10 minutes old, read it as a starting point. Mechanical checks (file existence, sections) are already done – focus on content evaluation.

## Context (Orchestrator prepares)
**Read the phase index first**, then load detail files only when their status row signals an open issue:
- From `docs/launch/LAUNCH.md`: status, key decisions, open risks (entry point)
- From `docs/launch/RELEASE_DOCS.md`: which release docs exist and whether legal review is still pending
- From `docs/launch/GTM.md`: KPI status and 30/60/90-day targets (or note "not applicable")
- From `docs/concept/CONCEPT.md` (P1 phase index, optional): project type (hobby vs. business)
- Repo-root files for content checks: `RELEASE_NOTES.md`, `USER_GUIDE.md`, `PRIVACY_POLICY.md`, `LEGAL_NOTICE.md`
- From the global CLAUDE.md: hosting type (local vs. public)

## Prompt Template
> **Goal**: Business readiness check for Gate P7.
>
> **Business Documents**:
> [inline summaries]
>
> **Output Format**:
> 1. Checklist (max. 6 items):
> | # | Check | Status | Reason |
> Status: Fulfilled / Partially / Not fulfilled / Not applicable
>
> 2. Business go-live assessment:
> - Ready / Conditionally ready / Not ready
> - Reason (2-3 sentences)
> - Conditions (if conditional, as numbered list)
>
> **Constraints**:
> - ONLY business evaluation, NO technical check
> - For hobby projects: rate GTM and pricing as "Not applicable"
> - Legal notice only required for public hosting

## Orchestrator Checkpoint
- [ ] Project type (hobby/business) taken into account?
- [ ] Mandatory document requirement correctly assessed?

## Output
- Business approval section consumed by `gate-p7.md` to compose `docs/launch/GATE_P7.md`. This sub-gate does not write its own file; it returns its evaluation as agent output that the orchestrator-level `gate-p7` aggregates.

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
