---
kind: commands-doc-detail
parent_index: ../SECTIONS_COMMANDS.md
section: gates
last_updated: 15.05.2026
---

# Gates (12 commands)

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
