---
kind: adr
adr_id: ADR-0001
status: accepted
last_updated: 15.05.2026
related:
  - ../CONSTITUTION.md
  - ../../Manual/LEAN_TRACK.md
  - ../../CHANGELOG.md
---

# ADR-0001: Versioning, Changelog, and Distribution Model

**Status:** Accepted (15.05.2026)
**Decision-makers:** Repo owner (Jonas), informed testers (Olli (@OlArtTro) and one other early tester)

## Context

CCPR is the worker repository that ships skills, agents, scripts, templates, and docs to `~/.claude/`. It is published on GitHub (a fresh public baseline; earlier development lived in a private repository) and may reach a wider audience after v1.0.

Today the repo has no version tags, no `CHANGELOG.md`, and no published update procedure. The install procedure documented in `README.md` is `cp -r ccpr/* ~/.claude/`, which silently overwrites local customisations. The Constitution (v1.0, 15.05.2026) lists three Aspirational goals that depend on a proper versioning model:

- *Multi-tenant readiness* — users on different machines must know which CCPR state they run.
- *Skill-footprint consolidation* — removing skills is a breaking change that needs a migration path.
- *v1.0 release with versioning + CHANGELOG.md in repo root, defined update procedure.*

Also relevant: **Inviolable #5** of the Constitution requires an ADR + migration path for every breaking skill-interface change. That rule is unworkable without a versioning scheme and changelog to attach migrations to.

The status quo is acceptable today (two testers know the repo state by talking to Jonas) but breaks the moment a third user lands. We need a model **before** that happens, not after.

## Decision

CCPR adopts **Semantic Versioning** (https://semver.org) with the following scoping for what counts as MAJOR / MINOR / PATCH in a meta-repo context, plus a **Keep a Changelog** (https://keepachangelog.com) style `CHANGELOG.md` at the repo root.

### Version scheme

Tags follow the format `vMAJOR.MINOR.PATCH` (e.g. `v0.1.0`, `v1.0.0`).

| Bump | Triggered by | Examples |
|---|---|---|
| **MAJOR** | Constitution Inviolable change; breaking skill-interface change; schema-breaking change in memory or phase-docs; agent removal | Removing `researcher` agent (would be MAJOR if we were post-1.0); changing `memory-lint.sh` to reject previously-valid frontmatter; renaming a slash command users depend on |
| **MINOR** | New skill, new agent, new script, new template, new convention that is backwards-compatible | Adding global Tier-2 memory slot; adding `local-llm/` stub wrappers; adding new gate sub-skill |
| **PATCH** | Typo, clarification, bug fix in scripts, doc-only correction that does not change any rule | Fixing a wrong count in README; correcting a typo in a skill prompt; bug fix in `memory-lint.sh` that does not change validation rules |

**Pre-1.0 caveat (semver §4):** while CCPR is below v1.0, MAJOR-bumps may occur on MINOR (`0.x.0`) to signal a meaningful surface change without committing to long-term API stability. Users are expected to read the changelog before upgrading.

### Changelog

`CHANGELOG.md` lives at the **repo root** (not under `docs/`) following Keep a Changelog 1.1:

- `## [Unreleased]` section at the top, grouped by `Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`.
- Each released version gets its own `## [vX.Y.Z] – DD.MM.YYYY` heading and groups the same way.
- Constitution changes call out the Inviolable involved.
- Skill removals link to their final commit SHA so removed code remains reachable.
- The bottom of the file holds a `[unreleased]: ...` link reference block to GitHub compare URLs once meaningful.

### Tag procedure

1. Update `CHANGELOG.md`: move `[Unreleased]` entries under a new `## [vX.Y.Z] – DD.MM.YYYY` heading.
2. Bump the version everywhere it is hardcoded (README badges/intro, future `package.json`-like files).
3. Commit with `chore(release): vX.Y.Z`.
4. Tag with `git tag -a vX.Y.Z -m "Release vX.Y.Z"` and `git push --tags`.
5. Cut a release on GitHub with the same body as the changelog section.

### Update procedure for users

Documented in `README.md`. The current `cp -r` approach is the v0.x install procedure; a proper installer or `sync` script is an Aspirational target for v1.0.

**Until v1.0:** users `git fetch && git checkout vX.Y.Z` in their CCPR clone, then re-run the documented install step. They are warned to back up `~/.claude/CLAUDE.md`, `~/.claude/instincts.md`, `~/.claude/instincts/` and `~/.claude/instincts-archive/` before re-running install — the docs show how (`cp -r ~/.claude ~/.claude.backup-$(date +%Y%m%d)`).

**At v1.0:** the install procedure is expected to either (a) ship an idempotent installer that preserves user-customised files, or (b) move shipped artefacts into a subdirectory of `~/.claude/` that does not conflict with user files. The decision lives in a future ADR triggered by approaching v1.0.

### Initial version

The repo enters this ADR at **v0.1.0**. This first tag will be set in a separate commit immediately after this ADR lands. Earlier history is reachable by SHA but unversioned.

### What does *not* require a tag

- Cleanup commits that change no shipped surface (e.g. fixing an internal stale link in a comment)
- WIP branches; tags only land on `main`

## Consequences

### Positive
- Constitution Inviolable #5 (no breaking change without ADR + migration) becomes enforceable: ADRs can now reference concrete version boundaries.
- Constitution Aspirational "v1.0 release with versioning + CHANGELOG.md" is now actionable instead of decorative.
- Testers and future users have a deterministic way to know which CCPR state they run.
- Conflicts when porting local changes back into the repo are framed by version diff, not by guess.

### Negative
- Every change now needs a changelog line. Trivial cleanup commits feel heavier.
- Pre-v1.0 the MAJOR-on-MINOR-bump caveat is a footgun for users who scan only the major number. Mitigated by README guidance.

### Neutral
- The current `cp -r` install procedure is documented as v0.x-only. The v1.0 installer story is deferred to a follow-up ADR — not blocking this one.

## Alternatives considered

- **CalVer (`2026.05.0`).** Rejected: CCPR releases are change-driven, not time-driven. SemVer's MAJOR signal carries the "watch out, migrate" information that testers actually need.
- **No versioning, rely on git SHAs.** Rejected: works only for the current "two informed testers" scope. Breaks the moment a third user lands or someone needs to reference a known-good state by name.
- **Combined CCPR + project-template version.** Rejected: the worker repo and downstream-project state are independent. Mixing them creates false coupling.

## Follow-ups

- Land the initial `CHANGELOG.md` at the repo root with `## [Unreleased]` plus a `## [v0.1.0] – DD.MM.YYYY` section that retroactively captures the cleanup-wave commits from 15.05.2026 (researcher removal, Lean transient marker, Constitution v1.0, global Tier-2 memory, doc splitting).
- Set the `v0.1.0` tag right after the CHANGELOG lands.
- Reflect the new versioning model in `README.md`'s Install section (replace the silent-overwrite warning with the backup-then-install procedure).
- Open a placeholder follow-up ADR for the v1.0 installer story once Aspirational targets are within reach.
