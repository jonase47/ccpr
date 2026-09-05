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

### Run them all at once

```bash
bash scripts/check-all.sh .
```

Runs the checks catalogued below and compares each against
`scripts/check-all.baseline.tsv`, the versioned record of what this repository's
checks are *supposed* to return. Takes about five minutes, most of it the test
suite.

**It does not compare against exit zero, and neither should you.** One of them
is non-zero on a correct tree — `memory-lint.sh` exits 1 on long-standing
warnings — so a collector that failed on any non-zero result would be
permanently red, and a check that is red when nothing is wrong gets ignored
within a fortnight. (It was two until 30.08.2026: `doc-volume-check.sh` now
scans only git-tracked files, and the oversized files it used to report are all
untracked working state.) A check
that *could not run* (no consumers configured, no `scripts/tests/` because you
are running from an installed `~/.claude`, ShellCheck not installed, no install
provenance to compare against) is reported
as `could-not-run` and counted separately: it is neither a pass nor a failure,
and it never lands in the matched count.

**One external tool is needed for the full set:** `shellcheck`
(`brew install shellcheck`, or your platform's package). Without it the
`shellcheck` check honestly reports `could-not-run` rather than passing — but it
also means you will not see a finding it would have caught until CI does. It is
the only non-stdlib dependency anywhere in the checks.

When you change what a check legitimately returns, update the baseline in the
same commit and say why in the commit body. The sections below stay useful for
running one check on its own while you work.

### Run the test suite

CCPR's shipped scripts are covered by a Python test suite under `scripts/tests/`.
Run it from the repository root:

```bash
python3 -m unittest discover -s scripts/tests -t .
```

- **`-t .` is not optional**, and the failure mode is worth knowing because it is
  partly silent. It sets the top-level directory imports resolve against. Measured
  on the current tree (05.09.2026): **with** it, discovery collects **2660 tests, 0
  import errors**, exit 0; **without** it, **1943 tests and 17 modules that fail to
  import**, exit 1 — the eight that use a relative import
  (`from .test_phase_docs_lint import …` in four modules,
  `from .test_artifact_gate import …` in two,
  `from .test_gitattributes_crlf_guard import …` in one, and
  `from . import …` of five sibling modules in the skip budget), plus the nine
  modules of the `scripts/tests/workitems/` subpackage. The run does go red on those
  17, so you will notice something — but **717 tests simply never execute**, and
  nothing in the output says so.

  That skipped count moves whenever a module gains a relative import:
  340 → 350 → 480 → 510 across four commits on 27–28.08.2026, 509 on 29.08., 510 on
  30.08.2026, 684 on 05.09., and 717 today. Each jump bought something — most came from sharing one
  parser instead of retyping a shipped list into four test modules (WI-0126), or
  from a fifth module joining the skip-budget import — but the cost lands here,
  silently, on anyone who forgets the flag.

  **Re-measure these numbers when you change them, rather than adjusting one.** The
  pair is the point: 2660 alone says nothing, and the four figures have now been
  found stale together four times — the file claimed 1691 / 1185 / 14 / ~510
  against a tree at 1848 / 1339 / 15 / 509, then 1848 / 1339 / 15 / 509 against a
  tree at 1987 / 1477 / 16 / 510, then 1987 / 1477 / 16 / 510 against a tree at
  2627 / 1943 / 17 / 684, and now 2627 / 1943 / 17 / 684 against a tree at
  2660 / 1943 / 17 / 717. These runs, back to back, take about eight minutes.
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
| `scripts/manual-lint.sh` | `Manual/` index↔detail contract: `parent_index`, back-links, `kind`, and marked numbers against the value derived from their glob |
| `scripts/doc-volume-check.sh` | file size against the 25/40/50 KB splitting thresholds |
| `scripts/shellcheck-run.sh` | ShellCheck over the shipped shell scripts at `--severity=warning` |
| `scripts/conformance-run.sh` | the shipped checks above, run against real consumer projects (see below) |
| `install.sh --verify` | the `~/.claude` installation against the commit its provenance marker records |

Two notes on reading their output:

- **A non-zero exit is not automatically your regression.** This repository has a
  known, stable baseline of findings — `memory-lint.sh` exits 1 on long-standing
  warnings. (`doc-volume-check.sh` used to exit 2 on oversized files under
  `docs/memory/`; since 30.08.2026 it scans only git-tracked files, so those
  untracked ones are out of its scope and it exits 0.) Rather than
  comparing against a run on `main` by hand, run `scripts/check-all.sh`, which
  holds those expectations in a versioned baseline and tells you which check
  diverged from it.
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

Every configured consumer is put through the same check set, so both the
invoked-check count and the wall-clock time scale with *your* consumer list — the
run reports both, and that report is current by construction in a way a number
written down here would not be. Use `--consumer <id>` for a single one.

A finding about a consumer's own documents never fails the run; only a check
disagreeing with its own contract, a zero-scope run over a non-empty target, or
a violated pin does. The reasoning is in
[docs/adr/ADR-0010-conformance-runs-against-consumers.md](docs/adr/ADR-0010-conformance-runs-against-consumers.md).

### Keep scripts syntactically clean

`bash -n <file>` for shell, `python3 -m py_compile <file>` for Python.

Beyond syntax, `scripts/shellcheck-run.sh` runs ShellCheck at
`--severity=warning` over the shipped shell scripts and is expected to find
**nothing** — the baseline is 0, deliberately, because `check-all.sh` compares
exit codes and a non-zero baseline would be blind to the next finding. When
ShellCheck flags something it is genuinely wrong about, suppress it with a
point-precise `# shellcheck disable=SCxxxx` **and a reason in the comment**;
this repository has no file-wide suppressions, so a directive never hides a
finding beyond the line it was written for.

### Follow the doc schemas

Phase docs follow the two-level **phase index + detail file** split and the
frontmatter schema in `templates/PHASE_DOC_SCHEMA.md`. Documents under `Manual/`
additionally follow the index↔detail contract that `manual-lint.sh` checks.

### Record an ADR's resolutions in place

Applies to this repository's own ADRs under `docs/adr/`. Whether adopter projects
should follow it is a separate question and is not decided here.

An ADR that carries both an open-questions list and, later, the answers will drift,
because resolving a question and updating the list that advertises it are two
separate acts and only the first is satisfying. The reader most likely to be misled
is the one using the list the way it invites: as a work queue. This is not
hypothetical — ADR-0009's follow-up 4 read "undefined" for six days after an
addendum in the same file had answered it, and a proposal contradicting that answer
was made on the strength of the stale entry. The sweep that followed (WI-0127) found
eight more across four ADRs, including one in an ADR a single day old.

Two rules, both cheap at the moment you write the answer and expensive later:

1. **A resolved follow-up is struck through in place, with a pointer to what
   resolved it — never silently deleted.** Deleting removes the only trace that the
   list can drift out of step with its own document, which is the evidence this rule
   rests on. The form, established in `docs/adr/ADR-0009-...md`:

   ```markdown
   4. ~~**The original wording, kept.**~~ **Resolved in Addendum 3 (21.08.2026):
      the answer, in one sentence.**
   ```

   Half-resolved counts as half: say which half is settled and which is still open,
   rather than striking the whole entry. If the answer diverged from what the
   follow-up asked for, record the divergence instead of smoothing it over.

2. **An addendum's heading names what it resolves** — `## Addendum 2 (21.08.2026):
   A7 resolved — where the scope anchor lives`. Without this, a reader working down
   the follow-up list has no way to find the answer, and no mechanical check keyed
   on headings could find it either. At the time this rule was written, one of
   ADR-0009's four addenda did it, and that one resolved two follow-ups while naming
   only one.

There is no automated check for either rule. Building one was deliberately deferred
until the convention has produced enough annotated cases to measure a check against.

### Derive a contract test's expectation from the other artifact, not the code under test

A test whose subject is a contract *between two artifacts* — "does tool A read the
path tool B writes?" — must derive its expected value from artifact B, never from
artifact A's own source. Deriving it from A makes the test agree with A by
construction, so the question the test exists to ask can never be asked.

Worked example (WI-0129): `command-check.py`'s `check_gate_passed()` probed
`docs/GATE_P4.md`, a flat path no `/gate-p4` command has ever written — every real
gate command writes into a phase folder (`docs/planning/GATE_P4.md`). The
corresponding test's fixture helper built its file at `docs/GATE_<PHASE>.md`,
documented in its own docstring as "the path `check_gate_passed` probes". The
fixture took its path from the code being tested, so the fix and its test agreed
with each other while both disagreed with every shipped `gate-pN.md` command. The
fix: derive the expected path from the command files' own "Create `docs/<folder>/
GATE_P<N>.md`" statements — but only on the test side. `GATE_FILE_PATHS`, the dict
`check_gate_passed()` actually consults in production, stays a hand-authored
mapping (its own comment says so); nothing at runtime parses `commands/gate-pN.md`.
The test parses each command's claim independently and asserts it equals
`GATE_FILE_PATHS` (`GateFilePathsMatchesTheCommandsClaimTest`). That is a drift
guard between two independently authored representations, not a single shared
source of truth: a maintainer still has to hand-edit `GATE_FILE_PATHS` whenever a
`gate-pN.md` write-target sentence changes — the guard only catches the moment the
two disagree, at test time; it does not remove the manual step.

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
