# CCPR — Claude Code Project Runner

CCPR is a tool for shaping software projects with Claude Code: 15 agents (13 domain agents + `project-guide` + `wingman`),
115 slash commands, a phase system (P0-P8) with quality gates plus an optional Lean-Track for prototypes/PoCs, and automation scripts.

> **Status: public beta (`v0.1.0-beta`).** CCPR is usable end-to-end but pre-1.0 — expect rough edges (see [`BETA.md`](BETA.md) for known limitations). Feedback is exactly what's wanted right now: [open an issue](https://github.com/jonase47/ccpr/issues), the bar is low.

## Two Tracks: Lean & Full

Projects start with `/track-decision` which chooses based on Knockouts (DSGVO, BFSG, regulatory, stakeholders, launch-imminent) and Indicators (lifespan, team-growth, complexity):

- **Lean-Track** (4 skills, no gates, *transient — sunset at CCPR v1.0*) — fast-test shortcut for CCPR itself and a bridge into Full. `/track-decision → /lean-frame → build → /lean-learn → /lean-promote` promotes to Full-Track when ready. Mandant/team projects default to Full from the start; Lean is for internal experimentation and bridging only.
- **Full-Track** (P0–P8, full pipeline) — production-grade software with regulatory, A11y, security, and operational readiness. `/project-init` calls `/constitution` to ratify the project's non-negotiable rules; gates verify against the Constitution Inviolables.

Spec: [`Manual/LEAN_TRACK.md`](Manual/LEAN_TRACK.md) in this repo.

## See it in action

<!-- A recorded demo lives here. To (re)create it: `asciinema rec demo.cast`,
     run the flow below, upload to asciinema.org and embed the player link —
     or convert to a GIF and reference it as ![demo](docs/demo.gif). -->
> _Demo recording coming soon._

A first run, end to end — in a fresh project directory:

```text
> /track-decision   # picks Lean vs Full from knockout + indicator questions
> /project-init     # scaffolds docs/, HANDOVER.md, a project-specific CLAUDE.md
> /p0-problem       # P0 Discovery: problem & target audience      (lead: konzeptor)
> /gate-p0          # quality gate — must pass before P1
> /p1-features      # P1 Conception: feature set & MVP boundary
> …                 # P2–P8, each phase held behind its own gate
> /guide            # anytime: status snapshot + the recommended next step
```

Each phase is led by a specialised agent, writes its result under `docs/`, and is
held by a **gate** that checks the work (and the project Constitution) before the
next phase may start. Try it without committing to anything: `./install.sh --dry-run`,
then run `/track-decision` and `/guide` in any project.

## Installation

> **Versioning.** CCPR follows [SemVer](https://semver.org/). Releases are tagged `vMAJOR.MINOR.PATCH`. Read [`CHANGELOG.md`](CHANGELOG.md) before upgrading — pre-1.0, MAJOR-on-MINOR bumps (`0.x.0`) can carry surface changes. Versioning rules: [`docs/adr/ADR-0001-versioning-and-distribution.md`](docs/adr/ADR-0001-versioning-and-distribution.md).

> **Windows.** `install.sh` is a bash script, so run it from a **bash environment**: **WSL** (recommended — the bash/Python helper scripts then run exactly as on Linux) or **Git Bash**. Native PowerShell/cmd cannot run the installer. If you have neither, the *Manual install on Windows (PowerShell)* fallback below places the files, but note the shipped `*.sh` helper scripts still need WSL or Git Bash to run. In WSL, run Claude Code inside WSL too, so it and `~/.claude` share the same home.

### 1. Pick a version

```bash
git clone git@github.com:jonase47/ccpr.git
cd ccpr
git checkout v0.1.0-beta   # latest tag; run `git tag -l` to see all available tags
```

### 2. Run the installer

```bash
./install.sh            # backs up ~/.claude, shows what gets overwritten, asks to confirm
./install.sh --dry-run  # preview only — change nothing
```

The installer takes a timestamped backup of your existing `~/.claude/` before
writing, lists every artifact that would be overwritten, and requires an
explicit `y` to proceed. It copies only framework artifacts (agents, commands,
docs, hooks, instincts, scripts, templates, `instincts.md`, `settings.json`,
`CLAUDE.md`) — repo-meta files like this README and your own `memory/` /
`scripts/local-llm/` are left untouched.

<details>
<summary>Manual install (fallback)</summary>

```bash
cp -r ~/.claude ~/.claude.backup-$(date +%Y%m%d-%H%M%S)   # back up first
cp -r ccpr/{agents,commands,docs,hooks,instincts,instincts-archive,scripts,templates} ~/.claude/
cp ccpr/instincts.md ccpr/settings.json ccpr/CLAUDE.md ~/.claude/
```
</details>

<details>
<summary>Manual install on Windows (PowerShell)</summary>

For when you have neither WSL nor Git Bash. This only places the files; the
shipped `*.sh` helper scripts still need a bash environment to run.

```powershell
# back up first
Copy-Item "$HOME\.claude" "$HOME\.claude.backup-$(Get-Date -Format yyyyMMdd-HHmmss)" -Recurse -ErrorAction SilentlyContinue
# copy framework artifacts
Copy-Item ccpr\agents,ccpr\commands,ccpr\docs,ccpr\hooks,ccpr\instincts,ccpr\instincts-archive,ccpr\scripts,ccpr\templates "$HOME\.claude\" -Recurse -Force
Copy-Item ccpr\instincts.md,ccpr\settings.json,ccpr\CLAUDE.md "$HOME\.claude\" -Force
```
</details>

> Pre-1.0 the install is a shallow file copy: shipped artefacts replace same-named files under `~/.claude/`. `install.sh` makes that copy *safe* (backup + confirmation) but does **not** yet merge in-place customisations of shipped files — if you edited a shipped file, re-apply your change from the backup. A customisation-preserving installer is on the v1.0 roadmap (see Constitution Aspirational).

### 3. Customize CLAUDE.md

Open `~/.claude/CLAUDE.md` and adjust the sections to your preferences:

- **Language & Communication** – Change communication language if desired
- **Personal Context** – Your role, experience, preferences
- **Infrastructure** – Your hosting setup (Hetzner/other), DSGVO (GDPR) requirements
- **Code Standards** – TDD, clean code etc. as needed

### 4. Check Permissions

In `~/.claude/settings.json`, Bash permissions are preconfigured.
Check if the allowed commands match your setup:

```json
"permissions": {
  "allow": [
    "Bash(curl:*)",
    "Bash(npm run:*)",
    "Bash(node:*)",
    "Bash(pkill:*)",
    "Bash(~/.claude/scripts/bootstrap.sh:*)",
    "Bash(bash:*)"
  ]
}
```

### 5. Test Hooks

```bash
python3 ~/.claude/hooks/agent-monitor.py
```

Should run without errors. The hook monitors agent usage per session.

### 6. Make Scripts Executable

```bash
chmod +x ~/.claude/scripts/*.sh
```

### 7. First Test

Start Claude Code in a new project directory and run:

```
/project-init
```

This initializes the project structure with HANDOVER.md, phase tracking, etc.

---

## Updating

There is no separate updater — the installer is the update path. To move to a
newer version:

```bash
cd ccpr
git fetch --tags && git checkout v0.1.0-beta   # or the version you want
./install.sh --update                           # framework only — keeps your local files
```

`--update` refreshes the pure framework (agents, commands, docs, hooks, scripts,
templates) and **deliberately leaves your local files as they are**:

- `CLAUDE.md` and `settings.json` — your personalisation and permissions.
- `instincts.md` + `instincts/` + `instincts-archive/` — these mature on your
  machine through your own `/postmortem` runs, so an update keeps them. Add
  `--with-instincts` if you *do* want the shipped starter set back.

A timestamped backup of `~/.claude/` is still taken before anything is written.
Your `memory/` and `scripts/local-llm/` are out of scope and never touched.

> Pre-1.0 there is no migration of local *state* — `--update` is a safe file
> refresh, not a merge. If you edited a *shipped framework* file in place (e.g. a
> command), `--update` overwrites it; re-apply your change from the backup. A full
> customisation-preserving installer is the v1.0 goal (Constitution, Aspirational).

---

## Structure

```
~/.claude/
+-- CLAUDE.md              # Global instructions (customize!)
+-- instincts.md           # Slim autoloaded index (starts as CCPR-shipped starter snapshot, then matures in your sessions)
+-- instincts/             # Topic files: agents.md, files.md, workflow.md, shell-git.md, external.md
+-- instincts-archive/     # HISTORY.md — rolling postmortem stream (not autoloaded)
+-- settings.json          # Permissions & hooks
+-- agents/                # 13 domain agents + project-guide + wingman = 15
+-- commands/              # 115 slash commands (P0-P8 + Lean-Track + cross-cutting)
+-- scripts/               # Automation scripts (save tokens)
|   +-- lib/               # Shared libraries (Python + Bash helpers)
|   +-- memory-lint.sh     # Validate docs/memory/** against schema
|   +-- phase-docs-lint.sh # Validate docs/<phase>/** against schema
|   +-- doc-volume-check.sh # Watch for files ≥25/40/50 KB (G-017 protection)
+-- docs/                  # Runtime reference docs (PROJECT_PHASES, NEXT_STEPS, CONSTITUTION, adr/, memory/)
+-- templates/             # HANDOVER, project, lean & schema templates
|   +-- MEMORY_SCHEMA.md            # Frontmatter for docs/memory/**
|   +-- PHASE_DOC_SCHEMA.md         # Frontmatter for docs/<phase>/**
|   +-- STARTER_INSTINCTS.md        # compact 13-instinct sampler (split layout ships the full 45)
|   +-- QA_SKELETON/                # Pre-P6 sub-index skeletons (qa/a11y/audit/functional/pentest/authz)
|   +-- constitution-bootstraps/    # Domain seeds for /constitution (b2b-tool, b2c-marketplace, mobile-b2c, on-device-privacy, saas-b2c)
+-- hooks/                 # Agent monitor hook (monitoring + token tracking)
```

The human-facing **`Manual/`** folder lives in this repo and is **not** installed —
it holds the "how to drive CCPR" guides (see [Documentation](#documentation)).

---

## Phase System

Each project goes through up to 9 phases. Between phases are quality gates
that must be passed before proceeding.

| Phase | Focus | Lead Agent |
|---|---|---|
| P0 | Discovery – "Is it worth it?" | konzeptor |
| P1 | Conception – "What are we building?" | konzeptor |
| P2 | Validation – "Are the assumptions correct?" | konzeptor |
| P3 | Architecture & Design – "How do we build it?" | system-architekt |
| P4 | Planning – "When do we build what?" | project-planner |
| P5 | Implementation – "Let's build!" | senior-developer |
| P6 | Quality Assurance – "Is it stable?" | qa-tester |
| P7 | Launch & Deployment – "Ship it!" | devops |
| P8 | Operations & Evolution – "Is it running?" | devops + business-analyst |

- Check gates: `/gate-p0` through `/gate-p7`
- After Gate-P7: `/release-baseline` for the baseline cut (archives HANDOVER, splits docs into frozen/active)
- In P8: `/p8-iteration` starts the next feature cycle

---

## Agent Team

15 agents: 13 domain subagents + `project-guide` + `wingman`. Claude automatically selects
the appropriate agents per command (max. 3-4 simultaneously).
`project-guide` is the entry door for status snapshots and skill/agent disambiguation;
`wingman` consolidates results after parallel agent runs.

| Agent | Focus |
|---|---|
| **project-guide** | Entry door: status snapshot, skill/agent recommendation, disambiguation, hand-off with context bundle (via `/guide`) |
| **konzeptor** | Product idea, target audience, features, MVP, value proposition |
| **business-analyst** | Business model, financial planning, pricing, market analysis |
| **system-architekt** | Tech stack, data model, APIs, ADRs |
| **project-planner** | Milestones, sprints, backlog, prioritization |
| **ux-designer** | UI concepts, user flows, accessibility, dark mode |
| **senior-developer** | Implementation (TDD), clean code, feature development |
| **code-reviewer** | Code review, quality, best practices (read-only access) |
| **qa-tester** | Test strategy, test cases, exploratory tests |
| **debugger** | Error analysis, root cause, troubleshooting |
| **devops** | CI/CD, deployment, hosting, monitoring |
| **security-master** | Security strategy, DSGVO (GDPR), threat modeling |
| **pentester** | Offensive security, finding vulnerabilities |
| **tech-writer** | Documentation, README, API docs, changelogs |
| **wingman** | Result consolidation of parallel agent outputs |

---

## Under the hood

CCPR ships supporting machinery that mostly runs for you — the **WHAT** is below,
the **HOW** (full tables, schemas, examples) lives in the Manual.

- **Scripts** (`~/.claude/scripts/`) run mechanical work locally — context
  gathering, gate pre-flight, test runs, quality scans, doc-hygiene lint — so
  Claude spends tokens on judgement, not bookkeeping. Most are invoked by the
  matching skill. → [`Manual/WORKFLOW_CHEATSHEET.md`](Manual/WORKFLOW_CHEATSHEET.md)
- **Hooks & monitoring** — one hook (`hooks/agent-monitor.py`, wired via
  `settings.json`) reacts to every event: activity/error logging, loop and
  stagnation detection, a compact reminder, and approximate per-session token
  tracking. Logs land under `~/.claude/logs/`; read them with `/logs-summary`.
  → [`Manual/system/monitoring-scripts.md`](Manual/system/monitoring-scripts.md)
- **Handover** — `docs/HANDOVER.md` carries work state across sessions (updated at
  the end of each command). After `/release-baseline`, docs split into **Frozen**
  and **Active** to save tokens in later iterations.
  → [`Manual/SYSTEM_OVERVIEW.md`](Manual/SYSTEM_OVERVIEW.md)
- **Project memory** — knowledge is versioned in `docs/memory/` in two tiers
  (cross-cutting `{type}_{slug}.md` + persona silos `{agent}/`); `user`-type
  memories stay global and unpushed. Validate with `memory-lint.sh`.
  → [`Manual/system/memory-instincts.md`](Manual/system/memory-instincts.md)
- **Document splitting (P3 + P6)** — slim phase index plus one detail file per
  sub-skill keeps context windows small; lint with `phase-docs-lint.sh`, watch
  sizes with `doc-volume-check.sh`. → [`Manual/SYSTEM_OVERVIEW.md`](Manual/SYSTEM_OVERVIEW.md)
- **Continuous learning (instincts)** — short, confidence-scored rules (0.3–0.9)
  Claude follows proportional to score and matures via `/postmortem`, across four
  scopes (global/project × cross-cutting/agent). Manage with `/instinct …`.
  → [`Manual/system/memory-instincts.md`](Manual/system/memory-instincts.md)

---

## Documentation

The **`Manual/`** folder (in this repo, **not** installed into `~/.claude/`) holds
the "how to drive CCPR" guides. The runtime references Claude reads during project
work stay in `docs/`.

| Document | What it covers |
|---|---|
| [`Manual/GETTING_STARTED.md`](Manual/GETTING_STARTED.md) | Read-along onboarding (quickstart + full walkthrough) |
| [`Manual/WORKFLOW_CHEATSHEET.md`](Manual/WORKFLOW_CHEATSHEET.md) | Quick reference for daily work (commands + scripts) |
| [`Manual/SYSTEM_OVERVIEW.md`](Manual/SYSTEM_OVERVIEW.md) | Agent-system architecture + all mechanics in depth |
| [`Manual/SECTIONS_COMMANDS.md`](Manual/SECTIONS_COMMANDS.md) | All 115 commands, grouped by section |
| [`Manual/LEAN_TRACK.md`](Manual/LEAN_TRACK.md) | Lean-Track spec (transient, sunset at v1.0) |
| [`docs/PROJECT_PHASES.md`](docs/PROJECT_PHASES.md) | Detailed phase descriptions with theory *(runtime doc)* |
| [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) | CCPR's own binding Inviolables *(runtime doc)* |
| [`docs/NEXT_STEPS_REFERENCE.md`](docs/NEXT_STEPS_REFERENCE.md) | Allowed phase transitions *(runtime doc)* |

---

## Notes

- **Instincts** learn automatically from your sessions – the file fills up over time
- **HANDOVER.md** is maintained per project and preserves context between sessions
- **Token tracking** provides approximations – useful for comparison, not as exact billing
- Optional: Local LLM (Ollama) for token delegation. Stub wrappers ship under
  `scripts/local-llm/` (`ollama-query.sh`, `summarize.sh`, `commit-msg.sh`,
  `handover-draft.sh`, `install-git-hook.sh`). Install Ollama separately, then pull a
  model and either match the default (`gemma3:4b`) or override via `OLLAMA_MODEL`
  in your shell. The wrappers degrade gracefully (clear error, exit 3) when Ollama
  is not running. `local-llm/` is out of scope for the installer (see `install.sh`
  PROTECTED paths), so your local model choice stays put. See the "Local LLM
  (Ollama)" section in `CLAUDE.md`.

---

## Feedback & questions

CCPR is in **public beta** — feedback is the whole point right now, and the bar
is deliberately low. Half-formed thoughts, "this confused me", and "I expected X"
are exactly what helps.

- **Open an issue** on GitHub: [github.com/jonase47/ccpr/issues](https://github.com/jonase47/ccpr/issues). Templates are provided for **bug**, **feedback / UX**, and **question**.
- See [`BETA.md`](BETA.md) for what we're especially looking for and the current known limitations.
- Want to contribute code or docs? See [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Found a security issue? Report it privately — see [`SECURITY.md`](SECURITY.md), not a public issue.

---

## License

CCPR is released under the [MIT License](LICENSE) — use, copy, modify, and
redistribute freely (including commercially), as long as the copyright notice
and license text are retained. The Software is provided "as is", without
warranty of any kind.

Copyright (c) 2026 The CCPR Authors. The full contributor list is in
[`AUTHORS`](AUTHORS); the generic copyright line keeps the door open for
additional contributors without per-file header changes.
