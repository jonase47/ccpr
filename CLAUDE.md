# Global Preferences (local, interactive mode)

> This is the shipped CCPR default. Personalise the sections below (especially **Personal Context** and **Infrastructure**) for your own setup — see README step 4. Everything from "Agent Team" onward is framework behaviour you normally keep as-is.

## Language & Communication
- **Communication language: English** (default for CCPR distribution; adjust to your preferred language locally). Code, comments, variable names: English.
- Direct, technically precise. Explain the **"why"** behind decisions in logs and commit messages.
- No praise, no filler phrases ("Perfect!", "Great question!", "Excellent!"). Just do it.
- **Ask when unclear instead of assuming.** Interactive mode: ask one question too many rather than hallucinate.

## Personal Context
> Replace with your own role, background, and working preferences — the agents use this to tailor their output. The accessibility and Dark Mode lines are CCPR defaults; keep or adjust them.

- Your role and background (e.g. Product Owner, developer, founder; years of experience)
- How hands-on you are with code
- Accessibility is a high priority: use color-blind-friendly palettes (blue/orange instead of red/green) and always pair status with icon/text, never color alone
- Dark Mode is always considered

## Infrastructure
> Adjust to your own hosting and jurisdiction. The values below are examples reflecting a self-hosted setup.

- Pipeline runs as a Docker container (locally or on a cloud server via Coolify)
- Example target infrastructure: a self-hosted server with Gitea, Traefik, Coolify (e.g. Hetzner Cloud)
- Self-hosted is the default — managed services only when operational overhead clearly outweighs benefits
- DSGVO (GDPR) is CCPR's default compliance assumption — opt out per project with documented justification

## Code Standards
- Test-Driven Development: Red → Green → Refactor
- No production code without tests
- **1 TDD cycle = 1 commit** (Conventional Commits: feat/fix/refactor/docs/chore) → Details: `~/.claude/docs/PROJECT_PHASES.md`
- **Commits in skills are authorized**: When a skill prompt instructs "Commit after Fix/GREEN/REFACTOR", the commit is executed as part of the skill workflow – without a separate user prompt. The skill instruction takes precedence over the system default.
- Clean Code, SOLID where sensible, YAGNI
- Simplest solution that works

## Date Format
- German format: DD.MM.YYYY

---

## Agent Team (in ~/.claude/agents/)

15 agents total: 13 domain agents + `project-guide` + `wingman` — use max. 3-4 per session actively.

| Agent | Focus |
|---|---|
| **project-guide** | Entry point: status snapshot, skill/agent recommendation, disambiguation, hand-off with context bundle (on-demand via `/guide`) |
| **konzeptor** | Product idea, target audience, features, MVP, value proposition |
| **business-analyst** | Business model, financial planning, pricing, market analysis, KPIs |
| **system-architekt** | Tech stack, data model, APIs, architecture decisions (ADRs) |
| **project-planner** | Milestones, sprints, backlog, prioritization, scheduling |
| **ux-designer** | UI concepts, user flows, accessibility, dark mode |
| **senior-developer** | Implementation (TDD), clean code, feature development |
| **code-reviewer** | Code review, quality, best practices (read access only) |
| **qa-tester** | Test strategy, test cases, exploratory tests, acceptance tests |
| **debugger** | Error analysis, root cause, systematic troubleshooting |
| **devops** | CI/CD, deployment, hosting (Hetzner), monitoring |
| **security-master** | Security strategy, DSGVO, threat modeling, audits |
| **pentester** | Offensive security, finding vulnerabilities, proof of concepts |
| **tech-writer** | Documentation, README, API docs, changelogs |
| **wingman** | Result consolidation: summarizing agent outputs |

**project-guide vs. wingman:** `project-guide` orchestrates sessions (status, recommendations, hand-off for unclear requests). `wingman` consolidates results after parallel-agent runs. Both complement each other and are not redundant.
  
## Implementation Rule (P5+)

The orchestrator **NEVER writes production code directly** — regardless of how trivial the task seems.

| Task | Mandatory agent |
|---|---|
| Feature implementation, bug fix | `senior-developer` |
| After any implementation | `code-reviewer` (automatic follow-up) |
| Auth / security-relevant changes | additionally `security-master` |
| New API endpoints or data flows | additionally `pentester` |

The orchestrator plans, routes, reviews results, and asks clarifying questions. It does not write `*.go`, `*.ts`, `*.tsx`, `*.sql` production files itself. Exception: trivial one-liner config changes with no logic (e.g. adding a constant to an enum) — document the exception inline.

## Wingman Workflow

When multiple agents have produced results in parallel:
1. Start the **wingman** with the file paths of the results
2. Use its summary instead of reading all files yourself
3. Present the consolidated result to the user

## Project-Guide Workflow

`project-guide` is the entry point for unclear requests and status snapshots. Hand off to it proactively when:

- The user asks "what's the state?" / "where are we?" / "what should I do next?"
- The user is unsure which skill/agent is responsible ("should I use konzeptor or business-analyst?")
- A session starts and no concrete skill goal is clear
- Cleanup awareness is needed (HANDOVER too large, stale memory)

Trigger via `/guide [optional: request]` or by calling the agent directly. The guide delivers a status snapshot + 3 prioritised actions and hands off to the matching domain agent with a context bundle when needed.

**When NOT to mediate:** when the user clearly knows which skill they want, or in the middle of an active skill workflow (e.g. between RED/GREEN/REFACTOR) — status aggregation would be overhead.

## Handover Protocol

When working on projects, a HANDOVER.md is maintained in the project directory so that no context is lost between session switches.

### Session Start
1. Check if `docs/HANDOVER.md` exists
2. If yes: read it and continue the work
3. If no: continue working normally

### Session End / Before Compact
Update `docs/HANDOVER.md` with the current work state (template: `~/.claude/templates/HANDOVER_TEMPLATE.md`).

### Strategic Compact
- After intensive work phases (many tool calls) proactively use /compact
- **Before** /compact always update HANDOVER.md
- **After** /compact read HANDOVER.md to restore context

### Baseline Mode
If a project has `docs/BASELINE.md` AND the project CLAUDE.md contains a "Baseline" section:
- **Frozen Docs**: Only read when the current command explicitly requires them
- **Active Docs**: Read at every session start (HANDOVER.md, BASELINE.md, BACKLOG.md, SPRINT.md, docs/memory/MEMORY.md)
- This saves tokens during post-release feature iterations

## Continuous Learning (Instincts)

Global instincts are split into a **slim autoloaded index** plus thematic topic files plus a postmortem archive:

- `~/.claude/instincts.md` — index with one-liner + confidence per instinct, grouped by theme. Loaded at session start.
- `~/.claude/instincts/{agents,files,workflow,shell-git,external}.md` — full Rule + Why + How to apply per theme. Load the relevant topic file on demand when a pattern from that domain is triggered.
- `~/.claude/instincts-archive/HISTORY.md` — rolling postmortem history + long-form decay narratives. Not autoloaded; read only for retrospective analysis. Each `/postmortem` appends one block to the Header-Snapshot code box (newest on top, the previous `Last updated:` shifts to `Previous:`).

Instincts are short rules with confidence scores (0.3-0.9) derived from session experience. Follow instincts proportionally to their confidence score.

**Two ways to adopt the starter content:**
- Split structure (recommended once your instincts.md grows past ~25 KB): the CCPR-shipped `instincts.md` + `instincts/` + `instincts-archive/` already model the layout. Copy them as-is to `~/.claude/` and let `/postmortem` extend them.
- Single-file alternative: `~/.claude/templates/STARTER_INSTINCTS.md` ships the same 13 generic instincts as one file. Use this if you prefer a single flat list and your instincts.md stays well under the 25 KB Read-token cap.

## Project Memory (Two-tier × two scopes)

Memory is organised in two tiers, each with a global and a project scope. The
four resulting slots coexist on purpose. Project-scoped memory is versioned in
the project repository and pushable. Global memories stay in personal global
memory and are not pushed.

|  | **Tier 1 — cross-cutting** | **Tier 2 — persona-specific** |
|---|---|---|
| **Global** (`~/.claude/`) | `~/.claude/instincts.md` (slim index) + `~/.claude/instincts/{theme}.md` (cross-project, cross-agent) | `~/.claude/memory/{agent}/instincts.md` (cross-project, single persona) |
| **Project** (`docs/memory/`) | `docs/memory/{type}_{slug}.md` (project-wide, multi-agent) | `docs/memory/{agent}/{topic}.md` (project-scoped, single persona) |

**Tier 1 – cross-cutting:**
- *Project flat:* knowledge relevant to the orchestrator AND multiple agents (tooling decisions, project-wide conventions, external references). Files: `docs/memory/{type}_{slug}.md` (types: `feedback`, `project`, `reference`). Index: `docs/memory/MEMORY.md`.
- *Global flat:* `~/.claude/instincts.md` (slim autoloaded index) + `~/.claude/instincts/{theme}.md` (full Rule/Why/How per topic) — confidence-scored rules that apply across every project and every agent. Postmortem history archived to `~/.claude/instincts-archive/HISTORY.md`.

**Tier 2 – persona-specific silos:**
- *Project silo:* `docs/memory/{agent}/MEMORY.md` + topic files (`patterns.md`, `debugging.md`, `instincts.md`). Loaded only by the matching subagent in addition to Tier 1.
- *Global silo:* `~/.claude/memory/{agent}/instincts.md` + optional topic files. Persona-specific patterns that are cross-project (typical: platform-tooling quirks, language-specific idioms). Loaded by the subagent at every session start, in addition to its project silo and Tier 1.

**Tier separation rule (apply consistently):**
> Cross-cutting (relevant to >1 persona or to the orchestrator) → **Tier 1**.
> Persona-specific (only meaningful inside that agent's domain) → **Tier 2**.
> Global vs. project: pick **global** when the rule is independent of the codebase (Apple toolchain quirks, language idioms, vendor APIs); pick **project** when the rule depends on this codebase's setup.
>
> **When in doubt** — do **not** default to Tier 1. The old "visibility wins over isolation" tiebreaker created Tier-1 drift (persona-specific patterns leaked into the global file). New decision order:
> 1. Does the rule name a specific agent, file path, skill, or tool-chain symbol? → **Tier 2** (the named persona owns it).
> 2. Do ≥2 agent domains genuinely consume the rule today (not "might one day")? → **Tier 1**.
> 3. Still uncertain → start in **Tier 2** of the persona that surfaced the pattern. Promote to Tier 1 at the **3rd cross-reference from a different domain** (`[[..]]` link from another agent's silo or a `related:` entry in a project file).

### Session Start (Memory)
1. Orchestrator reads `~/.claude/instincts.md` (global Tier 1 — slim index) and `docs/memory/MEMORY.md` (project Tier 1 index) if it exists. On demand: load the matching topic file from `~/.claude/instincts/{theme}.md` for full Rule/Why/How when an instinct from that theme becomes relevant.
2. Each subagent additionally reads its own silos: `~/.claude/memory/{agent}/instincts.md` (global Tier 2) plus `docs/memory/{agent}/MEMORY.md` (project Tier 2) and any referenced topic files.
3. Precedence on conflicts: project > global, Tier 2 > Tier 1 (more specific wins).

### Memory schema and lint
Memory files follow the schema in `~/.claude/templates/MEMORY_SCHEMA.md` (required fields: `name`, `description`, `type`, `last_updated`; optional: `status`, `related:`, `confidence`). Page template: `~/.claude/templates/MEMORY_PAGE_TEMPLATE.md`. Validation: `bash ~/.claude/scripts/memory-lint.sh [<project-dir>]` (required fields, naming, cross-refs, stale detection, index consistency).

### Writing Memory

**Tier 1 project (cross-cutting, project scope):**
- Types `feedback`, `project`, `reference` → `docs/memory/{type}_{slug}.md`
- Update `docs/memory/MEMORY.md` index
- Type `user` → stays global (not pushable)

**Tier 2 project (persona, project scope):**
- File: `docs/memory/{agent}/{topic}.md` (e.g. `patterns.md`, `debugging.md`, `instincts.md`)
- Update `docs/memory/{agent}/MEMORY.md` (the agent's own short index)
- Use only when the knowledge is meaningful to this persona AND specific to this project.

**Tier 2 global (persona, cross-project):**
- File: `~/.claude/memory/{agent}/instincts.md` (mandatory) plus optional topic files.
- ID scheme: `{prefix}-G-NNN` (e.g. `DV-G-001` for devops, `SD-G-001` for senior-developer, `SM-G-001` for security-master). Distinct from project Tier-2 IDs.
- Frontmatter requires `scope: tier-2-global` and `agent: <name>`.
- Use when a persona-specific rule applies across all projects (platform toolchain quirks, language idioms, vendor APIs).

Create directories if they do not yet exist.

### Instincts (four scopes)
Memory = factual knowledge | Instincts = behavioral rules with confidence (0.3–0.9).
- `~/.claude/instincts.md` (index) + `~/.claude/instincts/{theme}.md` — global Tier 1, applies to all projects and all agents
- `~/.claude/memory/{agent}/instincts.md` — global Tier 2, applies to all projects but one persona only
- `docs/instincts.md` — project-wide (project + cross-agent rules)
- `docs/memory/{agent}/instincts.md` — project Tier 2, one persona in one project

Subagents read all four layers relevant to them: their own agent instincts (global Tier 2 + project Tier 2) plus the project Tier 1 and the global Tier 1.

## Document Splitting (Phase Index + Detail Files)

Every phase writes its results in a two-level pattern: a slim **phase index**
(`docs/<phase-folder>/<PHASE>.md`, ~5–15 KB) plus one **detail file per
subskill** (`docs/<phase-folder>/<SUBSKILL>.md`). P3 and P6 add a sub-index
level under their lead-commands (e.g. `architecture/SECURITY.md` is a sub-index
for `/p3-sec-*`).

**Subskill commands** must:
1. Write their result to `docs/<phase-folder>/<DETAIL>.md` (overwrite, not append) with YAML frontmatter (`phase`, `subskill`, `status`, `last_updated`).
2. Update `docs/<phase-folder>/<PHASE>.md` (index): refresh the detail-file row, lift any one-line key decision or risk into the index.

**Gate commands** read the phase index first and pull detail files only when content checks demand it.

Full spec, schemas, and rationale: `~/.claude/docs/PROJECT_PHASES.md` ("Document Splitting Convention").

**Frontmatter schema and lint:** phase-detail and sub-index files follow the schema in `~/.claude/templates/PHASE_DOC_SCHEMA.md` (`phase`, `subskill`, `status ∈ {skeleton, draft, active, frozen, archived}`, `last_updated DD.MM.YYYY`; optional `related:`, `parent_index:`). Validation: `bash ~/.claude/scripts/phase-docs-lint.sh [<project-dir>] [--scope <glob>]`. Doc-volume watcher: `bash ~/.claude/scripts/doc-volume-check.sh [<docs-root>]` — lists files ≥25/40/50 KB with a splitting suggestion.

## Next-Steps Recommendations

After a command completes, recommend 1–3 sensible next steps.
The allowed transitions are in `~/.claude/docs/NEXT_STEPS_REFERENCE.md`.
Check the phase status in `docs/HANDOVER.md` before giving recommendations.
Never recommend commands from a later phase if the current phase's gate has not passed.

## Track Decision (Lean vs. Full)

Every new project starts with `/track-decision` (entry-point skill). The skill runs a knockout check (K1–K5: GDPR PII, special data categories, imminent launch, regulatory scope, external sign-off) + indicator score (I1–I5) and decides:

- **Lean-Track** (4 skills, *transient — sunset at CCPR v1.0*) — fast-test shortcut for CCPR dogfooding and a bridge into Full. `/lean-frame → build → /lean-learn → /lean-promote`. No gates, no BACKLOG/SPRINT, slim `docs/CLAUDE-lean.md` instead of the full CLAUDE. Constitution-Light in FRAME.md is sufficient. **Not** the default for mandant/team projects — those start on Full.
- **Full-Track** (P0–P8) — `/project-init → /constitution → /p0-problem → …`. Full phase pipeline with gates, constitution mandatory.

**No downgrade Full → Lean.** Reassessment via `/track-decision` is allowed at any time.

**Constitution mandatory in Full-Track:** `/project-init` calls `/constitution`, creates `docs/CONSTITUTION.md` with Inviolable/Default/Aspirational. All gates read the Inviolable section (via the `gate-preflight.py` extension) as a mandatory input. A violation = "Inviolable breach" in the gate verdict.

**CCPR is bound by its own constitution.** The worker repo ratified `docs/CONSTITUTION.md` (v1.1, 05.06.2026) to apply the same Inviolable discipline to itself. Changes to skills, agents, templates and shipped scripts must respect CCPR's own Inviolables — see the file for the binding rules.

**Domain bootstraps:** `~/.claude/templates/constitution-bootstraps/` provides starter seeds for common project types (`b2b-tool`, `b2c-marketplace`, `mobile-b2c`, `on-device-privacy`, `saas-b2c`). `/constitution` selects one when bootstrapping greenfield projects.

**P6 sub-index skeletons:** `~/.claude/templates/QA_SKELETON/` ships pre-filled sub-index files (`QA.md`, `A11Y.md`, `AUDIT.md`, `AUTHZ.md`, `FUNCTIONAL.md`, `PENTEST.md`) that P6 sub-skills extend rather than re-create from scratch.

## Cross-Check (optional pre-flight check)

`/cross-check` runs optionally before gates — checks inconsistencies across phases (features ↔ auth, NFR ↔ tests, threats ↔ mitigations, constitution inviolables ↔ ADRs). 7 rules initially. Output: `docs/.cross-check-report.md`.

## Phase Assignments (P0-P8)

### P0 – Discovery: "Is it worth it?"
Lead: **konzeptor** · Support: business-analyst, security-master

### P1 – Conception: "What are we building?"
Lead: **konzeptor** · Support: ux-designer, business-analyst, security-master, project-planner

### P2 – Validation: "Are the assumptions correct?"
Lead: **konzeptor** · Support: business-analyst, system-architekt, security-master

### P3 – Architecture & Design: "How do we build it?"
Lead: **system-architekt** · Support: ux-designer, security-master, devops, qa-tester, business-analyst, konzeptor

### P4 – Planning: "When do we build what?"
Lead: **project-planner** · Support: devops, tech-writer, senior-developer

### P5 – Implementation: "Now we build!" (Sprint Loop)
Lead: **senior-developer** · Support: code-reviewer, ux-designer, qa-tester, debugger, tech-writer

### P6 – Quality Assurance: "Is it stable?"
Lead: **qa-tester** · Support: security-master, pentester, ux-designer, code-reviewer, debugger, senior-developer

### P7 – Launch & Deployment: "Ship it!"
Lead: **devops** · Support: qa-tester, security-master, tech-writer, business-analyst, project-planner

### P8 – Operations & Evolution: "Is it running?"
Lead: **devops** + **business-analyst** · Support: debugger, konzeptor, project-planner, security-master, pentester

---

## Local Scripts

Before a session starts, you can run local scripts that provide structured context.
The scripts are located in `~/.claude/scripts/`.

### Pre-Session Bootstrap
If `docs/.session-context.md` exists and is less than 10 minutes old,
read it at session start as compact context.

### Gate Pre-Flight
If `docs/.gate-preflight-pX.md` exists and is less than 10 minutes old,
use it as the starting point for gate checks. Mechanical checks are done –
focus on content evaluation.

### Gate Checks: Freshness Guarantee
Every gate check evaluates the current state **freshly and independently** of previous runs.

- **No reuse** of previous gate results from the same session – even if they are visible in the conversation context
- **Clean up preflight**: After completing a gate check, delete the used preflight file (`rm -f docs/.gate-preflight-pX.md`) so it is not reused on the next call
- A repeated gate call requires a new preflight or reads the source documents directly

### Test Runner
If the user provides `run-tests.sh` results (JSON),
interpret these instead of running tests yourself via Bash.

### Quality Scans
If `docs/.quality-scan-report.json` exists,
use the report as the basis for /p6-audit and /p6-pentest commands.

### Local LLM (Ollama) – Token Delegation
Optional: Ollama can be set up locally to delegate token-saving routine tasks.
Use the wrapper scripts in `~/.claude/scripts/local-llm/` for tasks that do not
require Claude reasoning – saves tokens in long sessions.

**Use-case-specific model routing** (configured in the wrapper scripts, benchmark-driven):
- `summarize.sh` → a concise summarizer model (set via `OLLAMA_MODEL` inside the script)
- `commit-msg.sh`, `handover-draft.sh` → a format-disciplined model (default in `ollama-query.sh`)

Concrete model choices belong in the local scripts because they depend on the user's hardware.

**When to delegate:**
- Summaries of long files: `~/.claude/scripts/local-llm/summarize.sh <file>`
- HANDOVER drafts: `~/.claude/scripts/local-llm/handover-draft.sh [projectdir]` → as a starting point, then refine
- Commit messages: `~/.claude/scripts/local-llm/commit-msg.sh` → fetch a suggestion, adjust if needed

**When NOT to delegate:**
- Architecture decisions, code reviews, security analyses – anything that requires judgment
- When Ollama is not running (script returns an error) – then do it yourself

**Prerequisite:** Ollama server must be running (`curl -s http://localhost:11434/api/tags`).
If not reachable, handle the task yourself instead of asking the user to start Ollama.

**Switch-cost note:** Using two specialised models triggers a one-time cold-load (a few seconds)
when switching. Models stay warm in RAM for ~5 min after use. Fine for sparse use;
for tight back-to-back calls of different models, prefer a single universal model.

## Task System (TaskCreate/TaskUpdate)

The native Claude Code task system is **not** used as a second backlog.
The primary workflow runs via BACKLOG.md + SPRINT.md + HANDOVER.md.

**When to use tasks:**
- Parallel agent coordination (3+ agents on the same epic)
- Complex multi-step operations within a session

**When NOT to use:**
- Tracking sprint progress (use: SPRINT.md)
- Managing backlog items (use: BACKLOG.md)
- Saving session context (use: HANDOVER.md)

**Before TaskCreate check:** Is there already a task with the same goal? (`TaskList` first)
