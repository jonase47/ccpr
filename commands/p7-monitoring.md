# /p7-monitoring – Set Up Monitoring & Test Rollback Plan

Sets up production monitoring completely, configures alerting rules, and tests the rollback plan. The goal is a system that reports problems early and where a rollback works smoothly in an emergency.

## Argument: $ARGUMENTS = [Focus, e.g. "Alerting", "Logging", "Performance", "complete"]

If provided: Focus the setup on the specified area.
If not provided: Read INFRASTRUCTURE.md and set up all monitoring components completely. If any context is missing, ask about the monitoring infrastructure in use.

## Execution

### 1. Read Context
Read the following files (if available):
- **INFRASTRUCTURE.md** (monitoring concept, alerting strategy, chosen tools)
- **DEPLOYMENT_LOG.md** (current deployment status – monitoring builds on this)
- **SECURITY.md** (security-relevant events that must be monitored)
- **FEATURES.md** (which critical features should be monitored especially closely)

### 2. Delegation to DevOps Agent (Lead)
Delegate monitoring setup to the **devops** agent:

> Set up production monitoring. Focus (if specified): **$ARGUMENTS**
> Monitoring concept from INFRASTRUCTURE.md: [Apply tools, metrics, alerting strategy]
>
> **A. Application Performance Monitoring (APM)**
> - Response time metrics: P50, P95, P99 for all critical endpoints
> - Error rate: percentage of failed requests per endpoint
> - Throughput: requests per second / minute
> - Database queries: enable slow query logging (define threshold)
>
> **B. Infrastructure Monitoring**
> - CPU usage: warning at X%, critical at Y%
> - RAM usage: warning and critical thresholds
> - Disk space: warning at 80%, critical at 90%
> - Network: unusual traffic (potential DDoS signals)
>
> **C. Uptime & Health Checks**
> - External uptime monitor: checks every N minutes from outside whether the application is reachable
> - Health endpoint (/health): returns database connection, external services, and version
> - Alerting on outage: immediate notification on downtime
>
> **D. Logging**
> - Central log aggregation system configured (according to INFRASTRUCTURE.md)
> - Log level for production: INFO for normal events, WARN for irregularities, ERROR for failures
> - Structured logging (JSON) for machine-readable evaluation
> - Log retention: how long are logs kept?
> - Security logs: failed logins, unusual access attempts logged separately
>
> **E. Alerting Rules**
> Define concrete alerting rules with threshold, channel, and escalation:
> | Metric | Threshold | Channel | Escalate after |
> |---|---|---|---|
> | Uptime | outage > 1 min | SMS + Slack | immediately |
> | Error rate | > 5% over 5 min | Slack | 15 min: SMS |
> | Response time P99 | > 5s | Slack | 30 min: SMS |
> | CPU | > 85% over 10 min | Slack | – |
> | Disk | > 80% | Slack | – |
>
> **F. Test Rollback Plan**
> Execute a rollback test (on staging or with a controlled procedure):
> - Run through the rollback procedure once completely
> - Measure time: how long does a complete rollback take?
> - Check database state: is the state after rollback consistent?
> - Document the test result in RUNBOOK.md

### 3. Delegation to Security Master Agent (Support)
Delegate security monitoring configuration to the **security-master** agent:

> Supplement the DevOps agent's monitoring setup with security-relevant monitoring:
> 1. Which security events must be monitored in production? (Brute force, unusual access attempts, privilege escalation attempts)
> 2. Are the alerting thresholds for security events correct?
> 3. Are security-relevant logs retained sufficiently (for forensics)?

### 4. Write Detail File
Write the result to `docs/launch/MONITORING.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P7
subskill: monitoring
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Monitoring Components & Dashboards`, `## Alerting Rules` (complete table), `## Incident Response Process`, `## Rollback Instructions` (step by step, copy-paste ready), `## On-Call Contacts`.

(File replaces the legacy `RUNBOOK.md` name in this phase — `RUNBOOK.md` was previously also used in `/p7-prepare`; the new layout splits the responsibilities cleanly: PREPARE.md = pre-launch checklist, DEPLOYMENT.md = actual deployment log, MONITORING.md = ongoing monitoring & runbook.)

### 5. Update Phase Index
Update `docs/launch/LAUNCH.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[MONITORING.md](MONITORING.md)` with status `complete`.
- Lift the alerting target (e.g. "Sentry + Grafana with PagerDuty escalation") into **Key Decisions**.
- Lift any rollback-readiness gap into **Open Risks**.

## Result

- **`docs/launch/MONITORING.md`** (monitoring overview, alerting rules, incident response, rollback instructions)
- **`docs/launch/LAUNCH.md`** (phase index updated)
- Active monitoring dashboard in production
- Tested rollback plan
- Foundation for Phase 8 (Operations) and `/gate-p7`

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
