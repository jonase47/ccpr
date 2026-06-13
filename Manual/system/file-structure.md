---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: file-structure
last_updated: 15.05.2026
---

# File Structure

> **Repo vs installed.** `install.sh` copies the framework (`agents/`, `commands/`,
> `docs/`, `hooks/`, `scripts/`, `templates/`) into `~/.claude/`. The human-facing
> **`Manual/`** folder (this document included) lives only in the repo and is **not**
> installed — read it in the cloned repo or on the repository host. `~/.claude/docs/`
> therefore holds only the runtime reference docs Claude reads during project work.

## Global Configuration (~/.claude/)

```
~/.claude/
+-- CLAUDE.md                    # Global rules and preferences
+-- settings.json                # Hooks, permissions
+-- instincts.md                 # Global Tier-1 instincts — slim autoloaded index
+-- instincts/                   # Topic files: agents.md, files.md, workflow.md, shell-git.md, external.md
+-- instincts-archive/           # HISTORY.md — rolling postmortem stream (not autoloaded)
|
+-- agents/                      # 15 agents (13 domain + project-guide + wingman)
|   +-- project-guide.md
|   +-- konzeptor.md
|   +-- business-analyst.md
|   +-- system-architekt.md
|   +-- project-planner.md
|   +-- ux-designer.md
|   +-- senior-developer.md
|   +-- code-reviewer.md
|   +-- qa-tester.md
|   +-- debugger.md
|   +-- devops.md
|   +-- security-master.md
|   +-- pentester.md
|   +-- tech-writer.md
|   +-- wingman.md
|
+-- memory/                      # Global Tier-2 silos (persona × cross-project)
|   +-- {agent}/instincts.md     # e.g. devops/, senior-developer/, security-master/
|   +-- {agent}/<topic>.md       # optional topic files (patterns.md, references.md, …)
|
+-- docs/                        # Runtime reference docs (read by Claude during work)
|   +-- PROJECT_PHASES.md        # Phase model with gate checklists
|   +-- NEXT_STEPS_REFERENCE.md  # Transition reference for recommendations
|   +-- CONSTITUTION.md          # CCPR's own ratified constitution
|   +-- adr/                     # Architecture Decision Records
|   +-- memory/                  # Project memory (MEMORY.md index + project_*.md)
|
+-- hooks/
|   +-- agent-monitor.py         # Central monitoring script
|
+-- scripts/
|   +-- bootstrap.sh             # Pre-session context gathering
|   +-- gate-preflight.py        # Check gate artifacts
|   +-- command-check.py         # Check command prerequisites
|   +-- run-tests.sh             # Tests with JSON output
|   +-- quality-scan.sh          # Security/quality scans
|   +-- project-init.sh          # Project scaffolding
|   +-- logs-summary.py          # Log analysis
|   +-- instinct-check.sh        # Check instinct decay
|   +-- memory-lint.sh           # Validate docs/memory/** + global tier-1/2
|   +-- phase-docs-lint.sh       # Validate docs/<phase>/** schema
|   +-- doc-volume-check.sh      # Flag docs at 25/40/50 KB thresholds
|   +-- lib/                     # Shared Python libraries
|   |   +-- next_steps.py
|   |   +-- artefacts.py
|   |   +-- gate_checklists.py
|   +-- local-llm/               # Ollama wrapper scripts (stubs)
|       +-- ollama-query.sh      # Shared helper (API call)
|       +-- summarize.sh         # Summarize file
|       +-- handover-draft.sh    # HANDOVER draft
|       +-- commit-msg.sh        # Commit message
|       +-- install-git-hook.sh  # Git hook installer
|
+-- logs/                        # Monitoring logs
|   +-- activity.jsonl
|   +-- errors.jsonl
|   +-- performance.jsonl
|   +-- sessions/{session_id}/
|
+-- templates/
    +-- HANDOVER_TEMPLATE.md         # Handover template
    +-- MEMORY_SCHEMA.md             # Memory frontmatter schema
    +-- MEMORY_PAGE_TEMPLATE.md      # Memory page starter
    +-- MEMORY_INDEX_TEMPLATE.md     # MEMORY.md index starter
    +-- PHASE_DOC_SCHEMA.md          # Phase-doc frontmatter schema
    +-- STARTER_INSTINCTS.md         # 13 generic instincts as optional baseline
    +-- CONSTITUTION_TEMPLATE.md     # Constitution schema
    +-- constitution-bootstraps/     # Domain seeds for /constitution
    +-- QA_SKELETON/                 # Pre-P6 sub-index skeletons
    +-- ...
```

## Per Project (docs/)

```
my-project/
+-- .claude/
|   +-- CLAUDE.md                # Project-specific rules
|
+-- docs/
|   +-- HANDOVER.md              # Handover (work state)
|   +-- SPRINT.md                # Current sprint
|   +-- instincts.md             # Project-specific instincts
|   +-- memory/                  # Project memory
|   |   +-- MEMORY.md            # Tier-1 index
|   |   +-- {type}_{slug}.md     # Tier-1 entries (feedback_/project_/reference_)
|   |   +-- {agent}/MEMORY.md    # Tier-2 silos (project, persona-specific)
|   |   +-- {agent}/<topic>.md
|   |
|   |  # Phase artifacts (examples)
|   +-- DISCOVERY.md
|   +-- CONCEPT.md
|   +-- FEATURES.md
|   +-- MVP.md
|   +-- BUSINESS_MODEL.md
|   +-- VALIDATION.md
|   +-- ARCHITECTURE.md
|   +-- SECURITY.md
|   +-- INFRASTRUCTURE.md
|   +-- PROJECT_PLAN.md
|   +-- BACKLOG.md
|   +-- ...
|   |
|   |  # Lean-Track artifacts (only if track = lean)
|   +-- TRACK_DECISION.md       # /track-decision output
|   +-- CONSTITUTION.md         # /constitution (optional in Lean, mandatory in Full)
|   +-- FRAME.md                # /lean-frame Single Source of Truth
|   +-- CLAUDE-lean.md          # slim CLAUDE for Lean (replaces .claude/CLAUDE.md)
|   +-- LEARNINGS.md            # /lean-learn validation + decision
|   +-- PROMOTION_BRIEF.md      # /lean-promote bridge to Full-Track
|   +-- lean-archive/           # archived FRAME/LEARNINGS/CLAUDE-lean after promotion or pivot
|   |
|   |  # Generated files (in .gitignore)
|   +-- .session-context.md
|   +-- .gate-preflight-pX.md
|   +-- .quality-scan-report.json
|   +-- .cross-check-report.md
|
+-- ...
```
