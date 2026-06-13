# /p3-infra – Infrastructure, CI/CD & Test Strategy

Plans infrastructure, CI/CD pipeline, monitoring and test strategy. Each area is its own sub-skill.

## Argument: $ARGUMENTS = [Focus, e.g. "CI/CD", "Monitoring", "Hosting"]

If provided: Passed through to the sub-skills.
If not provided: All sub-skills run sequentially.

## Flow

### 0. Ensure Sub-Index Exists
Make sure `docs/architecture/INFRA.md` exists as a **sub-index** with the standard header (Status / Last Updated / Key Decisions / Open Risks / Detail Files / Gate Notes — see `~/.claude/docs/PROJECT_PHASES.md`). If missing, create it with empty placeholders. The four `p3-infra-*` sub-skills below each refresh their own row in this sub-index's **Detail Files** table.

### 1. Hosting & Deployment Strategy
`/p3-infra-hosting $ARGUMENTS` – Hosting platform, deployment model, environments.

### 2. CI/CD Pipeline
`/p3-infra-cicd $ARGUMENTS` – Pipeline stages, branch strategy, rollback.

### 3. Monitoring & Observability
`/p3-infra-monitoring $ARGUMENTS` – Logging, metrics, alerting, error tracking.

### 4. Test Strategy
`/p3-infra-teststrategy $ARGUMENTS` – Test levels, tools, coverage targets, critical paths.

### 5. Roll Up Sub-Index to Phase Index
After all `p3-infra-*` sub-skills have run, summarise the infrastructure sub-index into the phase index `docs/architecture/ARCHITECTURE.md`:
- Add an entry in the phase-index **Detail Files** table for `[INFRA.md](INFRA.md)` (the sub-index itself), status `complete` once all four sub-skill rows are `complete`.
- Lift the headline infrastructure decisions (hosting platform, CI/CD tool, coverage target) into the phase-index **Key Decisions**.

### 6. Final HANDOVER Update (Orchestrator-owned)

The orchestrator owns the final `docs/HANDOVER.md` update for this P3 section. Sub-skills (`/p3-infra-*`) also contain a Handover Epilogue — this is intentional, so the sub-skills remain usable on their own. **However, when this orchestrator runs, the orchestrator's HANDOVER update is the authoritative one and supersedes individual sub-skill updates.** Consolidate the four infra detail files into a single HANDOVER entry.

## Notes
- Steps 1-2 sequential (CI/CD requires hosting information)
- Steps 3-4 can run in parallel after 1+2
- Results: `INFRA.md` (sub-index) plus `HOSTING.md`, `CICD.md`, `MONITORING.md`, `TESTSTRATEGY.md` detail files

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for permitted transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
