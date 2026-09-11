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
checks are *supposed* to return. Takes **about 11 minutes** (measured
08.09.2026, `/usr/bin/time -p`: real 662.26s) — the test suite is a large
share of that, but not most of it on its own (see "a couple of minutes"
below); the remaining time is the other eight checks, `conformance-run.sh`
in particular scaling with however many consumer projects are configured
locally. Set a tool-call timeout well above this if you drive it from an
agent — see the note on single-module timeouts further down for the same
reasoning applied to one test module.

**One of the checks it runs IS the test suite below (`python3 -m unittest
discover -s scripts/tests -t .`) — do not run that command in a second
terminal, or a second agent session, while `check-all.sh` is running in the
first.** Two runs against the same working tree share it: `python3 -m
unittest discover` creates and removes real test fixtures on disk mid-run,
and two suites doing that at once can steal a fixture out from under each
other — a collision that looks exactly like a test failure, not like a
concurrency bug, so whoever hits it debugs the wrong thing (CCP-1145,
two independently observed real incidents). `check-all.sh` refuses a second
concurrent run against the same working tree outright instead: it exits **2**
("the run could not be performed as asked" — the same exit code a bad
`--baseline` or a missing project directory already use) and says a run is
already in progress, rather than silently racing it. The lock is keyed on
the working tree's own `.git` directory, so it catches the collision even
across two differently-spelled paths to the identical checkout (macOS's
case-insensitive filesystem, a symlink, a second clone bind-mounted over the
first) — a lock file named after the literal path string you typed would
have missed exactly that case. A run that crashes outright (killed, not
exited normally) does not leave a lock behind that blocks the next one.

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
  on the current tree (11.09.2026, CCP-1177): **with**
  it, discovery collects **2916 tests, 0 import errors**, exit 0; **without** it,
  **2145 tests and 19 modules that fail to
  import**, exit 1 — the eight that use a relative import
  (`from .test_phase_docs_lint import …` in four modules,
  `from .test_artifact_gate import …` in two,
  `from .test_gitattributes_crlf_guard import …` in one, and
  `from . import …` of five sibling modules in the skip budget), plus the eleven
  modules of the `scripts/tests/workitems/` subpackage (CCP-1172 added
  `test_workitem_similar.py` as the eleventh). The run does go red on those
  19, so you will notice something — but **771 tests simply never execute**, and
  nothing in the output says so.

  That skipped count moves whenever a module gains a relative import:
  340 → 350 → 480 → 510 across four commits on 27–28.08.2026, 509 on 29.08., 510 on
  30.08.2026, 684 on 05.09., and 717 since later that day — unchanged since, across
  seven further cuts (32, then 6, then 30, then 3, then 12, then 9, then 4 new
  tests, the middle two both CCP-1151 stage 4 cut 4, the fifth CCP-1151 stage 4's
  own push-gate.sh self-exemption fix, the sixth CCP-1163's manual-lint.sh
  single-file-root support — 7 from the initial cut plus 2 more from a
  code-reviewer finding on the same cut — and the seventh CCP-1163's own third
  cut, correcting the check-(g) exhaustion test's scope and method: a
  joint-removal control for a necessary pair a per-entry probe cannot see, an
  out-of-scope-becomes-load-bearing control, a genuine-redundancy control, and a
  three-way-classification arithmetic check) that all import cleanly with or
  without the flag, so each addition lands on both sides of the subtraction
  and cancels. Each jump bought something — most came from sharing one
  parser instead of retyping a shipped list into four test modules (WI-0126), or
  from a fifth module joining the skip-budget import — but the cost lands here,
  silently, on anyone who forgets the flag.

  **Re-measure these numbers when you change them, rather than adjusting one.** The
  pair is the point: 2698 alone says nothing, and the four figures have now been
  found stale together fourteen times — the file claimed 1691 / 1185 / 14 / ~510
  against a tree at 1848 / 1339 / 15 / 509, then 1848 / 1339 / 15 / 509 against a
  tree at 1987 / 1477 / 16 / 510, then 1987 / 1477 / 16 / 510 against a tree at
  2627 / 1943 / 17 / 684, then 2627 / 1943 / 17 / 684 against a tree at
  2660 / 1943 / 17 / 717, then 2660 / 1943 / 17 / 717 against a tree at
  2692 / 1975 / 17 / 717, then 2692 / 1975 / 17 / 717 against a tree at
  2698 / 1981 / 17 / 717, then 2698 / 1981 / 17 / 717 against a tree at
  2699 / 1982 / 17 / 717, then 2699 / 1982 / 17 / 717 against a tree at
  2729 / 2012 / 17 / 717, then 2729 / 2012 / 17 / 717 against a tree at
  2730 / 2013 / 17 / 717, then 2730 / 2013 / 17 / 717 against a tree at
  2733 / 2016 / 17 / 717, then 2733 / 2016 / 17 / 717 against a tree at
  2745 / 2028 / 17 / 717, then 2745 / 2028 / 17 / 717 against a tree at
  2747 / 2030 / 17 / 717, then 2747 / 2030 / 17 / 717 against a tree at
  2756 / 2039 / 17 / 717, then 2756 / 2039 / 17 / 717 against a tree at
  2760 / 2043 / 17 / 717, then 2760 / 2043 / 17 / 717 against a tree at
  2769 / 2052 / 17 / 717, then 2769 / 2052 / 17 / 717 against a tree at
  2775 / 2058 / 17 / 717 — the twelfth round running in which the skipped figure
  did NOT move with the others, because CCP-1148's six new tests
  (`scripts/tests/test_check_all.py`'s ArtifactGateDenylistSummaryVisibilityTest
  and ArtifactGateDenylistSummaryRedProofTest, plus
  `scripts/tests/test_ci_workflow.py`'s DenylistEnvMutationTest) import cleanly
  with or without the flag, so the addition lands on both sides of the
  subtraction and cancels, same as every round since 05.09.2026 — and now
  2775 / 2058 / 17 / 717 against a tree at 2781 / 2064 / 17 / 717, the
  thirteenth round running in which it did not move: CCP-1145's six new
  `scripts/tests/test_check_all.py` methods (ConcurrentRunIsRejectedTest,
  LockDoesNotBlockSequentialRunsTest, StaleLockFromACrashedRunDoesNotBlockTest,
  ConcurrentLockRedProofTest, GitDirKeyedLockTest — the last two added in a
  code-review follow-up, closing a gap where every OTHER new test here ran
  only against a non-git fixture and never exercised the git-directory-keyed
  lock path this repository's own real usage always takes — and
  CaseAliasedPathsShareTheSameGitDirLockTest, skipped on a case-sensitive
  filesystem) import cleanly with or without the flag too, same reason, same
  cancellation. These runs, back to back, take about eleven minutes — not
  independently re-measured this round (six more tests, counted without
  running the suite; the wall-clock figure needs an actual run, which is out
  of scope here).

  10.09.2026 (CCP-1172): a full re-run rather than an uncounted delta — the
  headline pair above moved (2867 → 2879, 2128 → 2130), so both sides needed
  re-measuring together, not adjusted one at a time. **A pre-existing drift,
  found rather than caused here:** this trajectory's own last entry said
  `2781 / 2064 / 17 / 717`, while the headline sentence above it already said
  `2867 / 2128 / 18 / 739` — the modules-fail and skip columns disagreed with
  the headline before this round touched anything, and this round could not
  say which of the two was measured correctly at `2781`, only what it
  measured itself.

  **Resolved 10.09.2026:** neither figure was wrong, and the gap between them
  is now bridged with two more measured points rather than left as an
  either-or. Reproduced independently in a throwaway worktree at `309440c`
  (the commit this trajectory's own `2781 / 2064 / 17 / 717` entry
  describes; `git worktree add --detach`, then
  `unittest.TestLoader().discover("scripts/tests")` without a top-level
  dir): **2064 tests, 17 import-failing modules**, an exact match. `17`
  decomposes as the eight non-`workitems/` relative-import modules named
  above (unchanged across every round since 05.09.2026) plus the nine
  `scripts/tests/workitems/` modules that existed at that commit.

  The missing row is filled in from a second throwaway worktree at
  `02930a9` — CCP-1171's own merge commit, which also carries CCP-1157
  (docs-only, no test-suite effect) and CCP-1166 since no round measured the
  tree in between — using the same method as every other entry here (a full
  `-t .` and no-`-t .` `unittest discover` CLI run each): **2831 / 2092 / 18
  / 739**. Modules-fail moved 17 → 18 because CCP-1171's `0fa9460` added a
  tenth `scripts/tests/workitems/` module, `test_workitem_lint.py`, and
  skip held its `with-total − without-total` identity (`2831 − 2092 =
  739`). This figure is not only self-measured here but independently
  corroborated by the commit history itself: CCP-1173's own two commits
  each state the register they re-measured against — `7c98791` logs
  "CONTRIBUTING.md 2831 -> 2856 with `-t .` and 2092 -> 2117 without (18
  import errors unchanged...)" and `12f6382` logs "2856 -> 2867 with `-t .`
  and 2117 -> 2128 without (18 import errors unchanged... 739 never execute
  ... stays correct)" — landing exactly on `2867 / 2128 / 18 / 739`, the
  figure already on record two paragraphs below as the shared fork base for
  both CCP-1170 and CCP-1172. Three independently-sourced points now chain
  without a gap: `2781 / 2064 / 17 / 717` (this trajectory, reproduced
  above) → `2831 / 2092 / 18 / 739` (CCP-1171 round, measured here, matching
  CCP-1173's own commit log) → `2867 / 2128 / 18 / 739` (CCP-1173's own
  commit log, matching the pre-existing fork-base citation below). The
  drift was a missing row, not a wrong number in either register.

  Fresh figures for the CCP-1172 round, each independently re-derived twice (a full
  `-t .`/no-`-t .` `unittest discover` run and, separately, cheap
  `TestLoader().discover(...).countTestCases()` calls) rather than carried
  from either register: **2879 / 2130 / 19 / 749** — modules-fail moved 18 →
  19 because `workitems/test_workitem_similar.py` (CCP-1172) joined the
  `scripts/tests/workitems/` subpackage's relative-import set; the skipped
  count's own delta (+10) is the new module's 11 test methods minus the 1
  that reclassifies from "skipped" to "counted as the module's own failed-
  import placeholder" the moment the module itself starts existing.

  10.09.2026, same day, code-review round: **2879 / 2130 / 19 / 749** against a
  tree at **2889 / 2133 / 19 / 756** — +10 test methods total (a full `-t .`/
  no-`-t .` `unittest discover` run and a separate cheap
  `TestLoader().discover(...).countTestCases()` cross-check agree). Modules-fail
  did NOT move (still 19): every new method landed inside an existing file, none
  in a new module. +3 count without `-t .` are `test_workitems_cli.py`'s three
  new `--checked-against` validation methods (no relative import, so they count
  either way); the other +7 are all inside
  `workitems/test_workitem_similar.py`, already one of the 19 failed-import
  modules, so they only ever show up in the `-t .` count -- the skipped
  column's own delta (+7) is exactly those seven.

  10.09.2026, merge round: `ticket/CCP-1172` (**2889 / 2133 / 19 / 756**) integrated
  `main`/CCP-1170 (**2869 / 2130 / 18 / 739**, itself base `2867 / 2128 / 18 / 739`
  plus two `test_install_provenance.py` methods that import cleanly either way) via
  `git merge`, not `git rebase`: both branches forked from the same base and touched
  disjoint files everywhere except this pin file and `CONTRIBUTING.md` itself, so a
  merge resolves the conflict once instead of a rebase re-running into it at every
  one of CCP-1172's thirteen commits. Re-measured directly against the integrated
  tree (a full `-t .`/no-`-t .` `unittest discover` run and a separate cheap
  `TestLoader().discover(...).countTestCases()` cross-check agree) rather than added
  from the two branches' deltas, because addition is arithmetic, not a measurement,
  and the two branches could in principle have landed overlapping or interacting
  test methods: **2891 / 2135 / 19 / 756** — with-flag and without-flag both moved by
  exactly main's own +2/+2 delta on top of CCP-1172's code-review-round figures;
  modules-fail stayed at 19 (main's two new methods land inside an existing module,
  none new); skipped stayed at 756 for the same reason it always does when an
  addition imports cleanly on both sides of the flag — main's own +2 cancels.

  10.09.2026 (CCP-1174: `source_provenance()` compared two case spellings of one
  directory as strings, classifying a real git checkout as `non-git`; fixed with
  `-ef` same-file identity, plus a warning when an unresolvable source still
  carries its own `.git`): **2896 / 2140 / 19 / 756** — +5 on both totals, all in
  `test_install_provenance.py` (no relative import, so the addition lands on
  both sides of the flag and cancels out of skipped); modules-fail unchanged
  (five new methods, no new module). Re-measured with a full `-t .`/no-`-t .`
  `unittest discover` run and a separate `TestLoader().discover(...)
  .countTestCases()` cross-check, agreeing.

  **A first attempt at this measurement was discarded, not corrected.** Running
  the `-t .` and no-`-t .` full suites at the same time against the same
  checkout reported 2896 / 2102 / **20** / — the twentieth failing import being
  `test_check_all`, which is not one of the 19 named above. Its failure trace
  pointed at `_tmp_root_is_case_insensitive()` (module-level, evaluated at
  import time), which writes a FIXED filename into the shared system temp
  directory and unlinks it in a `finally` — two concurrent interpreters racing
  the same path, one's `unlink()` running after the other's already removed it.
  Killed both runs, re-ran them one at a time (`test_workitems_cli.py` has the
  same shape of hazard — it writes a fake provider into
  `scripts/lib/workitems/` at runtime and cleans it up, so it does not tolerate
  a second run beside it either): `test_check_all` dropped out of the error
  list on both flags, back to the expected 19. The suspected cause was removed
  and the effect went with it — the control that turns a plausible diagnosis
  into a measured one (this repository's own rule against arguing conformance
  instead of running it, applied to itself). Not a defect in this ticket's own
  changes; a pre-existing, unrelated hazard in `test_check_all.py`, out of
  scope for CCP-1174 and left unfixed here, reported to the PO instead.

  10.09.2026, same day (CCP-1174 code-review follow-up: a filesystem-independent
  regression guard on the `-ef`-vs-case-folding-compare choice, plus one
  `@skipUnless`-gated supplementary test meaningful on a case-sensitive
  filesystem): **2899 / 2143 / 19 / 756** — +3 on both totals, all in
  `test_install_provenance.py` again (no relative import, cancels out of
  skipped the same way); modules-fail unchanged. The skipped-test COUNT (a
  different figure from this pair's own "skipped" column, which counts tests
  that never execute without `-t .`) moved too:
  `scripts/tests/test_platform_conditional_skip_budget.py`'s pinned budget
  went 0 → 1 contributed on this machine, registering the new
  `@skipUnless`-gated class the same way its docstring requires every
  platform/toolchain-conditional skip to be accounted for — re-derived via
  its own `expected_skip_count()`, not hand-typed, and confirmed by two
  mutation probes (a wrong per-source count, and an unregistered file) both
  still failing loudly afterward. Re-measured with a full `-t .`/no-`-t .`
  `unittest discover` run and a separate `TestLoader().discover(...)
  .countTestCases()` cross-check, agreeing; both runs sequential, not
  concurrent, per the previous entry's own lesson.

  11.09.2026 (CCP-1177: the link lint stops reading `create --checked-against`'s
  recorded dedup-evidence line as claimed relations): **2916 / 2145 / 19 / 771** —
  +17 with the flag, **+2 without it**, and the difference is the point: 15 of the
  17 are `scripts/tests/workitems/test_workitem_lint.py`'s new
  `DedupEvidenceLineTest` (12) and `DedupEvidenceComposerDriftTest` (3), and that
  module lives in the subpackage that cannot be imported without `-t .`, so they
  land in the skipped column instead (756 → 771, +15). Two of the 15 came from
  code review rather than from the ACs (a mixed linked/unlinked evidence line, and
  a pin on the shape-not-provenance limitation). The other 2 are
  `test_workitems_cli.py`'s end-to-end pair, which executes under both flags and
  therefore cancels out of skipped. Modules-fail unchanged at 19 — no new module.
  Both figures re-measured with `TestLoader().discover(...).countTestCases()` under
  each flag rather than added to the row above: the +17/+2 split is what a
  measurement shows and arithmetic on a single total would have hidden.
- The full run takes **a couple of minutes**. If you drive it from an agent whose
  tool calls time out, start it in the background and wait for it once rather than
  polling.
- **A single, scoped module can already exceed a short default tool timeout.**
  Many agent tool-call defaults sit around 120 seconds; a tool that is not told
  otherwise moves an overrunning call to the background automatically, which
  is easy to mistake for the agent choosing to run in the background against
  an explicit instruction not to (CCP-1145 — observed twice in one session).
  `scripts/tests/test_manual_lint_check_g.py` alone, run the scoped way this
  section recommends
  (`python3 -m unittest discover -s scripts/tests -t . -p
  'test_manual_lint_check_g.py'`), measured **173.7 seconds** on this machine
  (08.09.2026); `check-all.sh` itself, which runs the whole suite as one of
  its checks, takes the whole-suite time above on top of every other check.
  Set an explicit timeout comfortably above the module you are running,
  rather than the tool's own default.
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
| `scripts/manual-lint.sh` | `handbook/` index↔detail contract: `parent_index`, back-links, `kind`, and marked numbers against the value derived from their glob |
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
frontmatter schema in `templates/PHASE_DOC_SCHEMA.md`. Documents under `handbook/`
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
