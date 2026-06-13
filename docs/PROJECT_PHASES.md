# Project Phases Model

## Overview

Hybrid phase model with a linear base flow and iterative loops within phases.
Each phase has a quality gate – a checklist that must be fulfilled before the next phase begins.
The model applies equally to software projects AND business ventures.

```
+----------------------------------------------------------------------+
|                                                                      |
|  P0 Discovery -> P1 Conception -> P2 Validation -> P3 Architecture   |
|       |              |               |                |              |
|       v              v               v                v              |
|   [Gate 0]       [Gate 1]       [Gate 2]          [Gate 3]          |
|                                                       |              |
|  P4 Planning -> P5 Implementation -> P6 Quality -> P7 Launch        |
|       |          | <---- loop ---+        |            |            |
|       v          v  (Sprint Loop) v        v            v            |
|   [Gate 4]    [Gate 5]        [Gate 6]    [Gate 7]                  |
|                                                       |              |
|                                              P8 Operations &        |
|                                                 Evolution           |
|                                              | <---- loop --- back  |
|                                              v         to P1/P3/P5  |
|                                                                      |
+----------------------------------------------------------------------+
```

### Iterative Loops
- **Sprint Loop (P5 <-> P6)**: Implement -> test -> fix -> next feature
- **Validation Loop (P1 <-> P2)**: Sharpen concept -> validate -> adjust concept
- **Evolution Loop (P8 -> P1/P3/P5)**: From operations back to conception, architecture, or implementation

### Lean-Track Adaptation (parallel to Full-Track)

For prototypes, PoCs, tech-spikes, and validation projects, the full P0–P8 pipeline is overkill. The **Lean-Track** compresses P0+P1+P3 into a single `docs/FRAME.md` file (max. 5 KB, 8 sections) and skips P2/P4/P6/P7/P8 entirely.

```
/track-decision → Lean    (Knockout K1–K5 + Indicator score I1–I5)
   ↓
/lean-frame → docs/FRAME.md + docs/CLAUDE-lean.md  (optional: /constitution)
   ↓
[Build freely with senior-developer + Standard-TDD-Loop, no sprint ceremony]
   ↓
/lean-learn → docs/LEARNINGS.md → {PROMOTE | PIVOT-soft | PIVOT-hard | DROP}
   ↓ (PROMOTE)
/lean-promote → docs/PROMOTION_BRIEF.md (7 sections)
   ↓
/project-init → reads Brief, starts Full-Track from P0 (same repo, Lean artifacts in docs/lean-archive/)
```

**Lean-Track skills (4):** `/lean-frame`, `/lean-learn`, `/lean-promote` + entry point `/track-decision`. Constitution is optional (Constitution-Light in FRAME sufficient); use `/constitution` if needed.

**Promotion trigger (Lean → Full, mid-flight):** Real-person PII enters scope, lifetime >3 months, stakeholder requires gates, compliance audit announced, codebase >5,000 LOC. **No downgrade Full → Lean.**

**Pivot variants:**
- **Soft-Pivot:** New hypothesis, same tech base. Code stays; FRAME moves to `lean-archive/FRAME_v{N}.md`, new FRAME with `pivot_version: N+1`.
- **Hard-Pivot:** Wrong core assumption, tech reset. Code + FRAME move to `lean-archive/v{N}/` or branch `lean-archive/v{N}`.

Full spec: `Manual/LEAN_TRACK.md`.

### Cross-Cutting Mechanisms

**Constitution (Full-Track mandatory artifact):** Every Full-Track project has `docs/CONSTITUTION.md` with three sections (Inviolable / Default / Aspirational). Created by `/project-init` (via the `/constitution` sub-skill) — either as a greenfield with a domain bootstrap (`saas-b2c`, `mobile-b2c`, `b2b-tool`, `b2c-marketplace`, `on-device-privacy`) or as a promotion from Lean (with constitution candidates from `docs/PROMOTION_BRIEF.md`). Gates read the Inviolable section as a mandatory input (via `gate-preflight.py constitution_check`); a violation = "Inviolable breach". Versioning: semver-light, MAJOR bump on Inviolable change requires an ADR.

**Cross-Check (optional consistency check):** `/cross-check` runs optionally before gates and checks inconsistencies across phases via 7 rules (features ↔ auth, tech stack ↔ data model, threats ↔ mitigations, NFR ↔ test strategy, ADR status ↔ components, Constitution ↔ ADRs, story ↔ epic). Output: `docs/.cross-check-report.md`. Recommended, not a mandatory step (performance consideration).

**Wingman Consolidation**: When parallel agents produce results, the **wingman** agent consolidates them into a compact summary (max. 15 sentences). Agents write their full results to files and return only a brief summary (max. 5 sentences). This saves tokens and keeps the context lean.

**Handover (HANDOVER.md)**: On session changes, `docs/HANDOVER.md` in the project directory is maintained – current work state, open decisions, next steps. New sessions read it at the start for seamless continuation. Template: `~/.claude/templates/HANDOVER_TEMPLATE.md`.

**Strategic Compact**: After intensive work phases (100+ tool calls), the agent-monitor reminds about `/compact`. Before `/compact`, HANDOVER.md is always updated, then read again afterward.

**Document Splitting Convention**: Every phase produces results in a two-level pattern — a slim phase index plus one detail file per subskill. This prevents monolithic phase documents (multi-tens-of-KB single files that mix decisions, detail, and gate notes) and lets agents and gates load only what they need.

```
docs/<phase-folder>/
├── <PHASE>.md              ← Phase index (~5–15 KB): status, key decisions, links
└── <SUBSKILL>.md           ← Detail file per subskill (independently readable)
```

P3 and P6 carry an additional **sub-index level** under their lead-commands (e.g. `architecture/SECURITY.md` is a sub-index for the `/p3-sec-*` subskills, with `THREATS.md`, `AUTH.md`, etc. as detail files underneath).

**Sub-Index for growing detail files (generic)**: Any detail file that grows beyond ~20 KB or aggregates many discrete entities (epics, threats, journeys, ADRs, etc.) MAY become a **sub-index** with its own detail files in a sibling subfolder. This is the same mechanism P3/P6 use, generalised to any phase.

```
docs/<phase-folder>/
├── <PHASE>.md              ← Phase index
├── <SUBSKILL>.md           ← Sub-index (kind: sub-index)
└── <subskill>/
    ├── <ENTITY-01>.md      ← Detail file (kind: <type>-detail)
    ├── <ENTITY-02>.md
    └── <CROSS_REF>.md      ← Optional cross-reference tables (e.g. STORY_INDEX, FEATURE_COVERAGE)
```

*Concrete example (P4 Backlog with 8 epics, 53 stories)*:

```
docs/planning/
├── PROJECT_PLAN.md             ← Phase index
├── BACKLOG.md                  ← Sub-index (kind: sub-index, ~6–8 KB)
├── SETUP.md
└── backlog/
    ├── E01-foundation.md       ← Epic detail (kind: epic-detail)
    ├── E02-onboarding.md
    ├── ...
    ├── STORY_INDEX.md          ← Cross-ref: all stories at a glance
    └── FEATURE_COVERAGE.md     ← Cross-ref: feature ↔ epic mapping
```

*Lean-Index Rule*: A sub-index keeps only the navigation layer — status, overview table (one row per detail file), cross-file dependencies (DAG), and the link list. Bodies (stories, threat descriptions, ADR rationale) live in the detail files. The detail files keep their own short frontmatter with `kind: <type>-detail`.

*When to introduce a sub-index*: When a single detail file passes ~20 KB, or whenever a "living document" (e.g. backlog) is expected to grow substantially. Sub-indexes are optional — small phases stay flat.

*Concrete thresholds per skill (when in doubt, prefer Sub-Index — splitting later is more painful than splitting early):*

| Skill | File | Threshold (entity-count / size) | Sub-Index target |
|---|---|---|---|
| `/p3-arch-components` | `COMPONENTS.md` | ≥7 components OR ≥20 KB | `components/<COMPONENT>.md` |
| `/p3-data-model` | `DATA_MODEL.md` | ≥7 entities OR ≥25 KB | `data-model/<ENTITY>.md` |
| `/p3-data-model` | `API_SPEC.md` | ≥9 endpoints OR ≥25 KB | `api-spec/<RESOURCE>.md` |
| `/p3-ux-wireframes` | `WIREFRAMES.md` | ≥6 screens OR ≥25 KB | `wireframes/<SCREEN>.md` |
| `/p4-backlog` | `BACKLOG.md` | ≥6 epics OR ≥20 KB | `backlog/E0X-<slug>.md` |
| `/p4-sprint` | `SPRINT.md` | ≥10 KB OR sprint history matters | `sprint/SPRINT-NN.md` |
| `/p4-sprint` | `RISKS.md` | ≥7 risks OR ≥8 KB | `risks/R-NN-<slug>.md` |
| `/p5-polish` | `POLISH.md` | when `SPRINT.md` is sub-index (per-sprint history) | `polish/POLISH-SPRINT-NN.md` |
| `/p4-setup` | `SETUP.md` | ≥10 KB | `setup/<TOPIC>.md` |
| `HANDOVER.md` (template) | `HANDOVER.md` | ≥5 KB | move oldest block to `docs/.handover-archive/<YYYY-MM-DD>-<slug>.md` |

*Index size cap*: a sub-index file (the navigational layer) should stay ≤10 KB. If an index grows beyond that, content has leaked from a detail file into the index — refactor by moving content back to the appropriate detail file. Phase indexes (e.g. `ARCHITECTURE.md`) cap at ≤15 KB.

*Phase index format (identical for all phases):*

```markdown
# <Phase Name> – Index

**Status:** In Progress | Ready for Gate | Gate Passed (DD.MM.YYYY)
**Last Updated:** DD.MM.YYYY

## Key Decisions
- <one-liner> → see `<DETAIL>.md`

## Open Risks / Open Questions
- <one-liner>

## Detail Files
| Subskill | File | Status |
|---|---|---|
| Problem Definition | [PROBLEM.md](PROBLEM.md) | complete |

## Gate Notes
<notes for the gate check, e.g. Conditional-Go conditions>
```

*Detail file frontmatter:*

```yaml
---
phase: p0
subskill: problem
status: complete    # draft | complete | needs-rework
last_updated: DD.MM.YYYY
---
```

*Rules:*
- **Subskill commands** write their result to `docs/<phase-folder>/<DETAIL>.md` (overwrite, not append) and afterwards update the phase index: refresh the detail-file row and lift any one-line key decision or risk into the index.
- **Gate commands** read the phase index first, walk the detail-file table, and load detail files only when content checks demand it.
- Tier-1 memory (`docs/memory/`) is unaffected — it lives parallel to the phase folders.

**Git & Commit Policy**: Each TDD cycle produces exactly one commit. Build and tests must be green before every commit. Commits follow the Conventional Commits format:

| Timing | What is committed | Commit message type |
|---|---|---|
| After GREEN (tests green) | Feature code + tests | `feat: [Story-ID] description` |
| After REFACTOR | Structural improvements | `refactor: description` |
| After bugfix (P5 + P6) | Fix + regression test | `fix: [Bug/Finding-ID] description` |
| Gate P5 (sprint end) | Docs updates, SPRINT.md | `docs: Sprint-X completed` |
| Gate P6 (QA completion) | Set release tag | `chore: release vX.Y.Z` |

**Ground rule:** No code without a commit. When tests are green, commit – not at the end of the sprint. This prevents data loss and makes reviews easier. The Senior-Developer is responsible for committing after each TDD cycle; gate commands check whether all changes are committed.

---

## Phase 0: Discovery
> "Is the idea worth pursuing?"

### Goal
Quick initial assessment of whether an idea has potential – before significant time is invested.

### Activities
- Problem definition: What problem are we solving for whom?
- Initial market research: Is there demand? Are there competitors?
- Initial feasibility assessment: Can we actually build this?
- Identify constraints: Regulatory, financial, timeline
- Prepare Go/No-Go decision

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **Konzeptor** (Lead) | Problem analysis, initial target audience definition | Asks the right questions, structures the idea |
| **Business-Analyst** | Initial market assessment, rough viability | Checks: Is there a market? Is it potentially worthwhile? |
| **Security-Master** | Early regulatory assessment | Flags DSGVO (GDPR), health data, licenses early |

### Iterative Loop
Konzeptor <-> Business-Analyst: Sharpen idea until it's clear whether to proceed.

### Quality Gate 0 -> Conception
- [ ] Problem is clearly defined and documented
- [ ] Target audience is roughly identified
- [ ] Initial market assessment is available (demand, competition)
- [ ] Rough feasibility confirmed (technical, financial, regulatory)
- [ ] No showstoppers identified (or consciously accepted)
- [ ] **Go/No-Go decision**: Continue? Yes / No / Pivot

**Results**: `docs/discovery/DISCOVERY.md` (phase index) plus detail files `PROBLEM.md`, `MARKET.md`, `REGULATORY.md`. Go/No-Go decision lives in the index under "Gate Notes" after `/gate-p0`.

---

## Phase 1: Conception
> "What exactly are we building and why?"

### Goal
Well-thought-out, viable business concept with clear target audience, feature definition, and MVP scope boundary.

### Activities
- Detailed target audience analysis and personas
- Develop user journeys and scenarios
- Feature definition and prioritization (MoSCoW)
- Define MVP scope: What is the minimum that delivers value?
- Sharpen value proposition
- Design business model (Business Model Canvas)
- Initial financial planning (costs, revenue forecast, break-even)
- Deepen competitive analysis
- DSGVO (GDPR) initial assessment (what data is being processed?)

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **Konzeptor** (Lead) | Business concept, features, MVP, user journeys | Defines the "what" – delivers to all others |
| **UX-Designer** | Personas, user flows, information architecture | Works with Konzeptor on user journeys |
| **Business-Analyst** | Business model, financial plan, pricing approach | Checks economic viability of the concept |
| **Security-Master** | Data classification, DSGVO (GDPR) initial assessment | Flags data protection requirements early |
| **Project-Planner** | Rough effort estimate | Provides initial timeline assessment |

### Iterative Loop
Konzeptor <-> UX-Designer <-> Business-Analyst: Sharpen concept until features, MVP, and business model are aligned.

### Quality Gate 1 -> Validation
- [ ] Target audience and personas are defined
- [ ] At least 3 user journeys are documented
- [ ] Feature list exists with prioritization (Must/Should/Nice)
- [ ] MVP scope is clearly defined (what's in, what's out)
- [ ] Value proposition is formulated
- [ ] Business Model Canvas is filled out
- [ ] Initial financial planning is available (costs, revenue forecast)
- [ ] DSGVO (GDPR) initial assessment is done (data classification)
- [ ] All assumptions are explicitly documented and marked as such

**Results**: CONCEPT.md, USER_JOURNEYS.md, FEATURES.md, MVP.md, BUSINESS_MODEL.md, financial plan (draft)

---

## Phase 2: Validation
> "Are our assumptions correct?"

### Goal
Verify critical assumptions from Phase 1 before investing in architecture and implementation. Reduce risk.

### Activities
- Systematically list assumptions from Phase 1
- Define validation method per assumption (research, prototype, interviews, data)
- For software: Technical Proof of Concept for risky areas
- For business: Market validation (target audience interviews, competitor check, location analysis)
- Validate pricing assumptions
- Adjust concept based on findings
- Pivot decision on negative results

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **Konzeptor** (Lead) | Track assumptions, adjust concept | Decides on pivot or continue |
| **Business-Analyst** | Validate market and financial assumptions | Provides data for decision |
| **System-Architekt** | Validate technical feasibility (PoC) | Clarifies: Does the approach work technically? |
| **Security-Master** | Validate regulatory feasibility | Clarifies: Is this legally implementable? |

### Iterative Loop
Validation <-> Conception: On negative results, back to Phase 1, adjust concept, validate again.

### Quality Gate 2 -> Architecture
- [ ] All critical assumptions are identified and assessed
- [ ] At least the top-3 risk assumptions are validated (or consciously accepted)
- [ ] Technical feasibility is confirmed (PoC, if needed)
- [ ] Regulatory feasibility is confirmed
- [ ] Pricing assumptions are validated
- [ ] Concept is updated based on validation results
- [ ] Financial plan is updated
- [ ] **Go/No-Go/Pivot decision** is documented

**Results**: VALIDATION.md (assumptions, results, decision), updated CONCEPT.md, PoC code if applicable

---

## Phase 3: Architecture & Design
> "How do we build it technically and from a design perspective?"

### Goal
Viable technical architecture and UX concept that make the business concept implementable.

### Activities
- Design system architecture (components, data flows, integrations)
- Select and justify tech stack (ADRs)
- Design data model
- API design (define interfaces)
- Develop UX concepts (wireframes, navigation structure, component library)
- Create accessibility concept
- Dark mode concept
- Define security architecture (threat model, auth concept)
- Plan infrastructure (hosting, deployment, CI/CD)
- Define test strategy

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **System-Architekt** (Lead) | Architecture, stack, data model, APIs | Sets technical framework |
| **UX-Designer** | Wireframes, navigation, accessibility, dark mode | Delivers UI concepts to System-Architekt |
| **Security-Master** | Threat model, auth concept, security requirements | Provides security constraints to architecture |
| **DevOps** | Infrastructure planning, CI/CD concept | Plans deployment on existing Hetzner infra |
| **QA-Tester** | Define test strategy | Defines test levels and tools |
| **Business-Analyst** | Cost assessment of options | Evaluates operating costs of architecture options |
| **Konzeptor** | Clarify domain questions | Answers questions from conception |

### Iterative Loop
System-Architekt <-> UX-Designer <-> Security-Master: Align architecture, design, and security.

### Quality Gate 3 -> Planning
- [ ] System architecture is documented (component diagram, data flows)
- [ ] Tech stack is chosen and justified (ADRs present)
- [ ] Data model is designed
- [ ] API design is defined
- [ ] UX concept is available (wireframes, navigation, component library)
- [ ] Accessibility concept created (incl. dark mode, color blindness)
- [ ] Threat model created and security requirements defined
- [ ] Infrastructure plan is available (hosting, CI/CD, monitoring)
- [ ] Test strategy is defined (levels, tools, coverage target)
- [ ] Operating cost estimate is available
- [ ] All open questions to Konzeptor are resolved

**Results**: ARCHITECTURE.md, TECH_STACK.md, ADR/, DATA_MODEL.md, API_SPEC.md, UX_CONCEPT.md, ACCESSIBILITY.md, SECURITY.md, INFRASTRUCTURE.md, test strategy

---

## Phase 4: Planning
> "When do we build what in which order?"

### Goal
Define implementation order, build backlog, plan first sprints, provision development environment.

### Activities
- Break features into implementable tasks (work breakdown)
- Identify dependencies
- Build and prioritize backlog
- Define milestones and releases
- Plan first sprint
- Identify risks and define countermeasures
- Set up repository
- Set up CI/CD pipeline
- Configure development environment
- Create project README and contributing guide

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **Project-Planner** (Lead) | Backlog, sprints, milestones, risks | Orchestrates the planning |
| **DevOps** | Repo setup, CI/CD, dev environment | Provisions technical infrastructure |
| **Tech-Writer** | README, contributing guide, project structure docs | Documents the setup |
| **Senior-Developer** | Effort estimation for technical tasks | Estimates feature complexity |

### Iterative Loop
Project-Planner <-> Senior-Developer: Slice tasks, estimate effort, refine.

### Quality Gate 4 -> Implementation
- [ ] Backlog exists with prioritized, estimated tasks
- [ ] First sprint is planned (tasks assigned, sprint goal defined)
- [ ] Milestones and releases are defined
- [ ] Risk assessment is available
- [ ] Repository is set up
- [ ] CI/CD pipeline is running (build, test, lint)
- [ ] Development environment is configured and documented
- [ ] README and contributing guide exist
- [ ] All stakeholders know what is being implemented first

**Results**: PROJECT_PLAN.md, BACKLOG.md, SPRINT.md, RISKS.md, repository with CI/CD, README.md

---

## Phase 5: Implementation
> "Let's build!"

### Goal
Implement features in TDD cycles, review and test – iteratively in sprints.

### Activities (per sprint iteration)
1. Pick sprint task
2. Write tests (Red)
3. Implement (Green)
4. Refactor (Refactor)
5. Conduct code review
6. Run acceptance tests against requirements
7. Bug fixing on issues
8. Sprint review: What was accomplished?
9. Sprint Polish (optional, via `/p5-polish`): Collect small carry-over TODOs, triage, and resolve mini-items before the next sprint
10. Next task or next sprint

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **Senior-Developer** (Lead) | Implementation in TDD cycle | Builds the features |
| **Code-Reviewer** | Review after implementation | Reviews Senior-Developer's code |
| **QA-Tester** | Acceptance tests, edge cases | Tests from user perspective |
| **UX-Designer** | Clarify UI detail questions | Answers questions about states and interactions |
| **Debugger** | Error analysis on issues | Called when something doesn't work |
| **Tech-Writer** | Update code documentation | Keeps documentation in sync with code |

### Iterative Loop (Sprint Loop)
```
Senior-Developer -> Code-Reviewer -> QA-Tester -> [Bug found?]
     ^                                              |
     |              Yes: Debugger -> Fix            |
     +----------------------------------------------+
                    No: Next task
```

### Quality Gate 5 -> Quality Assurance (per sprint/release)
- [ ] All planned sprint tasks are implemented or consciously deferred
- [ ] All unit tests are green
- [ ] Code review is done (no open critical findings)
- [ ] Acceptance tests for implemented features have passed
- [ ] No known critical bugs open
- [ ] Code documentation is up to date
- [ ] CI pipeline is green

**Results**: Working, tested, reviewed code, sprint review result

---

## Phase 6: Quality Assurance
> "Is the overall system truly stable and secure?"

### Goal
Comprehensive review of the overall system before release – functional, security, and from a user perspective.

### Activities
- Run integration tests
- E2E tests for critical user paths
- Exploratory tests (areas not covered by automated tests)
- Accessibility review (a11y checklist)
- Dark mode review
- Performance check
- Security audit (code, dependencies, configuration)
- Penetration test (active attack simulation)
- DSGVO (GDPR) compliance check
- Regression tests (has new code broken existing features?)
- Bug fixing for found issues

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **QA-Tester** (Lead) | Integration, E2E, exploratory tests | Coordinates the overall review |
| **Security-Master** | Security audit, DSGVO (GDPR) check | Reviews defensively: policies, compliance |
| **Pentester** | Active attack simulation, PoCs | Reviews offensively: Can I still get in? |
| **UX-Designer** | Accessibility review | Reviews a11y, dark mode, color contrast |
| **Code-Reviewer** | Final code quality review | Last look at critical areas |
| **Debugger** | Root cause on found bugs | Analyzes found issues |
| **Senior-Developer** | Bug fixes | Fixes found issues TDD-style |

### Iterative Loop
```
QA-Tester/Pentester/Security-Master -> [Finding?]
     |                                      |
     |        Yes: Debugger -> Senior-Dev -> retest
     |                                      |
     +---- No: Continue to next review
```

### Quality Gate 6 -> Launch
- [ ] Integration tests passed
- [ ] E2E tests for all critical paths passed
- [ ] Exploratory tests done, findings documented
- [ ] Accessibility review passed (a11y checklist)
- [ ] Dark mode reviewed and functional
- [ ] Performance is acceptable (load times, response times)
- [ ] Security audit done, no open critical findings
- [ ] Penetration test done, no exploitable critical vulnerabilities
- [ ] DSGVO (GDPR) compliance confirmed
- [ ] All critical and high bugs are fixed
- [ ] Regression tests passed
- [ ] **Security-Master gives approval**: green / conditional / no approval
- [ ] **QA-Tester gives approval**: green / conditional / no approval

**Results**: Test protocols, security audit report, pentest report, DSGVO review protocol, bug fixes, approval

---

## Phase 7: Launch & Deployment
> "Ship it!"

### Goal
Secure deployment to production, go-to-market, set up monitoring.

### Activities
- Go through deployment checklist
- Prepare and test database migrations
- Execute deployment (Hetzner)
- Smoke tests after deployment
- Set up monitoring and alerting
- Prepare and test rollback plan
- Write release notes
- Create user manual / onboarding material
- Start go-to-market activities (if business project)
- Set up KPIs and tracking
- Launch privacy policy and imprint

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **DevOps** (Lead) | Deployment, monitoring, rollback plan | Executes the technical go-live |
| **QA-Tester** | Smoke tests after deployment | Checks: Is everything running in production? |
| **Security-Master** | Release security checklist, final review | Last security check before go-live |
| **Tech-Writer** | Release notes, user manual | Documents the release |
| **Business-Analyst** | Go-to-market, pricing live, set up KPIs | Starts marketing |
| **Project-Planner** | Check off milestone, retrospective | Documents progress |

### Quality Gate 7 -> Operations
- [ ] Deployment is successfully completed
- [ ] Smoke tests passed
- [ ] Monitoring and alerting are active
- [ ] Rollback plan is tested and documented
- [ ] Release notes are published
- [ ] User manual / onboarding is available
- [ ] Privacy policy and imprint are live
- [ ] KPI tracking is set up
- [ ] Runbook for operations is documented
- [ ] **Go-to-market is launched** (if business project)

**Results**: Live system, DEPLOYMENT.md, RUNBOOK.md, release notes, monitoring dashboard, go-to-market launched

---

## Phase 8: Operations & Evolution
> "Is it running? What's next?"

### Goal
Ensure stable operations, learn from user feedback, plan next iteration.

### Activities
- Evaluate monitoring (errors, performance, availability)
- Analyze and fix production errors
- Collect and evaluate user feedback
- Check KPIs (revenue vs. plan, usage, conversion)
- Optimize business model (pricing, channels, costs)
- Prioritize next features (back to P1 or P5)
- Reduce technical debt
- Security updates and dependency upgrades
- Verify backups
- Regular security scans

### Agents & Interaction
| Agent | Role | Interaction |
|---|---|---|
| **DevOps** (Lead – Technical) | Monitoring, performance, availability, updates | Keeps the system running |
| **Debugger** | Analyze production errors | Called on incidents |
| **Business-Analyst** (Lead – Business) | KPIs, business model optimization | Evaluates economic success |
| **Konzeptor** | Evaluate user feedback, next features | Prepares next iteration |
| **Project-Planner** | Maintain backlog, plan next sprint | Plans further development |
| **Security-Master** | Regular security scans, dependency updates | Keeps security current |
| **Pentester** | Periodic re-tests | Checks if new vulnerabilities have emerged |

### Iterative Loop (Evolution Loop)
```
Operations -> [New feature needed?] -> back to Phase 1 (Conception)
Operations -> [Architecture change needed?] -> back to Phase 3 (Architecture)
Operations -> [Small enhancement?] -> back to Phase 5 (Implementation)
```

### Ongoing Checkpoints (no single gate)
- [ ] Monitoring shows no critical anomalies
- [ ] All production incidents are documented and resolved
- [ ] KPIs are regularly evaluated (monthly recommended)
- [ ] Security updates are applied promptly
- [ ] Backups are regularly verified
- [ ] User feedback is systematically captured
- [ ] Backlog is regularly maintained and prioritized

**Results**: Stable production, KPI reports, prioritized backlog for next iteration

---

## Summary: Phases, Gates, and Lead Agents

| Phase | Name | Lead Agent | Gate Type |
|---|---|---|---|
| P0 | Discovery | Konzeptor | Go/No-Go |
| P1 | Conception | Konzeptor | Completeness Gate |
| P2 | Validation | Konzeptor | Go/No-Go/Pivot |
| P3 | Architecture & Design | System-Architekt | Completeness Gate |
| P4 | Planning | Project-Planner | Readiness Gate |
| P5 | Implementation | Senior-Developer | Sprint Gate (repeated) |
| P6 | Quality Assurance | QA-Tester | Approval Gate |
| P7 | Launch & Deployment | DevOps | Go-Live Gate |
| P8 | Operations & Evolution | DevOps + Business-Analyst | Continuous |

## Gate Types Explained
- **Go/No-Go**: Binary decision – continue, stop, or pivot
- **Completeness Gate**: All defined results must be present
- **Readiness Gate**: Technical and organizational prerequisites must be met
- **Sprint Gate**: Repeated per sprint, checks implementation quality
- **Approval Gate**: Formal approval by QA and Security for go-live
- **Go-Live Gate**: Technical readiness and business readiness for launch
- **Continuous**: No single gate, but regular checkpoints
