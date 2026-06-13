# Claude Code Agent System – System Documentation

Comprehensive documentation of the entire workflow, all processes, mechanisms, and infrastructure.
For the quick reference, see [WORKFLOW_CHEATSHEET.md](WORKFLOW_CHEATSHEET.md).

Last updated: 12.05.2026

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Agent Team](#2-agent-team)
3. [Phase Model & Gates](#3-phase-model--gates)
4. [Command System](#4-command-system)
5. [Cross-Cutting Mechanisms](#5-cross-cutting-mechanisms)
6. [Monitoring & Hooks](#6-monitoring--hooks)
7. [Local Scripts](#7-local-scripts)
8. [Local LLM (Ollama)](#8-local-llm-ollama)
9. [Memory](#9-memory)
10. [Document Splitting (P3 + P6)](#10-document-splitting-p3--p6)
11. [Continuous Learning (Instincts)](#11-continuous-learning-instincts)
12. [File Structure](#12-file-structure)

---

## 1. System Architecture

### Overview

```
+-------------------------------------------------------------+
|                        User                                   |
|   Terminal: shell aliases, local scripts, Ollama              |
+----------+---------------------------------------------------+
           |
           v
+-------------------------------------------------------------+
|                     Claude Code (Head)                        |
|                                                               |
|  +----------+  +----------+  +----------+  +----------+     |
|  | CLAUDE.md|  |instincts |  |HANDOVER  |  | Skills   |     |
|  |(rules)   |  |(learning)|  |(context) |  |(commands)|     |
|  +----------+  +----------+  +----------+  +----------+     |
|                        |                                      |
|               +--------+--------+                             |
|               v        v        v                             |
|         +------+ +------+ +------+   15 agents +             |
|         |Agent | |Agent | |Agent |   1 wingman               |
|         |  A   | |  B   | |  C   |   (max 3-4 parallel)     |
|         +--+---+ +--+---+ +--+---+                           |
|            +--------+--------+                                |
|                     v                                         |
|              +----------+                                     |
|              | Wingman  |  Result consolidation               |
|              +----------+                                     |
+----------+---------------------------------------------------+
           |
     +-----+---------------------+
     v     v                     v
+--------+ +---------------+ +------------------+
| Hooks  | |Local Scripts  | | Ollama (local)   |
|(monitor)| |(shell/python) | | gemma3:4b        |
+--------+ +---------------+ +------------------+
```

### Control Layers

| Layer | File(s) | Purpose |
|---|---|---|
| **Configuration** | `~/.claude/CLAUDE.md` | Global rules, preferences, agent assignments |
| **Configuration** | `~/.claude/settings.json` | Hooks, permissions, default mode |
| **Knowledge** | `~/.claude/docs/*.md` | Reference documents (phases, commands, workflow) |
| **Learning** | `~/.claude/instincts.md` | Experience-based rules with confidence score |
| **Context** | `docs/HANDOVER.md` (per project) | Current work state for session transitions |
| **Automation** | `~/.claude/hooks/agent-monitor.py` | Monitoring, loop detection, warnings |
| **Token saving** | `~/.claude/scripts/` | Run mechanical tasks locally |
| **Token saving** | `~/.claude/scripts/local-llm/` | Delegate routine text tasks to local LLM |

---

## 2. Agent Team

15 specialized subagents + 1 wingman. Max. 3-4 active per command.

### Agent Overview

| Agent | Specialization | Access |
|---|---|---|
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
| **researcher** | Web research with source-citation and PII protection (no Bash) | Read + Write + WebFetch + WebSearch |
| **wingman** | Result consolidation: summarize agent outputs | Read |

### Agent Definitions

Each agent has a Markdown file in `~/.claude/agents/` with:
- Role name and specialization
- Behavioral rules and constraints
- Output format specifications
- References to relevant docs

### Wingman Workflow

The wingman is not a regular agent, but a consolidation mechanism:

1. Parallel agents write full results to files
2. Each agent returns only a brief summary (max. 5 sentences)
3. Wingman reads the result files and creates a summary (max. 15 sentences)
4. Head-Claude presents the consolidated result to the user

**Token savings:** ~1000+ tokens per parallel agent run, because Head-Claude doesn't need all full results in context.

---

## 3. Phase Model & Gates

### Track Decision (Entry Point)

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

**Decision criteria** (see `/track-decision`): Knockouts K1-K5 (DSGVO PII, special categories, launch-imminent, BFSG/regulatory, external stakeholders) + Indicator Score I1-I5. Mid-flight re-assessment allowed; **no downgrade Full -> Lean**.

### Lean-Track Skills (4)

| Skill | Purpose |
|---|---|
| `/track-decision` | Lean vs Full decision (track-agnostic re-assessment tool) |
| `/lean-frame` | `docs/FRAME.md` + `docs/CLAUDE-lean.md` (one-page Single Source of Truth) |
| `/lean-learn` | `docs/LEARNINGS.md` + decision PROMOTE/PIVOT-soft/PIVOT-hard/DROP |
| `/lean-promote` | `docs/PROMOTION_BRIEF.md` as bootstrap input for `/project-init` |

### Full-Track Phase Overview

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

### Phases in Detail

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

### Iterative Loops

- **Validation Loop (P1 <-> P2):** Sharpen concept, validate, adjust
- **Sprint Loop (P5 <-> P6):** Implement, test, fix, next feature
- **Evolution Loop (P8 -> P1/P3/P5):** From operations back to earlier phases

### Gate Types

| Type | Meaning | Example |
|---|---|---|
| Go/No-Go | Binary decision: continue, stop, or pivot | Gate 0, Gate 2 |
| Completeness Gate | All defined results must be present | Gate 1, Gate 3 |
| Readiness Gate | Technical + organizational prerequisites met | Gate 4 |
| Sprint Gate | Repeated per sprint, checks implementation quality | Gate 5 |
| Approval Gate | Formal approval by QA and Security | Gate 6 |
| Go-Live Gate | Technical readiness + business readiness | Gate 7 |

### Gate Transitions

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

Detailed gate checklists are in [PROJECT_PHASES.md](../docs/PROJECT_PHASES.md).

---

## 4. Command System

### Overview

- **82 phase commands** (P0: 3, P1: 5, P2: 4, P3: 23, P4: 4, P5: 12, P6: 22, P7: 5, P8: 4)
- **12 gates** (8 main gates + 4 sub-gates for P6/P7)
- **2 learning commands** (/postmortem, /instinct)
- **13 utility commands** (/konzept, /konzept-update, /decision, /epic, /user-stories, /roadmap, /roadmap-update, /project-init, /logs-summary, /guide, /release-baseline, /cleanup, /specialize)
- **6 track + cross-cutting commands** (/track-decision, /constitution, /lean-frame, /lean-learn, /lean-promote, /cross-check)
- **Total: 115 commands**

### Naming Convention

```
/p[phase]-[section]     -> e.g. /p6-pentest
/gate-p[phase]          -> e.g. /gate-p0
/p[phase]-[sub-skill]   -> e.g. /p5-impl-red, /p6-audit-sast
```

### Sub-Skill Sequences

Within a phase there are fixed sequences. The most important:

**P3 Architecture** (branches after /p3-architecture):
```
/p3-architecture
    +-- p3-arch-components -> p3-arch-techstack -> p3-arch-adr -> p3-arch-nfa
    |
    +-- /p3-data-model
    +-- /p3-security
    |       +-- p3-sec-threats -> p3-sec-auth -> p3-sec-data -> p3-sec-api -> p3-sec-checklist
    +-- /p3-ux
    |       +-- p3-ux-navigation -> p3-ux-wireframes -> p3-ux-darkmode -> p3-ux-a11y
    +-- /p3-infra
    |       +-- p3-infra-hosting -> p3-infra-cicd -> p3-infra-monitoring -> p3-infra-teststrategy
    +-- /p3-cost
         -> gate-p3
```

**P5 Implementation** (TDD cycle per feature):
```
/p5-implement
    +-- p5-impl-red -> p5-impl-green -> p5-impl-refactor
         -> p5-review (p5-review-code -> p5-review-security)
              -> p5-acceptance (-> p5-bugfix on findings)
                   -> p5-docs
                        -> gate-p5
                             -> p5-polish (recommended cleanup)
                                  -> p4-sprint (next) OR p6-functional (all sprints done)
```

**P6 Quality Assurance:**
```
p6-functional (integration -> e2e -> regression)
    -> p6-exploratory
         -> p6-a11y (visual -> keyboard -> screenreader)
              -> p6-audit (sast -> auth -> deps -> config -> dsgvo)
                   -> p6-pentest (recon -> auth -> authz -> injection -> logic)
                        -> p6-bugfix
                             -> gate-p6 (gate-p6-qa + gate-p6-security)
```

### Next Steps Recommendations

After each command, Claude recommends 1-3 sensible next steps.
Rules:
1. HANDOVER.md determines the current phase state
2. Never skip phases – no P5 command if Gate-P4 has not been passed
3. Follow sub-skill sequences
4. Gates are authoritative – only gates open the way to the next phase

Full transition reference: [NEXT_STEPS_REFERENCE.md](../docs/NEXT_STEPS_REFERENCE.md)
All commands in detail: [SECTIONS_COMMANDS.md](SECTIONS_COMMANDS.md)

---

## 5. Cross-Cutting Mechanisms

### Constitution (`docs/CONSTITUTION.md`)

Mandatory artifact for every Full-Track project — the project's "constitution"
with three sections that gates load as binding input:

- **Inviolable** (non-negotiable): DSGVO, BFSG/A11y baseline, sectoral compliance, architectural leitplanken from "inviolable" ADRs
- **Default** (deviate with justification): tech stack, TDD discipline, language, platform targets, monetization pattern
- **Aspirational** (goals, measured): test coverage threshold, performance budget, A11y-audit quality, user-research minimum

**Creation** via `/constitution` in three modes:
- **Greenfield**: 5 domain bootstraps available (`saas-b2c`, `mobile-b2c`, `b2b-tool`, `b2c-marketplace`, `on-device-privacy`)
- **Lean-Vorlauf**: reads Constitution-Light from `docs/FRAME.md` Section 6
- **Existing Full-Track**: drafts from existing phase docs (ADRs, REGULATORY.md, A11Y.md, SECURITY.md, NFR.md)

**Versioning**: Semver-light. MINOR-bump for Default/Aspirational changes, MAJOR-bump for Inviolable changes (requires ADR).

**Gate integration**: `gate-preflight.py` extracts the Inviolable section into `docs/.gate-preflight-pX.md`. All 8 gate commands (P0-P7) load it as mandatory pre-gate input. Inviolable violations are flagged as **"Inviolable breach"** = No-Go signal in the verdict.

### Cross-Check (`/cross-check`)

Optional pre-gate consistency check across phases. 7 initial rules:

| # | Rule |
|---|---|
| R1 | FEATURES.md <-> AUTH.md (each user-facing feature has an auth flow) |
| R2 | TECH_STACK.md <-> DATA_MODEL.md (DB choice consistent with schema syntax) |
| R3 | THREATS.md <-> AUTH/SECURITY (each threat has a mitigation) |
| R4 | NFR.md <-> TESTSTRATEGY.md (each NFR has a test approach) |
| R5 | ADR-status <-> Components (rejected ADRs not actively referenced) |
| R6 | CONSTITUTION Inviolable <-> ADRs/Implementation (no ADR violates Inviolables) |
| R7 | STORY_INDEX <-> Epic-Detail-Files (bidirectional story-epic consistency) |

**Output**: `docs/.cross-check-report.md` (volatile, regenerated per run).
**Recommendation, not mandatory** — gates list `/cross-check` as a suggested pre-step. Iterative rule expansion expected.

### Handover (HANDOVER.md)

Preserves work state across session transitions. Located in `docs/HANDOVER.md` in the project directory.

**Session Start:**
1. Check if `docs/HANDOVER.md` exists
2. If yes: read it and continue work

**Session End / Before Compact:**
- Update HANDOVER.md with current work state
- Template: `~/.claude/templates/HANDOVER_TEMPLATE.md`

**Strategic Compact:**
1. At 100 tool calls: Compact reminder (via agent-monitor)
2. At 150 tool calls: Urgent HANDOVER warning
3. **Before** /compact: Update HANDOVER.md
4. **After** /compact: Read HANDOVER.md to restore context

### Wingman Consolidation

See [Agent Team > Wingman Workflow](#wingman-workflow).

Commands that use the wingman: `/konzept`, `/p1-features`, `/gate-p1`, `/p3-architecture`, `/gate-p3`, `/p5-review` and other commands with parallel agents.

### Token Optimization

Multiple mechanisms work together:

| Mechanism | Token Savings | How |
|---|---|---|
| Wingman consolidation | ~1000+ per agent run | Summary instead of full results in context |
| Local scripts | variable | Mechanical checks outside of Claude |
| Ollama delegation | ~500-1000 per call | Summaries, HANDOVER drafts locally |
| Strategic compact | significant | Context compression on long sessions |
| Agent brief summaries | ~500 per agent | Agents return max. 5 sentences |

---

## 6. Monitoring & Hooks

### Hook Architecture

A central Python script (`~/.claude/hooks/agent-monitor.py`) processes all hook events.

**Registered events (in settings.json):**

| Event | When | What the monitor does |
|---|---|---|
| `SessionStart` | Claude session starts | Create fresh loop state, start logging |
| `SessionEnd` | Session ends | Write summary, log incomplete agents, clean up state |
| `PreToolUse` | Before every tool call | Loop detection, tool count, stagnation check |
| `PostToolUse` | After every tool call | Performance tracking (duration) |
| `SubagentStart` | Agent is started | Record start time, duplicate batch detection |
| `SubagentStop` | Agent finishes | Calculate duration, slow agent warning |

### Loop Detection

Detects and blocks infinite loops:

```
Same tool call 3x -> Warning (log)
Same tool call 5x -> BLOCKED (exit 2, feedback to Claude)
```

Additionally:
- EISDIR pattern: 3x "Is a directory" error -> Warning
- Duplicate batch: Same agent set started again within 30 min -> Warning

### Tool Count Warnings

| Threshold | Action |
|---|---|
| 100 tool calls | Compact reminder (stderr -> Claude) |
| 150 tool calls | Token budget warning + update HANDOVER |
| 200 tool calls | High tool count in error log |
| 500 tool calls | Critical tool count in error log |

### Stagnation Detection

When no `Write` or `Edit` is executed for 15 minutes:
- Warning to Claude: "Stuck? Consider rethinking approach or asking user."
- Resets once a productive tool call occurs again

### Slow Agent Warning

When an agent runs longer than 10 minutes -> Warning to Claude via stderr.

### Input Validation

Certain tool inputs are validated before execution:
- `AskUserQuestion`: Every question needs 2-4 options. Invalid calls are blocked.

### Log Files

```
~/.claude/logs/
+-- activity.jsonl          # Aggregated activity log (rotates at 10MB)
+-- errors.jsonl            # Aggregated error log (rotates at 10MB)
+-- performance.jsonl       # Aggregated performance log (rotates at 10MB)
+-- sessions/
    +-- {session_id}/
        +-- activity.jsonl   # Session-specific
        +-- errors.jsonl     # Session-specific
        +-- performance.jsonl# Session-specific
        +-- session-summary.json  # Summary at SessionEnd
```

**Loop state:** `/tmp/claude-loop-{session_id}.json` (temporary, deleted at SessionEnd)

### Log Analysis

The script `logs-summary.py` analyzes the logs:
```bash
~/.claude/scripts/logs-summary.py errors        # Show errors
~/.claude/scripts/logs-summary.py performance   # Performance data
~/.claude/scripts/logs-summary.py agents        # Agent statistics
~/.claude/scripts/logs-summary.py loops         # Loop events
~/.claude/scripts/logs-summary.py all           # Everything
```

Periods: `today`, `week`, `all`

---

## 7. Local Scripts

Shell and Python scripts in `~/.claude/scripts/` for mechanical tasks.
Save Claude tokens because they run outside the session.

### Before Session Start

| Script | Usage | Result |
|---|---|---|
| `bootstrap.sh` | `~/.claude/scripts/bootstrap.sh [projectdir]` | `docs/.session-context.md` – Git status, HANDOVER, artifacts, instincts |
| `gate-preflight.py` | `~/.claude/scripts/gate-preflight.py p3 [projectdir]` | `docs/.gate-preflight-p3.md` – Artifacts, content patterns, Ollama summaries |
| `command-check.py` | `~/.claude/scripts/command-check.py p5-implement [projectdir]` | Stdout: ready/blocked with reason |

Claude reads generated files (if < 10 min old) automatically as compact context.

### During Work

| Script | Usage | Result |
|---|---|---|
| `run-tests.sh` | `~/.claude/scripts/run-tests.sh [testpath] [projectdir]` | JSON output (detects pytest/jest/vitest/cargo/go) |
| `quality-scan.sh` | `~/.claude/scripts/quality-scan.sh [scope] [projectdir]` | `docs/.quality-scan-report.json` |

Scopes for quality-scan: `all`, `deps`, `sast`, `config`, `dsgvo`

### One-Time / As Needed

| Script | Usage | Purpose |
|---|---|---|
| `project-init.sh` | `~/.claude/scripts/project-init.sh name [template]` | Project scaffolding (default/webapp/api/library) |
| `logs-summary.py` | `~/.claude/scripts/logs-summary.py [focus] [period]` | Analyze session logs |
| `setup-ollama.sh` | `~/.claude/scripts/setup-ollama.sh` | Install Ollama + gemma3:4b, generate wrapper scripts |
| `instinct-check.sh` | `~/.claude/scripts/instinct-check.sh` | Check instinct decay (no LLM needed) |

### Shared Libraries

Python modules in `~/.claude/scripts/lib/`:
- `next_steps.py` – Phase-to-commands mapping, HANDOVER.md parser
- `artefacts.py` – Phase-to-expected-files mapping
- `gate_checklists.py` – Gate checklists with required sections + content pattern checks (regex)

### Shell Aliases

Configured in `~/.zshrc`:

```
cb        -> bootstrap.sh + start Claude
cgate     -> gate-preflight.py
ctest     -> run-tests.sh
ccheck    -> command-check.py
cscan     -> quality-scan.sh
clogs     -> logs-summary.py
cmsg      -> commit-msg.sh (Ollama)
cinstinct -> instinct-check.sh
```

### How Claude Uses the Scripts

Claude automatically detects generated files and uses them as context:
- `docs/.session-context.md` (< 10 min old) -> reads instead of HANDOVER + git + instincts individually
- `docs/.gate-preflight-pX.md` (< 10 min old) -> uses as gate basis, focuses on content
- `docs/.quality-scan-report.json` -> uses as basis for /p6-audit and /p6-pentest

---

## 8. Local LLM (Ollama)

### Setup

- **Framework:** Ollama (CLI-first, OpenAI-compatible API)
- **Model:** gemma3:4b (~3.3GB, Google Gemma 3)
- **Server:** runs as brew service (`brew services start ollama`)
- **API:** `http://localhost:11434` (Generate API with stream=false)

### Wrapper Scripts

Located in `~/.claude/scripts/local-llm/`:

| Script | Purpose | Caller |
|---|---|---|
| `ollama-query.sh` | Shared helper – sends prompt to Ollama Chat API | Internal (from other scripts) |
| `summarize.sh <file>` | Summarize file in 3-5 sentences | Claude or user |
| `handover-draft.sh [dir]` | HANDOVER.md draft from git status | Claude or user |
| `commit-msg.sh` | Commit message from staged diff | Claude, user, or git hook |
| `install-git-hook.sh <dir>` | Install prepare-commit-msg hook | User (one-time per project) |

### Token Delegation by Claude

Claude delegates routine tasks to Ollama when the server is reachable:

**Delegate:**
- Long file summaries -> `summarize.sh`
- HANDOVER drafts -> `handover-draft.sh` as starting point, then refine
- Commit messages -> get `commit-msg.sh` suggestion

**Don't delegate:**
- Architecture decisions, code reviews, security analyses
- Anything that requires judgment

**Fallback:** If Ollama is not reachable, Claude handles the task itself.

### Git Hook (optional)

`install-git-hook.sh` installs a `prepare-commit-msg` hook:
- On every `git commit`, a message is automatically suggested
- The suggestion appears in the editor and can be overwritten
- Skipped on merge, amend, squash, or when Ollama is not running

### Technical Details

- gemma3:4b responds directly without thinking overhead (~12s per summary)
- `num_predict: 512` is sufficient for summaries and commit messages
- Generate API (`/api/generate`) for simple prompt-response
- `stream: false` for script usage (no spinner, no ANSI)
- Previous model qwen3.5 (14B) was too large for 24GB M4 (22 min per summary)
- qwen3:4b had thinking problem (empty content, output only in thinking field)

### Gate Preflight Integration

`gate-preflight.py` uses Ollama automatically for document summaries:
- Per gate artifact, `summarize.sh` is called (3-5 sentences per document)
- Summaries end up in the preflight report under "Document Summaries"
- Timeout: 90s per file. On timeout or Ollama failure: section is omitted
- Saves ~16k tokens per gate run (agent reads summaries instead of raw documents)

---

## 9. Memory

### Concept

Two-tier memory: cross-cutting (Tier 1) coexists with persona-specific silos (Tier 2). Memories are versioned in the project repository and pushable. Global personal memories (`type: user`) remain in personal global memory and are not pushed.

### Tiers

| Tier | Path | Scope |
|---|---|---|
| Tier 1 — cross-cutting | `docs/memory/{type}_{slug}.md` (flat) | Relevant to orchestrator AND ≥2 agents — tooling decisions, project conventions, external references |
| Tier 2 — agent silos | `docs/memory/{agent}/MEMORY.md` + topic files | Meaningful only inside one agent's domain |

**Tier-separation rule** — cross-cutting → Tier 1; persona-specific → Tier 2. When in doubt, prefer Tier 1 (visibility wins over isolation).

### Memory Types (Tier 1)

| Type | Use case |
|---|---|
| `feedback` | Guidance from the user — what to do, what to avoid, with reasoning |
| `project` | Project-specific facts, decisions, deadlines, constraints |
| `reference` | Pointers to external systems (URLs, dashboards, ticket trackers) |
| `user` | Personal user info — stays in `~/.claude/projects/.../memory/`, not pushed |

### Frontmatter Schema

```yaml
---
name: short-slug-or-title                 # required
description: one-line summary             # required
type: feedback|project|reference          # required (user stays global)
last_updated: DD.MM.YYYY                   # required
status: active|stale|superseded|archived  # optional
related: [other_memory.md]                # optional, paths relative to file
confidence: 0.4                           # optional, for instinct memories
---
```

Full schema: `templates/MEMORY_SCHEMA.md`.

### Indexes

- Tier 1 index: `docs/memory/MEMORY.md` (template: `templates/MEMORY_INDEX_TEMPLATE.md`)
- Tier 2 index: `docs/memory/{agent}/MEMORY.md` (one per agent silo, slim)

Indexes are listings — no frontmatter required.

### Memory Lint

`~/.claude/scripts/memory-lint.sh [projectdir]` checks:
- Required frontmatter fields present
- Naming convention (`{type}_{slug}.md` for Tier 1)
- Cross-refs in `related:` resolve to existing files
- `last_updated` older than 90 days → suggests `status: stale`
- Each Tier 1 file referenced in `MEMORY.md`

### Templates

| File | Purpose |
|---|---|
| `templates/MEMORY_SCHEMA.md` | Full field reference |
| `templates/MEMORY_PAGE_TEMPLATE.md` | Starter for a new memory file |
| `templates/MEMORY_INDEX_TEMPLATE.md` | Starter for `MEMORY.md` index |
| `templates/MEMORY_LINT_REPORT_TEMPLATE.md` | Lint output format reference |

---

## 10. Document Splitting (P3 + P6)

### Concept

Phases P3 (Architecture & Design) and P6 (Quality Assurance) produce many concerns. A single monolithic phase document would bloat past 30–50 KB and force re-reading large blocks. The solution: a **two-level pattern** — slim phase index + one detail file per sub-skill.

### Pattern

```
docs/<phase-folder>/
+-- <PHASE>.md              # Phase index (5–15 KB) — current state, key decisions, file pointers
+-- <DETAIL_1>.md           # Sub-skill detail file with full content
+-- <DETAIL_2>.md
+-- <SUB_INDEX>.md          # P3/P6 only — groups several detail files under one lead command
```

**Examples**
- P3: `architecture/ARCHITECTURE.md` (index) + `THREATS.md`, `ADRs.md`, `SECURITY.md` (sub-index for `/p3-sec-*`)
- P6: `quality/QA.md` (index) + sub-indexes for each lead command (`A11Y.md`, `AUDIT.md`, `PENTEST.md`, …)

### Sub-Skill Responsibilities

Each `/pX-...` sub-skill command must:

1. **Write detail file** — overwrite (not append) `docs/<phase>/<DETAIL>.md` with YAML frontmatter
2. **Update phase index** — refresh the detail-file row, lift any one-line key decision or risk into the index

### Frontmatter Schema

```yaml
---
phase: P3                     # required, P0..P8
subskill: p3-sec-threats      # required, slash command without leading /
status: active                # required: skeleton|draft|active|frozen|archived|living
last_updated: 12.05.2026      # required, DD.MM.YYYY (optional " (Notiz)" suffix)
related: [ARCHITECTURE.md]    # optional, paths relative to file
parent_index: SECURITY.md     # optional, for detail files under a sub-index
gate: pending                 # optional, for GATE_PX.md files
---
```

Full schema: `templates/PHASE_DOC_SCHEMA.md`.

### Status Semantics

| Status | Meaning |
|---|---|
| `skeleton` | Empty placeholder (e.g. P6 sub-index pre-implementation) |
| `draft` | Work in progress |
| `active` | Usable, current |
| `frozen` | Locked after gate pass; baseline mode |
| `archived` | Replaced by newer file, kept for history |
| `living` | Detail file designed to grow over time (e.g. `SPRINT-XX.md`, `RISKS.md`) |

Phase docs have **no stale detection** (unlike memory) — `frozen` is a wanted state, not a warning.

### Gate Reading Pattern

Gate commands (`/gate-pX`) read the phase index first. Detail files are pulled only when content checks demand it. This keeps the gate's context window small.

### Validation

`~/.claude/scripts/phase-docs-lint.sh [projectdir] [--scope <glob>]` checks:
- Required frontmatter fields present
- `status` is one of the allowed enum values
- Cross-refs in `related:` and `parent_index:` resolve
- Each detail file referenced in its phase index or sub-index

### Volume Watch

`~/.claude/scripts/doc-volume-check.sh [docs-root]` flags files at thresholds:
- ≥25 KB → review whether splitting helps
- ≥40 KB → split recommended
- ≥50 KB → split required (G-017 protection — large files erode Claude's effectiveness)

---

## 11. Continuous Learning (Instincts)

### Concept

Instincts are experience-based rules with confidence score (0.3-0.9).
They emerge from session experience and are confirmed or rejected over time.

### Levels

| Level | File | Scope |
|---|---|---|
| Global | `~/.claude/instincts.md` | All projects, all agents |
| Agent | `docs/memory/{agent}/instincts.md` | Specific agent |
| Project | `docs/instincts.md` | Specific project |

### Instinct Format

```markdown
### [ID] Short Title
**Confidence: 0.X** | Source: [context]
> Rule in one sentence.
```

**ID schema:** `G-NNN` (Global), `SD-NNN` (Senior-Dev), `QA-NNN` (QA-Tester), etc.

### Confidence Rules

| Action | Effect |
|---|---|
| Newly created | 0.4-0.5 |
| Confirmed (`/instinct confirm`) | +0.1 (max 0.9) |
| Contradicted (`/instinct reject`) | -0.2 (min 0.3) |
| Decay (> 30 days unconfirmed) | -0.1 |

Claude follows instincts proportional to their confidence score.

### Management Commands

| Command | Effect |
|---|---|
| `/postmortem` | Analyze session, propose instincts |
| `/instinct list` | Show all instincts |
| `/instinct add [rule]` | Create new instinct |
| `/instinct confirm [ID]` | Increase confidence |
| `/instinct reject [ID]` | Decrease confidence |
| `/instinct promote [ID]` | Promote agent instinct to global |
| `/instinct cleanup` | Remove outdated instincts |

### Instinct Check (Script)

`~/.claude/scripts/instinct-check.sh` checks without LLM:
- Age of instincts.md
- Number of active instincts
- Warning if > 30 days since last update

---

## 12. File Structure

### Global Configuration (~/.claude/)

```
~/.claude/
+-- CLAUDE.md                    # Global rules and preferences
+-- settings.json                # Hooks, permissions
+-- instincts.md                 # Global instincts
|
+-- agents/                      # 15 agents + 1 wingman
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
+-- docs/                        # Runtime reference docs (read by Claude during work)
|   +-- PROJECT_PHASES.md        # Phase model with gate checklists
|   +-- NEXT_STEPS_REFERENCE.md  # Transition reference for recommendations
|   +-- CONSTITUTION.md          # CCPR's own ratified constitution
|   +-- adr/                     # Architecture Decision Records
|   +-- memory/                  # Project memory (MEMORY.md index + project_*.md)
|
|   # Human-facing manual (this document) lives in the repo's Manual/ — not installed
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
|   +-- setup-ollama.sh          # Ollama + model setup
|   +-- instinct-check.sh        # Check instinct decay
|   +-- lib/                     # Shared Python libraries
|   |   +-- next_steps.py
|   |   +-- artefacts.py
|   |   +-- gate_checklists.py
|   +-- local-llm/               # Ollama wrapper scripts
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
    +-- HANDOVER_TEMPLATE.md     # Handover template
```

### Per Project (docs/)

```
my-project/
+-- .claude/
|   +-- CLAUDE.md                # Project-specific rules
|
+-- docs/
|   +-- HANDOVER.md              # Handover (work state)
|   +-- SPRINT.md                # Current sprint
|   +-- instincts.md             # Project-specific instincts
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

---

## Change History

| Date | Change |
|---|---|
| 06.03.2026 | Initial creation; Ollama integration (qwen3.5), instinct-check.sh, install-git-hook.sh |
| 06.03.2026 | Ollama model: qwen3.5 -> gemma3:4b (performance: 22 min -> 12s). Gate preflight: content patterns + Ollama summaries. gate-p4: Preflight-centered, 1 agent instead of 2 (~60% token savings). Command count: 103 commands (80 phase + 12 gates + 2 learning + 9 utility) |
| 13.05.2026 | Lean-Track introduced (parallel to Full-Track): /track-decision entry point, /lean-frame + /lean-learn + /lean-promote (4 skills, no gates). Constitution as mandatory Full-Track artifact: /constitution skill (Hybrid mode with 5 domain bootstraps), gate-preflight.py extracts Inviolables, all 8 gates load them as binding input. /cross-check as optional pre-gate consistency check (7 initial rules). 6 new commands, 6 new templates + 5 bootstraps. Command count: 109 -> 115. |
