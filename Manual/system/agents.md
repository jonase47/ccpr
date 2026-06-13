---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: agent-team
last_updated: 15.05.2026
---

# Agent Team

15 agents: 13 domain subagents + `project-guide` (entry-door orchestrator) + `wingman` (result consolidator). Max. 3-4 active per command.

## Agent Overview

| Agent | Specialization | Access |
|---|---|---|
| **project-guide** | Entry-door orchestrator: status snapshot, skill/agent recommendation, disambiguation, hand-off | Read |
| **konzeptor** | Product idea, target audience, features, MVP, value proposition | Read + Write |
| **business-analyst** | Business model, financial planning, pricing, market analysis, KPIs | Read + Write |
| **system-architekt** | Tech stack, data model, APIs, ADRs | Read + Write |
| **project-planner** | Milestones, sprints, backlog, prioritization | Read + Write |
| **ux-designer** | UI concepts, user flows, accessibility, dark mode | Read + Write |
| **senior-developer** | Implementation (TDD), clean code, feature development | Read + Write |
| **code-reviewer** | Code review, quality, best practices | **Read only** |
| **qa-tester** | Test strategy, test cases, exploratory tests, acceptance tests | Read + Write |
| **debugger** | Error analysis, root cause, systematic troubleshooting | Read + Write |
| **devops** | CI/CD, deployment, hosting (Hetzner), monitoring | Read + Write |
| **security-master** | Security strategy, DSGVO (GDPR), threat modeling, audits | Read + Write |
| **pentester** | Offensive security, finding vulnerabilities, PoCs | Read + Write |
| **tech-writer** | Documentation, README, API docs, changelogs | Read + Write |
| **wingman** | Result consolidation: summarize agent outputs | Read |

## Agent Definitions

Each agent has a Markdown file in `~/.claude/agents/` with:
- Role name and specialization
- Behavioral rules and constraints
- Output format specifications
- References to relevant docs

## Wingman Workflow

The wingman is not a regular agent, but a consolidation mechanism:

1. Parallel agents write full results to files
2. Each agent returns only a brief summary (max. 5 sentences)
3. Wingman reads the result files and creates a summary (max. 15 sentences)
4. Head-Claude presents the consolidated result to the user

**Token savings:** ~1000+ tokens per parallel agent run, because Head-Claude doesn't need all full results in context.
