# Sections & Commands – Overview

## Decisions
- **116 Commands** – full granularity, full control (P0–P8 Full-Track + Lean-Track + cross-cutting)
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

Entry-point and cross-cutting commands. `/track-decision` runs first and decides Lean vs. Full-Track; `/constitution`, `/lean-frame`, `/lean-learn` and `/lean-promote` carry out that decision; `/cross-check` is an optional pre-gate consistency check available on either track.

**Full chapter**: [commands/track.md](commands/track.md).

## Phase Commands (P0–P8, 82 commands)

All P0–P8 phase commands, grouped per phase. Lead commands appear first, then sub-skills in execution sequence where applicable. P3 (Architecture & Design, 23 commands) and P6 (Quality Assurance, 22 commands) are the largest phases — each has its own lead-command-plus-sub-skills structure, documented in full in the chapter.

**Full chapter**: [commands/phases.md](commands/phases.md).

## Gates (12 commands)

Quality gates between phases — single-purpose decision points. Main gates (P0–P7) plus sub-gates for the dual-approval gates P6 (QA + Security) and P7 (Tech + Business).

**Full chapter**: [commands/gates.md](commands/gates.md).

## Continuous Learning (2 commands)

Meta-commands for capturing session insight back into the system.

**Full chapter**: [commands/learning.md](commands/learning.md).

## Utility (14 commands)

Cross-cutting commands that operate outside the phase flow.

**Full chapter**: [commands/utility.md](commands/utility.md).

---

## Summary: 116 Commands

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
| Utility | 14 |
| Track + Cross-Cutting (`/track-decision`, `/constitution`, `/lean-frame`, `/lean-learn`, `/lean-promote`, `/cross-check`) | 6 |
| **Total** | **116** |

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
