---
disable-model-invocation: true
---
# /p3-infra-monitoring – Monitoring & Observability

Defines logging, metrics, alerting and error tracking.

## Argument: $ARGUMENTS = [Focus, e.g. "Alerting", "Logging", "APM"]

If provided: Deep-dive the named area.
If not provided: Create complete monitoring concept.

## Prerequisites
- INFRASTRUCTURE.md with hosting and CI/CD exists

## Agent
- **Type**: devops
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From INFRASTRUCTURE.md: Hosting platform and deployment model
- From ARCHITECTURE.md: Critical components
- From TECH_STACK.md: Technologies in use

## Prompt Template
> **Goal**: Define monitoring and observability. Focus: $ARGUMENTS
>
> **Context**:
> [inline from INFRASTRUCTURE.md, ARCHITECTURE.md]
>
> **Output Format**:
> 1. Logging: tool, retention, log level strategy (2-3 sentences)
> 2. Metrics: Table | Metric | Threshold | Alert |
> 3. Alerting: channels and escalation levels (1-2 sentences)
> 4. Error tracking: tool and integration (1 sentence)
> 5. Uptime monitoring: tool and check interval (1 sentence)
>
> **Constraints**:
> - ONLY monitoring, NO hosting, NO CI/CD
> - Max. 8 metrics
> - Tools must match the hosting (self-hosted vs. SaaS)

## Orchestrator Checkpoint
- [ ] Metrics cover CPU, memory, response time, error rate?
- [ ] Alerting channels defined?

## Write Detail File
Write the result to `docs/architecture/MONITORING.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: infra-monitoring
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Logging`, `## Metrics` (the table metric / threshold / alert), `## Alerting`, `## Error Tracking`, `## Uptime Monitoring`.

## Update Sub-Index
Update `docs/architecture/INFRA.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[MONITORING.md](MONITORING.md)` with status `complete`.
- Lift the headline tool decisions into **Key Decisions** of the sub-index.
- Do not edit `ARCHITECTURE.md` directly.

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
