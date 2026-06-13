# /p7-deploy – Execute Deployment & Smoke Tests

Executes the deployment to the target environment and then verifies with smoke tests that the system is running correctly. Only when the smoke tests pass is the deployment considered successful.

## Argument: $ARGUMENTS = [Environment, e.g. "staging", "production"]

If provided: Deploy to the specified environment.
If not provided: Ask for the target environment. Without a clear specification, do not start the deployment – the environment is critical information.

## Execution

### 1. Read Context and Check Prerequisites
Read the following files (if available):
- **DEPLOYMENT_CHECKLIST.md** (has the preparation from `/p7-prepare` been completed?)
- **INFRASTRUCTURE.md** (deployment procedure, rollback strategy)
- **GATE_P6.md** (approval status)

Mandatory checks before deployment:
- Does DEPLOYMENT_CHECKLIST.md exist with a completed checklist? If not → stop, recommend `/p7-prepare` first.
- Is Gate 6 approved with green or yellow? If not → stop.

### 2. Delegation to DevOps Agent (Lead)
Delegate the deployment to the **devops** agent:

> Execute the deployment to the following environment: **$ARGUMENTS**
> Deployment procedure from INFRASTRUCTURE.md and DEPLOYMENT_CHECKLIST.md: [Apply procedure]
>
> **A. Execute Deployment**
> Execute the deployment step by step and document each step:
> 1. Activate maintenance mode (if no zero-downtime deployment)
> 2. Execute database migrations
> 3. Deploy new application version
> 4. Restart services / switch traffic
> 5. Deactivate maintenance mode
> Log timestamp and result for each step.
>
> **B. Smoke Tests**
> Immediately after deployment, verify the most critical system functions:
> - Is the application reachable? (HTTP 200 on the home page)
> - Does authentication work? (Login successful)
> - Is the database connection active? (Health endpoint or simple DB query)
> - Does the most critical core workflow work? (1 E2E smoke test)
> - Are external services reachable? (email, payment, etc.)
> - Are monitoring and logging running? (Logs appear, metrics are collected)
>
> **C. Immediate Rollback on Smoke Test Failure**
> If a smoke test fails:
> 1. Immediately initiate rollback (according to the rollback plan from DEPLOYMENT_CHECKLIST.md)
> 2. Document the failure
> 3. Mark deployment as failed
> 4. Analyse the cause before the next deployment attempt

### 3. Delegation to QA Tester Agent (Support)
Delegate smoke test verification to the **qa-tester** agent:

> Execute the smoke tests after deployment and document the results:
> 1. Have all smoke tests passed?
> 2. Are there behavioural differences compared to the staging environment?
> 3. Recommendation: confirm deployment as successful – yes/no?

### 4. Write Detail File
Write the result to `docs/launch/DEPLOYMENT.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P7
subskill: deploy
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Deployment Steps` (timestamp + result per step), `## Smoke Test Results`, `## Overall Status` (✅ Successful / ❌ Failed with rollback documentation), `## Open Items Post-Deployment`.

Cross-file update: refresh the `## Pre-Launch Checklist` items in `docs/launch/PREPARE.md` (mark each completed item) and bump its `last_updated`. Do not rewrite PREPARE.md — only update the checklist statuses.

### 5. Update Phase Index
Update `docs/launch/LAUNCH.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[DEPLOYMENT.md](DEPLOYMENT.md)` with status `complete` (or `needs-rework` on failure).
- Lift the headline result (Live since DD.MM.YYYY / Rolled back) into **Key Decisions**.
- Lift any unresolved post-deployment item into **Open Risks**.

## Result

- **`docs/launch/DEPLOYMENT.md`** (deployment log with smoke test results)
- Updated **`docs/launch/PREPARE.md`** (checklist statuses)
- **`docs/launch/LAUNCH.md`** (phase index updated)
- Live system (on success)
- On success: next step is `/p7-monitoring`
- On failure: analyse cause, run `/p7-prepare` again

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
