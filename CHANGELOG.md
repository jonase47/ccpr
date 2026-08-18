# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/) — see [docs/adr/ADR-0001-versioning-and-distribution.md](docs/adr/ADR-0001-versioning-and-distribution.md) for the version-scoping rules in this meta-repo context.

> Development before this public GitHub release happened in a private repository. This changelog starts fresh at the first public version; the detailed pre-public history is retained privately.

## [Unreleased]

### Fixed
- **`memory-lint.sh` gained exit code 3 for a configuration error.** The severity knob for the new
  check was expanded in command position, so a typo aborted the run with `command not found`, exit
  127 and no report at all — a caller testing for "non-zero" would have read a dead script as a
  findings result. The value is now validated up front and findings are dispatched by `case`. The
  contract at the top of the script, in `templates/MEMORY_SCHEMA.md` and in `/cleanup` now all name
  the new code.
- **`instinct-check.sh` now actually counts instincts.** It reported `Active instincts: 0` in every
  project while hundreds existed. Three independent causes: (1) it counted `### ` headings in
  `~/.claude/instincts.md`, but under the split layout the index holds only bullets — the entries live
  in `instincts/{theme}.md`; (2) heading level is not uniform across the ecosystem (global topic files
  use `### G-100`, project Tier-2 persona silos use `## BA-P-001`), so entries were invisible depending
  on the layer — counting is now anchored on the instinct ID and accepts H2 and H3; (3) the script
  aborted with `unbound variable` on bash 3.2 (the macOS default) whenever a glob matched nothing,
  because `"${arr[@]}"` on an empty array trips `set -u`.
- **`instinct-check.sh` reported a stale age.** File age came from the index mtime alone, so editing a
  theme file without touching the index left the age unchanged. It now uses the newest mtime across
  the index and all theme files.

### Added
- **`memory-lint.sh` now validates the Tier-1 index's own links (check `n`).** The lint checked
  cross-references in one direction only: it found memory files the index had forgotten (check `g`)
  and `related:` entries pointing at nothing (check `f`), but a link *inside* `docs/memory/MEMORY.md`
  whose target had been deleted passed silently — reported from the field, where a manual pass found
  two such links in a live index. Reproduced before the fix: an index with two dead links produced
  zero findings. The check skips images, HTML-commented entries, code-fence-free inline links, anchors
  and external URLs, resolves root-absolute targets against the project root, and reports every dead
  link on a line rather than the first. It ships at **warning** severity: the link extraction does not
  yet see fenced/inline code examples or reference-style links, and erroring on an incomplete
  extraction would claim a completeness that is not evidenced. Promotion to error is tracked
  separately and is the SemVer-relevant step (ADR-0001).
- **First test coverage for a shell script in this repo.** `scripts/tests/` was Python-only and
  covered the work-item CLI; `scripts/tests/test_memory_lint.py` invokes `memory-lint.sh` as a
  subprocess with `HOME` redirected to a temp directory, so the checks against `~/.claude/**` cannot
  leak the developer's machine state into the result.
- **State verification design (proposed) — `docs/adr/ADR-0009-anchored-state-verification.md`.**
  `/cross-check` compares Markdown to Markdown in all seven rules — R6 even names "Implementation" in
  its title and reads no code — so a fully self-consistent documentation set can be stale against the
  implementation while every gate passes. ADR-0009 introduces an **anchor**: an optional, flat
  `anchor_commit` in phase-document frontmatter, one per scope by default with a lint-validated
  `covers:` opt-in for document-exact resolution. The check is two-stage — a mechanical delta that is
  never itself a verdict, then a scoped evaluation of whether the delta invalidates a claim — with
  severity keyed to the document's `status` (`living` info, `active` warning + work item, `frozen`
  error). Clearing drift is a dedicated `anchor ack` verb that renders the delta before it clears it
  and distinguishes a human assertion from an evidenced update; acknowledgement statistics ship as part
  of every check run so the mechanism turning into ceremony stays visible. Escalation goes through the
  existing work-item contract (ADR-0002) with `local` as default — **no contract change**, and no
  hosted service, so the check runs on a local git comparison. The field is optional by design: no
  existing project artifact becomes invalid. **Design only — no shipped surface changes yet;
  implementation follows.**
- **`instinct-check.sh` takes an optional `<project-dir>`** and reports all four instinct layers
  (global Tier-1 index + theme files, global Tier-2 persona silos, project Tier-1, project Tier-2)
  instead of only the global index. It also reconciles the index against the theme files: IDs present
  in a theme file but not listed in the index are reported as INFO (expected for frozen overlays such
  as `imported-*.md`), while index bullets with no matching entry are a WARNING — the index pointing
  at content that does not exist.

## [0.2.1-beta] - 2026-07-10

### Fixed
- **Instincts are now actually loaded at session start.** CLAUDE.md claimed the index was "loaded at
  session start", but Claude Code does not auto-inject `~/.claude/instincts.md` — it injects CLAUDE.md
  files and imports. Added an `@instincts.md` import to the shipped CLAUDE.md so the slim index (native
  + shared org-tier bullets) is really pulled into context each session; theme files stay on-demand.

### Changed
- **`memory-sync.sh pull` now lists the shared instincts in the autoloaded index.** The `{ORG}`-tier
  index block previously held only a pointer to the overlay topic file, so a session-start reader saw
  *that* a shared set exists but not *what's in it* — no trigger to load it. `pull` now generates a
  one-liner bullet per `### <ID>: <headline>` (with confidence) into a delimited, self-updating block,
  matching the visibility of native/imported instinct sections. Migrates a prior undelimited block in place.

## [0.2.0-beta] - 2026-07-10

### Added
- **Team setup — shared org-tier memory/instincts (`scripts/memory-sync.sh`).** First shipped surface of
  the layered-learnings scope model (ADR-0006) and shared vault (ADR-0007), previously design-only: a
  generic, config-driven sync tool that materializes a shared org-tier repo as a **read-only overlay**
  in `~/.claude` (`pull`) and shares local entries with a **discipline gate** (`promote`) that blocks
  secrets, personal data (home paths, emails, session hashes, `type: user`), non-allowlisted IPs, and
  work-item/TODO markers. All deployment specifics live in a personal, non-distributed
  `~/.claude/memory-sync.json` (template: `templates/memory-sync.example.json`); the script stays
  generic. Namespaces (`{ORG}-G-NNN` shared, `{SRC}-G-NNN` imported, native `G-NNN`) documented in
  `templates/MEMORY_SCHEMA.md`. Gate is a client-side best-effort lint — add a CI/pre-receive backstop
  before a large contributor circle. See CLAUDE.md → "Sharing instincts/memory across a team (org tier)".
- **`tokenFile` fallback for the YouTrack work-item backend** — `workitems.youtrack.tokenFile` names a
  file path (outside the repo, e.g. mode 600) the backend reads the token from when `tokenEnv` isn't
  set or its named environment variable is empty. Env still wins when both are configured and resolve.
  Removes the need to export an env var in every session; the token value still never enters
  `.claude/settings.json` or any tracked file.
- **"See it in action" demo section in the README** — a concise end-to-end command walkthrough (`/track-decision → /project-init → /p0-problem → /gate-p0 → …`) with a placeholder for a recorded asciinema/GIF demo, so first-time visitors grasp the phase-and-gate flow before installing.
- **Work-item backend design (proposed) — `Manual/WORKITEMS.md` + ADR-0002…0007.** A backend-neutral work-item contract (`create`/`list`/`get`/`claim`/`set-status`/`append-result`) so CCPR works **with or without a ticket system**, `local` (structured Markdown at `docs/workitems/<id>.md`) staying first-class: the contract + provider model (ADR-0002), the first remote backend — self-hosted YouTrack, resolved by name (ADR-0003), `lift`/`migrate` onboarding (ADR-0004), the claiming / branch-runner protocol with `Parked` resume (ADR-0005), and the layered learnings scope model (`framework`/`org:<name>`/`product`/`project`, ADR-0006) + shared Git vault (ADR-0007). **Design only — no shipped surface changes yet; implementation follows.**

### Changed
- **README restructured for clarity.** Added an audience-first introduction ("who it's for" / "what it covers"), a Table of Contents, and a new **Requirements** section; grouped Two Tracks + Phase System + Agent Team under a single "How it works" and moved the demo up front. Content, facts (15 agents, 115 commands), links and version are unchanged — structure and the intro only.

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

[Unreleased]: https://github.com/jonase47/ccpr/compare/v0.2.1-beta...HEAD
[0.2.1-beta]: https://github.com/jonase47/ccpr/compare/v0.2.0-beta...v0.2.1-beta
[0.2.0-beta]: https://github.com/jonase47/ccpr/compare/v0.1.0-beta...v0.2.0-beta
[v0.1.0-beta]: https://github.com/jonase47/ccpr/releases/tag/v0.1.0-beta
