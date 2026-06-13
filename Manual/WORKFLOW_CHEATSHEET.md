  # Workflow Cheat Sheet – Claude Code Agent System

> New here? Read [`GETTING_STARTED.md`](GETTING_STARTED.md) first — it explains the
> mental model and walks through a full project. This sheet is the lookup reference.

## Starting a New Project — Track Decision First

```
/track-decision               <- choose Lean (prototype/PoC/spike) or Full (P0-P8 full pipeline)
```

### Lean-Track (4 skills, no gates, no sprints)
```
/track-decision -> Lean
/lean-frame                   <- docs/FRAME.md (1 page) + docs/CLAUDE-lean.md
[build freely with senior-developer + TDD; no BACKLOG/SPRINT]
/lean-learn                   <- docs/LEARNINGS.md + decision PROMOTE/PIVOT/DROP
/lean-promote                 <- docs/PROMOTION_BRIEF.md
/project-init                 <- reads PROMOTION_BRIEF, starts Full-Track
```

### Full-Track (full P0-P8)
```
/track-decision -> Full
/project-init MyProject       <- creates structure, calls /constitution
cd MyProject
claude                        <- Claude Code starts, loads .claude/CLAUDE.md
/p0-problem ...               <- normal phase sequence
```

## Starting a New Project (legacy, without Track Decision)
```
/project-init MyProject       <- defaults to Full-Track + calls /constitution
cd MyProject
claude
```

## Phase Flow (sequential, with loops)

```
P0 Discovery --> P1 Conception <---> P2 Validation --> P3 Architecture
                                                            |
P8 Operations <-- P7 Launch <-- P6 Quality Assurance <---> P5 Implementation <-- P4 Planning
    |                                                         ^
    +------- New feature? Back to P1, P3, or P5 -------------+
```

## Git Workflow

### When to commit?
| Timing | Message Format | Example |
|---|---|---|
| After GREEN | `feat: [Story-ID] ...` | `feat: US-003 Login form validates email` |
| After REFACTOR | `refactor: ...` | `refactor: split AuthService into separate modules` |
| After bugfix | `fix: [ID] ...` | `fix: BUG-012 password reset token did not expire` |
| Sprint end (docs) | `docs: ...` | `docs: Sprint-2 review and retrospective` |
| QA completion | `chore: release vX.Y.Z` | `chore: release v1.0.0` |

### Ground Rules
- **1 TDD cycle = 1 commit** – don't batch, commit immediately
- **Build + tests green** before every commit
- **Conventional Commits** format (feat/fix/refactor/docs/chore)
- **Release tag** is set at Gate P6 (`git tag vX.Y.Z`)

## Commands Quick Reference

### P0 Discovery – "Is it worth it?"
| Command | What happens |
|---|---|
| `/p0-problem [idea]` | Define problem & target audience |
| `/p0-market [industry]` | Assess market & competition |
| `/p0-regulatory [area]` | Check regulations (DSGVO (GDPR) etc.) |
| `/gate-p0` | Go/No-Go decision |

### P1 Conception – "What are we building?"
| Command | What happens |
|---|---|
| `/p1-journeys [focus]` | Personas & user journeys |
| `/p1-features [area]` | Define features & MVP |
| `/p1-business-model [type]` | Business Model Canvas |
| `/p1-financial-plan [horizon]` | Financial planning |
| `/p1-privacy [data-type]` | DSGVO (GDPR) initial assessment |
| `/gate-p1` | Concept complete? |

### P2 Validation – "Are the assumptions correct?"
| Command | What happens |
|---|---|
| `/p2-assumptions [focus]` | Identify assumptions |
| `/p2-market-validation [assumption]` | Validate market assumptions |
| `/p2-poc [risk-area]` | Technical PoC |
| `/p2-regulatory-check [regulation]` | Legal feasibility |
| `/gate-p2` | Go/No-Go/Pivot |

### P3 Architecture – "How do we build it?"
| Command | What happens |
|---|---|
| `/p3-architecture [style]` | System architecture & ADRs |
| &ensp; `/p3-arch-components [area]` | &ensp; Component diagram & data flows |
| &ensp; `/p3-arch-techstack [criteria]` | &ensp; Tech stack decision |
| &ensp; `/p3-arch-adr [decision]` | &ensp; Write Architecture Decision Record |
| &ensp; `/p3-arch-nfa [area]` | &ensp; Non-functional requirements |
| `/p3-data-model [domain]` | Data model & APIs |
| `/p3-ux [focus]` | UX concept & wireframes |
| &ensp; `/p3-ux-navigation [area]` | &ensp; Sitemap & information architecture |
| &ensp; `/p3-ux-wireframes [screen]` | &ensp; Wireframes for key screens |
| &ensp; `/p3-ux-darkmode` | &ensp; Dark mode color strategy |
| &ensp; `/p3-ux-a11y [area]` | &ensp; Accessibility concept |
| `/p3-security [focus]` | Security architecture & threat model |
| &ensp; `/p3-sec-threats [area]` | &ensp; STRIDE threat model |
| &ensp; `/p3-sec-auth [concept]` | &ensp; Auth & authorization concept |
| &ensp; `/p3-sec-data [data-type]` | &ensp; Data security concept |
| &ensp; `/p3-sec-api [area]` | &ensp; API security requirements |
| &ensp; `/p3-sec-checklist` | &ensp; Developer security checklist |
| `/p3-infra [focus]` | Infrastructure & CI/CD |
| &ensp; `/p3-infra-hosting [provider]` | &ensp; Hosting & deployment strategy |
| &ensp; `/p3-infra-cicd [pipeline]` | &ensp; CI/CD pipeline |
| &ensp; `/p3-infra-monitoring [area]` | &ensp; Monitoring & observability |
| &ensp; `/p3-infra-teststrategy [area]` | &ensp; Define test strategy |
| `/p3-cost [scenario]` | Operating costs |
| `/gate-p3` | Architecture complete? |

### P4 Planning – "In what order?"
| Command | What happens |
|---|---|
| `/p4-backlog [epic]` | Backlog & milestones |
| `/p4-setup [project-name]` | Set up repo & CI/CD |
| `/p4-docs [focus]` | README & contributing guide |
| `/p4-sprint [goal]` | Plan sprint |
| `/gate-p4` | Ready to build? |

### P5 Implementation – "Let's build!" (Sprint Loop)
| Command | What happens |
|---|---|
| `/p5-implement [feature]` | TDD: Red -> Green -> Refactor |
| &ensp; `/p5-impl-red [feature]` | &ensp; Write failing tests (RED) |
| &ensp; `/p5-impl-green [feature]` | &ensp; Minimal code for green tests (GREEN) |
| &ensp; `/p5-impl-refactor [area]` | &ensp; Clean up code (REFACTOR) |
| `/p5-review [file/branch]` | Code review |
| &ensp; `/p5-review-code [file]` | &ensp; Check code quality |
| &ensp; `/p5-review-security [file]` | &ensp; Security checklist review |
| `/p5-acceptance [feature]` | Acceptance test |
| `/p5-bugfix [bug]` | Analyze & fix bug |
| `/p5-docs [module]` | Update documentation |
| `/gate-p5` | Sprint complete? |
| `/p5-polish` | Sprint polish: triage & resolve small carry-over TODOs |

### P6 Quality Assurance – "Is it stable?"
| Command | What happens |
|---|---|
| `/p6-functional [area]` | Integration & E2E tests |
| &ensp; `/p6-func-integration [area]` | &ensp; Run integration tests |
| &ensp; `/p6-func-e2e [path]` | &ensp; E2E tests for critical paths |
| &ensp; `/p6-func-regression [area]` | &ensp; Run regression tests |
| `/p6-exploratory [area]` | Exploratory testing |
| `/p6-a11y [page]` | Accessibility review |
| &ensp; `/p6-a11y-visual [page]` | &ensp; Contrast, colors & dark mode |
| &ensp; `/p6-a11y-keyboard [page]` | &ensp; Keyboard navigation & focus |
| &ensp; `/p6-a11y-screenreader [page]` | &ensp; ARIA, semantics & alt texts |
| `/p6-audit [focus]` | Security audit & DSGVO (GDPR) |
| &ensp; `/p6-audit-sast [area]` | &ensp; Static code analysis |
| &ensp; `/p6-audit-auth [area]` | &ensp; Auth implementation review |
| &ensp; `/p6-audit-deps` | &ensp; Dependency check |
| &ensp; `/p6-audit-config [area]` | &ensp; Infrastructure & configuration |
| &ensp; `/p6-audit-dsgvo [area]` | &ensp; DSGVO (GDPR) compliance review |
| `/p6-pentest [vector]` | Penetration test |
| &ensp; `/p6-pentest-recon [target]` | &ensp; Reconnaissance |
| &ensp; `/p6-pentest-auth [target]` | &ensp; Auth & session attacks |
| &ensp; `/p6-pentest-authz [target]` | &ensp; Authorization & access control |
| &ensp; `/p6-pentest-injection [target]` | &ensp; Injection attacks |
| &ensp; `/p6-pentest-logic [target]` | &ensp; Business logic attacks |
| `/p6-bugfix [finding]` | Fix findings |
| `/gate-p6` | QA + security approval |
| &ensp; `/gate-p6-qa` | &ensp; QA approval assessment |
| &ensp; `/gate-p6-security` | &ensp; Security approval assessment |

### P7 Launch – "Ship it!"
| Command | What happens |
|---|---|
| `/p7-prepare [environment]` | Prepare deployment |
| `/p7-deploy [environment]` | Go-live + smoke tests |
| `/p7-monitoring [focus]` | Monitoring & rollback |
| `/p7-release-docs [version]` | Release notes & manual |
| `/p7-gtm [channel]` | Start go-to-market |
| `/gate-p7` | Everything live? |
| &ensp; `/gate-p7-tech` | &ensp; Technical go-live review |
| &ensp; `/gate-p7-business` | &ensp; Business readiness review |

### P8 Operations – "Is it running?" (Evolution Loop)
| Command | What happens |
|---|---|
| `/p8-ops [incident]` | Monitoring & incidents |
| `/p8-business [KPI]` | KPIs & business review |
| `/p8-security [focus]` | Security updates & scans |
| `/p8-iteration [topic]` | Backlog & next iteration |

### Continuous Learning
| Command | What happens |
|---|---|
| `/postmortem [session]` | Analyze session, propose instincts |
| `/instinct list` | Show all instincts (global/agent/project) |
| `/instinct add [rule]` | Create new instinct |
| `/instinct confirm [ID]` | Increase confidence (+0.1) |
| `/instinct reject [ID]` | Decrease confidence (-0.2) |
| `/instinct promote [ID]` | Promote agent instinct to global |
| `/instinct cleanup` | Remove outdated instincts |

### Cross-Cutting
| Command | What happens |
|---|---|
| `/project-init [name]` | Create new project |
| `/specialize` | Adapt technical agents to the project's tech stack (project-local copies) |
| `/logs-summary [focus]` | Analyze agent logs |
| `/konzept [idea]` | Create high-level concept |
| `/konzept-update` | Revise existing concept |
| `/decision [topic]` | Develop decision basis |
| `/epic [topic]` | Create epic |
| `/user-stories [epic]` | Develop user stories |
| `/roadmap` | Create initial roadmap |
| `/roadmap-update` | Update roadmap |
| `/release-baseline [version]` | Baseline cut after release |

## Local Scripts (~/.claude/scripts/)

Save tokens: run mechanical tasks locally, Claude focuses on content.

### Before Session Start (in terminal, before `claude`)

| Script | Usage | What happens |
|---|---|---|
| **bootstrap.sh** | `~/.claude/scripts/bootstrap.sh [projectdir]` | Collects git status, HANDOVER, artifacts, instincts into `docs/.session-context.md` |
| **gate-preflight.py** | `~/.claude/scripts/gate-preflight.py p3 [projectdir]` | Checks gate artifacts, creates checklist in `docs/.gate-preflight-p3.md` |
| **command-check.py** | `~/.claude/scripts/command-check.py p5-implement [projectdir]` | Checks if prerequisites are met (ready/blocked) |

### During Work (in terminal alongside Claude)

| Script | Usage | What happens |
|---|---|---|
| **run-tests.sh** | `~/.claude/scripts/run-tests.sh [testpath] [projectdir]` | Run tests, JSON output (detects pytest/jest/vitest/cargo/go) |
| **quality-scan.sh** | `~/.claude/scripts/quality-scan.sh [scope] [projectdir]` | Security/quality scans -> `docs/.quality-scan-report.json`. Scope: all, deps, sast, config, dsgvo |

### One-Time / As Needed

| Script | Usage | What happens |
|---|---|---|
| **project-init.sh** | `~/.claude/scripts/project-init.sh my-project [template]` | Project scaffolding with git. Templates: default, webapp, api, library |
| **logs-summary.py** | `~/.claude/scripts/logs-summary.py [focus] [period]` | Analyze session logs. Focus: errors, performance, agents, loops, all. Period: today, week, all |
| **setup-ollama.sh** | `~/.claude/scripts/setup-ollama.sh` | Install Ollama + gemma3:4b, create wrapper scripts for local LLM |
| **instinct-check.sh** | `~/.claude/scripts/instinct-check.sh` | Check instinct decay (age, count, warnings). No LLM needed |
| **log-cleanup.sh** | `~/.claude/scripts/log-cleanup.sh [--days N] [--dry-run]` | Trim old session logs + aggregated logs (default: 7 days) |
| **install-git-hook.sh** | `~/.claude/scripts/local-llm/install-git-hook.sh <projectdir>` | Install prepare-commit-msg hook (LLM suggestion, editable in editor) |

### Local LLM (Ollama)

After `setup-ollama.sh`, the following wrapper scripts are available:

| Script | Usage | What happens |
|---|---|---|
| **commit-msg.sh** | `~/.claude/scripts/local-llm/commit-msg.sh` | Generate commit message from staged diff |
| **summarize.sh** | `~/.claude/scripts/local-llm/summarize.sh <file>` | Summarize file in 3-5 sentences |
| **handover-draft.sh** | `~/.claude/scripts/local-llm/handover-draft.sh [projectdir]` | Create HANDOVER.md draft from git status |

### Shell Aliases (optional in ~/.zshrc)
```bash
alias cb='~/.claude/scripts/bootstrap.sh && claude'    # Bootstrap + start Claude
alias cgate='~/.claude/scripts/gate-preflight.py'      # Gate check
alias ctest='~/.claude/scripts/run-tests.sh'            # Tests with JSON output
alias ccheck='~/.claude/scripts/command-check.py'       # Command prerequisites
alias cscan='~/.claude/scripts/quality-scan.sh'          # Quality scan
alias clogs='~/.claude/scripts/logs-summary.py'          # Log analysis
alias cmsg='~/.claude/scripts/local-llm/commit-msg.sh'    # Commit message via LLM
alias cinstinct='~/.claude/scripts/instinct-check.sh'     # Check instinct decay
```

### How Claude Uses the Scripts

Claude automatically detects generated files and uses them as context:
- `docs/.session-context.md` (< 10 min old) -> reads instead of HANDOVER + git + instincts individually
- `docs/.gate-preflight-pX.md` (< 10 min old) -> uses as gate basis, focuses on content
- `docs/.quality-scan-report.json` -> uses as basis for /p6-audit and /p6-pentest

Claude delegates token-intensive routine tasks to the local LLM (when Ollama is running):
- Long file summaries -> call `summarize.sh` via Bash
- HANDOVER drafts -> `handover-draft.sh` as starting point, then refine
- Commit messages -> get `commit-msg.sh` suggestion, adjust if needed
- Architecture decisions, reviews, security -> always handle directly (requires judgment)

All generated files are in `.gitignore` and are not committed.

---

## Typical Daily Workflow

```
1.  cd my-project
2.  ~/.claude/scripts/bootstrap.sh    <- Collect context (optional, saves tokens)
3.  claude                            <- Claude reads .session-context.md or HANDOVER.md
4.  /p5-implement login-feature       <- Build feature
5.  /p5-review src/auth/              <- Review (wingman consolidates)
6.  /p5-acceptance login-feature      <- Test
7.  /gate-p5                          <- Check sprint gate
8.  /logs-summary                     <- What happened?
    -> At session end: HANDOVER.md is updated
```

## Rules
- **Max. 3-4 agents per command** – more leads to chaos
- **Always sequential within a phase** – a before b before c
- **Gate must be passed** before next phase starts
- **When unclear: agent asks** – never make assumptions
- **Sprint number is in SPRINT.md** – not in the command

## Token Optimization

### Wingman Consolidation
- Agents write results to files, return only a brief summary (max. 5 sentences)
- **wingman** agent consolidates parallel results into a summary (max. 15 sentences)
- Saves 1000+ tokens per parallel agent run

### Handover (HANDOVER.md)
- `docs/HANDOVER.md` preserves work state across session changes
- New session -> read HANDOVER.md -> seamlessly continue work
- Commands automatically update HANDOVER.md at the end

### Strategic Compact
- agent-monitor reminds at 100 tool calls to use `/compact`
- At 150 tool calls: urgent HANDOVER warning
- Stagnation warning after 15 min without Write/Edit

### Continuous Learning (Instincts)
- Instincts are confidence-based rules (0.3-0.9) from session experience
- Global: `~/.claude/instincts.md` (slim index) + `~/.claude/instincts/{theme}.md` + `~/.claude/instincts-archive/HISTORY.md` (not autoloaded) | Agent: `docs/memory/{agent}/instincts.md` | Project: `docs/instincts.md`
- `/postmortem` after sessions: analyzes error patterns, proposes instincts
- `/instinct list/add/confirm/reject/promote/cleanup` for management
- Agents automatically read their instincts and follow them proportional to the score

## Monitoring
- Hooks automatically log every action
- Loop detection blocks after 5x identical call
- Compact reminder at 100 tool calls
- Token budget warning at 150 tool calls
- Stagnation detection after 15 min without productive action
- `/logs-summary errors` for troubleshooting
