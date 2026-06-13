---
kind: constitution
status: active
version: 1.1
last_updated: 05.06.2026
related:
  - README.md
  - CLAUDE.md
  - Manual/LEAN_TRACK.md
---

# Constitution – CCPR (Claude Code Pipeline Repo)

> **Scope.** This constitution binds CCPR itself — the worker repository that
> ships skills, agents, scripts, templates and docs to `~/.claude/`. It is
> deliberately separate from any project-level constitution that CCPR-driven
> projects generate via `/constitution`.
>
> **Why CCPR has its own constitution.** The Full-Track requires every project
> to ratify a constitution. CCPR is a meta-project, but a meta-project still
> ships artifacts that downstream users depend on — so the same discipline
> applies. This file makes the implicit rules explicit and gives gates,
> reviewers and contributors a single binding reference.

## Inviolable (non-negotiable)

- **No external services for distribution:** CCPR must be installable and runnable on a clean machine without API keys, cloud accounts, or paid services. Ollama and any third-party tooling are strictly optional. *Reasoning:* distribution must remain self-contained so any user can install CCPR offline and inspect every shipped artifact. *Reference:* README install procedure.
- **No personal or tenant data in shipped artifacts:** `templates/`, `agents/`, `commands/`, `scripts/`, `docs/`, and `instincts.md` must contain no real user names, client identifiers, personal email addresses, real domains, or sensitive numbers. *Reasoning:* CCPR is a worker template; any leakage propagates to every clone and breaches the privacy expectations of its testers. *Reference:* GDPR Art. 5 (1)(a).
- **GDPR as default assumption:** every project template, gate check, and security skill assumes GDPR applies until explicitly opted out with documented justification at project level. *Reasoning:* the primary deployment context is Germany; defaulting to GDPR protects downstream projects from forgetting it. *Reference:* GDPR Art. 25.
- **English in code and shipped content:** skill names, agent names, file paths, comments, identifiers, frontmatter keys, and the body of shipped doc content are written in English. User-facing conversation language is separately configurable in CLAUDE.md. *Reasoning:* CCPR is shared with non-German testers; mixed-language artifacts produce friction and reduce reusability.
- **No breaking skill-interface changes without ADR + migration:** any change to a skill prompt, agent contract, or template schema that invalidates existing project artifacts requires an Architecture Decision Record and a documented migration path before the change is merged. *Reasoning:* CCPR is used live by testers; surprise breakage erodes trust and forces them to throw away work. *Reference:* `commands/p3-arch-adr.md` ADR convention.
- **No vendor lock-in:** infrastructure choices, model selections, and tooling must be replaceable. Every component that integrates with an external vendor (Ollama, Hetzner, Coolify, Traefik, …) requires either a self-hosted alternative or a documented migration path to a comparable replacement. *Reasoning:* the distribution must survive the failure, pricing change, or terms-of-service change of any single vendor. *Reference:* Inviolable "No external services for distribution".

## Default (deviate with justification)

- **TDD discipline:** Red → Green → Refactor, with 1 TDD cycle = 1 commit using Conventional Commits. *Deviation:* exploratory spikes that are squashed before merge. *Decided by:* skill author / committer.
- **Self-hosted before managed:** prefer Hetzner Cloud + Coolify + Traefik + Gitea over managed cloud services. *Deviation:* when operational overhead of self-hosting clearly outweighs the benefits for the specific component. *Decided by:* DevOps lead / project owner.
- **Markdown-first documentation:** all docs, ADRs, memory pages, and skill outputs are written in Markdown. *Deviation:* downstream exports (PDF, slides, dashboards) generated from Markdown sources. *Decided by:* tech-writer / PO.
- **Conventional Commits:** all commit subjects follow `type(scope): subject` (`feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `style`, `ci`, `build`, `revert`). *Deviation:* emergency hotfixes that get rebased into conforming commits later. *Decided by:* committer + reviewer.
- **Accessibility WCAG 2.2 AA + Dark Mode:** every project with a user interface ships a dark mode and meets WCAG 2.2 AA. Status colours always pair with icon and text — never colour alone. *Deviation:* CLI-only tools without graphical UI. *Decided by:* ux-designer during P3.

## Aspirational

- **Multi-tenant readiness:** CCPR usable in parallel by multiple persons on multiple projects for multiple clients without modification. *Measurement:* at least one real client project running on CCPR without local patches. *Review cadence:* quarterly during the v1.0 stabilisation period.
- **Skill-footprint consolidation:** reduce the current 114-skill surface where sub-skills always run sequentially (e.g. P3 sub-trees). *Measurement:* skill-invocation frequency from session logs; merge candidates after 30 days of consistent co-occurrence. *Review cadence:* every `/postmortem`.
- **v1.0 release with versioning and changelog:** SemVer tags (`v1.0.0`, `v1.1.0`, …), `CHANGELOG.md` in the repo root, and a defined update procedure for users. *Measurement:* tag `v1.0.0` exists, CHANGELOG complete, update path documented. *Review cadence:* target = before declaring CCPR **stable** (v1.0). A public **beta** ships earlier under `0.x` with rough edges flagged (see `BETA.md`); stable status — stable interfaces and a defined upgrade path — is what this goal gates.
- **Lean-Track sunset:** the Lean-Track is removed after CCPR v1.0 stabilises. *Measurement:* `commands/lean-*.md`, `commands/track-decision.md`, `Manual/LEAN_TRACK.md` removed (or repurposed), references purged from README/CLAUDE.md. *Review cadence:* immediately post-v1.0.

## Changelog

- **v1.1** (05.06.2026): re-scoped the "v1.0 release" Aspirational goal — its review cadence now gates on declaring CCPR **stable** (stable interfaces + upgrade path) rather than "before any public release", to allow an earlier `0.x` public beta. No Inviolable or Default changed.
- **v1.0** (15.05.2026): initial ratification. Six Inviolables (distribution self-containment, no PII/tenant data, GDPR default, English in code, no breaking skill changes, no vendor lock-in), five Defaults (TDD, self-hosted, Markdown-first, Conventional Commits, WCAG 2.2 AA + Dark Mode), four Aspirational goals (multi-tenant, skill consolidation, v1.0 release, Lean sunset).
