# /p8-ops – Production Operations: Analyse Incidents & Monitor Performance

Analyses production errors and performance issues, evaluates incidents, and initiates countermeasures. Called reactively for specific incidents or proactively for regular operational reviews.

## Argument: $ARGUMENTS = [Incident/area, e.g. "500 errors since 14:30", "high response times", "weekly review"]

If provided: Analyse the described incident or conduct the review for the specified area.
If not provided: Read RUNBOOK.md and current monitoring data and conduct a general operational review. If any context is missing, ask whether a specific incident exists or a scheduled review should be performed.

## Execution

### 1. Read Context
Read the following files (if available):
- **RUNBOOK.md** (incident response process, alerting thresholds, escalation paths)
- **DEPLOYMENT_LOG.md** (most recent deployment – frequently the cause of new incidents)
- **ARCHITECTURE.md** (system components – for root cause analysis)
- Previous incident reports (if available)

### 2. Delegation to DevOps Agent (Lead)
Delegate operational analysis to the **devops** agent:

> Analyse the following incident or operational area: **$ARGUMENTS**
> Incident response process from RUNBOOK.md: [Apply process and thresholds]
>
> **A. For a Specific Incident**
>
> Incident analysis (using the 5-Why principle):
> - What exactly happened? (symptom, timeframe, affected users)
> - When was it discovered? (alert, user report, proactively)
> - What was the immediate cause? (Why 1)
> - What was the deeper cause behind it? (Why 2–5)
> - Timeline: when did the incident occur, when was it responded to, when resolved?
>
> Immediate measures:
> - What was done as a first response?
> - Rollback necessary? If so: executed?
> - Is the incident resolved or only contained?
>
> **B. For a Scheduled Review**
>
> Check operational health:
> - Uptime for the past period (target vs. actual)
> - Average and P99 response times (trend)
> - Error rate (trend, notable spikes)
> - Resource utilisation (CPU, RAM, disk – is any limit approaching?)
> - Planned scaling need: when will current resources no longer be sufficient?
>
> **C. Post-Incident Review (PIR) – for severe incidents**
> - Complete incident timeline
> - Root cause (not symptom)
> - Impact: how many users affected, for how long?
> - What worked well? (detection, response, communication)
> - What could have gone better?
> - Concrete follow-up actions with ownership and deadline

### 3. Delegation to Debugger Agent (Support)
Delegate technical root cause analysis for specific code errors to the **debugger** agent:

> Analyse the technical root cause of the incident: **$ARGUMENTS**
> System context from ARCHITECTURE.md: [Apply relevant components]
>
> 1. Identify the faulty code location or configuration
> 2. Propose a fix (short-term mitigation + long-term clean fix)
> 3. Which regression test would prevent this incident in the future?

### 4. Write Detail File
This subskill maintains a **living** detail file `docs/operations/OPS_REVIEW.md` plus optional dated snapshots for individual incidents.

Write `docs/operations/OPS_REVIEW.md` (overwrite on each call with the latest summary). Frontmatter:

```yaml
---
phase: P8
subskill: ops
status: living
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Period`, `## Recent Incidents` (table: ID / Date / Severity / Root Cause / Status), `## Performance Trends`, `## Recommendations`, `## Open Action Items`.

For individual incident detail (full timeline, post-mortem): optionally archive as `docs/operations/snapshots/INCIDENT_REPORT_<YYYY-MM-DD>.md` and reference it from the OPS_REVIEW.md table.

Cross-file update: append follow-up tasks (with deadlines) to `docs/planning/BACKLOG.md` and bump its `last_updated`.

### 5. Update Phase Index
Update `docs/operations/OPS.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[OPS_REVIEW.md](OPS_REVIEW.md)` with status `living`.
- Lift any active Critical/High incident into **Open Risks / Open Questions**.
- Lift the headline reliability metric (e.g. "uptime 99.7% last 30 days") into **Key Decisions**.

## Result

- **`docs/operations/OPS_REVIEW.md`** (latest ops summary)
- Optional **`docs/operations/snapshots/INCIDENT_REPORT_<date>.md`** (per-incident post-mortem)
- Updated **`docs/planning/BACKLOG.md`** (follow-up tasks)
- **`docs/operations/OPS.md`** (phase index updated)
- Follow-up tasks as new items in **BACKLOG.md** (for `/p8-iteration`)
- Updated **RUNBOOK.md** if applicable (incorporate lessons from the incident)

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
