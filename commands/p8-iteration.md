# /p8-iteration – Evaluate Feedback, Maintain Backlog & Plan Next Sprint

Evaluates user feedback and operational insights, maintains the backlog, and initiates the next iteration. This is the link between ongoing operations and the next development round – the engine of the evolution loop.

## Argument: $ARGUMENTS = [Topic/feature area, e.g. "user feedback week 10", "technical debt", "new feature ideas"]

If provided: Focus the iteration planning on the specified topic.
If not provided: Read all available inputs (KPI reports, incident reports, user feedback) and conduct complete iteration planning. If any context is missing, ask about the available feedback sources.

## 0. Work-item adoption guard (ADR-0002 §8)

Run `python3 ~/.claude/scripts/workitems.py list`.
- **Non-empty array** → the project uses the structured store. Use the CLI for the backlog updates
  in step 2B below (instead of hand-editing BACKLOG.md prose).
- **`[]` and no `docs/workitems/` directory** → still on prose. Edit BACKLOG.md directly, as before.
  Emit one line: *"Tip: run `lift` to adopt the structured work-item store."*
- **`[]` but `docs/workitems/` exists** → adopted store, just empty right now. Treat as adopted: use
  the CLI, not the prose fallback.

See Manual/WORKITEMS.md §8 for the full guard rationale and the status-verb mapping.

## Execution

### 1. Read Context
Read the following files (if available):
- **KPI_REPORT_[current].md** (business insights and recommendations)
- **INCIDENT_REPORT_*.md** / **OPS_REVIEW_*.md** (technical operational insights)
- **SECURITY_UPDATE_*.md** (open security findings)
- **BACKLOG.md** (current backlog status) / `workitems list` (structured store, per the §8 guard)
- **PROJECT_PLAN.md** (milestones and progress to date)
- **FEATURES.md** (original prioritisation as reference)

### 2. Delegation to Project Planner Agent (Lead)
Delegate iteration planning to the **project-planner** agent:

> Plan the next iteration based on: **$ARGUMENTS**
> Input: [Apply KPI recommendations, incident findings, security updates, user feedback]
>
> **A. Feedback Evaluation**
> Collect and categorise all inputs from the ongoing operational phase:
>
> | Source | Feedback/Finding | Category | Priority |
> |---|---|---|---|
> | KPI report | (e.g. churn at feature X) | Feature adjustment | High |
> | Incident report | (e.g. recurring DB timeout) | Technical debt | Medium |
> | Security update | (e.g. open CVE) | Security | Critical |
> | User feedback | (e.g. request for export function) | New feature | Low |
>
> Categories: Bug fix / Feature adjustment / New feature / Technical debt / Security / Performance / UX improvement
>
> **B. Update Backlog**
> Using the guard result from step 0:
> - Structured store: new items from the feedback evaluation → `workitems create --title "<item>"
>   --type feat --description "<estimate + acceptance criteria>"` (check the full, unfiltered
>   `workitems list` for a matching title first — trim + casefold — so a re-run never duplicates an
>   already-added item; record the assigned `**Work-Item:** WI-NNNN` id in the generated view, §4).
>   Outdated items (no longer relevant) → `workitems set-status <id> "Cancelled"` (resolve `<id>` by
>   matching title against `workitems list`), never a silent removal — a Cancelled item stays
>   traceable. Re-prioritising existing items (ranking, not a status change) has no CLI equivalent
>   yet — keep that ordering in the generated BACKLOG.md view.
> - Prose fallback: add new items to BACKLOG.md (with estimates and acceptance criteria);
>   re-prioritise existing items; mark or remove outdated items (no longer relevant).
> - Make technical debt visible as its own epic (if accumulated) — either way, this is a BACKLOG.md
>   view-level grouping, not a per-item CLI operation.
>
> **C. Evolution Loop Decision**
> Based on the scope and nature of the next work: where does the evolution loop go?
>
> | If... | Then back to... |
> |---|---|
> | New features with significant scope | P1 (Conception) – plan new user journeys, features |
> | Architecture must be adjusted for scaling or new features | P3 (Architecture) – write ADR, adjust model |
> | Small improvements and bug fixes | P5 (Implementation) – directly into sprint |
>
> Clearly recommend which loop entry point you recommend for the next iteration and why.
>
> **D. Prepare Next Sprint** (if P5 loop)
> If the next iteration goes directly into implementation:
> - Propose a sprint goal
> - Select the top stories from the updated backlog
> - Hand over to `/p4-sprint` for formal sprint planning

### 3. Delegation to Konzeptor Agent (Support)
Delegate content prioritisation to the **konzeptor** agent:

> Supplement the project planner's iteration planning from a product and user perspective:
> 1. Which items from the backlog have the greatest positive impact on the user experience?
> 2. Are there user feedback signals indicating structural concept problems (→ P1)?
> 3. What should the communication of the next iteration look like for users (changelog, release notes)?

### 4. Write Detail File
Write the result to `docs/operations/ITERATION.md` (living — overwritten on each call to reflect the most recent iteration plan). Frontmatter:

```yaml
---
phase: P8
subskill: iteration
status: living
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Iteration Period`, `## Feedback Evaluation` (table), `## Evolution Loop Decision` (with reasoning: back to P1 / P3 / P5 / hold), `## Next Iteration Recommendation`.

Cross-file updates:
- Structured store: new/cancelled work items from step 2B (`workitems create`/`set-status`).
  `docs/planning/BACKLOG.md` (P4 living, generated view) still gets re-prioritised and its
  `last_updated` bumped, but item creation/cancellation itself goes through the CLI, not hand-edits.
- Prose fallback: `docs/planning/BACKLOG.md` (P4 living): add new items, re-prioritise, mark
  outdated; bump `last_updated`.
- `docs/planning/PROJECT_PLAN.md` (P4 phase index): update the `## Milestones & Release Planning` body section with the next iteration's milestones; bump `last_updated`.

### 5. Update Phase Index
Update `docs/operations/OPS.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[ITERATION.md](ITERATION.md)` with status `living`.
- Lift the evolution-loop decision into **Key Decisions**.

## Result

- **`docs/operations/ITERATION.md`** (latest iteration plan)
- New/cancelled work items (structured store) or updated **`docs/planning/BACKLOG.md`** (prose fallback, re-prioritised either way)
- Updated **`docs/planning/PROJECT_PLAN.md`** (next-iteration milestones)
- **`docs/operations/OPS.md`** (phase index updated)
- **PROJECT_PLAN.md** (updated)
- **ITERATION_PLAN_[Date].md** (feedback evaluation, loop decision, next steps)

## Ongoing Operational Checkpoints (no one-time gate)

P8 has no final gate, as operations run continuously. Instead, these ongoing checkpoints apply – they should be reviewed regularly (monthly recommended):

- [ ] Monitoring shows no critical anomalies (→ `/p8-ops`)
- [ ] All production incidents are documented and resolved (→ `/p8-ops`)
- [ ] KPIs are evaluated regularly (→ `/p8-business`)
- [ ] Security updates are applied promptly (→ `/p8-security`)
- [ ] Backups are checked regularly
- [ ] User feedback is systematically captured (→ `/p8-iteration`)
- [ ] Backlog is maintained and prioritised regularly (→ `/p8-iteration`)

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
