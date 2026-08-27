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

### Run the test suite

CCPR's shipped scripts are covered by a Python test suite under `scripts/tests/`.
Run it from the repository root:

```bash
python3 -m unittest discover -s scripts/tests -t .
```

- **`-t .` is not optional**, and the failure mode is worth knowing because it is
  partly silent. It sets the top-level directory imports resolve against. Measured
  on the current tree: **with** it, discovery collects **1458 tests, 0 import
  errors**; **without** it, **1118 tests and 11 modules that fail to import** — the
  two that use a relative `from .test_artifact_gate import …`, plus the entire
  `scripts/tests/workitems/` subpackage. The run does go red on those 11, so you
  will notice something — but roughly **340 tests simply never execute**, and
  nothing in the output says so.
- The full run takes **a couple of minutes**. If you drive it from an agent whose
  tool calls time out, start it in the background and wait for it once rather than
  polling.
- `scripts/run-tests.sh` is **not** the entry point for this repository. It is a
  framework script shipped for downstream *projects* and detects their test runner
  from `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod`. CCPR itself has
  none of those, so it answers `{"framework": "unknown"}` here. That is correct
  behaviour, not a bug to fix.

### Run the linters

Run the ones relevant to what you touched — each is read-only:

| Script | Validates |
|---|---|
| `scripts/memory-lint.sh` | memory frontmatter, naming, cross-refs, index consistency |
| `scripts/phase-docs-lint.sh` | phase-doc frontmatter (scoped to the phase folders) |
| `scripts/manual-lint.sh` | `Manual/` index↔detail contract: `parent_index`, back-links, `kind` |
| `scripts/doc-volume-check.sh` | file size against the 25/40/50 KB splitting thresholds |
| `scripts/conformance-run.sh` | the shipped checks above, run against real consumer projects (see below) |

Two notes on reading their output:

- **A non-zero exit is not automatically your regression.** This repository has a
  known, stable baseline of findings (`memory-lint.sh` exits 1 on long-standing
  warnings; `doc-volume-check.sh` exits 2 on two agent-memory files). Compare
  against a run on `main` before assuming your change caused it.
- **`phase-docs-lint.sh` reports `Files scanned: 0` here** — CCPR has no phase
  folders of its own. A run that scanned nothing is not a pass; it just means that
  check has nothing to say about this repository.

### Run the conformance check, if you have consumers configured

`scripts/conformance-run.sh` runs the checks above against real projects that
*use* CCPR, rather than against fixtures. It exists because a rule written in the
repository that defines it is a hypothesis until it meets a consumer: on
27.08.2026 three shipped defects were found in one session that were
structurally invisible from inside this repository while the suite reported
**1478 tests, OK**.

It reads its consumer list from the personal, non-distributed config
(`conformance` key, see `templates/memory-sync.example.json`). **With nothing
configured it exits 0 and says so out loud** — `0 configured, 0 covered — the
conformance check DID NOT RUN` — so a clean machine is never blocked, and a run
that checked nothing never reads as a pass. Use `--require-consumers` when you
want the unconfigured case to fail instead.

Measured: three consumers, fifteen checks, **about 30 seconds**. Use
`--consumer <id>` for a single one.

A finding about a consumer's own documents never fails the run; only a check
disagreeing with its own contract, a zero-scope run over a non-empty target, or
a violated pin does. The reasoning is in
[docs/adr/ADR-0010-conformance-runs-against-consumers.md](docs/adr/ADR-0010-conformance-runs-against-consumers.md).

### Keep scripts syntactically clean

`bash -n <file>` for shell, `python3 -m py_compile <file>` for Python.

### Follow the doc schemas

Phase docs follow the two-level **phase index + detail file** split and the
frontmatter schema in `templates/PHASE_DOC_SCHEMA.md`. Documents under `Manual/`
additionally follow the index↔detail contract that `manual-lint.sh` checks.

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
