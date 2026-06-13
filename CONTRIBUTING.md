# Contributing to CCPR

Thanks for your interest in CCPR — a phase-based project framework for Claude Code
(agents, slash commands, quality gates, templates, and automation scripts).
Contributions of all sizes are welcome: fixes, new commands or templates, docs, and
script improvements.

## Ground rules (non-negotiable)

CCPR ratifies its own [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md). Two Inviolables
apply directly to every contribution:

1. **English in code and shipped content.** All shipped artifacts — command and agent
   prose, templates, doc content, code comments, and user-facing strings — are written
   in English. (The conversation language a user sees is separately configurable in
   their own `CLAUDE.md`.)
2. **No personal or tenant data in shipped artifacts.** No real user names, client or
   project identifiers, personal email addresses, real domains, or sensitive numbers.
   Use neutral placeholders (e.g. `ExampleApp`) in examples.

A PR that violates either will be asked for changes before merge. Please also keep the
distribution self-contained: it must install and run on a clean machine without API
keys, paid services, or cloud accounts (third-party tooling like Ollama stays
optional).

## Workflow

1. Fork the repo on GitHub and create a topic branch (`feature/…`, `fix/…`).
2. Make your change. Keep one logical change per commit.
3. Open a pull request against `main` with a short description of the *why*.

## Commit conventions

- **[Conventional Commits](https://www.conventionalcommits.org/)**: `feat`, `fix`,
  `refactor`, `docs`, `chore`. Example: `docs(commands): clarify /gate-p3 inputs`.
- Explain the **reasoning** in the commit body, not just the what.
- Per [`ADR-0001`](docs/adr/ADR-0001-versioning-and-distribution.md), every change adds
  a line under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).

## Quality checks before opening a PR

- Markdown / docs that follow the schemas: run the linters where relevant —
  `scripts/memory-lint.sh`, `scripts/phase-docs-lint.sh`, and
  `scripts/doc-volume-check.sh`.
- Shell or Python scripts must stay syntactically clean: `bash -n <file>` for shell,
  `python3 -m py_compile <file>` for Python.
- Phase docs follow the two-level **phase index + detail file** split and the
  frontmatter schema in `templates/PHASE_DOC_SCHEMA.md`.

## Adding yourself

New contributors may add their name (or handle) to [`AUTHORS`](AUTHORS) in the same PR.
The copyright line stays the generic "The CCPR Authors".

## Conduct

Be respectful and constructive. Assume good intent, keep feedback about the work, and
help keep the project welcoming. Reports of unacceptable behaviour can be sent
privately to the maintainer via GitHub ([@jonase47](https://github.com/jonase47)).

## License

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE).
