# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/) — see [docs/adr/ADR-0001-versioning-and-distribution.md](docs/adr/ADR-0001-versioning-and-distribution.md) for the version-scoping rules in this meta-repo context.

> Development before this public GitHub release happened in a private repository. This changelog starts fresh at the first public version; the detailed pre-public history is retained privately.

## [Unreleased]

## [v0.1.0-beta] – 13.06.2026

Initial public release on GitHub. CCPR (Claude Code Project Runner) is a phase-based project framework for Claude Code: specialised agents, slash commands, quality gates, templates, and local automation scripts that drive a software (or business) venture from discovery to operations.

### Added
- **Agent team (15):** 13 domain agents (konzeptor, business-analyst, system-architekt, project-planner, ux-designer, senior-developer, code-reviewer, qa-tester, debugger, devops, security-master, pentester, tech-writer) plus `project-guide` (entry point / status snapshots / disambiguation) and `wingman` (result consolidation).
- **115 slash commands** covering the full phase pipeline P0–P8, quality gates, the Lean-Track, learning commands (`/postmortem`, `/instinct`), and utilities (`/guide`, `/project-init`, `/cleanup`, `/release-baseline`, `/specialize`, …).
- **Phase system P0–P8 with quality gates** — a hybrid linear-plus-iterative model; each gate is a checklist that must pass before the next phase. Includes the holistic end-of-sprint review (`/p5-review-sprint`) and per-story reviews.
- **Two tracks:** Full-Track (P0–P8, gates, mandatory Constitution) and a transient **Lean-Track** (4 skills, no gates) for fast experimentation and as a bridge into Full. `/track-decision` chooses based on knockouts + indicators.
- **Constitution + Cross-Check** — `/constitution` ratifies a project's Inviolable/Default/Aspirational rules (5 domain bootstraps); gates read the Inviolables as binding input. `/cross-check` is an optional pre-gate consistency check.
- **Memory & instinct system** — two-tier × two-scope memory (global/project × cross-cutting/persona) plus confidence-scored instincts that mature via `/postmortem`. Lint scripts validate schema, naming, cross-refs and size.
- **Documentation split** — runtime references in `docs/` (read by Claude during work: `PROJECT_PHASES.md`, `NEXT_STEPS_REFERENCE.md`, `CONSTITUTION.md`) vs. the human-facing **`Manual/`** (repo-only, not installed) for the "how to drive CCPR" guides.
- **Automation scripts & monitoring hook** — `scripts/` (context bootstrap, gate pre-flight, test runner, quality scans, doc-hygiene lints) and a single `hooks/agent-monitor.py` (activity/error logging, loop & stagnation detection, approximate token tracking).
- **Safe installer** — `install.sh` with timestamped backup, overwrite preview, `--update` (framework-only, preserves personal files + matured instincts) and `--dry-run`; user-owned sub-paths preserved across wholesale replace. Windows guidance (WSL / Git Bash / PowerShell fallback) in the README.
- **Open-source scaffolding** — `LICENSE` (MIT), `AUTHORS`, `CONTRIBUTING.md`, `SECURITY.md`, `BETA.md` (public-beta charter), and GitHub issue templates under `.github/ISSUE_TEMPLATE/` (bug / feedback / question).

[Unreleased]: https://github.com/jonase47/ccpr/compare/v0.1.0-beta...HEAD
[v0.1.0-beta]: https://github.com/jonase47/ccpr/releases/tag/v0.1.0-beta
