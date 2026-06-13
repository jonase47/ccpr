# Project: {{PROJECT_NAME}}

## Project Type
<!-- Software | Business | Software+Business -->
{{PROJECT_TYPE}}

## Description
{{PROJECT_DESCRIPTION}}

## Current Phase
<!-- Updated by the workflow -->
**Phase**: P0 – Discovery
**Status**: Not started

## Constitution (mandatory read in Full-Track)

This project has a `docs/CONSTITUTION.md` with three sections (Inviolable / Default / Aspirational).
**Inviolables** are mandatory at all Gates (`gate-preflight.py` extracts them into the preflight report)
and at every ADR. Updates via `/constitution` (MINOR bump for Default/Aspirational, MAJOR bump for Inviolable).

## Baseline
<!-- Filled by /release-baseline. Leave empty before the first release. -->

## Project Goals
<!-- What should be the end result? -->
- {{GOAL_1}}
- {{GOAL_2}}

## Target Audience
<!-- Who uses the result? -->
{{TARGET_AUDIENCE}}

## Constraints
<!-- Specifics of this project -->
- **Budget**: {{BUDGET}}
- **Timeline**: {{TIMELINE}}
- **Regulatory**: {{REGULATORY}} <!-- e.g. DSGVO (GDPR), health data, DiGA -->
- **Infrastructure**: Hetzner Cloud, Self-Hosted, Gitea

## Tech Stack (if software project)
<!-- Defined in P3, only preferences/constraints here -->
{{TECH_PREFERENCES}}

## Key Decisions
<!-- Filled during project progress -->
| Date | Decision | Phase | Rationale |
|---|---|---|---|
| | | | |

## Open Risks
<!-- Filled during project progress -->
| Risk | Severity | Status | Countermeasure |
|---|---|---|---|
| | | | |

## Phase Status Tracker
| Phase | Status | Gate passed | Date |
|---|---|---|---|
| P0 Discovery | ⬜ Not started | ⬜ | |
| P1 Conception | ⬜ Not started | ⬜ | |
| P2 Validation | ⬜ Not started | ⬜ | |
| P3 Architecture | ⬜ Not started | ⬜ | |
| P4 Planning | ⬜ Not started | ⬜ | |
| P5 Implementation | ⬜ Not started | ⬜ | |
| P6 Quality Assurance | ⬜ Not started | ⬜ | |
| P7 Launch | ⬜ Not started | ⬜ | |
| P8 Operations | ⬜ Not started | – | |

## Agent Notes
<!-- Project-specific instructions for agents -->
<!-- Examples:
- "konzeptor: Focus on accessibility, target audience 50+"
- "business-analyst: Consider funding constraints and pricing model"
- "devops: Deploy on existing self-hosted server"
-->
{{AGENT_NOTES}}

## Project Memory & Instincts
Memory is two-tier:
- **Tier 1 (cross-cutting):** `docs/memory/{type}_{slug}.md` with index `docs/memory/MEMORY.md`. Read by orchestrator and all agents.
- **Tier 2 (persona-specific):** `docs/memory/{agent}/` — each subagent's own silo (MEMORY.md + topic files).

Instincts have three scopes: `~/.claude/instincts.md` (global), `docs/instincts.md` (project + cross-agent), `docs/memory/{agent}/instincts.md` (agent-specific).

Tier separation rule and full details: see global `~/.claude/CLAUDE.md`. Both tiers are read at session start and maintained by `/postmortem`.

**Schema & Lint:** Memory files follow `~/.claude/templates/MEMORY_SCHEMA.md` (required fields: `name`, `description`, `type`, `last_updated`). Validation: `bash ~/.claude/scripts/memory-lint.sh` (read-only).

## Handover
On session changes, `docs/HANDOVER.md` is automatically updated. New sessions read it at the start for seamless continuation. Template: `~/.claude/templates/HANDOVER_TEMPLATE.md`.

## Phase Documents (Index + Detail Files)
Every phase produces a slim **phase index** plus one **detail file per subskill** (Document Splitting Convention — full spec in `~/.claude/docs/PROJECT_PHASES.md`). Subskill commands write detail files; the gate command reads the index first and pulls detail files only as needed. P3 and P6 add a sub-index level (e.g. `architecture/SECURITY.md` as sub-index for the `/p3-sec-*` subskills).

**Schema & Lint:** Phase-detail and sub-index files follow `~/.claude/templates/PHASE_DOC_SCHEMA.md` (required fields: `phase`, `subskill`, `status ∈ {skeleton, draft, active, frozen, archived}`, `last_updated`). Validation: `bash ~/.claude/scripts/phase-docs-lint.sh [--scope <glob>]`. Doc-volume watcher: `bash ~/.claude/scripts/doc-volume-check.sh` (warns for files ≥25/40/50 KB with a splitting suggestion).

## Directory Structure
```
{{PROJECT_NAME}}/
├── .claude/
│   └── CLAUDE.md              ← This file
├── docs/
│   ├── memory/                ← Project Memory (feedback, project, reference)
│   │   └── MEMORY.md
│   ├── instincts.md           ← Project Instincts (optional)
│   ├── HANDOVER.md            ← Handover for session changes
│   ├── discovery/             ← P0: DISCOVERY.md (index) + PROBLEM.md, MARKET.md, REGULATORY.md
│   ├── concept/               ← P1: CONCEPT.md (index) + USER_JOURNEYS.md, FEATURES.md, BUSINESS_MODEL.md, FINANCIAL_PLAN.md, DSGVO_INITIAL_ASSESSMENT.md
│   ├── validation/            ← P2: VALIDATION.md (index) + ASSUMPTIONS.md, MARKET_VALIDATION.md, POC.md, REGULATORY_CHECK.md
│   ├── architecture/          ← P3: ARCHITECTURE.md (index) + COMPONENTS.md, TECH_STACK.md, NFR.md, DATA_MODEL.md, ADR/, COST_ESTIMATION.md
│   │   ├── SECURITY.md        ← P3 sub-index: THREATS.md, AUTH.md, DATA_SECURITY.md, API_SECURITY.md, CHECKLIST.md
│   │   ├── UX_CONCEPT.md      ← P3 sub-index: WIREFRAMES.md, A11Y.md, DARKMODE.md, NAVIGATION.md
│   │   └── INFRA.md           ← P3 sub-index: HOSTING.md, CICD.md, MONITORING.md, TESTSTRATEGY.md
│   ├── planning/              ← P4: PROJECT_PLAN.md (index) + BACKLOG.md, SPRINT.md, RISKS.md
│   ├── quality/               ← P6: QA.md (index) + A11Y.md, AUDIT.md, FUNCTIONAL.md, PENTEST.md sub-indexes plus their detail files
│   ├── launch/                ← P7: LAUNCH.md (index) + RUNBOOK.md, DEPLOYMENT.md, MONITORING.md, RELEASE_DOCS.md, GTM.md
│   └── operations/            ← P8: OPS.md (index) + BUSINESS.md, ITERATION.md, OPS_REVIEW.md, SECURITY.md
├── src/                       ← P5: Source code
├── tests/                     ← P5: Tests
└── README.md                  ← P4: Created by the Tech Writer
```
