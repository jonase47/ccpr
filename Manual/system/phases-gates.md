---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: phase-model-and-gates
last_updated: 15.05.2026
---

# Phase Model & Gates

## Track Decision (Entry Point)

Every new project starts with `/track-decision`, which chooses between two parallel tracks:

```
/track-decision
     |
     +-- LEAN (Prototyp/PoC/Spike, 4 skills, no gates)
     |       |
     |       +-- /lean-frame -> [TDD build] -> /lean-learn
     |                                              |
     |                              +---------------+----------------+
     |                              |               |                |
     |                           PROMOTE         PIVOT             DROP
     |                              |               |                |
     |                       /lean-promote   /lean-frame        [repo frozen]
     |                              |       (re-frame or
     |                              |        hard reset)
     |                              v
     +----> FULL ---> /project-init -> /constitution -> /p0-problem -> ...
                                                         (P0-P8 full pipeline)
```

**Decision criteria** (see `/track-decision`): Knockouts K1-K5 (DSGVO PII, special categories, launch-imminent, BFSG/regulatory, external stakeholders) + Indicator Score I1-I5. Mid-flight re-assessment allowed; **no downgrade Full -> Lean** (Lean is a transient fast-test shortcut, see `Manual/LEAN_TRACK.md`).

## Lean-Track Skills (4)

| Skill | Purpose |
|---|---|
| `/track-decision` | Lean vs Full decision (track-agnostic re-assessment tool) |
| `/lean-frame` | `docs/FRAME.md` + `docs/CLAUDE-lean.md` (one-page Single Source of Truth) |
| `/lean-learn` | `docs/LEARNINGS.md` + decision PROMOTE/PIVOT-soft/PIVOT-hard/DROP |
| `/lean-promote` | `docs/PROMOTION_BRIEF.md` as bootstrap input for `/project-init` |

## Full-Track Phase Overview

```
P0 Discovery --> P1 Conception <---> P2 Validation --> P3 Architecture
     |                |                    |                   |
     v                v                    v                   v
 [Gate 0]         [Gate 1]            [Gate 2]             [Gate 3]
                                                               |
P4 Planning --> P5 Implementation --> P6 Quality --> P7 Launch
     |            | <-- Sprint Loop --+       |              |
     v            v                    v       v              v
 [Gate 4]     [Gate 5]             [Gate 6]  [Gate 7]
                                                    |
                                          P8 Operations & Evolution
                                          | <-- Evolution Loop
                                          v    back to P1/P3/P5
```

## Phases in Detail

| Phase | Name | Lead Agent | Question | Gate Type |
|---|---|---|---|---|
| P0 | Discovery | Konzeptor | "Is it worth it?" | Go/No-Go |
| P1 | Conception | Konzeptor | "What are we building?" | Completeness Gate |
| P2 | Validation | Konzeptor | "Are the assumptions correct?" | Go/No-Go/Pivot |
| P3 | Architecture & Design | System-Architekt | "How do we build it?" | Completeness Gate |
| P4 | Planning | Project-Planner | "In what order?" | Readiness Gate |
| P5 | Implementation | Senior-Developer | "Let's build!" | Sprint Gate (repeated) |
| P6 | Quality Assurance | QA-Tester | "Is it stable?" | Approval Gate (QA + Security) |
| P7 | Launch & Deployment | DevOps | "Ship it!" | Go-Live Gate (Tech + Business) |
| P8 | Operations & Evolution | DevOps + Business-Analyst | "Is it running?" | Continuous |

## Iterative Loops

- **Validation Loop (P1 <-> P2):** Sharpen concept, validate, adjust
- **Sprint Loop (P5 <-> P6):** Implement, test, fix, next feature
- **Evolution Loop (P8 -> P1/P3/P5):** From operations back to earlier phases

## Gate Types

| Type | Meaning | Example |
|---|---|---|
| Go/No-Go | Binary decision: continue, stop, or pivot | Gate 0, Gate 2 |
| Completeness Gate | All defined results must be present | Gate 1, Gate 3 |
| Readiness Gate | Technical + organizational prerequisites met | Gate 4 |
| Sprint Gate | Repeated per sprint, checks implementation quality | Gate 5 |
| Approval Gate | Formal approval by QA and Security | Gate 6 |
| Go-Live Gate | Technical readiness + business readiness | Gate 7 |

## Gate Transitions

Gates are the only way to move to the next phase:

```
gate-p0 -> /p1-journeys
gate-p1 -> /p2-assumptions
gate-p2 -> /p3-architecture
gate-p3 -> /p4-backlog
gate-p4 -> /p5-implement (or /p4-sprint)
gate-p5 -> /p4-sprint (next sprint) or /p6-functional (all sprints done)
gate-p6 -> /p7-prepare
gate-p7 -> /p8-ops
```

Detailed gate checklists are in [PROJECT_PHASES.md](../../docs/PROJECT_PHASES.md).
