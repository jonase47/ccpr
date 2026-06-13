---
kind: commands-doc-detail
parent_index: ../SECTIONS_COMMANDS.md
section: utility
last_updated: 15.05.2026
---

# Utility (13 commands)

Cross-cutting commands that operate outside the phase flow.

| Command | Title | Description |
|---|---|---|
| `/cleanup` | Doc Hygiene: HANDOVER cap + lint aggregator | Runs a one-shot hygiene pass on a project's docs to keep them lean and machine-readable: HANDOVER size cap enforcement plus the three existing lint scripts (memory-lint.sh, phase-docs-lint.sh, doc-volume-check.sh) bundled into one consolidated drift report. Use this between phases (after a Gate) or whenever the project-guide warns about HANDOVER size, stale memory or doc volume drift. |
| `/decision` | Develop a decision basis | This command analyzes an open decision question, automatically determines which perspectives are relevant, assembles the appropriate analysis agents, and develops a structured decision basis (Decision Basis) – without making the decision itself. That is the PO's responsibility. |
| `/epic` | Create an epic | This command creates one or more epics – either derived from an existing concept or roadmap, or standalone from a free description. An epic can already contain rough associated user stories or be created as a pure high-level shell – this is selectable per call. |
| `/guide` | Project Guide (status, skill recommendation, disambiguation) | Invokes the project-guide agent as the entry point for the current project: structured status snapshot, prioritised next steps with skill/agent recommendations, and disambiguation for unclear requests. |
| `/konzept-update` | Revise an existing rough concept | This command updates an existing rough concept based on new findings, clarified open questions, or changed requirements. Each revision is versioned and timestamped so that the evolution of the concept remains traceable. |
| `/konzept` | Create a rough concept for a feature or (sub-)project | This command guides through the initial conception phase as a Product Owner. The result is a first structured rough concept that serves as the basis for further steps (user stories, roadmap, stakeholder presentation). |
| `/logs-summary` | Log summary | Analyzes and summarizes the agent monitor logs. |
| `/project-init` | Project initialization | Initializes a new project with directory structure, project-specific CLAUDE.md, and Git repository. |
| `/release-baseline` | Set project state as baseline | Makes a "cut" after a release: project state is documented as given, HANDOVER is archived and summarized, docs are split into Frozen/Active. |
| `/roadmap-update` | Update an existing roadmap | This command updates an existing roadmap based on new findings, completed milestones, changed priorities, or new decisions. Each revision is versioned and timestamped with date + time. |
| `/roadmap` | Create an initial roadmap | This command creates a first roadmap based on an existing rough concept. The roadmap structures epics, milestones, and dependencies either time-based (quarters/months) or phase-based (MVP, Phase 1, Phase 2...) – selectable depending on the project character. |
| `/user-stories` | Create or elaborate user stories | This command creates detailed user stories – either derived from an existing epic, roadmap, or concept, or standalone from a free description. Each story contains acceptance criteria, priority, dependencies, and a definition of done. |
