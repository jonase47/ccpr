---
disable-model-invocation: true
---
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
