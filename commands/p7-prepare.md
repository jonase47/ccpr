# /p7-prepare – Deployment Preparation & Pre-Launch Checklist

Prepares the deployment: checks all environments, prepares database migrations, verifies configurations, and ensures nothing has been overlooked. Only after this checklist is complete will `/p7-deploy` be executed.

## Argument: $ARGUMENTS = [Environment, e.g. "staging", "production"]

If provided: Prepare the deployment for the specified environment.
If not provided: Ask for the target environment. Default order is staging first, then production – confirm or adjust accordingly.

## Execution

### 1. Read Context
Read the following files (if available):
- **INFRASTRUCTURE.md** (Hosting, Environments, Rollback strategy)
- **GATE_P6.md** (Approval status – deployment only after Gate 6 has passed)
- **SECURITY.md** (Security requirements for production deployment)
- **DSGVO_INITIAL_ASSESSMENT.md** (DSGVO (GDPR) obligations before go-live)
- **DATA_MODEL.md** (Identify database migrations)

### 2. Verify Gate 6 Approval
Before preparation starts: Does GATE_P6.md exist with a green or yellow approval from both reviewers?
If not: Stop and point out that Gate 6 must be completed first.

### 3. Delegation to DevOps Agent (Lead)
Delegate deployment preparation to the **devops** agent:

> Prepare the deployment for the following environment: **$ARGUMENTS**
> Context from INFRASTRUCTURE.md: [Apply hosting, environment configurations, CI/CD pipeline]
>
> **A. Environment Check**
> - Are all required environment variables set in the target environment?
> - Are configurations correct (CORS origins, Allowed Hosts, API URLs) for the target environment?
> - Are all external services (email, payment, monitoring) configured for the target environment?
> - Are secrets correctly stored (database passwords, API keys, certificates)?
>
> **B. Database Migrations**
> - Which migrations need to be executed for this deployment?
> - Have all migrations been successfully tested on the staging environment?
> - Are there destructive migrations (DROP COLUMN, DELETE)? If so: backup beforehand?
> - Is a rollback of the migrations possible if needed?
>
> **C. Deployment Artifacts**
> - Is the release branch clearly identified and tagged (e.g. v1.0.0)?
> - Are all CI checks passing on the release tag?
> - Are Docker images built and available in the container registry?
>
> **D. Rollback Plan**
> - What is the rollback procedure if the deployment fails?
> - How long does a rollback take?
> - Who is responsible for the rollback decision?
> - Are the database state and application code consistent during a rollback?
>
> **E. Downtime Planning**
> - Is a maintenance page/maintenance mode prepared for the deployment?
> - Is there a zero-downtime deployment (Blue/Green, Rolling Update)?
> - If downtime is unavoidable: what is the best time window?
>
> **F. Pre-Launch Checklist**
> Create a concrete, actionable checklist for the upcoming deployment.
> Each item should be checkable as ✅/❌.

### 4. Delegation to Senior Developer Agent (Support)
Delegate technical migration verification to the **senior-developer** agent:

> Review the deployment preparation from the DevOps agent:
> 1. Are all database migrations correct and complete?
> 2. Are there code changes that require a specific migration order?
> 3. Are there known breaking changes that require special deployment measures?

### 4. Write Detail File
Write the result to `docs/launch/PREPARE.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P7
subskill: prepare
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Environment Check` (status per item), `## Migration Plan`, `## Rollback Plan`, `## Pre-Launch Checklist` (actionable items).

(File replaces the legacy `DEPLOYMENT_CHECKLIST.md` name — keep `PREPARE.md` going forward; the actual deployment steps live separately in `DEPLOYMENT.md` written by `/p7-deploy`.)

### 5. Update Phase Index
Update `docs/launch/LAUNCH.md` (create from index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[PREPARE.md](PREPARE.md)` with status `complete`.
- Lift any unfinished checklist item into **Open Risks / Open Questions** so it cannot be missed before `/p7-deploy`.

## Result

- **`docs/launch/PREPARE.md`** (complete deployment preparation)
- **`docs/launch/LAUNCH.md`** (phase index updated)
- Prerequisite for `/p7-deploy` – no deployment without a completed checklist

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
