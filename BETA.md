# CCPR is in public beta

CCPR works and is used on real projects, but it is **pre-1.0**: rough edges are
expected, and the point of this beta is to find them with your help. This page
says what we're looking for and what we already know — so your feedback lands
where it's useful.

*Last updated: 05.06.2026*

---

## What we're especially looking for

Feedback is the whole reason CCPR is public this early. The bar is deliberately
low — half-formed thoughts count. A few questions that are most useful:

- **Did onboarding land?** After the README + `Manual/GETTING_STARTED.md`, did you
  understand *what CCPR is* and *how you drive it*? Where did it click, where did
  you stall?
- **Did the install go cleanly?** `install.sh` — backup, preview, confirmation:
  clear enough? Anything surprising?
- **Which phase felt too heavy?** The P0–P8 pipeline is thorough on purpose, but
  if a phase or gate felt like overkill for your project, say so.
- **Did a skill produce something useless or wrong?** Concrete examples (which
  skill, what you expected, what you got) are gold.
- **Naming & docs.** Anything you had to re-read, or a term that didn't mean what
  you assumed.

Open an issue: [github.com/jonase47/ccpr/issues](https://github.com/jonase47/ccpr/issues)
— pick the **feedback / UX** template (or **bug** / **question**). Security issues
go privately via [`SECURITY.md`](SECURITY.md), not public issues.

---

## Known limitations (no need to report these)

These are understood and on the roadmap — reporting them again is fine but not
needed. Reports of *anything else* are very welcome.

- **Updates are a file refresh, not a merge.** The installer is also the updater:
  `./install.sh --update` refreshes the pure framework and keeps your local files
  (`CLAUDE.md`, `settings.json`, and instincts that matured via `/postmortem`).
  It still does not *merge* edits you made directly inside *shipped framework*
  files — those get overwritten (the timestamped backup lets you re-apply them).
  A customisation-preserving installer is the v1.0 goal (see
  [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md), Aspirational). See the README
  "Updating" section for the exact steps.
- **No migration of local state.** Upgrading does not transform existing project
  state; it only swaps framework files.
- **Pre-1.0 versioning.** Per SemVer, `0.x.0` bumps can carry surface changes.
  Read [`CHANGELOG.md`](CHANGELOG.md) before upgrading.
- **Lean-Track is transient.** It exists for fast internal experimentation and as
  a bridge into Full-Track; it is scheduled to be sunset after v1.0. Mandant/team
  projects should start on Full-Track.
- **Large skill surface.** ~115 slash commands; some sub-skills always run in
  sequence. Consolidation is planned (tracked as an Aspirational goal, reviewed at
  each `/postmortem`).
- **Multi-tenant / multi-person use is not yet "without local patches".** Running
  CCPR unmodified across several people and client projects is a v1.0 target, not
  a beta guarantee.

---

## What "beta" does and doesn't promise

- **Does:** the framework is usable end-to-end; the artifacts are English-only and
  carry no personal/tenant data; it installs and runs on a clean machine without
  paid services.
- **Doesn't:** stable interfaces, an upgrade/migration path, or customization
  preservation — those are the v1.0 stabilisation goals.

Thanks for trying it this early. The fastest way to shape CCPR right now is to
tell us where it got in your way.
