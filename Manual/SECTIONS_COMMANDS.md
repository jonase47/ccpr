# Sections & Commands – Overview

## Decisions
- **115 Commands** – full granularity, full control (P0–P8 Full-Track + Lean-Track + cross-cutting)
- **Gate convention**: `/gate-pX` (dedicated prefix, e.g. `/gate-p6`)
- **Sprint number**: tracked in project context (SPRINT.md), not in command
- **Language**: all command names in English
- **Arguments**: commands accept optional `$ARGUMENTS` where useful

## Naming Convention
- Section commands: `/p[phase]-[section]` -> e.g. `/p6-pentest`
- Sub-skill commands: `/p[phase]-[section]-[subskill]` -> e.g. `/p3-sec-auth`
- Gate commands: `/gate-p[phase]` -> e.g. `/gate-p0`
- Arguments: `/p5-implement Login-Feature` -> `$ARGUMENTS` = "Login-Feature"

---

## Track-Skills (Cross-Cutting, 6 commands)

| Command | Title | Description |
|---|---|---|
| `/track-decision` | Decide (or re-assess) Lean vs. Full-Track | Prerequisite check + Knockout (K1–K5) + Indicator score (I1–I5). Determines Lean (prototype/PoC/spike) or Full (P0–P8). Also for mid-flight re-assessment. No downgrade Full → Lean. |
| `/constitution` | Create or revise the project Constitution | Creates `docs/CONSTITUTION.md` with Inviolable/Default/Aspirational. Hybrid mode: greenfield with domain bootstrap, existing Full-Track reads phase docs, Lean lead-in reads FRAME. Read mandatorily by all gates. |
| `/lean-frame` | Lean-Track Single-Source-of-Truth | Creates `docs/FRAME.md` (max. 5 KB, 8 sections) + `docs/CLAUDE-lean.md`. Replaces P0+P1+P3 conception work for prototypes. |
| `/lean-learn` | Validate Lean-Track and make a decision | Creates `docs/LEARNINGS.md` with hypothesis check and decision PROMOTE/PIVOT-soft/PIVOT-hard/DROP. On pivot: module table (keep/refactor/rebuild). |
| `/lean-promote` | Promote Lean → Full-Track via Promotion Brief | Creates `docs/PROMOTION_BRIEF.md` (7 sections) as bootstrap input for `/project-init`. Archives FRAME/LEARNINGS/CLAUDE-lean to `docs/lean-archive/`. |
| `/cross-check` | Cross-Artifact Consistency Check | Checks inconsistencies across phases (features ↔ auth, NFR ↔ tests, ADRs ↔ Constitution, …). 7 rules initially, growing iteratively. Recommended before gates. |

---

## P0: Discovery (3 commands)

| Command | Title | Description |
|---|---|---|
| `/p0-problem` | Problem Definition & Target Audience Identification | Defines the core problem of a project or business idea and identifies the first rough Target Audience. The result is a clear problem statement that serves as the foundation for all subsequent phases. |
| `/p0-market` | Market Assessment & Competition Overview | Delivers a first market assessment: Is there demand? Who are the competitors? Is the idea roughly viable economically? The result is an overview needed for the Go/No-Go Decision at Gate 0. |
| `/p0-regulatory` | Regulatory & Legal Knock-Out Criteria | Identifies regulatory requirements, DSGVO (GDPR) obligations, and legal knock-out criteria early on, before significant time is invested in the idea. A regulatory showstopper should be recognised as early as possible. |

## P1: Conception (5 commands)

| Command | Title | Description |
|---|---|---|
| `/p1-journeys` | Personas & User Journeys | Develops detailed personas, user journeys, and usage scenarios based on the Discovery results. These artefacts form the user foundation for all further conception decisions. |
| `/p1-features` | Feature Definition & MVP Scope Boundary | Defines the feature scope of the project, prioritises using MoSCoW, and clearly defines the MVP scope. The result is FEATURES.md and MVP.md as the binding basis for architecture and planning. |
| `/p1-business-model` | Business Model Canvas & Value Proposition | Develops the Business Model with Business Model Canvas, sharpens the value proposition, and defines a first pricing approach. The result is BUSINESS_MODEL.md as the economic foundation of the project. |
| `/p1-financial-plan` | Cost Structure, Revenue Forecast & Break-Even | Creates a first financial plan with Cost Structure, Revenue Forecast, and break-even analysis. The goal is not exact bookkeeping but a plausible set of numbers that demonstrates the economic viability of the venture. |
| `/p1-privacy` | Data Classification & DSGVO Initial Assessment | Conducts a systematic initial assessment of data protection requirements: What personal data is processed, on what legal basis, and what DSGVO (GDPR) obligations arise from this? The result is a well-founded DSGVO initial assessment as a mandatory component of the Concept. |

## P2: Validation (4 commands)

| Command | Title | Description |
|---|---|---|
| `/p2-assumptions` | Identify & Prioritise Critical Assumptions | Systematically lists all critical Assumptions from the conception phase and prioritises them by risk and validatability. The result is an Assumptions register that serves as the working basis for all further validation steps. |
| `/p2-market-validation` | Validate Market, Pricing & Demand Assumptions | Checks critical market, pricing, and demand Assumptions from the Assumptions register using concrete research, data, and competitive analyses. The result is confirmed or refuted Assumptions as the basis for informed Concept decisions. |
| `/p2-regulatory-check` | Validate Regulatory Feasibility | Validates the regulatory Assumptions from Phase 1 concretely and practically: Is the venture legally implementable? Which hurdles are real, which are surmountable? The result is a robust regulatory validation as the Decision basis for Gate 2. |
| `/p2-poc` | Technical Proof of Concept | Builds a minimal technical Proof of Concept for the riskiest technical area of the project. The goal is not a finished feature but proof that the planned approach fundamentally works – before investing in architecture and implementation. |

## P3: Architecture & Design (23 commands)

Lead commands first, each followed by its sub-skills in execution sequence. After `/p3-architecture` the remaining tracks (`/p3-data-model`, `/p3-security`, `/p3-ux`, `/p3-infra`, `/p3-cost`) run in any order.

| Command | Title | Description |
|---|---|---|
| `/p3-architecture` | System Architecture, Tech Stack & ADRs | Designs the system architecture, selects the tech stack and documents architectural decisions. Each concern is its own sub-skill. |
| `/p3-arch-components` | Component Diagram & Data Flows | Creates the system architecture overview with component diagram, responsibilities and data flows. |
| `/p3-arch-techstack` | Tech Stack Decision | Selects the tech stack and justifies each technology decision. |
| `/p3-arch-adr` | Write Architecture Decision Records | Documents all significant architectural decisions as ADRs. |
| `/p3-arch-nfa` | Define Non-Functional Requirements | Defines the non-functional requirements (scalability, performance, availability, maintainability). |
| `/p3-data-model` | Data Model & API Design | Designs the Data Model with entities and relationships as well as the API design with interface specification. The result is DATA_MODEL.md and API_SPEC.md as the binding foundation for implementation. |
| `/p3-security` | Security Architecture, Threat Model & Auth Concept | Creates the complete security architecture: threat model, auth concept, data security, API security and developer checklist. Each area is its own sub-skill. |
| `/p3-sec-threats` | Create STRIDE Threat Model | Analyzes the system according to the STRIDE model and identifies threats with countermeasures. |
| `/p3-sec-auth` | Auth & Authorization Concept | Defines the authentication and authorization concept including session management. |
| `/p3-sec-data` | Data Security Concept | Defines encryption (transit/rest), secrets management and backup security. |
| `/p3-sec-api` | API Security Requirements | Defines input validation, rate limiting, CORS and security headers. |
| `/p3-sec-checklist` | Developer Security Checklist | Creates a concrete checklist that every feature in phase 5 must fulfill. |
| `/p3-ux` | UX Concept, Wireframes & Accessibility | Develops the complete UX concept: navigation, wireframes, dark mode and accessibility. Each area is its own sub-skill. |
| `/p3-ux-navigation` | Sitemap & Information Architecture | Creates the navigation structure, sitemap and identifies critical flows. |
| `/p3-ux-wireframes` | Wireframes for Key Screens | Creates wireframes (ASCII art) for the most important screens with interaction descriptions. |
| `/p3-ux-darkmode` | Dark Mode Color Strategy | Defines the color strategy for dark mode with semantic colors and toggle mechanism. |
| `/p3-ux-a11y` | Accessibility Concept | Defines WCAG target, contrast requirements, keyboard navigation, screen reader requirements and testing methods. |
| `/p3-infra` | Infrastructure, CI/CD & Test Strategy | Plans infrastructure, CI/CD pipeline, monitoring and test strategy. Each area is its own sub-skill. |
| `/p3-infra-hosting` | Hosting & Deployment Strategy | Plans hosting platform, deployment model, environments and CDN strategy. |
| `/p3-infra-cicd` | CI/CD Pipeline | Designs the CI/CD pipeline with stages, branch strategy and rollback concept. |
| `/p3-infra-monitoring` | Monitoring & Observability | Defines logging, metrics, alerting and error tracking. |
| `/p3-infra-teststrategy` | Define Test Strategy | Defines test levels, test tools, coverage targets and critical test paths. |
| `/p3-cost` | Operating Costs of the Architecture | Estimates the ongoing Operating Costs of the chosen architecture for various usage scenarios. The goal is realistic cost planning that feeds back into the financial plan – no surprises after launch. |

## P4: Planning (4 commands)

| Command | Title | Description |
|---|---|---|
| `/p4-backlog` | Work Breakdown, Backlog & Milestones | Breaks down the features from FEATURES.md into actionable tasks, builds the prioritized backlog, and defines milestones and release planning. The result is BACKLOG.md and PROJECT_PLAN.md as the steering foundation for the entire implementation. |
| `/p4-setup` | Repository, CI/CD & Development Environment Setup | Sets up the repository, CI/CD pipeline and local development environment. The result is a working development infrastructure in which the team can immediately start with /p5-implement. |
| `/p4-docs` | README, Contributing Guide & Project Structure Documentation | Creates the foundational project documentation: a meaningful README, a contributing guide, and documentation of the project structure. The result is a documentation base that quickly onboards new developers and bindingly establishes standards. |
| `/p4-sprint` | Plan Sprint | Plans the current sprint: pulls matching stories from the backlog, defines the sprint goal, identifies risks, and creates the sprint document. Called repeatedly at the start of each new sprint. |

## P5: Implementation (12 commands)

Sprint workflow: `/p5-implement` (with TDD sub-skills) → `/p5-review` → `/p5-acceptance` → `/p5-bugfix` on findings → `/p5-docs` → `/p5-review-sprint` (holistic, once before the gate) → `/gate-p5` → `/p5-polish`.

| Command | Title | Description |
|---|---|---|
| `/p5-implement` | Implement Feature (TDD Cycle) | Implements a feature in the TDD cycle: Red → Green → Refactor. Each phase is its own sub-skill with a focused agent call. |
| `/p5-impl-red` | Write Failing Tests (RED) | Writes unit tests for a feature BEFORE production code exists. Tests must fail. |
| `/p5-impl-green` | Minimal Code for Green Tests (GREEN) | Writes the minimal production code that makes the existing tests green. No over-engineering. |
| `/p5-impl-refactor` | Clean Up Code (REFACTOR) | Improves code quality without changing behavior. All tests must continue to pass. |
| `/p5-review` | Code Review | Conducts a structured code review: first code quality, then security. Each dimension is its own sub-skill. |
| `/p5-review-code` | Check Code Quality | Checks code for quality, clean code, logic errors and test coverage. Delivers review findings with severity level. |
| `/p5-review-security` | Check Security Checklist | Checks code against the security checklist. Focus on OWASP Top 10, injection, auth and data handling. |
| `/p5-acceptance` | Acceptance Tests | Tests an implemented feature against its requirements from a user perspective: are all acceptance criteria met? Are edge cases handled correctly? The result is test findings that determine whether the feature counts as "Done". |
| `/p5-bugfix` | Analyze & Fix Bug | Systematically analyzes a found bug, identifies the root cause and fixes it with an accompanying regression test. Goal: the bug is fixed, secured by a test, and cannot be silently reintroduced. |
| `/p5-docs` | Keep Code Documentation Up to Date | Keeps code documentation in sync with the implemented code: inline comments, API documentation, changes to README or CONTRIBUTING, and updates to technical specifications if the code deviates from them. Called after implementing a feature. |
| `/p5-review-sprint` | Holistic Sprint Code Review (whole-context) | Runs the `code-reviewer` agent on **opus** once over the whole sprint diff at sprint end — complementary to the per-story `/p5-review-code`. Reasons across the full diff plus conformance anchors (Constitution Inviolables, touched ADRs, all migrations) to surface findings single-story reviews structurally miss: cross-story interactions, repeated schema/constraint anti-patterns, ADR/Inviolable drift, async/coalescing correctness. Output: `docs/reviews/SPRINT-<n>-review.md`. Wired into `/gate-p5` as an automatic step (guarded by a `reviewed_head` SHA so opus is spent once per sprint state); any unresolved CRITICAL/HIGH finding blocks the gate. |
| `/p5-polish` | Sprint Polish: Collect & Resolve Small Carry-Over TODOs | Collects small clean-up TODOs accumulated during the sprint (from /p5-review, /p5-acceptance, /p5-bugfix, TODO/FIXME comments) that do not justify a full story but make the next sprint easier. Triages each item into polish-now, backlog, handover, or drop. Optionally executes polish-now items directly (TDD mini-cycle, one commit per item). Runs between /gate-p5 (Sprint Done) and the next /p4-sprint. |

## P6: Quality Assurance (22 commands)

Main sequence: `/p6-functional` → `/p6-exploratory` → `/p6-a11y` → `/p6-audit` → `/p6-pentest` → `/p6-bugfix`. Each lead command is followed by its sub-skills in execution order.

| Command | Title | Description |
|---|---|---|
| `/p6-functional` | Integration, E2E & Regression Tests | Runs systematic functional tests at the system level. Each test level is a separate sub-skill. |
| `/p6-func-integration` | Run Integration Tests | Tests the interaction between system components: API against DB, middleware chains, external services against mocks. |
| `/p6-func-e2e` | E2E Tests for Critical Paths | Tests critical user journeys end-to-end – from start to the expected final result. |
| `/p6-func-regression` | Run Regression Tests | Ensures that existing functionality has not been broken by new changes. |
| `/p6-exploratory` | Exploratory Tests | Conducts unstructured, experience-based tests that automated tests and defined test cases do not cover. The goal is to find unexpected behaviours, usability issues, and hidden bugs that remain invisible in structured testing. |
| `/p6-a11y` | Accessibility Check | Systematically checks the application for accessibility. Each A11y dimension is a separate sub-skill. |
| `/p6-a11y-visual` | Contrast, Colours & Dark Mode | Checks colour contrast (WCAG AA), colour-independence of information presentation, and dark mode conformance. |
| `/p6-a11y-keyboard` | Keyboard Navigation & Focus | Checks full keyboard operability: tab order, focus indicator, Enter/Space, Escape, focus trap. |
| `/p6-a11y-screenreader` | ARIA, Semantics & Alt Texts | Checks screen reader compatibility: semantic HTML, ARIA attributes, alt texts, live regions. |
| `/p6-audit` | Security Audit, Dependency Check & DSGVO (GDPR) Compliance | Conducts a defensive security audit. Each audit area is a separate sub-skill. |
| `/p6-audit-sast` | Static Code Analysis | Checks source code for injection vulnerabilities, insecure cryptography, secrets in code, and insecure error handling. |
| `/p6-audit-auth` | Review Auth Implementation | Compares the auth implementation against the requirements in SECURITY.md: JWT, sessions, RBAC, password hashing. |
| `/p6-audit-deps` | Dependency Check | Checks all dependencies for known vulnerabilities (CVEs), outdated packages, and maintenance status. |
| `/p6-audit-config` | Review Infrastructure & Configuration | Checks security headers, CORS, DB access, secrets management, and server configuration. |
| `/p6-audit-dsgvo` | DSGVO (GDPR) Compliance Check | Compares the implementation against the DSGVO initial assessment: data subject rights, data minimisation, deletion deadlines, data processing agreements. |
| `/p6-pentest` | Penetration Test | Conducts an active attack simulation. Each attack phase is a separate sub-skill. |
| `/p6-pentest-recon` | Reconnaissance | Collects publicly available information: tech fingerprinting, exposed endpoints, debug remnants. |
| `/p6-pentest-auth` | Auth & Session Attacks | Actively tests authentication: brute-force protection, token predictability, session invalidation, JWT confusion. |
| `/p6-pentest-authz` | Authorisation & Access Control | Tests IDOR, horizontal/vertical privilege escalation, and unprotected endpoints. |
| `/p6-pentest-injection` | Injection Attacks | Tests SQL injection, XSS, and command injection on input fields and API parameters. |
| `/p6-pentest-logic` | Business Logic Attacks | Tests manipulation of business logic: prices, quantities, race conditions, flow bypasses. |
| `/p6-bugfix` | Fix QA Findings | Fixes bugs and vulnerabilities found during the QA phase (functional tests, exploratory tests, accessibility check, security audit, pentest). Each fix is secured by a regression test. |

## P7: Launch & Deployment (5 commands)

| Command | Title | Description |
|---|---|---|
| `/p7-prepare` | Deployment Preparation & Pre-Launch Checklist | Prepares the deployment: checks all environments, prepares database migrations, verifies configurations, and ensures nothing has been overlooked. Only after this checklist is complete will /p7-deploy be executed. |
| `/p7-deploy` | Execute Deployment & Smoke Tests | Executes the deployment to the target environment and then verifies with smoke tests that the system is running correctly. Only when the smoke tests pass is the deployment considered successful. |
| `/p7-monitoring` | Set Up Monitoring & Test Rollback Plan | Sets up production monitoring completely, configures alerting rules, and tests the rollback plan. The goal is a system that reports problems early and where a rollback works smoothly in an emergency. |
| `/p7-release-docs` | Release Notes, User Guide & Privacy Documents | Creates all user-facing documents for the launch: release notes, user guide or onboarding materials, and the legally required mandatory documents (privacy policy, legal notice). These documents must be available before go-live. |
| `/p7-gtm` | Launch Go-to-Market & Set Up KPI Tracking | Launches the go-to-market activities and sets up KPI tracking. The result is active marketing measures and a working tracking setup that delivers meaningful data from day one. |

## P8: Operations & Evolution (4 commands)

`/p8-ops`, `/p8-business`, `/p8-security` run in parallel/continuously. `/p8-iteration` triggers the evolution loop back into P1, P3, or P5.

| Command | Title | Description |
|---|---|---|
| `/p8-ops` | Production Operations: Analyse Incidents & Monitor Performance | Analyses production errors and performance issues, evaluates incidents, and initiates countermeasures. Called reactively for specific incidents or proactively for regular operational reviews. |
| `/p8-business` | Evaluate KPIs & Optimise Business Model | Evaluates the KPIs from ongoing operations, compares them with the plans from FINANCIAL_PLAN.md, and derives optimisation measures for the business model. Called regularly (recommended: monthly) or on an ad-hoc basis. |
| `/p8-security` | Ongoing Security: Dependency Updates, Scans & Re-Tests | Keeps the security of the running system current: regular dependency updates, security scans, checking for new CVEs, and periodic re-tests of critical areas. Security is not a one-time task – it must be continuously maintained. |
| `/p8-iteration` | Evaluate Feedback, Maintain Backlog & Plan Next Sprint | Evaluates user feedback and operational insights, maintains the backlog, and initiates the next iteration. This is the link between ongoing operations and the next development round – the engine of the evolution loop. |

## Gates (12 commands)

Quality gates between phases — single-purpose decision points. Main gates (P0–P7) plus sub-gates for the dual-approval gates P6 (QA + Security) and P7 (Tech + Business).

| Command | Title | Description |
|---|---|---|
| `/gate-p0` | Quality Gate 0: Discovery → Conception | Checks whether all criteria of the Discovery phase have been met and prepares the Go/No-Go Decision. No argument – this gate always checks the complete checklist. |
| `/gate-p1` | Quality Gate 1: Conception → Validation | Checks whether all results of the conception phase are complete and robust, and prepares the transition to the validation phase. No argument – this gate always checks the complete checklist. |
| `/gate-p2` | Quality Gate 2: Validation → Architecture | Checks whether all critical Assumptions have been validated and a well-founded Go/No-Go/Pivot Decision can be made. This is the most important gate in the model – here it is decided whether to invest in the cost- and time-intensive architecture and implementation phase. No argument – this gate always checks the complete checklist. |
| `/gate-p3` | Quality Gate 3: Architecture & Design → Planning | Checks whether all architecture and design decisions are completely documented and robust before transitioning into the planning and implementation phase. No argument – this gate always checks the complete checklist. |
| `/gate-p4` | Quality Gate 4: Planning → Implementation | Checks whether all organizational and technical prerequisites are met to begin implementation. This is a readiness gate – all participants must know what to do first. No argument – this gate always checks the complete checklist. |
| `/gate-p5` | Sprint Gate: Check Implementation Quality | Checks at the end of each sprint whether all tasks meet quality standards and the sprint can be considered successfully completed. Called repeatedly after each sprint. No argument – this gate always checks the complete current sprint status. |
| `/gate-p6-qa` | QA Approval Evaluation | Evaluates all QA-relevant points of the Gate-P6 checklist and grants QA approval. |
| `/gate-p6-security` | Security Approval Evaluation | Evaluates all security-relevant points of the Gate-P6 checklist and grants Security approval. |
| `/gate-p6` | Release Gate: QA & Security Approval | Checks whether the system is ready for launch. Both QA and Security must explicitly grant approval. No go-live without dual approval. |
| `/gate-p7-tech` | Technical Go-Live Check | Checks technical go-live readiness: deployment, monitoring, rollback, smoke tests. |
| `/gate-p7-business` | Business Readiness Check | Checks business readiness: documentation, GTM, KPIs, legal mandatory documents. |
| `/gate-p7` | Go-Live Gate: Technical Readiness & Business Readiness | Checks whether the system is fully ready for production operation. Last gate before the official go-live status. |

## Continuous Learning (2 commands)

Meta-commands for capturing session insight back into the system.

| Command | Title | Description |
|---|---|---|
| `/instinct` | Instinct Management | Manage instincts (confidence-based rules from session experience). |
| `/postmortem` | Session Postmortem | Analyze the last session and extract instinct proposals. |

## Utility (13 commands)

Cross-cutting commands that operate outside the phase flow.

| Command | Title | Description |
|---|---|---|
| `/cleanup` | Doc Hygiene: HANDOVER cap + lint aggregator | Runs a one-shot hygiene pass on a project's docs to keep them lean and machine-readable: HANDOVER size cap enforcement plus the three existing lint scripts (memory-lint.sh, phase-docs-lint.sh, doc-volume-check.sh) bundled into one consolidated drift report. Use this between phases (after a Gate) or whenever the project-guide warns about HANDOVER size, stale memory or doc volume drift. |
| `/decision` | Develop a decision basis | This command analyzes an open decision question, automatically determines which perspectives are relevant, assembles the appropriate analysis agents, and develops a structured decision basis (Decision Basis) – without making the decision itself. That is the PO's responsibility. |
| `/epic` | Create an epic | This command creates one or more epics – either derived from an existing concept or roadmap, or standalone from a free description. An epic can already contain rough associated user stories or be created as a pure high-level shell – this is selectable per call. |
| `/guide` | Project Guide (Status, Skill Recommendation, Disambiguation) | Invokes the project-guide agent as the entry point for the current project: structured status snapshot, prioritised next steps with skill/agent recommendation, and disambiguation for unclear requests. |
| `/konzept-update` | Revise an existing rough concept | This command updates an existing rough concept based on new findings, clarified open questions, or changed requirements. Each revision is versioned and timestamped so that the evolution of the concept remains traceable. |
| `/konzept` | Create a rough concept for a feature or (sub-)project | This command guides through the initial conception phase as a Product Owner. The result is a first structured rough concept that serves as the basis for further steps (user stories, roadmap, stakeholder presentation). |
| `/logs-summary` | Log summary | Analyzes and summarizes the agent monitor logs. |
| `/project-init` | Project initialization | Initializes a new project with directory structure, project-specific CLAUDE.md, and Git repository. |
| `/release-baseline` | Set project state as baseline | Makes a "cut" after a release: project state is documented as given, HANDOVER is archived and summarized, docs are split into Frozen/Active. |
| `/specialize` | Adapt agents to the project's tech stack | Writes project-local specialized copies of the technical agents (`senior-developer`, `code-reviewer`, `qa-tester`, `debugger`, `devops`, …) under `.claude/agents/` and injects a marker-delimited Project Tech Context block with stack-specific correctness/security/idiom rules per persona. `docs` mode reads the P3 `TECH_STACK.md` + ADRs; `codebase` mode scans an existing codebase's manifests + CI config. No auto-commit, no blind overwrite, `⚠ verify` instead of invented facts. |
| `/roadmap-update` | Update an existing roadmap | This command updates an existing roadmap based on new findings, completed milestones, changed priorities, or new decisions. Each revision is versioned and timestamped with date + time. |
| `/roadmap` | Create an initial roadmap | This command creates a first roadmap based on an existing rough concept. The roadmap structures epics, milestones, and dependencies either time-based (quarters/months) or phase-based (MVP, Phase 1, Phase 2...) – selectable depending on the project character. |
| `/user-stories` | Create or elaborate user stories | This command creates detailed user stories – either derived from an existing epic, roadmap, or concept, or standalone from a free description. Each story contains acceptance criteria, priority, dependencies, and a definition of done. |

---

## Summary: 115 Commands

| Category | Count |
|---|---|
| P0 Discovery (incl. sub-skills) | 3 |
| P1 Conception | 5 |
| P2 Validation | 4 |
| P3 Architecture & Design | 23 |
| P4 Planning | 4 |
| P5 Implementation | 12 |
| P6 Quality Assurance | 22 |
| P7 Launch & Deployment | 5 |
| P8 Operations & Evolution | 4 |
| **Subtotal — phase commands** | **82** |
| Gates (main + sub-gates) | 12 |
| Continuous Learning | 2 |
| Utility | 13 |
| Track + Cross-Cutting (`/track-decision`, `/constitution`, `/lean-frame`, `/lean-learn`, `/lean-promote`, `/cross-check`) | 6 |
| **Total** | **115** |

---

## Cross-Cutting Mechanisms

### Wingman Consolidation
Commands with parallel agents (e.g. `/konzept`, `/p1-features`, `/p3-architecture`, `/p5-review`) call the **wingman** agent at the end, which consolidates results into a compact summary. All agents write their full results to files and return only a brief summary (max. 5 sentences).

### Project-Guide Entry Door
`/guide` invokes the **project-guide** agent, which delivers a status snapshot plus three prioritised next-step recommendations and handles skill/agent disambiguation when the next move is unclear. Not a domain agent itself — it routes work to the right domain agent with a bundled context hand-off.

### Handover (HANDOVER.md)
Key commands update `docs/HANDOVER.md` with the work state at the end. This enables seamless session transitions. The agent-monitor warns at 100 tool calls (compact reminder) and 150 tool calls (update HANDOVER).

### Sub-Skill Structure (P3 + P6)
Phases P3 and P6 use a sub-skill pattern: a lead command (e.g. `/p3-architecture`, `/p6-audit`) orchestrates focused sub-skill commands that each handle one concern with a single dedicated agent call. This keeps individual context windows small and produces detail files alongside a phase index.

---

## $ARGUMENTS Patterns

| Pattern | Example | Usage |
|---|---|---|
| Feature/ticket | `/p5-implement Login-Feature` | Implement specific feature |
| Focus area | `/p6-pentest API` | Narrow scope |
| Environment | `/p7-deploy staging` | Specify target environment |
| Version | `/p7-release-docs v1.0.0` | Version for documentation |
| Scenario | `/p3-cost 10k users` | Calculate specific scenario |
| Question | `/guide should I use konzeptor or business-analyst?` | Disambiguation request |
| No argument | `/p5-implement` | Agent asks for context |
