# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/) — see [docs/adr/ADR-0001-versioning-and-distribution.md](docs/adr/ADR-0001-versioning-and-distribution.md) for the version-scoping rules in this meta-repo context.

> Development before this public GitHub release happened in a private repository. This changelog starts fresh at the first public version; the detailed pre-public history is retained privately.

## [Unreleased]

### Added

- **The catalogue's own size stopped being typed, and `install.sh --verify` became the ninth
  check.** The two are one change on purpose: adding a ninth entry would have meant retyping a
  number word by hand, which is the sixth instance of the register-drift class — and the first
  that could be seen coming. That made it the strongest available red proof for the mechanism
  added earlier in this release: a number derivable from the catalogue, typed instead.

  **The count was larger than either estimate.** A tree-wide sweep found **15 live sites** of
  the catalogue number and **14 derived ones**, across six files. Both earlier counts had been
  narrowed the same way — by a pattern requiring the noun `checks`, which misses `eight
  commands`, `one of the eight`, and `all eight from being attempted`.

  **Derived numbers are caught, not merely named.** The forbidden set is generated from the
  catalogue arrays rather than typed: catalogued, sibling-script, CCPR-only, generic. That
  covers "the other seven checks" (N−1, at eight sites) and the generic/CCPR-only split, which
  `install-verify` moves from 4/4 to 4/5 — three sentences that would have become false.
  Ordinals are deliberately excluded and said to be: they name a position, and appending moves
  none.

  Every site was measured for whether the number carried anything, and none did. `Seven of the
  eight checks are shipped SIBLING SCRIPTS` became `A catalogued check is normally a shipped
  SIBLING SCRIPT`, killing N and N−1 at once. The informing number is in every run's own
  report, where it is current by construction.

  One site was in no list: the baseline header claimed **Three** entries are
  environment-independent, wrong since ShellCheck gained its own could-not-run state.

  **The could-not-run branch looks redundant and is not.** Unlike the other three,
  `install.sh --verify` makes its could-not-run visible in the exit code (3). But `check-all.sh`
  compares any unrecognised exit code against the baseline, so without the branch a run that
  compared *nothing* would be reported as a **divergence** — "we looked and found a problem",
  for a check that never looked. The red proof pairs the report sentence with a non-zero exit
  so the classification demonstrably comes from the text, and the counter-proof pairs the same
  exit code *without* the sentence and expects an ordinary divergence.

  The entry uses a new catalogue kind parametrised by the project directory rather than the
  script directory: `install.sh` sits one level *above* the directory the test seam replaces,
  so `$CHECK_SCRIPT_DIR/../install.sh` would have escaped the scratch tree and run the real
  installer against the real `$HOME`. **A third home neither earlier option contained** — the
  entry in `0b3617e` recorded that both *proposed* homes were blocked, which was true; this is
  not one of them, and needs no new script.

  Two exemptions were built and removed on measurement. A date rule would have been *reachable
  and wrong* here — one file names a date and the live catalogue number in the same sentence —
  where the same exemption in the earlier slice was *unreachable*. And the earlier slice's
  quote-stripping, ported over, took the candidate property away from two of four pass fixtures,
  so they would have passed for the wrong reason; the prose was reworded instead.

- **`install.sh` records where it installed from, and `--verify` checks whether that still
  holds.** A measurement in this round needed to state what `~/.claude/commands/` actually
  *is* before it could say anything about it, and the only way to establish that was a hand
  comparison of all 116 files. It worked — **by luck**: `commands/` happened not to have been
  touched since the install. Had it been, nothing on disk could have said which state was
  installed. Same provenance logic as the check baseline's dropped header line, one layer
  outside the repository.

  The marker carries what it can support, and no more. A bare commit SHA would be a false
  claim when the source tree was dirty, so `source_state` qualifies it rather than replacing
  it — what was installed is that commit *plus* uncommitted work. A source that is not a git
  repository gets **no** `source_commit` line at all rather than an invented one, and the
  guard for that is a physical-path comparison of `rev-parse --show-toplevel` against the
  source, because `git rev-parse` walks upward and an unpacked copy inside someone else's
  checkout would otherwise inherit that checkout's HEAD.

  **`--verify` answers two questions and keeps them apart**, because they are routinely
  confused: *origin* is read from the marker and measures nothing; *present state* compares
  the installed files against the recorded commit's tree. A user can edit `~/.claude` by hand
  without the marker changing.

  **Six doors lead to could-not-run and none of them to a pass:** no destination, no marker,
  unreadable marker, non-git source, dirty source, recorded commit absent here, or an empty
  comparison scope. The message says *"Nothing was compared. This is NOT the same as 'no
  divergence'."* Every installation made before today takes the second door.

  Both proposed homes for the check were measured and both were blocked: a ninth catalogue
  entry needs a new tracked script, and an untracked one fails the executable-bit check that
  reads the git index; a plain unittest module would have had to express could-not-run as a
  skip, which runs vacuously green on CI — the fail-open shape. `--verify` lives in
  `install.sh` because the destination resolution, the framework list and the allowlist are
  already there; a second script would have been a second copy of them.

  Red-proven in all three directions separately — marker matches, marker does not match,
  marker absent — and nine structural mutations, each with its substitution count asserted
  first. One finding out of that: the divergence test does **not** catch a mutation that
  swaps the recorded commit for `HEAD`, because in that fixture the mutated commit *is* HEAD.
  Only the clean-verification test catches it. The docstring had claimed otherwise.

- **The nine portability findings now say why they work, at the place where they work** (R3).
  All nine are `||` fallback chains rather than `uname` branches. Until that is written down, the
  next reader takes the chain for intent and builds on it — which turns a reported finding into
  an inherited assumption.

  **They are two unequal groups, and each instance was measured rather than the class.** Seven
  `date` sites are genuine portable idioms: `date -v` is an *invalid option* on GNU, `date -d`
  on BSD, so the wrong side fails loudly with a non-zero exit and empty stdout, and the chain
  works as intended. Verified end to end on a machine carrying both implementations, with the
  shipped functions run under a GNU-first PATH: `fm_date_to_epoch "16.05.2026"` returns the same
  epoch either way.

  **The two `stat` sites are not, and the measurement is worse than the finding claimed.**
  `stat -f` is a *valid* GNU option meaning something else entirely (`--file-system`), so GNU
  never rejects the flag. The chain falls through only because GNU then reads the format string
  `%Lp` as a second file operand that does not resolve — while writing a real filesystem block
  for the first operand to stdout. Demonstrated on the shipped function, not reconstructed:
  under a GNU-first PATH `_fm_preserve_mode` restores mode 755 correctly; create a file
  literally named `%Lp` in the working directory and the same call returns 600, because the
  fallback never fires. The marker says `stat-f-guard-is-an-operand-accident`, and the comment
  above the function, which previously called the chain *portable*, now says it holds by
  accident.

  The exemption form is itself checked, because an exemption list nobody verifies is the next
  drifting skip list — this repository has had four. A marker with no reason does not exempt;
  the exempted set is pinned as a **set** of `(path, line, rule, category)` so a swap of two
  categories is visible where a count would not be; and a marker pointing at a site with no
  finding is itself a finding, built after the sibling guard that already does this for the
  absence-only register.

  **A blocking discovery on the way:** without extending marker sight to the *logical* line, the
  second limb of any backslash-continued chain cannot be marked at all — a comment on a middle
  line eats the rest of the command. One mutation survived and was measured rather than assumed:
  a loosened grammar produced byte-identical output because the empty capture is falsy at the
  only decision point. An equivalent mutant, not a gap, and recorded as such.

- **The agent lint now checks the memory-frontmatter contract** (R4). A `code-reviewer`
  subagent wrote a silo file without frontmatter, `memory-lint` went from exit 1 to exit 2, and
  `check-all` reported a divergence on a change that had nothing to do with it. Structural, not
  incidental: an agent produces an artifact that violates the project's own lint, in an area CI
  cannot see — `docs/memory/` is gitignored and `memory-lint` reports could-not-run on a runner.

  **The obvious rule would have missed the trigger.** `agents/code-reviewer.md` already names a
  frontmatter contract — the *global* Tier-2 silo's (`scope: tier-2-global`). The file that
  broke sat in the *project* silo, whose contract is `templates/MEMORY_SCHEMA.md`. Measured
  across the fleet: **fifteen of fifteen** agents named the global contract, **zero** named the
  project one. So the rule keys per silo, not per agent.

  Built as **one rule with two triggers** rather than two rules, because the schema prescribes
  the same required fields for both tiers — two rules would have restated one obligation over
  overlapping sets. Neither trigger contains the other, which was measured rather than assumed:
  the own-silo trigger covers eleven agents, the Tier-1 trigger thirteen, and `project-guide`
  is caught only by the first while four others are caught only by the second. The first
  assertion written was that one set contained the other; it went red immediately.

  Two further rules came out of the same measurement. A body that directs a **write** while the
  frontmatter grants no write tool is now refused — `wingman` was doing exactly that, and its
  fix is a prose correction with a test pinning that its `tools:` line is **unchanged**, so a
  later "fix" by granting the tool cannot pass as the same repair. And Rule 5's tool-name match
  was opened to case, which catches `qa-tester`'s "Use bash to run existing tests" against a
  frontmatter without Bash. That opening was measured before and after: over the whole corpus
  the strict and the widened pattern disagree on **exactly one** file — the real finding.

  Found while building it, and fixed: a **second `unittest.main()`** in the middle of the test
  module, left by an earlier wave. Under `python3 -m unittest` it was inert; run as
  `python3 <file>` it ended the run there, loaded only rules 1–4, and reported **OK**. A check
  that reports success while checking a fraction of its subject is the defect class this
  repository keeps removing, and it was sitting inside the lint that removes it.

- **A mechanism against register drift, instead of a seventh sweep** (R1). A *register* is
  any place that records a claim about the state of something else — a docstring about its
  own test's outcome, a file header about its data rows, a list about open findings. Six
  instances in a fortnight: nine ADR follow-ups that outlived their answers, a module
  docstring claiming "red" against a green tree, a findings list that counted eleven and
  omitted one, the baseline note counts (four times in three days), `check-all.sh`'s header
  against its own baseline, and four closed findings still listed as open. Every other defect
  class in this repository has been given a procedure; this one had been given six sweeps and
  no mechanism.

  **The inventory came first, and it narrowed the answer sharply.** Of every claim kind a
  register carries, exactly one is derivable with no measurement at all: *a check in this
  repository, as it ships, is failing right now*. A green suite refutes that outright, so it
  is generated rather than stored. Note counts, work-item status and open-findings lists each
  need their own generator and are **not** covered — and, decisively, all three of those
  registers (`docs/HANDOVER.md`, `docs/.handover-archive/`, `docs/workitems/`) are
  **gitignored**, so a shipped test cannot reach them in an adopter's repo at all.

  `scripts/tests/test_live_status_claims.py` requires **four** conditions together: a
  *now-anchor* (`today`, `the real tree`, `at HEAD`); a *present-indicative failure predicate*
  (`is`/`are` immediately before `red|failing|broken`); quoted and emphasised spans stripped,
  since a sentence in quotation marks is being *shown* rather than made; and a self-referential
  subject somewhere ahead of the copula. Dated history is let through **structurally** rather
  than by exemption — a dated sentence anchors to its date and never satisfies the now-anchor.
  A date-pattern exemption was written first, **measured unreachable, and deleted**: a branch
  that never executes is not a guard, it is decoration that will be trusted later.

  **The last two conditions were not in the design; they were forced by the check's first
  contact with new prose.** Written with the first two alone, it went red on three sentences
  written within the hour — all three describing or quoting the check itself, none asserting
  anything. So the normal act of documenting the mechanism violated it. Neither remaining
  condition was sufficient alone, measured against all five real instances: subject-anchoring
  alone still caught the sentence whose *quoted example* contains its own self-reference, and
  quote-stripping alone still caught the docstring that describes the rule in plain words.
  Narrowing them was not free and the cost is written down: a named but non-self-referential
  subject — "the conformance check is broken today" — is no longer caught.

  Red-proven in **both** directions against the real tree, not fixtures. Caught: two sentences
  in `test_agent_frontmatter.py` claiming that module's Rule 5 check "is RED today" while it
  ran 26 tests green — the drift was live and tracked at the moment the check was written. Let
  through: three real sentences elsewhere in the suite, each first asserted to be a genuine
  candidate, so the pass is attributed rather than merely observed. Five mutations, each
  proven landed by occurrence count; dropping the now-anchor turns all three history fixtures
  into false positives.

  Correcting the drifted docstrings surfaced a second, smaller one: the original said F9
  touched **three** agents. Run across the fix boundary it was **four** —
  `security-master.md` was resolved by *gaining* the tool rather than by losing the prose, so
  it left no body change to notice. A replacement register is a new claim and was measured
  like one.

- **A scanner for BSD/GNU coreutils divergence** (WI-0130). Three instances of one class
  turned up in a single week: `mktemp` with a suffix after `XXXXXX` (BSD substitutes only a
  *trailing* run of X's and returns the template literally), `find -printf` (GNU-only), and
  `stat -f` (on GNU an entirely different mode — it does not fail, it silently returns
  nonsense). The third shape is the dangerous one: a failure wearing the costume of a success.

  **The justification is measured, not assumed.** ShellCheck ran clean at `--severity=warning`
  over all 22 shipped scripts *while two defects of this class were live*. The eighth check
  does not cover it. And the correct `uname` pattern already existed twice in the tree — a
  pattern applied by hand in several places with one place forgotten is what a scanner closes
  and a fix does not.

  Eleven constructs adopted, each recorded with **which side is silent**; six rejected with
  reasons, because a list that names only its hits hides its own shape. `xargs -r` is the
  instructive rejection: the divergence lives in the flag's *absence*, so a rule matching `-r`
  would flag the compatible spelling and miss the incompatible one.

  "In sight" of a `uname` guard is the enclosing function body, or ten lines at top level with
  function bodies subtracted — the boundary both correct shipped instances already respect. A
  `||` fallback chain is explicitly **not** an exemption, and that is measured rather than
  stylistic: the founding defect *was* such a chain, and a chain only guards constructs that
  fail loudly, which half this list does not.

  Red-proven against the real history rather than against rebuilt examples: the pre-fix
  `log-cleanup.sh` and `run-tests.sh` are reported at exactly the defective lines, and the
  three *correct* `mktemp` calls in the same file are asserted **not** reported — the sharper
  half, since it shows the rule matches the shape and not the word.

  Twelve structural mutants, of which **one initially survived** although a test named for
  exactly that property existed and passed: its fixture could not discriminate, because the
  paired rule had only one flag to key on. The test named the right thing and proved nothing.
  Recorded because that is what a mutation battery is for.

  It reports **nine findings on today's tree, deliberately not repaired** — each needs its own
  round and its own red proof. Two of them work today only through luck of an exit status,
  which the scanner cannot check and a reader should not have to infer.

- **The project template's document tree now names every file a command writes** (finding
  #18). `templates/PROJECT_CLAUDE_TEMPLATE.md`'s `docs/` tree is what a new project copies to
  learn its own layout, and it omitted six documents that shipped commands produce:
  `architecture/API_SPEC.md`, `planning/SETUP.md`, `planning/DOCS.md`,
  `quality/EXPLORATORY.md`, `quality/BUGFIX.md` and `launch/PREPARE.md`. The finding named
  only the last one; the other five turned up when the tree was held against the commands'
  own `## Result` sections rather than against the one reported case.

  The expectation is derived from the **producers** — each command's statement about the file
  it writes — not from `scripts/gate-preflight.py`, which is a hand-maintained consumer list
  exactly like the tree. Two consumers agreeing proves only that they were copied together.

  The test states what it does **not** claim, because both limits were measured. The reverse
  direction ("the tree names something no command writes") produces 24 false positives, since
  only 49 of 116 commands carry a parseable `## Result` section — so only producer → tree is
  asserted. And the six `GATE_P<N>.md` artifacts are excluded deliberately: the string `GATE_`
  occurs **zero** times in the whole template, at 6 of 6 gate files, which is a consistent
  omission rather than a hole. That premise is itself asserted, so the exclusion fails loudly
  if a gate file ever appears in the tree instead of quietly widening.

  Red-proven three ways: deleting a name (presence), and — because a flat name-list check
  survives that — **moving** one between two folder rows, where the multiset of all names is
  unchanged and only the mapping breaks. Plus the historical proof: the pre-fix template fed
  through the parser returns exactly the six.

- **This repository has CI** (WI-0129, finding F11 — the last one that was open). Until now
  nothing but a person ran the test suite: `.github/` held only issue templates, `.git/hooks/`
  only samples, and there had been **zero** workflow runs. With a second person working on the
  repo, the runner is the only instance both can measure against without "it works on mine"
  ending the discussion.

  Two jobs, and deliberately neither a superset of the other (ADR-0011, decision 4).
  `ubuntu-latest` runs the bash-4-shaped tests in `test_memory_sync_promote.py` that macOS's
  `/bin/bash` 3.2 skips; `macos-latest` is the only place the 3.2 floor and BSD-vs-GNU userland
  differences are exercised at all. One of the latter had already cost a real defect before this
  CI existed — BSD `mktemp` returning a suffixed template literally.

  Two things in here are easy to lose to a later tidy-up, so both are asserted rather than
  commented. **`fetch-depth: 0`**: `test_agent_frontmatter.py` pins a commit 45 behind `HEAD` and
  reads it through `git show` with `check=True`; `actions/checkout`'s default of 1 makes that
  test *error*, not merely fail. **The bash version**: the shebang does not carry the floor —
  every script starts `#!/usr/bin/env bash`, so `PATH` decides, and a runner image with a newer
  bash ahead of `/bin` would silently verify bash 5 behind a green badge. The job forces `/bin`
  to the front of `PATH`, calls `/bin/bash` explicitly, and its **first** step prints the
  resolved interpreter and fails unless it starts with `3.2`. The PATH forcing is not redundant
  with the explicit call: `check-all.sh` invokes its sibling scripts as `bash $script_path`,
  which is what actually needs the resolution.

  `test_ci_workflow.py` guards all of it by **mutation**, not by presence: `fetch-depth` weakened
  to 1, removed, or stripped of its justifying comment; the assert step missing, softened to
  `exit 0`, or moved after checkout; `continue-on-error` or a bare `|| true` anywhere; the two
  jobs drifting to different Python versions. Its own first red run is worth keeping: the
  workflow header explains the no-swallowed-failures rule *by naming* `continue-on-error` and
  `|| true`, and the checker flagged its own explanation. It now reads operative lines only.

  What only a real run can settle is recorded in the file so it gets read rather than assumed:
  whether a Homebrew bash actually precedes `/bin` there, whether `GITHUB_PATH` behaves as
  expected, and whether `check-all.sh` reports the 5-matched/2-could-not-run shape measured
  locally. A macOS run reporting 8/8 would be the surprising result, not the expected one.

- **ShellCheck is the eighth catalogued check** (WI-0129). It ran nowhere, although ten sites in
  this repo already carry `# shellcheck` directives, and it would have reported F8's unquoted
  arguments on its own instead of leaving them to an external review.

  The threshold decided the shape. `check-all.sh` compares **exit codes only**, so a baseline of
  1 would be blind to the next finding — 62 and 63 sites both exit 1 and both count as "match".
  Only a baseline of **0** catches anything. Hence `--severity=warning` with the 30 findings
  cleared, rather than `--severity=error` (zero findings today, but that level catches neither
  the `install.sh` find below nor the F8 class).

  Each disposition was decided, not batch-silenced: seven genuinely dead variables removed; the
  14 `SC2088` in `memory-lint.sh` suppressed **individually** rather than file-wide, because
  they sit in human-facing message text where the tilde is deliberate and a file-wide directive
  would also hide a future real one; and one real find — `install.sh:346`'s
  `rm -rf "$DEST/$p"`, in an installer, now `${DEST:?}` with a test proving it aborts on an empty
  variable instead of deleting.

  `scripts/shellcheck-run.sh` wraps the external binary, because the catalogue invokes sibling
  scripts rather than tools, and it reports its own missing scope the way `memory-lint`,
  `conformance-run` and `artifact-gate` now do: on a machine without ShellCheck the check is
  could-not-run, never exit 0. Not hypothetical — it was not installed here until this work, and
  is not on any clone.

- **ADR-0011 records that bash 3.2 stays the floor.** The constraint was real and enforced —
  a static guard test finds zero bash-4 constructs in the shipped scripts, and a dozen inline
  comments name it where it costs something — but it had never been written down as a decision.
  A CI forces the question, because choosing only `ubuntu-latest` would have made bash 5 the
  de-facto floor by omission.

  Writing it down turned up something that changes the reasoning: **the shebang does not carry
  the floor.** All 26 scripts use `#!/usr/bin/env bash`, so `env` takes the first bash on `PATH`.
  On the maintainer's machine that happens to be `/bin/bash` 3.2.57 — the floor holds by accident
  of environment, not by construction. So the floor is a promise about which language *features*
  the scripts use, not about which interpreter runs them; the static guard is the enforcement,
  and the CI has to measure the interpreter it actually got.

- **The instinct sampler and the shipped index are now checked against each other** (WI-0129,
  finding F14, the part that stayed open). CCPR ships its starter instincts in two shapes —
  `instincts.md`, the 45-entry split-layout index, and `templates/STARTER_INSTINCTS.md`, a flat
  13-entry sampler for adopters who prefer one file — and nothing compared them.

  They agree today; this pins that rather than repairing it. The reason it is worth pinning is
  that `/postmortem` **deletes** instincts when confidence decays to 0.3 — three went in the most
  recent round alone. A sampler entry naming an instinct the full set has dropped would point an
  adopter's entry point at something that no longer exists, and nothing would have noticed.

  The test parses **entries**, not mentions: the index's `- G-NNN` bullets and the sampler's
  `### G-NNN` headings. That distinction is the whole difficulty — both files also name instinct
  IDs in prose, the index alone listing ten under "Intentionally NOT in this starter set", and a
  naive ID grep counts 55 and 24 instead of 45 and 13. Those ten are pinned as excluded, so a
  future parser that starts counting mentions fails loudly instead of quietly agreeing with
  itself.

  **What it does not close, stated in its own docstring**: the defect that actually occurred was
  in neither file. `CLAUDE.md` characterised the relationship between them wrongly while every
  number it gave was correct. No structural test sees that. This closes the drift class — an ID
  that stops existing, a count that moves unnoticed — and leaves the description class where it
  belongs, with a reader.

- **`scripts/check-all.sh` — one command for the seven quality checks, compared against a
  versioned baseline.** `CONTRIBUTING.md` asked a contributor to remember seven separate
  commands and to know, from prose, which of them are *supposed* to fail. Nothing recorded
  those expectations in a form a machine could read, and nothing noticed if a check was
  skipped entirely.

  **The design point is that exit zero is not the pass criterion.** Measured on this
  repository at the time: `memory-lint.sh` exits 1 and `doc-volume-check.sh` exits 2 on a
  perfectly correct tree. (`doc-volume-check.sh`'s expected exit became 0 later in this same
  release, when it was scoped to git-tracked files — see the entry below. The reasoning is
  what survived, not the pair of numbers.) A collector that failed on any non-zero result would be red from its first
  run, and a check that is red when nothing is wrong is ignored within a fortnight. So each
  check's expected exit lives in `scripts/check-all.baseline.tsv` and the script reports
  agreement or divergence with it, naming both numbers.

  A check that **could not run** — no consumer projects configured, or no `scripts/tests/`
  because the script is running from an installed `~/.claude` — is a third state, counted
  separately and never folded into the matched count. Reporting no scope as a pass is the
  defect this repository has already fixed twice elsewhere.

  The baseline is a tab-separated file under `scripts/`, deliberately not a `docs/.<name>`
  dotfile: that prefix means "volatile, gitignored" here, and a baseline the next contributor
  never receives is not a baseline. It declares expectations only — the catalogue of what to
  run stays in the script, so the data file can never become a second, executable register.

  It found real drift on its first honest run: adding two shipped files moved six hand-typed
  inventory pins in four other test modules. Each was re-measured rather than adjusted, and
  one of them mattered — the exit-status scanner's `bare-needs-exemption` bucket grew by two,
  and in that module the count *is* the guard, so a blind bump would have waved through two
  unchecked exit statuses. They turned out to be a `sed | sed` pipeline under
  `set -euo pipefail` carrying a valid `set-e-sufficient` marker; the reasoning now sits in a
  comment beside the number.

  Also corrected while documenting it: `CONTRIBUTING.md` claimed the suite collects **1691
  tests** with `-t .` and 1185 without, across 14 failing modules. Re-measured: **1848 and
  1339, across 15 modules, 509 tests silently skipped.** All four figures were stale together,
  which is why the file now says to re-measure them as a set — 1848 on its own says nothing.
  The same paragraph's claim that `doc-volume-check.sh` "exits 2 on two agent-memory files"
  was stale as well; it is five critical findings, six warnings and eight info.

- **`agents/*.md` frontmatter is validated for the first time** (open finding #4, first half;
  WI-0128). On 27.08.2026 a shipped agent declared invoking `code-reviewer` MANDATORY in its
  body while its own `tools:` line lacked `Agent` — it could not do what its own instructions
  required. That was filed as a shipped-tree-versus-installed-tree divergence, because the
  maintainer's local copy carried the missing entry and hid it. Planning this check showed
  that to be the expensive reading of a cheap defect: the contradiction sat **inside one
  file**, between its frontmatter and its body, and needed no comparison against anything.
  Until now nothing read agent frontmatter at all — `scripts/lib/frontmatter.sh` exists but
  serves only the four lints over `docs/`, `Manual/` and `docs/memory/`.

  Four rules: the four required fields, `name` matching the filename, tool names against a
  closed snapshot, and the one that would have caught the defect — an agent whose **body**
  requires invoking another agent must carry `Agent`. Proven in both directions against the
  fixture in history: the rule fires on the pre-fix tool line and is silent on the fixed one,
  with the two bodies asserted byte-identical first so the comparison isolates the tools line.

  The body restriction is the whole rule. A first probe scanning each file whole reported nine
  of fifteen agents as violators — every `description:` field explains when a *reader* should
  launch that agent, which is not the agent invoking anyone. Scoped to the body, exactly one
  matches, and it is correct. The tool list is documented as a snapshot rather than a source of
  truth: CCPR cannot know Claude Code's tool set, so a new legitimate tool is meant to fail this
  test and be looked at. That has already earned its keep once, when `Task` was written for
  `Agent`.

  The tree comparison — repository against `~/.claude` against a project's own `.claude/agents/`,
  where `/specialize` copies once and never re-syncs — remains a separate, more expensive item.
- **Rule 3 of the conformance run had never been seen red** (open finding #10; WI-0128). It
  checks five mandatory report-skeleton lines across two branches — `**Anchors:**` and
  `**Last production-code commit:**` for `anchor`, and `**Files scanned:**`, `**Summary:**`,
  `**Exit:**` for everyone else — and since WI-0124 nothing had ever shown it reacts to a
  missing one. The guard could have been inert the whole time without a symptom.

  Each of the five now has its own proof: a stub omitting exactly that line, asserting the C1
  finding names it and only it, plus the other direction — a complete stub must produce no C1
  finding, or the rule would be firing always rather than discriminating. The two branches are
  proven separately, since anchor's two lines are not the generic three. The line list itself
  is parsed from the script rather than retyped, and pinned at 2 and 3, so a sixth line cannot
  arrive unproven.

  The proofs were then checked against a neutralised copy of the rule: with Rule 3 disabled all
  five fail, while the complete-stub test alone stays green — which is what makes the per-line
  proofs, not the reverse direction, the part that could detect an inert guard.

- **The absence-only scanner's two measured blind spots are described once, where its numbers
  are** (open findings #7 and #11; WI-0128). `_calls_a_subprocess` recognises `self.<name>(...)`
  but not a bare module-level helper, and `_is_stdout_like` follows only one hop from `.stdout`,
  so an assertion whose subject comes through a chained `split(...)` is invisible. Both were
  already recorded, in two different places; they share one root cause — each function knows
  exactly one syntactic shape — and the consequence belongs beside the pinned counts: they
  certify what the scanner can see, not what exists. The scanner itself is deliberately not
  widened; its recognition rules are pinned by those very numbers, and changing them is a
  separate decision.
- **Per-entry coverage for the three phase-folder lists (WI-0126, tranche 1)**. An entry in an
  enumerated list with no test of its own is an unverified claim wearing the credibility of its
  neighbours: `PLACEHOLDER_NAMES` shipped with tests for two of its three names, and a typo in
  the third would have passed the entire suite. Measured before this change, the string `launch`
  appeared **zero** times in the whole test suite, five of the nine phase folders were never used
  as `docs/<folder>` anywhere, and nothing swept `PHASE_FOLDERS` (`phase-docs-lint.sh`),
  `PHASE_FOLDER_NAMES` (`conformance-run.sh`) or `PHASE_SCOPES` (`anchor.sh`) at all. All three
  lists are now parsed **out of the shell source** and swept per entry, so a new entry joins the
  sweep by itself, with a count pin in each so a removed one turns the sweep red instead of
  letting it quietly shrink. `PHASE_FOLDER_NAMES` additionally gets an automated per-entry
  mutation proof against a scratch copy. The duplication between `PHASE_FOLDERS` and
  `PHASE_FOLDER_NAMES` — verbatim, in two files, with nothing noticing a divergence — is now
  bound by a test. `reviews` is in the first two lists and deliberately not in `PHASE_SCOPES`;
  that asymmetry is pinned with the reason `anchor.sh` gives for it, rather than left silent.

- **Per-entry coverage for the three enumerated lists in `next_steps.py` (WI-0126, tranche 2)**.
  `PHASE_SEQUENCES` (9 phases, 50 commands) drives `get_allowed_commands` — its one real
  consumer — and was missing from the audit that raised WI-0126 in the first place;
  `scripts/command-check.py` imports the name alongside it but never references it again (a dead
  import, recorded as a finding rather than fixed here — editing a shipped script is outside this
  module's write boundary). `GATE_TRANSITIONS` (8 entries) is derivable from `PHASE_SEQUENCES` per
  its own comment ("gate -> first command of next phase") and nothing tested that derivation.
  Both now get a per-entry existence sweep (against a real `commands/<name>.md`) plus a literal
  count pin (50, 9, 8); the removal proofs for both patch the real, already-imported dict object
  in place (`unittest.mock.patch.dict`, restored on exit) and confirm the shipped
  `get_allowed_commands` reacts to the mutation — the same evidence strength as tranche 1's
  scratch-file proof, exercised on a plain Python constant instead of shell text to regex out.
  The `GATE_TRANSITIONS`-to-`PHASE_SEQUENCES` binding (invariant B) is now a test, computed from
  `PHASE_SEQUENCES` rather than retyped, alongside a pin for invariant A (`p0`-`p7` each end their
  own sequence with their own gate; `p8` has none). `UTILITY_COMMANDS` (8 entries) is measured
  dead — `grep -rn "UTILITY_COMMANDS"` across every `.py`, `.sh` and `.md` in the repo returns
  only its own definition line — so it gets a vocabulary pin (each name has a real command doc,
  count pinned at 8) with a docstring stating plainly that no behaviour depends on it; its removal
  check stays an in-memory length formula, not a shipped-code-reacts proof, because there is no
  consumer to react — a weaker, explicitly disclosed evidence strength, not the same as the two
  patched-dict proofs above. New module `scripts/tests/test_next_steps_lists.py` (19 tests), kept
  separate from the pre-existing `test_next_steps_placement.py`, whose scope is a single narrow
  parser-anchor fix (WI-0024) and has nothing to do with these three lists.

- **`quality-scan.sh`'s three disagreeing SKIP_DIRS tuples unified, and per-entry coverage for its
  producer contract (WI-0126, tranche 3a)**. `scripts/quality-scan.sh` has **four**
  `os.walk("src")` call sites, not three: the CORS wildcard scan, the PII-in-logging scan, the
  DSGVO consent-mechanism scan, and a fourth, unfiltered counting walk
  (`src_files = sum(1 for r, d, f in os.walk("src") for _ in f)`) that gates whether the consent
  finding fires at all. Only the first three carried an inline skip tuple, and two of the three
  lacked `venv` — including two loops in the SAME Python heredoc that still disagreed with each
  other. PO decision (28.08.2026): unify those three skip *lists* on the superset including
  `venv` — walking a virtualenv for either signal is third-party noise, never a real finding about
  the project's own code. The fourth walk has no directory filter at all and was deliberately left
  alone; filtering it would change *when* the consent finding fires, a second, unapproved
  behaviour change (see the "report, not fixed" paragraph below). Each of `quality-scan.sh`'s two
  heredocs now defines its own `SKIP_DIRS` constant (they cannot share one definition — both are
  independently quoted heredocs, and unquoting either to share a name would let the shell expand
  `$`-prefixed tokens inside the Python body; a third option, one `export`ed shell variable read
  via `os.environ` in both heredocs, was considered and declined as more machinery than
  duplicating a four-tuple warrants). Measured before/after with a scratch-copy mutation that
  reverts only the CORS and consent walks to their pre-fix tuples: before, a `src/venv/` fixture
  produces a CORS finding and, more subtly, SUPPRESSES the "no consent mechanism found" finding by
  reading venv noise as the project's own consent handling; after, neither happens.

  Separately, `SEVERITIES`, `COMPLETED` and `HANDLERS` — three constants inside the
  `TOOL_REPORT_PY` heredoc that WI-0055/WI-0102 already hardened — had never been referenced by
  name in `test_quality_scan.py`. `COMPLETED` (4 entries) and `HANDLERS` (4 entries) must share
  the same key set: `read_tool()` checks `kind not in HANDLERS` before it ever touches
  `COMPLETED[kind]`, so a producer present in one dict and missing from the other reaches an
  **unhandled KeyError**, not a `scan_error`, a mutation now measured directly (removed the entry
  from a scratch copy of the extracted heredoc source, confirmed the traceback). `pattern-scan`'s
  `COMPLETED` tuple is `("0",)` only, unlike the other three's `("0", "1")` — status `"1"` is
  legitimate for npm-audit/pip-audit/semgrep and an error for pattern-scan, the discriminating
  case a status-"0"-only sweep would never exercise. `SEVERITIES` (5 entries) feeds
  `findings_npm()`'s `buckets = [k for k in SEVERITIES if k in meta]`; a missing name is dropped
  from the total **silently** — the report still parses, the scan still exits 0, the count is just
  wrong — measured per entry against a report carrying all 5 buckets with only the target one
  non-zero. All three constants are extracted verbatim out of the shipped heredoc for every test
  (never retyped), run either as a real subprocess (the same argv contract `run_py()` uses) or
  exec'd into an in-memory namespace when only the data shape is needed.

  Report, not fixed (outside this tranche's PO decision and write boundary): the same three walks
  also filter FILES differently — the CORS walk accepts `.py/.js/.ts`, the PII walk accepts those
  plus `.jsx/.tsx`, and the consent walk filters by nothing at all and opens every file in `src/`.
  Separately, the fourth walk — the unfiltered counting walk that gates whether the consent
  finding fires (`if src_files > 2`) — has no directory filter either, so files under
  `node_modules`, `venv` and `.git` count toward "is there actual code": a project whose only
  files live in a virtualenv can trip the consent finding on venv noise alone. Also not fixed in
  this tranche, and not the same PO decision — filtering that walk would change when the finding
  fires, not just what noise a filtered walk skips.

- **Per-entry coverage for `quality-scan.sh`'s three content lists, plus a fifth skip list
  surfaced along the way (WI-0126, tranche 3b)**. `PII_PATTERNS` (`email`, `phone-de`, `iban`,
  `geburtsdatum`) and the DSGVO consent terms (`consent`, `cookie-banner`, `datenschutz`,
  `privacy-policy`) had **zero** references by name anywhere in the test suite; of the six config
  filenames (`config.json`, `config.yaml`, `config.yml`, `settings.py`, `app.config.ts`,
  `app.config.js`), only `config.json` was ever exercised. All three are now covered per entry:
  each PII regex is proven against a fixture built to trip only its own shape — `phone-de` and
  `iban` are permissive enough that a careless IBAN fixture containing a literal `"0"` digit also
  reads as a phone number, which would have collapsed the per-entry claim; each consent term is
  proven to suppress the "no consent mechanism found" finding alone, in mixed case, with the
  `src_files > 2` gate satisfied (a fixture with two files measures nothing — the exact way an
  earlier probe in this work item measured nothing); each config filename is proven to produce its
  own "debug mode possibly active" finding. All three get a real-subprocess removal proof (never
  an in-memory list rebuild) and a literal count pin (4, 4, 6).

  Auditing PII_PATTERNS's own skip-list comment surfaced a **fifth** skip list this item had not
  named: `scripts/lib/quality_scan_sast_patterns.py:66` carries its own inline `os.walk("src")`
  skip tuple, already `("node_modules", ".git", "__pycache__", "venv", ".venv")` — five entries,
  including `.venv`, before this tranche touched anything. Tranche 3a's PO decision to unify on
  "the superset" was taken over three lists; the true superset across all four is five entries, not
  four. `.venv` is added to both `SKIP_DIRS` definitions in `scripts/quality-scan.sh` — the only
  shipped-script edit this tranche is authorised to make; `quality_scan_sast_patterns.py`'s own
  tuple is untouched, since it was already the superset. Measured the same way tranche 3a measured
  `venv`: before, a `src/.venv/` fixture produces a CORS finding and suppresses the "no consent"
  finding by reading `.venv` noise as the project's own consent handling; after, neither happens.
  `SkipDirsDefinitionsStayEqualTest`'s length pin moves from 4 to 5, and a new binding test
  asserts the SAST module's skip tuple and `quality-scan.sh`'s two `SKIP_DIRS` definitions are now
  equal as sets — the point of the whole item: the next divergence between the fourth skip list
  and the other three is caught here, not discovered by a sixth tranche.

- **Per-entry coverage for the SAST pattern rules in `quality_scan_sast_patterns.py` (WI-0126,
  tranche 3c)**. `PATTERNS` (5 rules — `eval/exec`, `innerHTML`, `SQL-String`, `hardcoded-secret`,
  `console-log`) — four of the five (`innerHTML`, `SQL-String`, `hardcoded-secret`,
  `console-log`) had zero references by name in the test suite before this tranche. `eval/exec`
  is the exception, corrected here after an earlier claim (in this same entry) said otherwise:
  `pattern-eval/exec` was already asserted against the real pipeline in three places in
  `test_quality_scan.py`, but only for one extension and only on its rendered type string, never
  on severity, message, or its other two extensions. The earlier claim came from grepping the raw
  dict key `eval/exec`, which finds the key but not what the code emits — tests assert on the
  rendered value `"pattern-" + name`, not the key. Each rule now fires through the real `main()`
  on a fixture whose content is proven, by running every
  rule's regex against every fixture, to match only that rule — the module's own extension gate
  means only same-extension rules could ever collide, and the fixtures are built so none do. The
  sharpest gap named in the audit, per-rule `extensions` (19 entries across 3/4/1/7/4), is now
  covered both ways: a positive fixture per (rule, extension) pair, and the discriminating
  negative half — a rule's own matching content under an extension it does not claim (a real
  extension another rule DOES use, not an arbitrary unknown one) produces no finding for that
  rule, e.g. `SQL-String` claims only `.py`, so an f-string `SELECT` under `.js` stays silent for
  it. The removal proof mutates one extension entry out of a rule's real list via
  `unittest.mock.patch.dict` (never a full-list swap) and fires the real `main()`.

  The module's own docstring claim about a missing rule key — "no `.get`, so a rule missing one
  is an unhandled KeyError" — does not survive a run: `main()`'s own per-file `try/except
  Exception: pass` catches it. Measured precisely: since `PATTERNS.items()` iterates in a fixed
  insertion order on every line of every file, breaking the FIRST rule in that order
  (`eval/exec`) silently zeroes an entire file's findings, including that rule's own genuine
  matches; breaking the LAST rule (`console-log`) only loses findings from the point in each
  line's rule iteration where the break is hit onward, so an earlier rule's match on the same
  line survives. Either way `main()` exits 0 with a plausible, non-empty report — the caller never
  sees an error. Corrected and pinned as measured, not left as the briefing's original framing.

  Verified, not fixed: `quality-scan.sh`'s summary combiner explicitly buckets only `critical`,
  `high` and `warning` by name and assigns everything else to `info` by subtraction, while the
  separate npm-side `SEVERITIES` vocabulary in the same script legitimises `low` and `moderate`
  too — extracting the combiner's exact source (never retyped) and running it as a real subprocess
  confirms both would silently land in `info`. Today's three rule severities (`high`, `critical`,
  `info`) are all safe; PATTERNS uses neither `low` nor `moderate`. Also pinned, not closed: the
  documented "up to 50" findings cap (`findings[:50]`) — a run with exactly 50 matches and a run
  with 60 produce structurally identical output (a bare 50-item list, no per-item or top-level
  marker), so a consumer of this stdout cannot tell "exactly 50" from "at least 51 more". A full
  re-read of the ~90-line module found no other enumerated list beyond `PATTERNS` and the `:66`
  skip tuple tranche 3b already bound.

- **The alignment invariant across `conformance-run.sh`'s seven parallel check-table columns, plus
  per-entry coverage for the four still-uncovered ones (WI-0126, tranche 4)**. `CHECK_NAMES`,
  `CHECK_SCRIPTS`, `CHECK_SUBCMD`, `CHECK_ARG_SHAPE`, `CHECK_EXIT_SET`, `CHECK_C2_EXEMPT` and
  `CHECK_HAS_SUMMARY_LINE` (`conformance-run.sh:168-197`) are seven bash arrays aligned by
  POSITION only — bash 3.2 has no associative arrays. Only three of the seven had any test tying
  their lengths together (inside a parser helper, not a test of its own); `CHECK_SUBCMD`,
  `CHECK_ARG_SHAPE` and `CHECK_C2_EXEMPT` had **zero** references anywhere in the suite,
  `CHECK_HAS_SUMMARY_LINE` had exactly one, in a comment. Measured directly under this file's own
  `set -euo pipefail`: a column one entry SHORTER than its six siblings dies loudly (`unbound
  variable`, exit 1) the instant the classifier reaches the missing index — but a column
  TRANSPOSED to the same length runs to completion silently, with check N quietly getting check
  M's argument shape, exit set or exemption. A removal proof would therefore pass while proving
  the wrong thing; every per-entry proof for the four uncovered columns here is a swap in a
  scratch copy, not a removal, following G-109.

  `parse_check_exit_set_table`'s former private array parser is now a module-level helper shared
  by a new `parse_full_check_table`, which reads all seven columns and asserts they agree on
  length (5) — a scratch copy proves this fires both when a column is shortened by one entry and
  when an untied EIGHTH `CHECK_*` array is added, found by sweeping the whole file for the pattern
  rather than trusting this test module's own enumeration of seven names. `CHECK_SUBCMD` (only
  `anchor` carries `status`), `CHECK_ARG_SHAPE` (a 3/2 `project`/`docs` split), `CHECK_C2_EXEMPT`
  (only `anchor` is exempt) and `CHECK_HAS_SUMMARY_LINE` (only `anchor` lacks one) each get a
  transposition proof crossing their own asymmetry: `CHECK_ARG_SHAPE`'s and
  `CHECK_HAS_SUMMARY_LINE`'s swaps are clean two-sided flips (a Files-scanned:-0 report appears
  for both swapped checks; a self-contradicting report's C1 finding moves from one check to the
  other). `CHECK_C2_EXEMPT`'s swap is measured, not assumed, to be one-sided: gaining exemption
  silences a real finding for `memory-lint`, but `anchor` gaining non-exempt status changes
  nothing observable, because the independent C2 candidate probe (`_c2_probe_has_candidates`) has
  no `case` arm for `anchor` at all — a genuine, orthogonal double-guard, reported as measured
  rather than forced into a symmetric assertion the code does not support. `CHECK_SUBCMD`'s swap
  is the one end-to-end proof driving the REAL `memory-lint.sh`/`anchor.sh` (never stubs) against a
  real git-initialised consumer: memory-lint.sh reads only its own `$1` as the project directory
  (silently ignoring a stolen `$2`), so gaining a leading `status` token makes it scan the wrong,
  nonexistent directory instead of erroring — turning a populated consumer into a spurious C2
  finding; anchor.sh dispatches on its own `$1` as a subcommand name, so losing `status` makes the
  consumer's absolute path look like an unrecognised subcommand, landing it under Could-Not-Run.

  Enumerated (deliverable 5): `KNOWN_PIN_FIELDS` (5 entries: `exit`, `errors`, `warnings`, `info`,
  `filesScanned`, `:802`) already has genuine per-entry BEHAVIOURAL coverage via
  `PinFieldEvaluationTest`, even though the constant itself is never parsed from source by name —
  judged adequately covered, no new test added. The three inline known-key sets in the config
  reader (`{"consumers","pins"}` at the `conformance` level, `{"id","path","optional"}` per
  consumer, and the 8-key pin-object set, `:729/754/822`) each have a dedicated unknown-key
  rejection test, and their KNOWN members are transitively exercised by nearly every other test in
  the module — judged covered by the rest of the suite, not a fresh gap. `RESULT_*`, `CONSUMER_*`
  and `PIN_*` are runtime accumulators that start empty, as the briefing already named — out of
  scope. One genuine gap found and reported, not fixed (outside this tranche's four-column scope):
  Rule 3's two mandatory-report-line lists (`:580` anchor's own two lines, `:587` the generic
  three) have no test that removes ONE line from a stub report and confirms the classifier's own
  "missing mandatory line(s)" message names exactly that line — `RealCheckSkeletonTest` only pins
  that the REAL checks' output happens to include these substrings today, which is a presence
  check on real output, not a red proof of the classifier's own reaction to an absent one. Flagged
  as a candidate for a future tranche.

  **Round 2 — WI-0125's own absence-only guard fired on three of this tranche's new tests before
  commit.** `test_swap_flips_which_of_the_two_gets_the_c1_contradiction_finding` and
  `test_swap_turns_memory_lint_into_a_c2_finding_and_anchor_into_could_not_run` are measured
  scanner false positives, not real gaps: both derive a report-section variable through a chained
  `result.stdout.split(...)[i].split(...)[j]` and assert real, positive facts against it, but
  `_is_stdout_like`/`_stdout_bound_names` only track a name bound in ONE hop directly from
  `.stdout` — a fourth false-positive category, distinct from the three already registered, and
  recorded as `chained-stdout-slice-not-tracked-as-output` in `test_absence_only_assertions.py`'s
  `EXEMPTION_REASONS`/`KNOWN_FINDINGS` rather than widening the scanner itself (a decision outside
  this tranche's write boundary, same call as tranche 3c's module-level-helper blind spot).
  `test_anchor_gaining_non_exempt_status_measured_to_not_change_its_own_report` genuinely lacked a
  liveness assertion: measured directly, the mutated run's own exit code is 0 (both halves of the
  swap null out), so it now asserts that fact instead of relying on the section text alone.

- **The last five retyped copies converted to parse-from-source, each paired with a count pin,
  plus the binding this tranche was really for (WI-0126, tranche 5)**. A retyped copy and a
  parsed one have OPPOSITE blind spots: the retyped copy catches a shipped list SHRINKING (the
  test still expects the now-missing value) but not GROWING (a new value is simply never swept);
  a parsed one catches growth automatically but not shrinkage, unless it ships with its own
  count pin. `VALID_STATUSES`/`VALID_PHASES`/`LIVING_FILE_NAMES` (`test_phase_docs_lint.py`),
  `VALID_KINDS` (`test_manual_lint.py`) and `CHECK_FILENAMES` (`test_conformance_run.py`, now a
  direct binding against `parse_full_check_table()["CHECK_SCRIPTS"]`, whose own alignment
  invariant already supplies the count pin) are now parsed from their shipped scripts, never
  retyped — `test_frontmatter_examples_match_the_lint.py`'s own `_read_enum`, the first instance
  of this parser shape, is lifted into `test_phase_docs_lint.py` as `read_enum(varname,
  script_path)` so the other four reuse it instead of growing a fifth near-identical regex (a
  fourth and fifth file now need `-t .` on `unittest discover` — CONTRIBUTING.md's own documented
  set, up from three). Confirmed on a scratch copy for all four string-shaped targets: removing
  an entry breaks its count pin, adding one is picked up by the sweep with no test-file edit.

  The prize: `LIVING_FILES` is duplicated verbatim across two shipped scripts
  (`phase-docs-lint.sh:62`, `anchor.sh:67`) — deliberately, per `anchor.sh`'s own comment
  (sourcing the other script would execute its whole scan), but nothing checked the two stayed in
  agreement. Measured, not assumed from the two lines looking alike: byte-identical today.
  `LivingFilesCrossScriptBindingTest` binds both, parsed from source on both sides; a scratch
  mutation proof narrows `anchor.sh`'s copy — one subTest per name — and confirms the binding
  fires. The assertion is symmetric, so narrowing the other copy would fail it too, but the
  suite does not exercise that direction and this entry does not claim it does.
  `VALID_PHASES`'s own derivation (`range(9)`) was checked against the shipped
  `VALID_PHASES="P0 P1 P2 P3 P4 P5 P6 P7 P8"` directly — still exactly `P0`…`P8` contiguous, no
  gap hiding behind the derivation.

  Enumerated (deliverable 5), two more retyped copies this item's own audit did not name: (b)'s
  required-field list at `test_phase_docs_lint.py:260` (`["phase", "subskill", "status",
  "last_updated"]`, a local swept list mirroring `phase-docs-lint.sh:250`'s
  `"phase,subskill,status,last_updated"`) and `REVIEW_REQUIRED_FIELDS` (`:1679`, mirroring the
  same script's `:275`/`:296` `kind: review` required-field checks). Both share the same
  shrink-only blind spot as the five converted here; neither converted in this tranche (outside
  the write boundary named for it). A related but distinct gap surfaced alongside them:
  `memory-lint.sh:206`'s own required-field string (`"name,description,type,last_updated"`) has
  no per-entry sweep test at all in `test_memory_lint.py` — one test covers one of its four
  fields, not a retyped copy with a blind spot but a bare absence of the coverage this whole item
  exists to close.

- **An ADR convention: a resolved open point records its resolution in place (WI-0127)**.
  ADR-0009's follow-up 4 read "undefined" for six days after an addendum in the same file had
  answered it, and a proposal contradicting that answer was made on the strength of the stale
  entry. Resolving a question and updating the list that advertises it are two separate acts,
  and only the first is satisfying; the reader most likely to be misled is the one using the
  list the way it invites, as a work queue. A sweep of all ten ADRs found eight more such
  entries across four files — including one in an ADR a single day old, whose implementation
  comment names the follow-up it answers while the follow-up still said "not decided here".
  All are now struck through in place with a pointer to what resolved them, never deleted:
  an entry that outlived its answer is itself the evidence that a list can drift out of step
  with its own document. `CONTRIBUTING.md` carries the rule, plus a second half the sweep
  earned — an addendum's heading must name what it resolves. A mechanical check is
  deliberately deferred: keyed on headings today it would have found almost nothing, since
  exactly one of ADR-0009's four addenda names its target, and that one resolves two
  follow-ups while naming only one.

- **`scripts/tests/test_absence_only_assertions.py` — flagging tests that can never fail (WI-0125)**.
  Six of the eleven `covers:` tests in `test_phase_docs_lint.py` (WI-0122) asserted only the
  ABSENCE of a finding — `assertFalse(any("covers:" in w for w in warnings), warnings)`. When the script died
  with empty stdout, `findings()` returned `[]` and every one of them passed: a regression that
  killed the tool outright was reported by the full suite as clean. The general rule (G-126): an
  assertion of the form "X did not happen" is worth nothing without a paired assertion that the
  thing capable of producing X actually ran.

  This ships a meta-scan over the repository's OWN test sources (not a shipped lint — an adopter's
  test suite is none of CCPR's business) that finds the same shape anywhere in `scripts/tests/`:
  a test invoking a subprocess whose only assertions about the result are negative
  (`assertFalse`, `assertNotIn`, an empty-list/zero-length `assertEqual`), with no positive
  liveness assertion recognised in any of several shapes — a `files_scanned()`-style helper, a
  `returncode` check, an `assertIn` on a report header line, or an exact nonzero-count assertion.
  Measured against the exact parent state of the commit that introduced the by-hand fix: flags
  precisely the six negative-only methods among the two `covers:` classes' 11, never the five
  siblings that carry a positive assertion — the discriminating acceptance case.

  Narrowed from a deliberately coarse first pass to 53 defensible hits across the current
  tree after three measured precision fixes, each proven red-then-green: a subprocess call
  unrelated to the negative assertion it sits beside (`git ls-files` feeding a content check, not
  a liveness one) was no longer mistaken for coverage; a `_run_*` helper returning extracted
  stdout TEXT directly, rather than the raw `CompletedProcess`, is now recognised the same as a
  `.stdout`-bound name; and an exact nonzero `assertEqual(len(x), N)` is now treated as the
  liveness guard it actually is, not left neutral. A fourth fix, gating the `assertTrue` branch
  behind `_references_the_result`, closed a masking bug of the exact shape this check itself
  targets — an unrelated `assertTrue` was hiding a genuinely blind `assertFalse` beside it — and
  reclassified one previously-`not-flagged` method to flagged, landing the count at 54. Every
  current hit is individually triaged and accounted for via a `KNOWN_FINDINGS` baseline (51
  genuine, pre-existing gaps reported to the PO rather than fixed here — outside this item's
  write boundary — plus three measured false positives: a custom `assert_*` helper this scanner
  cannot see into, a `run_*`-named helper that is an in-process Python call, not a subprocess,
  and a `self.<helper>(...)`-bound findings list not literally named `self.findings`, so this
  scanner's own name-tracking misses it) — any NEW absence-only test added anywhere in the
  corpus from this point on fails the mandatory pin immediately.

  Also closes the one genuinely blind "clean baseline" guard found while auditing the three
  candidates the item named: `test_doc_volume_check.py`'s `BaselineTest` asserted stderr/bullets/
  returncode but nothing about scan scope — a `find` glob collapsing to zero matches over a
  populated `$DOCS_ROOT` passed the same three assertions vacuously. Proven red with a scratch-copy
  mutation (never the tracked file) before the `files_scanned()` liveness assertion was added.

- **`scripts/conformance-run.sh` — the shipped checks, run against real projects that use them**
  (WI-0124, ADR-0010). CCPR's checks are rules about documents, and a rule written in the repository
  that defines it is a hypothesis until it meets a consumer. On 27.08.2026 three shipped defects were
  found in one session that were structurally invisible from here while the suite reported
  **1478 tests, OK**: `covers:` appeared in zero documents across all three reference projects, so its
  check had nothing to check; the production-code classification had never met a repository whose
  newest commit was hygiene; and a shipped agent's tool list was patched by the maintainer's own
  installed copy.

  **The attribution rule is the whole design.** A finding belongs to CCPR only when the evidence lies
  in the check's own contract, or in a difference the consumer did not cause — a contract violation, a
  zero-scope run over a non-empty target, or a violated pin. Everything else is a finding about the
  consumer's documents and never moves the exit code. The worked example: one real run produced 25
  warnings that were all correct behaviour and must exit 0, while another's CCPR defect was a warning
  that *failed to fire* and must exit 1. An implementation that escalated on "any finding" would
  report a regression on the first run, every run, forever.

  A fourth class, `could-not-run`, carries a check that refused an unsuitable target and said why. It
  does not fail the run, but it appears in the scope accounting — `**Checks:** N invoked, M ran, K
  could not` — because a consumer where four of five checks refused must not read as fully covered.

  **Pins** are how the absent-finding case becomes detectable: a per-consumer expectation with a
  mandatory `why`, printed beside the finding, so the operator states at pin time why this fact is
  CCPR behaviour rather than consumer content. A pin's subject must be something CCPR controls; two
  anchor fields describing a consumer's own working state were removed for inviting exactly the
  misattribution the rule forbids.

  Consumers are **local paths** — nothing is fetched, so the run works offline and behind a VPN — and
  live only in the personal, non-distributed config. With none configured the run exits 0 and says so
  out loud rather than failing on a clean machine. Unknown config keys are refused at all three levels
  after a hand-written config silently dropped its `pins` block and reported a clean pass.

  Measured: three consumers, fifteen checks, about 30 seconds.

  **The acceptance proof, at one commit.** At `7af990d` the unit suite reports 1478 OK and the
  conformance run against that same tree reports exit 1 with the pin violated. The second
  demonstration does the same for the classification default against the tree before `abd5120`. Both
  run through a `git worktree` at the historical commit, so nothing is reverted.

  Docs: `Manual/system/conformance.md`.

- **A test that can see the two bracket scans drift apart (WI-0117).** WI-0095 brought the
  bracket scan into `scripts/memory-lint.sh` a second time — `protect_link_destinations()`
  (depth + escape) and `process_link_line()` (depth + escape, plus per-level
  `st_act[]`/`st_img[]`/`st_pos[]`, image markers, rule-3 deactivation, shortcut and
  collapsed references). These are **not** one rule written twice and were deliberately not
  merged: one caller needs a per-level struct, the other a counter.

  What the duplication cost was mutation strength. `_mutate_both()` restored it for the
  shared case by mutating both copies in lockstep — but a lockstep mutation can never
  produce a disagreement between them, so nothing could notice the two **drifting apart**.
  Tighten the escape handling in one and not the other and every test stayed green.

  Both functions compute the shared verdict — "is a live, unescaped opener open right now" —
  as a plain local boolean (`had_opener = (sp > 0)`; the `sp == 0` guard before rule 3).
  A scratch **copy** of the shipped script gets one `print` inserted after each of those two
  decision points, gated on an environment variable, and the two verdict *sequences* are
  compared over eight bracket fixtures. Neither function's control flow changes; the shipped
  script is never written to (asserted by md5 in a `finally`), and the environment variable
  does not appear in it at all, so a real run cannot emit the trace.

  The instrument's discriminating power is itself a permanent test rather than a one-off
  manual check: `test_a_deliberate_divergence_between_the_two_scans_is_caught` tightens
  **only** `protect_link_destinations()`'s escape check to a naive one-byte lookbehind and
  feeds it an **even** run of backslashes — precisely the input where escape *parity* (what
  both actually implement) and a one-byte lookbehind disagree. An odd run would have proven
  nothing. The agreement test additionally asserts each trace is **non-empty** before
  comparing, so two silently empty traces cannot pass as agreement.

  Documented limit, stated rather than left to be discovered: the eight fixtures are chosen
  so a resolved destination's length change never lands *between* two positions being
  correlated. A fixture with a second destination following an already-resolved one on the
  same line would need correlation by ordinal occurrence instead of byte offset — that change
  first, then the fixture.

### Fixed

- **`scripts/lib/frontmatter.sh` was blind to CRLF frontmatter** (finding #22). `fm_has` and
  its siblings compared `$0 == "---"`; on a CRLF file awk sees `"---\r"`, so the whole block
  read as absent. **The error direction is the dangerous one**: the lint is the strict reader
  and the gate the lenient one, so a CRLF project was told a valid `gate: go` was missing while
  the gate silently opened on it. Measured on one such file: `check_gate_passed` returned
  `(True, None)` while `fm_field` returned the empty string.

  Fixed now rather than later because `.gitattributes` (`bc87c9f`) covers **this** repository's
  contributions, not an adopter's — their repos may carry CRLF and do not have it. Same
  category as the `.gitkeep` finding: outward effect, not working tree.

  Eight blind sites, and they are not one kind. Four are `awk` blocks; `:24` is a **shell**
  string comparison that runs before any `awk`, so no `sub(/\r$/, "")` reaches it — it took
  `${first%$'\r'}` and its own test. The two writer blocks could not take the readers' repair
  either: stripping `$0` would have found the block and silently rewritten the whole document
  to LF, so they compare a stripped copy and carry the original terminator onto generated lines.

  **The consumer set is six, not the four the finding named** — `anchor.sh`,
  `freeze-phase-docs.sh`, `migrate-review-headers.sh`, `manual-lint.sh`, `memory-lint.sh`,
  `phase-docs-lint.sh`, each verified to call `fm_*` rather than merely to source the library.

  **The hardening introduced one new false positive, and it is fixed in the same commit.**
  `memory-lint.sh` carries a *second* parser: `if fm_has; then <own awk>; else <count whole
  file>`. Before, the `else` branch made a CRLF silo accidentally right; after, `fm_has`
  succeeded while the second parser still could not find the closing marker, so a silo holding
  real content was reported as an empty skeleton. Two parsers over one document are one unit,
  and the repair belongs in both. Shipping that in a later item would have meant a known new
  false alarm behind a green `check-all` — in the very check that last cost a debugging round
  for a cause outside itself.

  Red-proven with real bytes: fixtures are written, read back, compared against a hand-written
  literal, and asserted to contain no bare LF at any offset; the runners omit `text=True`
  because universal-newline translation would erase the byte under test. Twenty-one of
  thirty-five tests red before the fix. Eight structural mutations, each with its replacement
  count asserted before measuring and the file byte-compared after restoring — moving a strip
  *behind* its comparison, or applying it in only one of the four blocks, so the proof shows
  each block is reached individually rather than through one shared path.

  One consumer is **improved but still half-blind** and deliberately left unpinned:
  `migrate-review-headers.sh`'s body-hoist no longer reports `last_updated` missing, but
  `reviewed_head`, `reviewer` and `base_commit` stay unhoisted from a CRLF document. A test
  written today would enshrine that half-state.

- **Two cleanup mechanisms that existed, were correct, and never ran** (findings #27 and #25).
  `log-cleanup.sh` has had a retention rule since it was written — 7 days by default,
  `--days N`, `--dry-run` — and nothing ever called it: no hook, no cron entry, no settings
  line. Its first run ever, on 30.08.2026, took the log tree from 285 session directories and
  144 MB to 23 and 24 MB. And `cleanup_loop_state()` was called from exactly one place, inside
  `handle_session_end()`, so any termination that never emits that event — a killed process, a
  crash — left its state file behind.

  Both now run at `SessionStart`, where an interrupted session's leftovers are still there to
  find. The log cleanup is throttled to once a day by a stamp file; the state sweep is **not**,
  because it is a glob plus a stat per entry with no subprocess, and throttling it would let an
  orphan outlive its session by up to a day for nothing. That asymmetry is pinned by a test.

  **The point is visibility, not disk space.** A cleanup that quietly does nothing is
  indistinguishable from one that never ran — which is the defect being fixed, not a detail of
  it. So a run that happens files a record with its numbers *including all zeros*, plus a
  stderr line; a throttled start files nothing at all. The mutant "a no-op run files no record"
  turns three tests red.

  The hook can never fail a session start. A missing stamp, an unreadable one, one containing
  undecodable bytes, or a directory where the stamp should be: each runs the cleanup and
  replaces the stamp, and none can switch the cleanup off permanently. The unreadable case
  needs `os.replace` rather than an in-place open — permission on the directory, not on the
  file the fail-open path exists to recover from.

  Deliberately **not** capped: the sweep walks every entry in the temp directory. Measured at
  0 / 1 000 / 10 000 / 50 000 files → 28 / 32 / 78 / 340 ms, about 6 µs per entry, so a
  five-second session start would need roughly 750 000 files. A cap would mean a legitimately
  large backlog never finishes being cleaned — the same defect class one layer down.

  Cost on a throttled start: **+3 ms** (25 → 28 ms). The one run per day: ~680 ms.

- **Two defects that only exist on Linux, and were therefore never seen.** Both predate this
  work; the CI found them on its first run, because nobody had ever executed these scripts on
  Linux.

  `memory-sync.sh`'s home masking was a **no-op on bash 4+**. The line read
  `${msg//$HOME/~}`, and bash tilde-expands an *unquoted* replacement word starting with `~`
  — to the value of `$HOME`, not to a tilde character. So `$HOME` was substituted back in for
  itself. bash 3.2 does not do this, which is why a Mac never showed it. Measured on the
  identical line: bash 3.2 → `"xx~yy"`, bash 5.3.15 → `"xx/rootyy"`. This is a product defect,
  not a test artefact: the masking exists so error messages do not leak a home path, and on any
  Linux machine a real user saw the unmasked path. The obvious fix, `${msg//$HOME/"~"}`, was
  measured and rejected — it prints literal quotes on bash 3.2.

  Widening the sweep from "the same line" to "any replacement whose right-hand side starts with
  an unquoted tilde" found a **second site with no test at all**, `ensure_memory_pointer()`.
  It has one now, seen red against the original under real bash 5.

  `log-cleanup.sh` **removed nothing on Linux**. `find -printf` had no `-name '*.jsonl'` filter,
  so GNU find matched every file including the just-written `session-summary.json`, making old
  sessions look fresh — invisible on macOS, where BSD find rejects `-printf` outright and a
  fallback covers it. And that fallback used `stat -f '%m'`, BSD syntax; GNU's `-f` means
  *filesystem* status, a different mode that does not fail but returns a multi-line block, so the
  comparison after it failed silently. Measured in Docker with the real script:
  `Sessions: 0 removed, 1 kept`. Fixed with the `uname` branch this repo already uses twice.

- **Four platform assumptions in the test infrastructure**, repaired before the two defects above
  — deliberately in that order, because verifying a bash-5 fix requires a working Ubuntu job.

  Three tests broke on an absent `commonmark`. They do **not** test CommonMark conformance; they
  test the fixture generator's refusal branches, while the 46 real conformance tests run against
  the frozen fixture without the package. They now use a **recorded** oracle double: a manual
  script reads the markdown out of the test classes' own attributes, calls the real commonmark
  0.9.2, and stores the outputs with version and capture date. The double raises loudly on an
  unrecorded input rather than guessing, and carries a "What this module does NOT prove" section
  naming the gap it accepts.

  `SANDBOXED_PATH` was `/usr/bin:/bin:/usr/sbin:/sbin` — which is where apt puts shellcheck, so
  the sandbox contained the tool it existed to exclude. It builds itself from individual tool
  symlinks now. Two `could-not-run` causes were mutually exclusive by control flow, so when both
  applied the second was invisible; all applicable causes are reported now — could-not-run has
  been load-bearing since `check-all.sh`, and two causes indistinguishable behind it make the
  diagnosis soft exactly where it is relied on. And the bash-3.2 quoting mutation test, which has
  nothing to reproduce on bash 5, got the skip guard this repo already uses — plus a **skip
  budget**: counts pinned per source, multiplied by the same condition the original module uses,
  and a second test that walks the whole tree for unregistered skip decorators. A skip is a check
  that does not happen; without a counter such a set grows unnoticed.

- **Three checks were divergent on every machine but the maintainer's, because none of them
  reported its own scope** (WI-0129, groundwork for F11). A fresh clone with an empty `HOME` —
  which is what a CI runner is — produced `memory-lint: exit 0 (expected 1)`,
  `doc-volume-check: exit 0 (expected 2)` and `artifact-gate: exit 1 (expected 0)`. All three
  harmless, all three permanent.

  `check-all.sh`'s own header argues that a check which is red when nothing is wrong gets ignored
  within two weeks. That is the state this would have shipped into — and the diagnosis would have
  been wrong on top: "expected 1, got 0" reads as *the warnings are fixed*, not as *there was
  nothing to check*.

  The common cause is that all three depend on state only one machine has: untracked working
  files, or personal non-distributed config (ADR-0010). And all three **already announced their
  missing scope in plain text**. `check-all.sh` reads such a self-report today — but only for
  `conformance-run`. The mechanism did not need inventing, only applying consistently, which is
  also `CONTRIBUTING.md`'s rule about deriving an expectation from the other artifact.

  `memory-lint.sh` now prints `**Targets:** N of 4 present`. An earlier draft had `check-all.sh`
  match on `0 of 4 present` and was changed in review: that would have coupled the detector to
  the target count and broken silently at a fifth target. `doc-volume-check.sh` scans only
  git-tracked files inside a work tree — measured, the 5 critical and 6 warning findings were
  100% untracked working state, the 3 info are tracked. `check-all.sh` passes
  `--require-denylist` only where a deny-list exists, reading the same library `artifact-gate.sh`
  sources rather than re-deriving the lookup, and states the decision either way.

  That last part exposed a third state worth naming: `gate_load_config()` has an `exit 2` path
  that used to be contained in a subprocess and now sits in `check-all.sh`'s own process, before
  any check runs. A crash there would have bypassed the very rule this script enforces —
  "NOTHING WAS VERIFIED … This is not a pass" would never execute, and one check's broken config
  would suppress all eight. It now runs in a command substitution, and a broken detection is
  reported as **broken** rather than as merely absent: the two call for different actions.

  Fresh clone, empty `HOME`: 3 divergent / exit 1 → **0 divergent, 2 could-not-run, exit 0**.

- **Three defects that a fresh machine reproduced on every run** (findings #26, #19, #22). A CI
  runner is a fresh machine each time, so each of these is a defect a local hand-correction
  cannot hold.

  `log-cleanup.sh` created `${LOG_DIR}/session-archive` without a mode, so it landed on the
  executing umask — observed at `drwxr-xr-x` while WI-0129/F10 had put the rest of that tree on
  `drwx------`. Fixed with an explicit `chmod` rather than `mkdir -m`: `-m` does not touch an
  already existing directory, `chmod` does.

  Two `mktemp` templates in `run-tests.sh` carried a suffix after `XXXXXX`. BSD `mktemp`
  substitutes only a **trailing** run of X's, so both returned a literal, predictable path in
  shared `/tmp` and collided on any following call. Wider than recorded: `/tmp/pytest-cov.json`
  was hardcoded outright at three more sites. The new test asserts the rule over every `mktemp`
  call in the file, so the next line added is covered too.

  No `.gitattributes` existed. Four awk frontmatter parsers here are CRLF-blind while three
  Python ones are not, and the lint is the strict side — a valid `gate: go` reads as missing
  while the gate passes it silently. With a second person now committing, `* text=auto eol=lf`
  closes the door. Measured before writing: 0 of 321 tracked files carried CRLF, 2 are binary.

- **The shipped `CLAUDE.md` presented two instinct-adoption paths as equivalent when one carries
  a third of the other** (WI-0129, finding F14). It offered "Two ways to adopt the starter
  content" and described the single-file option as shipping *"the same 13 generic instincts as
  one file"* — a phrase with no antecedent, since the bullet above it never mentions 13.
  Measured: the split layout carries **45** instincts, `templates/STARTER_INSTINCTS.md` carries
  **13**.

  The sampler file itself was never wrong; it says so three times in its own header ("the only
  path that ships the full 45-instinct set", "happy with a reduced set"). The drift sat entirely
  in the summary of it — the shape the finding describes: a second register restating a first,
  with nothing comparing them. An adopter reading only `CLAUDE.md` would have taken the reduced
  set believing it equivalent.

  Recorded so the next reader does not repeat the measurement: 13 and 45 are both correct as the
  files state them. A first pass reported 24 and 55 and was wrong — that was grep counting
  instinct IDs mentioned inside each file's "intentionally NOT included" prose, not entries.

  Findings F12 and F13 were verified in the same round and need no change; their dispositions,
  with the measurements behind them, are recorded in the work item.

- **The monitor hook validates the session id before it reaches a path, and stops writing session
  state where every local process can read it** (WI-0129, finding F10). `hooks/agent-monitor.py`
  is wired into `settings.json` on **ten** events, so it runs on essentially every action in every
  session — unlike `command-check.py`, which had no programmatic caller at all.

  `session_id` came from the hook payload on stdin and went straight into paths unchecked. That is
  not an injection finding — the value comes from the harness, not from an attacker — but nothing
  constrained its shape, and a `/` or `..` in it would have silently relocated a session's logs.
  The report named two path-building sites; grepping found **six**. All now route through one
  `session_log_dir()` built on a `sanitize_session_id()` that accepts `[A-Za-z0-9_-]{1,128}` and
  falls back to a fixed constant rather than raising — the hook's contract is that it never breaks
  a session.

  The loop state moved out of a hardcoded, world-readable `/tmp` into `tempfile.gettempdir()` at
  `0600`. On macOS that is a private per-user directory, which removes the shared-directory
  exposure outright.

  **Two follow-ups from the security review, and the second corrects the premise the first half
  was written under.** The loop-state file holds only counters, timestamps and an input hash — no
  content. The *session logs* are a different matter: `prompt_preview` is the first 100 characters
  of the real prompt, `message` 200 characters of a notification, `input_summary` 500 characters of
  raw tool input — and they sat at `-rw-r--r--` in a `drwxr-xr-x` directory. The argument made for
  hardening the loop-state file applied more strongly here and had not been extended. Log
  directories are now `0700` and log files `0600`, with the mode **re-asserted on files that
  already exist**, so a backlog written before this change is tightened on its next write rather
  than only new sessions being covered.

  Both writers now carry `O_NOFOLLOW`. The first draft omitted it on the log path with a careful
  argument — planting a symlink under `$HOME` needs an attacker who already writes to your home,
  which crosses no privilege boundary. That reasoning is sound and answers the wrong question: the
  operation appends JSON and then `fchmod`s the target, so a **stale** symlink left by a backup or
  a sync tool corrupts a file and changes its permissions with no attacker involved at all. One
  flag is also cheaper than the paragraph explaining why two writers in one file differ.
  `O_NOFOLLOW` rejects only a symlinked final component, so a symlinked log *directory* keeps
  working.

  Verified by driving the real hook: `../../escape`, `a/b` and an empty id all collapse to the
  fallback and write nothing outside the intended directories; the state file lands under `TMPDIR`
  at `-rw-------`; a planted symlink leaves its target's bytes *and* mode untouched; every case
  exits 0.

  Not fixed, recorded: `cleanup_loop_state()` runs only on the `SessionEnd` event, so a killed or
  crashed session leaves its state file behind — two such files were sitting in `/tmp` when this
  was measured.

- **Four shipped agents were instructed to do things their own tool list forbids** (WI-0129,
  finding F9). `agents/code-reviewer.md` said "Use `git diff`, `git diff --cached`,
  `git log --oneline -10`" in step 1 of its working method and, eight lines later, "**You have no
  shell.** … You cannot run `git diff`." Its `tools:` line settles which sentence was true.

  Measuring the class rather than the instance found three more, none of them in the external
  review that reported the first: `security-master` named the Bash tool **four times** ("using
  Bash tool", "Execute … via Bash") without carrying it; `system-architekt` told itself "You have
  access to Read, Write, Edit, Bash, Grep, and Glob tools"; `konzeptor` and `tech-writer` listed
  Bash among their available tools. A shipped agent that reads its own instructions cannot comply
  with them, and has no way to discover that until it tries.

  Resolved by asking, per agent, whether the shell is part of its job. `security-master`'s is —
  dependency auditing is in its brief and `pentester` and `devops` already carry Bash — so it
  **gained** the tool. The others' mentions were incidental capability lists, so the prose was
  corrected to the truth: they say plainly that they have no shell, and where a command's output
  is genuinely needed (a commit log for a changelog, a diff for a review) the text now says the
  orchestrator supplies it.

  **Rule 5 in the agent lint** keeps it from returning: an agent whose body names the `Bash` tool
  must carry `Bash` in `tools:` — the exact mirror of Rule 4, which does the same for the `Agent`
  tool. The rule deliberately detects the **tool's name**, not shell commands. A command-shaped
  detector was written first and measured against the corrected tree: it flagged three agents,
  and two of the flagged sentences were the corrections themselves — "You cannot run `git diff`"
  and "not a `grep -c` command". A rule that fires on the cure is worse than no rule, so its
  boundary is documented instead: Rule 5 does not see an instruction that names a command without
  naming the tool, which is the shape `code-reviewer`'s original defect had. Those three sentences
  are pinned as regression fixtures so a future widening of the pattern fails loudly.

  The body-mention corpus pin moves 7 → 4, and every one of the four now carries the tool it names.

- **A gate with no artifact, and a command that does not exist, both stop reporting `ready`**
  (WI-0129, findings F5 and F6). Two fail-open paths in `scripts/command-check.py`.

  **F5**: when a gate's artifact did not exist, the check compared the project's current phase —
  parsed out of `docs/HANDOVER.md` prose — against the gate's phase number, and passed the gate if
  the phase looked further along. A scratch project with **zero** gate documents and the single
  line `**Phase**: P5` in its handover returned `ready` for `/p1-features`, `/p3-architecture` and
  `/p4-backlog`.

  What decided it was measuring that input in the field rather than arguing about the policy. Two
  of the three reference projects have no `Phase: PN` line at all, so the fallback never fired;
  the third reads `**Phase**: P2`, unchanged since 20.04.2026, while the project carries gate
  documents up to P6. The lenient path could not lift a gate correctly in any of them — it could
  only fire where a handover **overstates** the phase. It is removed outright, not narrowed. A
  missing artifact now blocks and names the file and the command that writes it.

  **F6**: an unknown command returned `ready`, exit 0. Two faces of one defect — a name with no
  `pN-` prefix collected no checks at all, while an invented `p9-…` name had a phase derived from
  it and produced a plausible check against `gate-p8`, a gate that does not exist (CCPR has p0
  through p7). The command set is now derived from the `commands/*.md` files shipped beside the
  script — the same relative position in a checkout and after install — plus any
  `<project>/.claude/commands/`. An unknown name is rejected before a phase is derived from it, so
  a fabricated gate can no longer be the reason. If the shipped directory cannot be found at all,
  the tool says the command set could not be determined rather than passing or blanket-blocking.

  **Closing both changed no real project's answer.** All 116 shipped commands were run against all
  three reference projects, before and after: **348 pairs, zero verdict changes.** The leniency
  these paths provided had never been exercised.

- **The gate verdict is read from a declared field instead of scraped from prose** (WI-0129,
  findings F3/F4). `scripts/command-check.py` decided whether a phase gate had passed by
  searching the document body for the words "Go" and "No-Go". That predicate was wrong three
  times in three consecutive attempts, each fix creating the next: the substring `Go` also
  occurs inside `No-Go` and inside `Go-**Live**`, and every gate command instructs authors to
  *name* "No-Go" in prose when flagging an Inviolable breach. The last measured failure: a
  document reading `Verdict: No-Go` followed by a Go-Live paragraph returned `ready`, exit 0.
  A document saying `Pivot`, and a document with no verdict vocabulary at all, both passed
  through a lenient `return True`.

  The verdict now lives in the frontmatter field `gate:` — **a field
  `templates/PHASE_DOC_SCHEMA.md` has documented since the beginning and nothing ever read.**
  No script, no hook, no command consumed it, and no `gate-p*.md` ever asked an author to write
  it; one of the three reference projects nevertheless carries it in seven gate documents,
  written purely by following the schema. The defect was never a missing machine-readable
  verdict — CCPR shipped one, ignored it, and parsed prose instead.

  The body is no longer read at all, in any language or spelling: measured across three real
  CCPR-using projects, 18 gate documents used **seven different prose spellings** of their
  verdict. Two closed vocabularies now apply, chosen by artifact — `pending | go |
  conditional_go | no_go | pivot` for a `GATE_P*.md`, and `pending | done | conditionally_done |
  not_done` for `docs/planning/SPRINT.md`, which is `gate-p5`'s own gate artifact (P5 is the one
  gate with no `GATE_P5.md`; three P6 commands named it as a prerequisite and it had never been
  checkable). A value valid on one artifact is rejected on the other. `conditional_go` and
  `conditionally_done` unblock, matching every gate command's own outcome table; `pending`,
  `no_go`, `pivot` and `not_done` do not.

  Fail-closed, and the reason now says which of four things went wrong — artifact missing, field
  missing, value outside the vocabulary, or a real negative verdict — instead of the single
  sentence `gate file missing or no 'Go'`, which was printed even for `gate-p5`, a gate that has
  no file by design. `scripts/phase-docs-lint.sh` enforces the field's presence and vocabulary
  as an error, so a project finds every affected document in one run. There is deliberately no
  alias and no transitional fallback: accepting a second spelling is what made the previous
  parser unfalsifiable.

  **Verified against consumers, because it cannot be verified here.** CCPR has no phase folders
  of its own, so this rule cannot fire against this repository at all. Predicted before running
  and then measured against the three reference projects: 6 / 6 / 1 lint errors, and the one
  project whose documents already carry the field stays `ready` for `/p4-sprint` and
  `/p5-implement` while the other two now block, naming the exact file and field to add.

- **The shipped ADR prompt told adopters to write ADRs this project's own linter rejects**
  (open finding #9; WI-0128). `commands/` ships to every adopter. An ADR written exactly as
  `commands/p3-arch-adr.md` prescribed, placed where `commands/cross-check.md` looks for it,
  failed `phase-docs-lint`: exit 1 with no frontmatter, and **exit 2 with `status: accepted`**
  — the very value the prompt named. `rejected` and `superseded` fail the same way, and rule
  R5 needs exactly those two, so R5 could not work for an adopter at all.

  Two lifecycles had collided on one field: the document status
  (`skeleton|draft|active|frozen|archived|living`) and the decision status. CCPR's own ADRs
  escaped it only because `docs/adr/` is not a phase folder, so the linter never sees them —
  which is the finding, not an excuse. Resolved the way `13a0dae` resolved the identical
  collision for risks two days earlier: the decision lifecycle moves to its own namespaced
  field, `adr_status`, and `status` takes a value from the document enum.
  `archived` is the schema's own word for "superseded", so the mapping nearly writes itself.

  The vocabulary is deliberately **open** rather than a closed set of four. Pinning
  `partially-implemented` — this repo's own ADR-0007 — as a fifth prescribed value would
  recreate the same defect for the next project's own term; the rule is instead that any
  `adr_status` is fine provided its mapped `status` is valid, with ADR-0007 as the worked
  example. A first draft of the fix prescribed three values while this repository used five,
  reproducing the finding one level up before it was caught.

  Also corrected: the "Max. 6 ADRs" cap (this repo has ten), three-digit numbering (it uses
  four), and an under-specified output path. The follow-up and addendum conventions from
  WI-0127 are now prescribed for adopters too, which `CONTRIBUTING.md` had explicitly left
  open. `cross-check.md`'s R5 reads `adr_status`, and all ten of this repository's ADRs carry
  the new shape — the point of the finding was that CCPR prescribed what it did not do.

  `scripts/tests/test_adr_status_mapping.py` binds the prompt's table to the linter by running
  it, not by comparing enums: every core row is written to a real ADR and scanned, and the real
  `docs/adr/` corpus is checked against the table. Its first version had a dead branch — a
  character class missing an underscore made the header-row filter unreachable, so the output
  was right for the wrong reason.
- **A failed `quality-scan.sh` run now says so, and says how long it has been failing**
  (open findings #8 and the follow-up decision to #6; WI-0128).

  The counting walk that decides whether a project has "actual code" at all — and so whether
  the DSGVO consent finding fires — was the only one of `scan_dsgvo()`'s four `os.walk("src")`
  call sites with no directory filter, so `node_modules` and virtualenv files counted. Measured:
  three files, all under `src/venv/`, used to trip the gate; they no longer do.

  The three extension filters were reported as inconsistent and are deliberately **not**
  unified: a CORS header is set in server code, a PII literal can appear anywhere a developer
  types a string including JSX, and a consent notice lives as readily in HTML or Markdown as in
  source. Each is pinned as an argued asymmetry with its reason in the code, the treatment
  `reviews` already gets in `PHASE_SCOPES`.

  And the open question wave 1a left — what a failed run does with an existing report — is
  decided: it is overwritten with a marker carrying `status`, the reason, and, because nothing
  anywhere records a failed run, `consecutive_failures` and the timestamp of the first failure
  in the streak. It has no `summary` or `scans` key, so it cannot be mistaken for a clean
  report by a consumer that never sees the exit code. All three failing exits write it; the
  unknown-scope exit deliberately does not, because nothing was attempted and destroying a
  valid earlier report over a typo is loss without gain.

  Two claims about bash were corrected against measurement rather than argued. A comment
  asserting that a crashed scan always aborts the script via errexit is false in general —
  a crash that is not the function's last command does not abort, and the guard then does see
  it. The conclusion holds here for a script-specific reason now stated: `run_py()`'s explicit
  `exit` is position-independent, while the two heredoc scans depend on being their function's
  literal last command, and appending one output-less line after either would flip that
  silently. Separately, a cleanup trap inherited by a `$(...)` subshell does not run for that
  subshell — measured — so the marker registers its own.
- **Three defects in `quality-scan.sh`'s report path, all in the step that produces the file
  `/p6-audit` and `/p6-pentest` read** (open findings #6, #8-adjacent).

  *An apostrophe in the project path killed the scan and left a 0-byte report.* The report
  combiner interpolated `${TIMESTAMP}`, `${SCOPE}` and `${PROJECT_DIR}` into a
  `python3 -c "..."` string. Measured against a path containing `'`: `SyntaxError:
  unterminated string literal`, exit 1, and `docs/.quality-scan-report.json` present at zero
  bytes — a file CLAUDE.md tells the audit skills to use *if it exists*. This is the same
  defect WI-0055 fixed twice in this file, and the file's own header forbids it in writing;
  a second, unnoticed occurrence in the stderr summary printer was found while fixing the
  first. Values now travel through `argv`, and the report is written to a scratch file
  beside its destination and renamed in only after the combiner exits 0 with non-empty
  output — closing the whole "an aborted run leaves something that looks like a result"
  class, not just the apostrophe. The scratch file is placed next to the target rather than
  under `/tmp` on purpose: `mv` is atomic within one filesystem, and CCPR's documented
  deployment target is a container where those are routinely two.

  *Every semgrep finding was counted as `info`.* semgrep emits uppercase severities; the
  summary compared lowercase and assigned the remainder to `info` by subtraction. A semgrep
  **ERROR** therefore appeared as `info` in the line a person reads to decide whether a
  release is safe. Severities are now normalised once, at the single point all four scans
  converge, which fixes the stored per-finding value as well as the summary. An unrecognised
  severity is not guessed at: the finding keeps its own value and a separate
  `severity-normalization` entry names the type and value and says it was counted in no
  bucket.

  *Two caps truncated silently.* The pattern scan kept 50 findings and semgrep 20, with no
  trace either way, so "50 findings" and "50 plus an unknown number more" were identical
  output. Both now append one `scan-truncated` finding naming the true total.

  Three existing tests pinned these defects as facts and had to change — one asserted the
  report was zero bytes, one that severities were miscounted, one that no truncation marker
  ever appears. Had none of them changed, nothing would have been fixed.
- **A `.gitignore`-only commit set the anchored-state comparison point** (WI-0123). `anchor.sh`
  classified a commit as production code if it touched anything outside `docs/` and `.claude/` that
  was not a `.md` file. `.gitignore` passes that test, so a commit changing nothing about the running
  system became the point every anchor is measured against.

  Two of the three reference projects were in that state simultaneously, measured 27.08.2026:

  | Project | reported | actual last code change | off by |
  |---|---|---|---|
  | consumer-c | `11606deb` — `chore(claude)` + 7 lines of `.gitignore` | `bec9a8a` | 14 days |
  | consumer-b | `87641bea` — `.gitignore` only, 5 added lines | `63b0dfc0` | 8 days |

  Frequency was never the issue: hygiene-only commits are ~2% of production-code commits across four
  repositories. What matters is how often one is the **newest** commit, because that is the one
  Stage 1 compares against — and that was two out of three on the day it was measured.

  **The criterion, not just the list.** Excluded is a file that describes only *how the repository or
  the editor is handled*, never *the system that runs*: `.gitignore`, `.gitattributes`,
  `.editorconfig`, `.prettierignore`. Deliberately kept as production code, each a counter-example to
  "root-level dotfile ⇒ hygiene": `.dockerignore` (determines image contents), `.env.example`
  (declares the runtime's required configuration), `.nvmrc` / `.tool-versions` (pin the runtime
  version). `.env*` needed no rule — no real `.env` is tracked in any of the four repositories, and one
  that were would be a secrets finding rather than a classification question.

  The question itself is recorded in ADR-0009 Addendum 4, so the next candidate is decided by it
  rather than by resembling the four names already on the list.

  **Shipped default, not per-project config**, because these files exist in every project and are
  production-relevant in none — the per-project route means every adopter meets the same misleading
  measurement once, independently. The trade-off is stated where it is made: `load_exclude_config`
  extends the defaults rather than replacing them, so a project cannot walk this boundary back, which
  is why each of the four names is argued individually.

  Each list entry is covered by a test that fails if that entry is dropped — verified by removing all
  four in turn. The unexercised third entry in WI-0122's placeholder list showed what an unpinned name
  costs.

- **A `.gitkeep` satisfied the `covers:` emptiness check, so a reserved-but-unbuilt directory
  reported clean** (WI-0122). `phase-docs-lint.sh` check (h) warns when a `covers:` entry points
  at an empty directory — "the list covers nothing". The predicate is `find -type f -print -quit`,
  and a `.gitkeep` is a file. A directory whose only content is the placeholder that makes its
  emptiness representable in git therefore counted as covered, and the warning stayed silent —
  in exactly the case it exists to name.

  Direction: **false negative**, and one that hit the `.gitkeep`/`.keep`/`.placeholder`
  convention rather than an exotic setup.

  **Not a widened predicate.** `is_empty_dir()` is untouched: "holds nothing" and "holds nothing
  but a placeholder" say different things to a reader, and the second one — *reserved, not built*
  — is the more useful. Check (h) gained a third branch with its own wording:

  ```
  <doc> — covers:'<entry>' holds only a placeholder (<name>, <path>) — reserved, not built
  ```

  A directory holding a placeholder **and** real content stays silent, as before.

  **How it was found, and what the first fix broke.** The defect surfaced only when the field was
  adopted in a real project — `covers:` appears in zero documents across all three CCPR reference
  projects, so nothing in this repository could have produced it. The first fix then shipped a
  regression that the suite reported as green: the new helper returns non-zero by contract on any
  directory with real content, and its call site was a bare `var=$(cmd)` assignment, which under
  the script's `set -euo pipefail` killed the entire run — exit 1, zero bytes, no report — at the
  first ordinary `covers:` directory. Every document after it went unchecked.

  Eight `covers:` tests missed it because they asserted only the **absence** of a finding
  (`assertFalse(any(...))`), which an empty stdout satisfies. They could not tell "ran and
  correctly said nothing" from "did not run at all". All of them now assert liveness first, via
  the report's own `Files scanned` line. Removing the call site's guard turns five of them red.

  **Coverage added** beyond the fix: a directory of only real files (the shape that broke, which
  no fixture had), a directory with two placeholders at different depths, and a `.placeholder`
  fixture — the third name in the list had no test, so a typo in it would have passed the suite.

  Verified against three real projects: the pilot reports the expected single warning over 154
  documents; two controls without `covers:` are unchanged at 242 and 95 documents, 0/0/0.

- **A block quote interrupting a LIST ITEM's paragraph still hid a link — three shapes, not
  the one that was reported.** `709f241` fixed the plain-paragraph case; the `code-reviewer`
  pass on it found the same defect one container further. Sweeping the family against
  `commonmark` 0.9.2 found two more the review had not:

  | Shape | Reference | check (n) before |
  |---|---|---|
  | `- foo …` then `> …` | both links | one link |
  | `1. foo …` then `> …` | both links | one link |
  | `- foo …` then `  > …` (indented) | both links | one link |

  Direction: **false negative** — a real link went unchecked, so a dead target passed.
  `# foo …` then `> …` was already correct (headings flush), which localised the cause to the
  list-item branch.

  **Why one guard could not get both right.** The interrupt guard keyed off `pbuf_para`, which
  records *what opened the buffer*, not *which container is open*. The list-item branch
  deliberately never sets that flag — that is what stops the WI-0082 setext guard from firing
  inside a list item — so "continuing an open quote" (which must **not** flush) and "a list
  item's paragraph is open" (which must) both read `pbuf_para == 0`.

  The repository's own `senior-developer` memory had already written the rule down on
  23.08.2026, three days before this surfaced: *a container guard must key off the CONTAINER,
  not off what opened the buffer*, with the generalised test — for a flag set at
  construct-open, ask whether the construct can appear mid-block; if yes, the clear and the
  set need different conditions.

  Fixed with an orthogonal `pbuf_quote` flag rather than by widening `pbuf_para`, which would
  have re-coupled it to the setext guard it must stay decoupled from. Verified afterwards that
  `pbuf_quote` is **read** in exactly one place — the guard itself — so the one path that
  leaves it stale (the `END` block's deferred reference-definition case, which never consults
  the guard) cannot be affected by construction, not merely for want of a fixture.

  Eight shapes now agree with the reference, including a three-line quote and a
  quote-then-paragraph transition. Corpus 89 → 94.

- **The YouTrack read path warned about an out-of-vocabulary `status` but said nothing about
  `priority`.** `_item_from_issue` reads both through structurally identical one-line helpers
  (`self._reverse_X_map.get(name, name)` — an identity fallback), so a project value absent
  from the configured map arrives verbatim in both cases. Only `status` noticed. After the
  filter-path fix below made the two fields consistent, this read path was the one place left
  where they diverged.

  Priority now warns the same way, through a shared `_warn_if_field_outside_vocabulary()`
  helper called from both blocks. The existing status warning's wording is **byte-for-byte
  unchanged** — verified by rendering the helper with the state arguments and comparing to the
  pre-refactor literal, not by reading it. The helper keeps the field's display name and the
  vocabulary's name as separate parameters because they differ for State (YouTrack's field is
  "state", CCPR's vocabulary is "status") and coincide only for Priority; collapsing them
  would have silently reworded the existing message.

  Field impact, measured against the live consuming project rather than estimated: of its
  **187 issues**, priorities are `Normal` 119, `Major` 35, `Minor` 31, `Critical` 1 — all four
  reverse-map cleanly and stay silent — plus one `Show-stopper`, which is in no map. Simulated
  over that exact distribution: **187 items in, one warning line out.** The warning sits inside
  `_item_from_issue`, which `list()` calls once per issue and `get()` once, so it cannot fire
  per field access.

- **`workitems.py list --status <typo>` returned `[]` and exit 0, and a gate would have
  believed it.** An unknown filter value produced an empty array indistinguishable from a
  genuine no-match. That is not merely a usability wart: `Manual/WORKITEMS.md`'s adoption
  guard instructs every wired command that an **empty result is real** and that for a gate it
  is "a genuine finding (e.g. 'no Ready story' = Not Met)". A single typo in a gate command's
  `--status` therefore produced a false **Not Met** verdict, with nothing anywhere saying so.

  The same gap existed on `--priority`, which has its own closed vocabulary. Both are
  validated on the **write** path already (`set_status`, `validate_priority`); only the
  **filter** path checked nothing.

  **The fix warns rather than rejects, and the reason is measured, not preferred.** An item
  carrying a value outside the vocabulary can exist today on both backends — a hand-edited
  local frontmatter file, or a YouTrack project's own State/Priority bundle, which
  `_item_from_issue` already passes through deliberately so that "a value already on the issue
  must still be readable". Rejecting the filter would have made such an item **unfindable**.
  So `list()` now warns on stderr and runs the filter unchanged.

  Deliberately unchanged: the exit code stays 0 (the filter did run correctly, and every
  existing caller — the adoption guard included — reads that code), and stdout stays pure
  JSON. Verified end to end: stderr is byte-for-byte empty for a valid filter value, so
  nothing new appears on the happy path.

  This is the same defect family as WI-0121 (`phase-docs-lint` reporting `Files scanned: 0`
  with exit 0) — a run that checked nothing reading as a run that found nothing.

- **check (n): a block quote interrupting a paragraph could hide a real link (WI-0089).**
  CommonMark lets a block quote interrupt an open paragraph. `memory-lint.sh`'s paragraph
  buffer cleared its `pbuf_para` flag when a `>` line arrived — WI-0082's fix, which stopped
  the setext branch from wrongly claiming a boundary inside a quote — but still appended the
  quote's line into the **same** buffer as the paragraph it interrupts. A code span opened in
  the paragraph and closed inside the quote therefore paired **across a join CommonMark keeps
  separate**, swallowing a link that the reference renders.

  Direction: **false negative** — the link was silently not checked, so a dead target passed.
  It needs a code span straddling the boundary; the plain case always worked, because the
  merged buffer still found the link. Measured against `commonmark` 0.9.2 with controls at
  both ends of the series, per this project's rule that conformance is decided by running the
  reference, never by arguing.

  The guard now flushes the paragraph before the quote line starts a new buffer, but **only**
  when an ordinary, not-yet-quoted paragraph is actually open (`pbuf_n > 0 && pbuf_para`). A
  `>` line that merely *continues* an already-open quote must not flush — a quote's own
  paragraph legitimately spans several `>` lines, and a code span may straddle that join the
  way it may straddle any paragraph's.

  Covered by two behaviour tests, a mutation test that restores the guard to its **exact**
  pre-fix form (not a deletion — deleting code makes any test red and proves nothing), and
  two corpus entries: the diverging fixture plus a no-straddle control. The corpus generator,
  which queries the reference parser and the real script as two independent oracles and
  refuses to write a fixture where they disagree silently, accepted both with no recorded
  divergence — i.e. the script now agrees with the reference on this shape. 87 → 89 entries.


## [v0.3.0-beta] – 26.08.2026

### Changed
- **The check baseline's note column states reasons, not measurements.** All eight notes in
  `scripts/check-all.baseline.tsv` carried a quantity — `332 files scanned`, `1965 tests`,
  `14 tracked / 188 untracked`, `3 consumers covered`. None had a reader: `check-all.sh` never
  parses that column, nothing re-derives the figures, nothing goes red when they are wrong.
  They only aged, and were corrected by hand each time — artifact-gate's count went
  313 → 323 → 328 → 332 in three days.

  Three were worse than stale. `4 of 4 targets present`, `deny-list active (source: config)`
  and `3 consumers covered` describe the maintainer's own `~/.claude`; on a CI runner those
  three checks report could-not-run. A versioned expectation file was documenting one private
  machine.

  **The provenance line is gone rather than corrected.** It read "Measured on the working tree
  of HEAD `666e8e6`" while `1965 tests` arrived three commits later and `332 files scanned`
  five — measured with `git log -S`, not assumed. An unchecked freshness claim goes stale
  exactly like the counts it vouches for, and this one sat in a header asking for deliberate
  re-measurement. With the measurements gone, nothing in the file is bound to a point in time.
  A note may now be empty; `check-all.sh` is untouched, its reader takes a two-field line
  unchanged.

  Two durable phrases had to survive the new guard, and both are traps: `none` contains `one`,
  and `\bzero\b` matches inside `non-zero` because a hyphen **is** a word boundary. Beyond
  the synthetic mutation, the detector was proven against the real prior state — it fires on
  8 of 8 notes of the pre-change file.

- **Four figures in `CONTRIBUTING.md` re-measured as a set, and two machine-local ones
  removed.** The `-t .` pair was 1848 / 1339 / 15 / 509 against a tree at
  **1987 / 1477 / 16 / 510** — the second time all four were found stale together, which is
  why the file asks for them to be re-measured as a set rather than adjusted one at a time.
  Separately, the conformance paragraph read "Measured: three consumers, fifteen checks, about
  30 seconds": every one of those numbers describes the maintainer's own consumer list (one
  consumer invokes five checks, three invoke fifteen — measured both ways). Replaced by the
  durable statement that the counts scale with *your* list and that the run reports them,
  where they are current by construction.

  Also corrected: within this same `[Unreleased]` block, the `check-all.sh` entry stated as a
  present-tense measurement that `doc-volume-check.sh` exits 2 on a correct tree, while a
  later entry in the same block records its scoping to git-tracked files and an expected exit
  of 0. The historical sentence is kept and marked as of-its-time rather than rewritten.

- **The scanner limitation in `test_absence_only_assertions.py` is documented where it lives.**
  `_classify_assert_call` asks "does this reference the result?" two different ways inside one
  function — `_references_the_result` walks the whole call for `assertTrue`,
  `_is_stdout_like` inspects a single argument node for `assertIn` — so
  `assertIn("#2", r.stdout + r.stderr)` is invisible on one branch and seen on the other.
  Deliberately not widened: the decision on the two sibling blind spots was to name them
  narrowly rather than change rules whose counts are pinned. The note sits at the `assertIn`
  branch, not in the module docstring where the other two are, because reading the docstring
  is not how anyone arrives at this one.

- **The chapter that calls itself "the full script catalogue" was missing half the scripts,
  and three shipped scripts were documented nowhere at all.** Measured across `Manual/` and
  `README.md` while preparing this release: `Manual/system/monitoring-scripts.md` — which
  `SYSTEM_OVERVIEW.md` §7 points to as "the full script catalogue" — listed **10 of the 20**
  scripts under `scripts/`. Absent: `anchor.sh`, `baseline.sh`, `doc-volume-check.sh`,
  `freeze-phase-docs.sh`, `log-cleanup.sh`, `manual-lint.sh`, `memory-lint.sh`,
  `migrate-review-headers.sh`, `phase-docs-lint.sh`, `workitems.py`. Of those,
  `baseline.sh`, `manual-lint.sh` and `migrate-review-headers.sh` appeared in **no**
  documentation whatsoever — `manual-lint.sh` although `commands/cleanup.md` runs it, so an
  adopter would first meet it as an unexplained red lint.

  Two groups were added — "Doc Hygiene & Validation" and "State, Baselines & Migration" —
  and §7 now *names* them and points to the catalogue rather than restating it. (A first
  draft copied both tables into the index, which is precisely the defect the same release
  fixed in §9–§11; it was rolled back before commit.)

  **Each row was written from the script's own header rather than from what the name
  suggested**, which corrected five drafts before they shipped: `baseline.sh` writes
  `docs/.baseline-prep.md` (not `BASELINE.md`) and its `<version>` argument is **required**;
  `freeze-phase-docs.sh` promotes only from `draft`/`active`, is a deliberate no-op in P5
  and P8, and does **not** stamp the anchor; `log-cleanup.sh` defaults to 7 days;
  `anchor.sh` is a stage-1 mechanical check that renders no verdict; `workitems.py` reads
  `.claude/settings.json`, not a repo-root settings file.

- **The "not shipped in any tagged release yet" notices are false as of this tag, and were
  resolved rather than left to rot.** `artifact-gate.sh`, `lib/discipline_gate.sh`,
  `anchor.sh` and `commands/anchor.md` were absent from `v0.2.1-beta`, and five places said
  so — two "Not Yet Released" table sections plus banner blocks in
  `system/anchored-state.md` and `system/discipline-gate.md`. All now read "shipped since
  `v0.3.0-beta`" and tell a reader on an older installation what to do about it.

- **The test suite was invisible outside one detail chapter.** Before this release it was
  named only in `system/scripts-conventions.md`, as a side note to two shell conventions.
  `README.md` and `Manual/README.md` now name it, its mandatory `-t .`, and the fact that
  `scripts/run-tests.sh` is for downstream projects rather than for CCPR's own suite.
  `Manual/README.md` also gained rows for `WORKITEMS.md` and `system/scripts-conventions.md`,
  and `README.md`'s scripts tree gained `tests/`, `manual-lint.sh`, `artifact-gate.sh` and
  `anchor.sh`.

- **`Manual/SYSTEM_OVERVIEW.md` §9–§11 were copies of `Manual/system/memory-instincts.md`,
  and §11 had drifted away from the model it describes.** The "slim index → detail files"
  split was started and never finished for these three sections: the `Full chapter` pointers
  added earlier made the duplication visible without removing it. All three are now
  summaries plus a pointer, matching the shape §5 and §7 already use.

  §11 had drifted furthest — it named **three** instinct levels where the model has **four
  scopes**, omitted global Tier 2 (`~/.claude/memory/{agent}/instincts.md`) entirely, and
  gave the ID schema without `{prefix}-G-NNN`. §9 said "Two-tier" for a 2×2 model, had no
  Global column, omitted `scope: tier-2-global` / `agent:` from its frontmatter block, and
  never mentioned org-tier sharing although §7 links to it.

  **The copies were deliberately not re-synced.** Restoring parity would rebuild the exact
  mechanism that produced the drift. Instead every surviving claim was checked against its
  *source* rather than against the other copy — which found three places where **both
  copies agreed with each other and neither agreed with the source**:

  - the memory `type` table was missing `index` (Tier 1) and `patterns` (Tier 2), and did
    not mention that Tier 1 is a closed enum while Tier 2 deliberately only warns
    (`templates/MEMORY_SCHEMA.md`);
  - a new instinct starts at **0.4**, not "0.4-0.5", and `reject`'s 0.3 is a *delete
    prompt*, not a floor (`commands/instinct.md`);
  - `doc-volume-check.sh`'s bands are info / warning / error at 25 / 40 / 50 KB, and the
    info band does **not** raise the exit code (the script's own header and exit logic).

  Those three were fixed in `system/memory-instincts.md`, which is now the single copy.
  `SYSTEM_OVERVIEW.md` 43.7 KB → 41.1 KB.

  **Still open, and named rather than silently left:** §12 File Structure is the same
  defect one section further — a 129-line directory tree that `system/file-structure.md`
  already carries in full, and the ~4 KB that keeps the index in `doc-volume-check.sh`'s
  40–50 KB warning band.
- **`CONTRIBUTING.md` did not mention the test suite at all.** Its "Quality checks before
  opening a PR" section listed three linters and two syntax checks; the 1458-test Python
  suite under `scripts/tests/` — the only thing that actually covers the shipped scripts —
  appeared nowhere, so a new contributor had no way to learn it exists. The section now
  names the command, and three things a first run gets wrong:

  **`-t .` is not optional, and omitting it is partly silent.** Measured: with it,
  discovery collects 1458 tests and 0 import errors; without it, 1118 tests and 11 failing
  module imports (the two relative `from .test_artifact_gate` importers plus the whole
  `scripts/tests/workitems/` subpackage). The run goes red on those 11, so something is
  visible — but ~340 tests never execute and nothing says so.

  **`scripts/run-tests.sh` is not the entry point**, despite the name being the obvious
  thing to reach for. It is a framework script for downstream *projects* and detects their
  runner from `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod`. CCPR has none,
  so it answers `{"framework": "unknown"}` on its own repository.

  **A non-zero lint exit is not automatically the contributor's regression.** This
  repository has a stable baseline (`memory-lint.sh` exits 1, `doc-volume-check.sh` exits
  2), and `phase-docs-lint.sh` reports `Files scanned: 0` because CCPR has no phase folders
  — which, per the project's own rule, is not a pass either.

  `scripts/manual-lint.sh` was also missing from the linter list although `commands/cleanup.md`
  now runs it; the list is a table now, one row per script and what it validates.

### Fixed
- **`manual-lint.sh` shipped a `kind` vocabulary derived from one repository and enforced it as an
  error.** Pointed at the two real projects that use CCPR, on its first day: **21 errors in one,
  6 in the other**, every one an unrecognised-but-legitimate genre — `memory-archive`,
  `handover-archive`, `analysis`, `story-detail`, `story-index`, `portable-learnings`,
  `living-list`, `gate-protocol`, `coverage-map`, `sprint-review`. None of them wrong; all of them
  unforeseen. Since `commands/cleanup.md` now runs this lint, every adopter's hygiene loop would
  have gone red on documents that are fine.

  `memory-lint.sh` had already answered this question one field over, and its own comment says why:
  the Tier-2 `type` set stays open, "so an unforeseen but legitimate persona-specific label does not
  repeat the defect this fixes". The same reasoning applies to `kind` and had simply not been
  carried across. An unrecognised value is now a **warning**: the value being *named* is useful
  signal, the value being *unknown to this list* is not a defect. Finding counts are unchanged
  (21+4 → 25 warnings, 6+0 → 6) — a severity change, not a coverage change — and `review` keeps its
  status as the one value `phase-docs-lint.sh` reads as a behavioural switch, because it stays a
  *recognised* value either way.

  **The list was deliberately not widened.** Two values recur across both projects (`story-index`,
  `sprint-review`) — normally the bar for adopting one — but each has a canonical CCPR equivalent
  those projects deviated from (`sub-index`, `review`), so codifying them would reward drift rather
  than name a new genre. `templates/PHASE_DOC_SCHEMA.md` now states plainly that the vocabulary is
  the KNOWN set, not the ALLOWED set.
- **`templates/QA_SKELETON/QA.md`, the P6 phase index, carried `subskill: p6-functional` — its own
  sub-index's identity.** Copy-paste, inherited by every project bootstrapped from the skeleton.
  Measured before choosing a replacement: `subskill` is presence-checked only, nothing reads the
  value, and the convention already exists in the field — one reference project carries
  `subskill: index` on all five of its phase indexes and `subskill: gate` on its gate documents.
  `QA.md` is now `index`. The schema's own definition of the field ("Slash-command without leading
  `/`") was the thing actually wrong: that project carries **117 distinct values against CCPR's 116
  commands**, many mapping to no command at all. The row now describes what the field is rather
  than what it was assumed to be — with no enum, because 117 values is not an enumerable set.
- **`/p4-sprint` prescribed a `status:` value `phase-docs-lint.sh` rejects, and this one was not a
  typo.** In the `kind: risk-detail` block, `status: open | mitigated | accepted | closed` is the
  RISK lifecycle; `status` in the document schema is the DOCUMENT lifecycle. Two axes on one field
  name. Reproduced rather than argued: a `docs/planning/RISK_R-01.md` written exactly as prescribed
  gave exit 2, `status='open' is not in {skeleton draft active frozen archived living}`. The risk
  lifecycle moves to `risk_status:`, joining the block's already risk-namespaced `risk_id` /
  `severity` / `sprint_identified`, and the document `status` becomes `living` — the schema's own
  wording for "actively maintained detail file designed to keep growing", which is what a risk file
  does through its `## History` section. Same block after the change: exit 0.
  WI-0121's corpus test carried a narrow exemption for this genre, and
  `RiskDetailExemptionIsNarrowTest` existed to prove the exemption was load-bearing rather than
  vacuous. With the collision fixed at the source the exemption has nothing left to exempt, so it is
  **removed** rather than kept as a standing hole; the proof-test is replaced by one pinning the new
  state on a synthetic block, since the real corpus entry can no longer distinguish "no exemption"
  from "nothing to catch".
- **Four more `producer | grep -q` sites under `set -o pipefail`, the shape `9b1fdf5` fixed in
  `manual-lint.sh`.** `freeze-phase-docs.sh` (unbounded `anchor set` output — the one with the same
  risk profile as the site that actually failed), `artifact-gate.sh` (one file line, but a minified
  or base64 line has no small bound), `run-tests.sh` (two sites) and `lib/discipline_gate.sh`, whose
  sibling site at :477 already carried the here-string form with its own comment. All four converted,
  not just the large one: the alternative was to classify sites by content size against a threshold
  that could not be measured — synthetic reproductions stayed clean from 8 to 60 KB while the real
  43 KB file failed 18% and its 41 KB predecessor 0%. The sweep is complete and its two negatives are
  proven rather than assumed: `artifact-gate.sh:242` pipes into `grep -v`, and `_gate_hits` is called
  36 times with printing flags and never `-q` — both read to EOF, so neither can exit early on a
  match. `artifact-gate.sh`'s `sed` moves from `checked-condition` to `bare-needs-exemption`
  (`downstream-checks-result`) since it is now an argument rather than the tested command; the pinned
  total stays at 144.
- **Three shipped files named `/entscheidung`, a command that does not exist.** The file is
  `commands/decision.md`, so the invocable command is `/decision`, and the Manual says so in four
  places — but the command's own H1 announced `/entscheidung`, and `agents/project-guide.md`'s
  hand-off table and `commands/roadmap.md`'s next-steps prompt both recommended it to the user by
  that name. The guide would have routed people to a command that does not resolve, which makes
  this functional rather than cosmetic. All fifteen sibling commands use `# /<filename> – Title`;
  these now do too. It was also the last German word in shipped English content outside the
  gitignored working files (Constitution Inviolable), together with the one below.
- **`templates/QA_SKELETON/PENTEST.md` listed four of its five sub-skills, omitting the only one
  that ships a skeleton.** `/p6-pentest` has five sub-skills (recon, injection, auth, authz,
  logic); the sub-index's Detail Files table carried four, and the missing row was `authz` — the
  one sub-skill for which `AUTHZ.md` actually exists as a file. `AUTHZ.md` correctly declared
  `parent_index: PENTEST.md` all along; what was missing was the acknowledgement in the other
  direction, which is exactly the gap `manual-lint.sh` (WI-0112a) was built to find, and it found
  this one on its first run over the repository root. The row is now present and links the file;
  the other four stay plain text because no file exists for them. `QA.md`'s German `## Sub-Indizes`
  heading is now `## Sub-Indexes`.
- **`SECTIONS_COMMANDS.md` and `Manual/commands/*.md` held the same 116-command tables twice, and
  the two copies had already drifted (WI-0112b).** Measured 26.08.2026: 116 command rows in the
  index, 115 across the five chapters, 108 identical — the same species of duplicate-content drift
  WI-0104 found and fixed one level down (`SYSTEM_OVERVIEW.md` vs. its `system/*.md` chapters).
  `/p5-review-sprint` existed only in the index; `commands/phases.md` was missing it entirely and
  is now complete. 7 rows were worded differently between the two copies (`/track-decision`,
  `/constitution`, `/lean-frame`, `/lean-learn`, `/lean-promote`, `/cross-check` in
  `commands/track.md`, plus a capitalisation-only diff on `/guide` in `commands/utility.md`); each
  was reconciled clause-by-clause against its source `commands/<name>.md` file rather than
  defaulting to either copy — see `docs/memory/tech-writer/` for the per-row reasoning. With the
  duplicate tables removed, `SECTIONS_COMMANDS.md`'s five per-category sections became orientation
  paragraphs pointing at their chapter (`commands/track.md`, `phases.md`, `gates.md`, `learning.md`,
  `utility.md`), closing 5 of the 12 `manual-lint.sh` findings from WI-0112a. The other 7 — none of
  `SYSTEM_OVERVIEW.md`'s 10 `system/*.md` chapters but `anchored-state.md`, `discipline-gate.md`
  and `memory-instincts.md` were reachable — are closed by adding the missing "Full chapter"
  pointers to `agents.md`, `phases-gates.md`, `commands.md`, `cross-cutting.md`,
  `monitoring-scripts.md` (one detail file spanning three index sections: Monitoring & Hooks,
  Local Scripts, Local LLM), `scripts-conventions.md`, and `file-structure.md` — content stays in
  `SYSTEM_OVERVIEW.md` as-is, only the back-link was missing, mirroring the pattern WI-0104 already
  established for `memory-instincts.md` and `anchored-state.md`. Makes `Manual/README.md`'s "slim
  index → detail files" claim true for both index files, and drives `manual-lint.sh`'s 12
  `Manual/`-scoped findings to 0 (the 13th, `templates/QA_SKELETON/AUTHZ.md`, is a real defect in
  shipped templates and deliberately untouched).
- **`manual-lint.sh`'s reverse-link check answered differently on identical input (WI-0112a
  regression, found the same day it shipped).** Six consecutive runs against an unchanged tree
  reported 0, 1, 2, 3, 0 and 1 findings, naming a different set of files each time. The check read
  `printf '%s' "$idx_content" | grep -qF "]($target)"` under this file's `set -o pipefail`: `grep -q`
  exits the instant it matches, `printf` is still writing and takes SIGPIPE, the pipeline's status
  becomes 141, and `if ! ...` reads that as "the link is missing". A lint that reports a real hit as
  a miss is worse than no lint, and it did so often enough to matter — isolated with a control that
  removes the suspected mechanism, 200 iterations each on content that provably contains the
  pattern: the shipped pipe form reported NOT-FOUND 32 times, a here-string 0 times.
  The site is now a here-string, so no producer remains to receive SIGPIPE, and the read-once-per-
  index shape the surrounding loop depends on is preserved. Pinned by `ReverseLinkRaceStabilityTest`,
  which runs the check 50 times over a ~37 KB fixture and requires every run to agree — at the
  measured 16% per-run rate that leaves a 0.016% chance a still-racy build passes unnoticed, where a
  single assertion would have passed 84% of the time. The same `producer | grep -q` shape survives at
  four other sites in shipped scripts; they are recorded rather than changed here, with
  `freeze-phase-docs.sh:234` the one carrying unbounded content and therefore the same risk profile.
- **No linter in this repository looked at `Manual/`'s own structure — measured 26.08.2026:
  `Manual/README.md` calls both `SYSTEM_OVERVIEW.md` and `SECTIONS_COMMANDS.md` "slim index →
  detail files", and that direction was never checked at all (WI-0112a).** `phase-docs-lint.sh`
  validates a different schema (`phase`/`subskill`/`status`) under `docs/<phase>/`,
  `memory-lint.sh` scans `docs/memory/**` only, `doc-volume-check.sh` measures size, not
  structure — none of the three read `Manual/`'s `kind`/`parent_index` frontmatter. New
  `scripts/manual-lint.sh` (generic over any root — not hardwired to `Manual/`, which
  `install.sh` never ships into `~/.claude/`) validates three checks: (a) every `parent_index:`
  resolves (document-relative first, root-fallback second, reusing `phase-docs-lint.sh`'s
  checks (f)/(g) cascade rather than a second rule); (b) the reverse direction — the index a
  working `parent_index:` names must itself link the claiming file back; (c) `kind:` against a
  fixed 19-value vocabulary, now documented in `templates/PHASE_DOC_SCHEMA.md` (`review` flagged
  as load-bearing: `phase-docs-lint.sh` reads it as a behavioural switch for the `docs/reviews/**`
  profile). Measured against this repository's own `Manual/` (22 files): the `parent_index`
  direction (check (a)) was already fully correct — all 15 pointers resolve, nothing to find —
  but the reverse direction (check (b)) was not: `SECTIONS_COMMANDS.md` links 0 of the 5 chapters
  that name it as parent, `SYSTEM_OVERVIEW.md` links only 3 of its 10 (`anchored-state`,
  `discipline-gate`, `memory-instincts`) — 12 findings total, left red on purpose; repairing
  `Manual/`'s own back-links is follow-up work, not part of this item. Registered as a fourth
  `/cleanup` step (`commands/cleanup.md` §6, pointed at `[projectdir]/docs` by default, since
  `Manual/`-style trees are not universal across CCPR projects).
- **A hand-typed test count in a docstring was three times the actual value, and the class it
  describes is exactly the one place that overstatement can cause a real regression (WI-0120).**
  `scripts/tests/test_memory_lint.py:309` said "this class's ~600 tests" where `MemoryLintTest`
  measured 26.08.2026 carries 205. The same class's size already caused a defect once: a sibling
  test class inherited from `MemoryLintTest` for its fixtures and silently inherited ~200 duplicate
  test executions with it (suite count 1397 → 1599, still exit 0 since duplicates pass). Both
  occurrences are reworded to state their point without a hand-maintained count that goes stale the
  same way the class grows — `test_memory_lint.py:198`'s "~200" is correct and left alone. The
  demanded sibling sweep found one more of the same species, milder: `test_external_tool_exit_status.py:119`
  said "~80 exemption sites" against a measured 95 (19%, already hedged with `~`); reworded the
  same stale-proof way.
- **The documented checklist and the checks it describes were never bound to each other
  (WI-0110).** Measured 26.08.2026: `scripts/memory-lint.sh` and the "Per file" checklist chapter
  of `Manual/system/memory-instincts.md` already agree — both name the same 15 check letters
  (`a b c c2 d e f g h i j k l m n`), since WI-0104 repaired the content. What was still missing
  was a test that would notice the *next* divergence; nothing enforced the binding, it only
  happened to hold. `scripts/tests/test_memory_lint_checklist_binding.py` extracts both letter
  sets — the script's `# (x)` comments (distinguishing genuine check-openers, preceded by a blank
  line, from three in-file back-references to already-defined checks) and the chapter's `**(x)`
  bullets — and asserts the sets are equal in both directions. Its RED proof was constructed
  deliberately on in-memory mutations (the real files already agreed, so the test cannot go red on
  its own): removing a chapter bullet, adding an undefined one, and re-lettering a script opener
  (a structural mutation, not a deletion) each surface the expected mismatch.
- **`memory-lint.sh` excluded every `MEMORY.md` index from its checks, on a stated reason that
  turned out to be false (WI-0108).** The exclusion comment read "indexes have no frontmatter" —
  measured 26.08.2026 across the four reference stores this project draws on (ccpr-gh,
  consumer-b, Org-X, ccpr): 16 of 27 index files DO carry a frontmatter block, and none of those
  16 had ever been validated, because the `find` populating the checked-files list excluded every
  file literally named `MEMORY.md` regardless of its content.

  The eleven frontmatter-less indexes in that same census decided the shape of the fix: dropping
  the exclusion outright (the item's original framing) would have sent all eleven through the
  "no YAML frontmatter" check as an immediate `err` — eleven errors in files nobody wrote
  frontmatter for on purpose, the opposite of a fix. The rule this change implements instead is
  what `templates/MEMORY_SCHEMA.md` already said and the lint had never actually enforced:
  frontmatter on an index is **optional**, and **validated when present**. An index without one
  stays silent; an index that does carry one now runs the same field/date/cross-ref checks as any
  other memory file — required fields, the `type` enum (now including `index` as a legal value on
  both the Tier-1 closed enum and the Tier-2 open one), `last_updated` form/age, and `related:`
  cross-refs — with one deliberate exception: `docs/memory/MEMORY.md` itself stays exempt from
  the Tier-1 `{type}_{slug}.md` naming check, since it is the index, not a Tier-1 memory file the
  rule was written for.

  Removing the `-not -name "MEMORY.md"` clause from the shared `find` also put the index file
  itself into the same array check (g) walks to warn about Tier-1 files the index forgot to
  reference — without a guard, every project's index would have been required to reference its
  own filename inside its own body, which no index does. That guard is the one change in this fix
  that reaches outside the frontmatter checks proper; measured against this repository's own
  `docs/memory/MEMORY.md`, it is what keeps the lint's own 5-warning baseline at 5 instead of 6.
  `instincts.md` stays excluded from the same `find` — same shape, a different question,
  deliberately untouched here.

  The sibling exclusion in check (i) (Tier-2-global silo validation,
  `[[ "$gbase" == "MEMORY.md" ]] && continue`) was aligned the same way, for consistency rather
  than because it fixes anything measurable today: only one Tier-2-global index exists across the
  reference stores (`~/.claude/memory/org-x/MEMORY.md`), and it has no frontmatter, so this half
  changes zero findings in any store currently in use.

- **`phase-docs-lint.sh`'s empty-scope report read like a clean pass, and the generator commands it
  validates against prescribed values it then rejects (WI-0121).** The item was filed against a
  different claim -- five files "self-declaring" as phase docs while never being validated -- which
  was retracted on re-measurement: those "violations" sat inside fenced `yaml` example blocks, not
  real frontmatter, and a frontmatter parser found the only files carrying real `phase:` frontmatter in
  this repository are the six shipped `templates/QA_SKELETON/*.md`, all valid. What survived
  re-measurement was two smaller, real defects.

  **First, the same empty-scope trap WI-0090 fixed for `artifact-gate.sh`'s deny-list scope.**
  `bash scripts/phase-docs-lint.sh .` on this repository (which has no `docs/<phase-folder>/` yet)
  printed `Files scanned: 0` next to `0 errors, 0 warnings` -- a true sentence that reads as "every
  phase folder was checked and found clean". The exit code is unchanged and stays 0: an empty scope
  here is a *supported* configuration (a project before P3, or on the Lean-Track, has no phase
  folders yet), not an error, for the same Constitution "installable and runnable on a clean
  machine" Inviolable reason WI-0090 decided for artifact-gate.sh's default. What changed is the
  report: a companion `**Phase folders found:**` line now names which of the nine `PHASE_FOLDERS`
  actually exist (or, on a `--scope` run, its own glob already said so), and a run that collects zero
  files emits a notice on **stderr** -- naming the directory and the folder names it looked for --
  so a caller keeping stdout as its findings report cannot lose it. Unlike artifact-gate.sh, nothing
  here routes through a deny-list mask that escalates to `python3` on a non-ASCII byte, so the
  em-dash trap that check found does not apply to this script's summary line.

  **Second, three generator documents prescribed frontmatter values the validator's own
  `VALID_PHASES`/`VALID_STATUS` enums reject** -- `docs/PROJECT_PHASES.md`'s canonical "Detail file
  frontmatter" example (`phase: p0` lowercase; `status: complete` with a `# draft | complete |
  needs-rework` comment, all three of which are outside `VALID_STATUS`), `docs/adr/ADR-0009-...md`
  and a companion local working note (`phase: 3`, missing the `P` prefix), and three `commands/p4-*.md`
  detail-file examples (`status: active | partial | pending`, `status: living | complete`, and a
  comment naming `complete` again) -- so a document written by following one of these examples
  literally would fail the lint meant to accept it. `complete` has no direct counterpart in
  `VALID_STATUS`; `frozen` ("completed (phase passed Gate)" per `templates/PHASE_DOC_SCHEMA.md`) is
  the closest semantic match and is now used at every `complete` site. `p4-setup.md`'s
  `active | partial | pending` maps onto the existing `active`/`draft`/`skeleton` semantics instead
  (`partial` = in progress = `draft`, `pending` = not started = `skeleton`) -- a cleaner fit than
  repurposing `frozen` there. One value was deliberately left alone: `p4-sprint.md`'s
  `kind: risk-detail` block's `status: open | mitigated | accepted | closed` is the RISK lifecycle,
  not the document lifecycle -- a different axis that happens to collide on the field name.

  A new corpus test (`scripts/tests/test_frontmatter_examples_match_the_lint.py`) binds every fenced
  `yaml` frontmatter example under `commands/`, `docs/` and `templates/` to `phase-docs-lint.sh`'s
  own `VALID_PHASES`/`VALID_STATUS` -- read from the script's source text, never re-typed -- so this
  generator/validator disagreement cannot recur silently.

- **`artifact-gate.sh` could report a clean pass on a run where the check it is named after never
  executed (WI-0090).** The deny-list of tenant/project names comes from a personal, non-distributed
  config, so it is unset on every freshly installed CCPR — and on the machine where this was
  measured. On such a run the other checks did all the work and the summary said `scanned 296 files,
  0 findings in 0 files`, a true sentence that reads as "every check ran". The notice above it did
  say the deny-list was unconfigured, but it was printed on **stdout**, next to the findings:
  `artifact-gate.sh --repo . >/dev/null` printed nothing at all and exited 0 — byte-identical to a
  fully configured clean run redirected the same way.

  **The default was measured and kept.** Making an unconfigured deny-list fail by default was the
  first candidate and is the wrong answer here: the list is personal and non-distributed, so the
  Constitution's "installable and runnable on a clean machine" Inviolable makes running without it a
  *supported* configuration, not an error. Measured before deciding — flipping the default turns
  **101 of this repository's 1388 tests** red and contradicts the shipped CI template's documented
  default (`templates/ci/artifact-gate.ci.sh` ships `REQUIRE_DENYLIST=0` and promises the run "does
  not pass silently" rather than fail), which makes it a breaking interface change under ADR-0001
  rather than a style choice. `--require-denylist` remains the opt-in for callers that need the
  strict answer, and the reasoning is now written into the script's header, which is also its
  `--help` text.

  **What changed is the report.** The summary line now names the scope of *checks* as well as the
  scope of *files*: `scanned N files, F findings in D files; deny-list: K name(s) checked`, or
  `; deny-list check DID NOT RUN (no names configured)`. The count and never a name — a CI log is a
  shipped artifact too — which also lets an operator see that a five-entry list arrived as five. And
  the not-configured notice moved to **stderr**, the channel this script already uses for every
  other "the run could not do its job" line, so a caller that keeps stdout as its findings report
  cannot lose it. Two clean runs over the same file, one configured and one not, both still exit 0
  and are now told apart by their summary line.

  **Found by the existing suite while fixing it:** the first version of the summary line used an em
  dash like its neighbours. Every emitted line passes through the deny-list mask, which escalates to
  a `python3` subprocess as soon as either the line or the list carries a non-ASCII byte — so an em
  dash on a line that prints on *every* run started python3 on every run with a configured ASCII
  deny-list, and under a broken interpreter printed a Python fatal-error dump where an ASCII-only run
  is meant to be silent. The summary line is ASCII on purpose, with the reason recorded at the call
  site.

- **The Manual carried the Memory Lint checklist twice, and neither copy matched the script
  (WI-0104).** `Manual/SYSTEM_OVERVIEW.md` and `Manual/system/memory-instincts.md` held the same
  list by intent; the overview had fallen four bullets behind. Copying the four across would have
  restored parity for a day — `Manual/README.md` already declares `SYSTEM_OVERVIEW.md` a *slim
  index* over `system/` detail files, so the duplication was an unfinished split, not a design.
  The chapter is now the single documented list and the overview carries an orientation paragraph
  plus a `**Full chapter**` pointer, the same shape the `/anchor` section in that file already
  uses.

  **Counted in the script rather than inherited from the list.** `memory-lint.sh` runs **fifteen**
  checks — (a)–(n) plus (c2). Both registers named ten of them. Four were undocumented anywhere:
  the tier-aware `type` enum (c), the `last_updated` *form* check added by WI-0106 (e), the
  split-layout topic-file schema and size caps (l), and the archive-presence note (m); the
  project-root fallback in (f) and the two extraction limits in (n) were likewise unmentioned.
  Every bullet now names its check letter, so a sentence can be traced to the code block that
  implements it, and severities are stated — the old list said which checks existed but not which
  of them fail a run.

- **Three German words in shipped English Manual prose, each duplicated across an index/chapter
  pair (WI-0104, Constitution Inviolable "English in shipped content").** `# required, DD.MM.YYYY
  (optional " (Notiz)" suffix)` in both frontmatter examples now reads `DD.MM.YYYY or
  "DD.MM.YYYY (note)"`, matching `PHASE_DOC_SCHEMA.md`'s own wording. `architectural leitplanken`
  and `Lean-Vorlauf` in `SYSTEM_OVERVIEW.md` + `system/cross-cutting.md` are now `architecture
  guardrails from "inviolable"-tagged ADRs` and `Lean pre-run` — the terms `commands/constitution.md`
  itself uses, so the Manual stops describing a mode by a name the command does not have.

- **`SYSTEM_OVERVIEW.md` still taught the tier tiebreaker CLAUDE.md withdrew.** "When in doubt,
  prefer Tier 1 (visibility wins over isolation)" — the exact phrase removed from
  `commands/postmortem.md` under WI-0065 for leaking persona-specific patterns into the globally
  autoloaded file. The correction swept the skill and missed this copy, which is the same defect
  the item above is filed for, one section further on. Replaced with the reversed rule and a
  pointer to the full three-step decision order in `system/memory-instincts.md`.
- **`last_updated` accepted a trailing note that the memory schema never mentioned, and the two
  linters disagreed about which notes were legal (WI-0106).** `MEMORY_SCHEMA.md` specified
  `DD.MM.YYYY` and nothing else, yet ten files in this repository's own store append a note to the
  value — `24.08.2026 (WI-0102)`, `16.05.2026 (Note: agent migration verified later same day)`.
  They passed because `memory-lint.sh` never asked about the value's shape: it handed the raw string
  to `date`, and both implementations accept trailing text after the part they matched. The
  tolerance was therefore real but accidental, and invisible to anyone reading the schema — which is
  how it was rediscovered, as the collateral of a WI-0087 fix shape that would have turned all ten
  into hard errors.

  **Resolved by widening the schema, not the files.** The note says *why* the date moved — which
  round, which item — and that is context no other field carries; the practice is older than the
  rule and better than it. `MEMORY_SCHEMA.md` now specifies the form precisely enough to enforce:
  `DD.MM.YYYY`, optionally followed by whitespace and a single parenthesised group running to the
  end of the value. `PHASE_DOC_SCHEMA.md` had specified the same optional suffix for phase documents
  all along.

  **The tolerance is now checked rather than inherited.** `memory-lint.sh` check (e) matches the
  documented pattern — character-for-character the one `phase-docs-lint.sh` already used — before it
  parses the date, and keeps the parse behind it: the pattern says nothing about whether `32.13.2026`
  is a day, the parse says nothing about what follows the year. Measured across the four live
  inventories: 106 `last_updated` values in scope, 10 annotated, **0 outside the documented form**,
  and every report byte-identical before and after. This rejects nothing that exists today; it
  closes three shapes that were silently accepted here while `phase-docs-lint.sh` rejected them
  (`24.08.2026 a note without parentheses`, `24.08.2026(WI-0102)`, `24.08.2026 (unclosed`).

  **One divergence is left open on purpose.** A well-formed but impossible date (`32.13.2026`,
  `99.99.9999`) is rejected by `memory-lint.sh` and accepted by `phase-docs-lint.sh`, which has no
  date check beyond its pattern. Closing it would reject content that script accepts today — an
  ADR-0001 promotion decision, not the writing-down of an existing practice. Both scripts now say so
  at the check.

- **`phase-docs-lint.sh`'s `last_updated` tolerance was documented but not held by any test.**
  Measured against mutants of check (e)'s pattern: loosening the required space before the note,
  dropping the parentheses from the note group, dropping either anchor — all four survived the
  suite, because the one negative case it had (`2026-05-04`) fails under every variant. Four cases
  added; each kills one mutant. No behaviour change.

- **`memory-lint.sh` reported a file's age as a property of the clock, not of the file (WI-0087,
  rediscovered independently as WI-0103).** `date_to_epoch()` parsed `DD.MM.YYYY` with a BSD format
  string carrying no time component, and BSD `date` fills unnamed fields from the RUNNING wall clock.
  `TODAY_EPOCH` was captured once at script start, so the two sides of the subtraction held different
  times of day and their difference was short by the script's own elapsed runtime — after integer
  truncation, one day low. Measured on a live store before the fix: six consecutive runs over the same
  unchanged inventory reported `93/93/91` four times and `94/94/92` once, with nothing changed between
  them. On a store large enough to take a second to walk, the SAME run disagreed with itself: of 60
  files all 91 days old, 58 reported 90 and stayed silent.

  **The consequence was a silent false negative at exactly the threshold check (e) exists for.** A file
  genuinely `STALE_DAYS + 1` days old was reported as `STALE_DAYS`, the `>` comparison was false, and no
  warning fired. The check under-reported staleness; it never over-reported it.

  **And the two branches disagreed with each other.** The GNU fallback builds an ISO date, which `date -d`
  anchors on midnight, so the same file could warn on Linux and stay silent on macOS. Measured with GNU
  coreutils 9.11 in the script's own GNU path: `94/94/92` on every run, against a BSD path flapping
  between `93/93/91` and `94/94/91`.

  Both ends are now anchored at **UTC** midnight and derived through the same function, so the difference
  is an exact multiple of 86400 by construction. UTC rather than local midnight because two local
  midnights spanning a spring-forward are only 23 h apart, which reintroduces the identical off-by-one
  for every window crossing that transition — measured on both implementations: 01.01.2026 to 01.04.2026
  is 90 days and comes out as 89 when anchored locally. The BSD branch normalises in two steps rather
  than appending a time to the value, so that what counts as a parseable date is unchanged: both
  implementations accept trailing text after the date, ten files across the live stores are written that
  way, and the single-call form turns every one of them into a hard error (measured: 10 new errors, and
  this script moving from exit 1 to exit 2 on its own repository). Whether that tolerance should stay is
  filed separately as WI-0106.

  **This changes reported numbers, which is the point.** Across the four inventories the fix moves ages up
  by one where the old code truncated, adds and removes no finding, and leaves every exit code as it was
  (1/2/1/1). Six consecutive runs per inventory now produce identical reports (bar the report's own
  `**Run:**` timestamp line), and the BSD and GNU paths agree byte for byte on the same store.

  The suite could not have caught this: no test asserted a concrete age. Two now do, and neither adds a
  seam to the script. The first sizes its fixture so the defect reproduces rather than coin-flips; the
  second places the run in a time zone whose calendar day currently differs from UTC's — `TZ` is a plain
  POSIX variable, not something added to make the script testable — which is what pins "today" to the
  local calendar day at any hour of the day.

- **The dependency scan reported "clean" exactly when it found something (WI-0102).** Every external
  scanner `quality-scan.sh` drives shares one shape: it prints its full JSON report AND exits non-zero
  when it finds vulnerabilities. The `|| echo '{}'` arm therefore fired on the FINDINGS case, appending a
  second JSON document to a complete one; `json.load` died on "Extra data", and a bare `except: print(0)`
  turned the crash into a zero. Measured against a throwaway project pinning `minimist 0.0.8`: npm's own
  answer was `{critical: 1, total: 1}` with exit 1, the shipped chain's answer was `0`. Measured on
  `pip-audit 2.10.1` against `jinja2 2.10`: 6 vulnerabilities, exit 1, chain reported `0`. The wrong
  direction is the dangerous one — a zero reads as a clean bill, not as a failed measurement.

  **The count was wrong even when the chain worked.** `sum(meta.values())` added npm's severity buckets
  AND its `total` key, which holds their sum, so one critical advisory came out as `2`. On the Python
  side `len(json.load(...))` counted the report object's two TOP-LEVEL KEYS (`dependencies`, `fixes`), so
  a project with no vulnerabilities at all was reported as "2 Python vulnerabilities found" — a false
  alarm to go with the false all-clear. Both are now counted by what they claim to count: severity
  buckets only, and vulnerabilities summed per dependency (both pip-audit report shapes).

  **No silent fallback is left.** "the tool could not be evaluated" and "the tool found nothing" no longer
  produce the same number: an unusable report becomes a `scan-error` finding carrying the producer's own
  last stderr line, and a lockfile or manifest present with no scanner installed becomes a `scan-skipped`
  finding. Only a tool that ran and genuinely found nothing yields an empty findings list. A non-zero exit
  status outside the range each tool documents as "ran to completion" is a `scan-error` too, even when the
  report happens to parse.

- **`semgrep` findings killed the whole SAST scan whenever a rule message contained an apostrophe
  (WI-0102, found while measuring the above).** The merge step interpolated the semgrep findings JSON
  straight into Python source. Measured against real semgrep 1.174.0: the first rule it hits on a
  `subprocess(..., shell=True)` call is worded `Found 'subprocess' function 'call' with 'shell=True'`, the
  interpolated source failed to parse, `set -e` aborted the run — exit 1, no report written at all. Same
  apostrophe class as WI-0055, one function further down. No shell value is interpolated into Python
  source in this script any more: producers write to a file and the reader receives the PATH in `argv`.
  (semgrep's exit code itself was measured and is the benign one of the three: `--config=auto --json -q`
  exits 0 with findings. The same run with `--error` prints the same report and exits 1, so the shape was
  one flag away from breaking there too, and it is now handled either way.)

- **`set -e` never protected any scan function, on the bash this project pins (WI-0102).** Each scan is
  invoked as `results+=("$(scan_X)")`, and bash 3.2 — macOS `/bin/bash` — does not honour `set -e` inside
  a `$(...)` command substitution: measured, a failing command there aborts neither the function nor the
  script, and the outer run still exits 0. So the `# exit-status: exempt set-e-sufficient` justification
  did not hold inside these functions, and a crashed producer silently contributed nothing. The grep-based
  pattern pass now goes through the same reader as the external tools (a crash becomes a `scan-error`, not
  zero patterns), the report reader is called through an explicit `if !` check, and a scan function that
  produces no record at all now fails the run loudly instead of vanishing from the report.

  Also fixed in passing: a project with both a lockfile and a `requirements.txt` lost its npm findings,
  because both tools wrote the whole scan record to the same file and pip-audit clobbered npm's.

- **check (n) reported the target of a definition-shaped line that cannot open a definition — the last
  false positive in the corpus (WI-0096).** A link reference definition may not INTERRUPT a paragraph.
  With prose open above it, `foo` then `[ref]: dead.md`, the reference reads the second line as ordinary
  text, defines nothing and renders `<p>foo
[ref]: dead.md</p>`. check (n) reported `dead.md` anyway:
  `refmap` already declined to treat the line as a definition (WI-0093), but the REPORTING path was
  gated on nothing. Both now sit behind the same `pbuf_n == 0` gate. Pre-existing — `4f2ffa7` behaves
  identically — and pinned by a mutation that drops the gate and asserts the exact inverse behaviour on
  the same fixture.

  **Why WI-0085 stays** — the two are the same bytes and the opposite verdict, and the line between them
  is what the READER sees, not the syntax. `[ref]: dead.md` standing alone renders as NOTHING: the author
  declared a destination, the file is gone, and no reader will ever notice it. That is invisibly dead, and
  catching it is what check (n) is for, even where CommonMark renders no link at all (PO decision
  23.08.2026). The same line under an open paragraph renders as VISIBLE paragraph text: the path is prose
  on the page, not a pointer, and reporting it said something untrue about a line the reader can read.
  Both verdicts have their own corpus entry, and dropping either gate turns exactly one of them red.

  The `reflbl != ""` half of the same gate answers a third shape by the same rule, and it was measured
  rather than assumed: `[ ]: dead.md` (a label of nothing but whitespace) and `[]: dead.md` are no
  definitions either — a label needs one non-whitespace character — and both render as visible prose.
  `4f2ffa7` reported the whitespace one; the working tree already did not, through `reflbl != ""` and not
  through the paragraph gate. Measured both ways (removing one gate leaves the other shape silent) and
  now pinned by two corpus entries, where before it was an untested accident.

- **`tolower()` on a reference label answered differently depending on the process locale, and the
  harness measured the narrow answer (WI-0099).** Label matching follows the reference normalisation,
  which case-folds — and what `tolower()` does above 0x7F is a property of the LOCALE, not of this
  script. Under a UTF-8 locale `[ÄÖ]:` matched `[äö]` and agreed with the reference; under C/POSIX it did
  not and the enclosing link was reported. The test harness runs the script with a bare environment
  (`HOME` and `PATH` only), i.e. in the C locale, so the suite froze one answer while an interactive run
  gave the other.

  Fixed in two parts, because pinning the locale alone would only have made the wrong answer STABLE.
  (1) `LC_ALL=C` at the awk call site, in line with `artifact-gate.sh`, `memory-sync.sh` and
  `lib/discipline_gate.sh` — the byte-oriented answer is now the same everywhere. (2) A label carrying
  any byte >= 0x80 short-circuits to "resolves" without consulting `refmap` at all, so a non-ASCII label
  is never DECIDED by a folding that cannot fold it. The direction of that short-circuit follows from the
  shape of the caller and not from a sample of inputs: "resolves" only ever deactivates an enclosing
  opener, and the only `print` sits behind an active opener, so the branch can drop a finding and not
  invent one. The detection is byte-wise via `index()` and deliberately not a regex — all three regex
  spellings abort this awk with `towc: multibyte conversion failure`.

  **The trade, named:** an UNDEFINED non-ASCII label now silences the link around it — a false negative
  that is a property of this code, in place of a false positive that was a property of the environment it
  was measured in (PO decision 24.08.2026), with its own corpus entry. Deliberately NOT narrowed on the
  definition side: `[ÄÖ]: dead.md` still reports its target. Whether a label MATCHES is the question
  narrowed here; whether a destination EXISTS is check (n)'s own contract and needs no folding at all.

- **The corpus now carries no `false-positive` divergence at all.** 68 -> 76 entries. Of the 68
  pre-existing rows exactly two move: the WI-0096 row (its `known_divergence` becomes null and
  `dead-interrupt.md` leaves its findings) and the WI-0098 row (its `reason` now states the class rather
  than the one shape). Eight rows are added — two for the whitespace/empty definition labels above, and
  six for the WI-0098 collision class: three divergences, each paired with a control carrying the same
  label and NO colliding definition, where the link IS still reported. Twelve `false-negative`
  divergences remain and three `documented_intent` rows. WI-0096 is also removed from the closed set of
  work items allowed to own a `known_divergence`, so re-opening it has to be a deliberate act.

- **check (n) reported an outer link whose text contains a reference whose label the paragraph
  resolver rewrites — a false positive the two-pass round below introduced (WI-0098).** The two ends of
  the reference mechanism read their label from different text. The definition line reads the RAW
  record; the usage side reads the paragraph after `protect_link_destinations()` and
  `resolve_paragraph()` have run, and those DELETE a code span outright and replace a closed inline
  comment with a boundary sentinel. So ``[`a`]: def.md`` registered the label `` `a` `` while
  ``[outer [`a`] text](out.md)`` looked up the empty string, nothing matched, no deactivation happened
  and `out.md` was reported. Measured three ways: the reference (`commonmark==0.9.2`, HTML and AST) and
  `4f2ffa7` both report only `def.md`; the working tree reported both. `4f2ffa7` was right by accident —
  its `[^][]*` label class could not match a bracketed label at all. The inline-comment spelling
  (`[<!--x-->]`) was measured separately rather than assumed to be the same mechanism; it is.

  Fixed on the definition side, by registering each definition label a SECOND time in the shape the
  scanner will read it in — the raw label put through the same two functions — so that both ends key one
  space. It is an additional key, never a replacement, and that is what bounds the risk: adding keys can
  only make more references RESOLVE, a resolving reference only ever DEACTIVATES an enclosing link, so
  this cannot invent a finding — so long as `protect_link_destinations()` draws correct spans, which is
  WI-0095 and still open. `parse_link_label()` is blind to the destination sentinel, so a `]` inside a
  wrongly drawn span terminates a label and the consuming advance lands inside that span, where the
  argument no longer holds; on bracket-soup input check (n) has been measured reporting targets the
  reference never renders. That precondition is now written into the source next to the argument.

  Under it, the error the fix can make is dropping one, and it makes exactly one — a CLASS, not a shape.
  Label resolution is not INJECTIVE, and it has two accumulation points: the EMPTY key (a code-span-only
  label ``[`x`]``, a literal `[]`, a whitespace-only `[   ]` — the last two wider than the shape this was
  found on, because the reference never looks an empty label up at all) and the `boundary` key (any label
  that is exactly one closed inline comment, so `<!--a-->` and `<!--b-->` are interchangeable with no
  empty label involved). Once any definition owns such a key, every other label collapsing to it reads as
  a resolving reference and silences the link around it. All routes are measured, each against a control
  carrying the same label and NO colliding definition where the link IS reported, so the loss is pinned
  on the collision and not on the label shape. Traded deliberately (PO decision
  24.08.2026 — a false negative may replace a false positive, not the other way round) and counted as
  its own corpus entry. The counter-fixture that forbids the blunt repair has its own test: a code-span
  label with NO definition must keep reporting the outer link, because the reference renders it.

  The fix covers every construct either function rewrites, because the label is put through the
  functions rather than through a list of cases. It does not cover a construct whose resolution depends
  on text OUTSIDE the label (an unpaired backtick finding its partner later in the paragraph), where
  standalone and in-context resolution can still disagree; named in the source, not fixed here.

- **`paren_mark`, the sentinel a link destination's escaped `)` was detoured through, is removed.** Its
  stated reason had already expired: `process_link_line()` used to find a link span with a `[^)]*` scan
  blind to the `dest_mark` opacity, and WI-0080 replaced that scan with one that reads the extent off
  the span. The retention argument — "no test can pin the removal in either direction" — was false, and
  the line below the substitution is why: `decode_numeric_entities()` runs AFTER it, so
  `[x](a&#41;b.md)` has been putting a literal `)` inside a protected destination since WI-0081 and
  resolving correctly. The post-removal state was already pinned by a fixture that predates the removal;
  both spellings now have an explicit one, plus a two-links-on-one-line pin per spelling.

- **The pass-boundary reset now has tests, and three of its lines turn out to be the load-bearing
  ones.** Reading each index twice means pass 2 must start from BEGIN state; five of the reset lines
  were pinned by nothing. The three that can be observed — `in_fence`, `in_html_block1`,
  `in_html_block6` — get one behaviour test each (an unclosed construct at the pass boundary, with a
  dead link in FRONT of it, so an assertion of "one finding" cannot be satisfied by a pass that scanned
  nothing) and one mutation test each that removes exactly that reset line. Two measured details shape
  the fixtures: the dead link has to sit before the first BLANK line of the document, because a leaked
  fence arrives with `fence_char`/`fence_len` already reset and its closer test degenerates into a
  blank-line match, and a leaked type-6 block closes at a blank line by its own rule. The remaining two,
  `fence_char` and `fence_len`, are deliberately left untested and the reason is measured, not assumed:
  removing either changes nothing observable on any of ten fixtures, because both are read only under
  `if (in_fence)` and every path that sets that flag assigns them in the same breath. Nineteen structural
  mutations in that class now, each falsified once by neutralising the mutation.

- **Three corpus entries added: one for a reach that was described rather than pinned, one for a PO
  decision, one for a divergence traded in.** The WI-0097 stray-sentinel entry claimed a reach it could
  not discriminate — a second, independent
  link AFTER the construct shows the loss is the whole remainder of the paragraph, not just the link
  between the two sentinels (`stray_sentinel_byte_swallows_the_rest_of_the_paragraph`). WI-0092 (a link
  inside IMAGE ALT TEXT, `![a [b](in.md) c](out.png)`, which
  the reference renders as plain text and check (n) reports) is filed as `documented_intent` on the
  WI-0085 argument, PO decision 23.08.2026; it is pre-existing and `4f2ffa7` behaves identically. The
  third is `two_labels_with_the_same_resolved_shape_are_interchangeable`, the false negative the WI-0098
  fix above buys — it was counted in the 65 -> 68 total but not named here. The
  generator's docstring now carries the guard that class needs: `documented_intent` may only be assigned
  when the justification would hold even if no criterion depended on it — otherwise a round ends clean
  because a divergence changed its name. Corpus 65 -> 68 entries; all 65 previous entries are
  byte-identical after regeneration.

- **check (n) reported the outer target of a link whose text contains a RESOLVING reference link
  (WI-0093), and did not recognise a reference definition whose label carries an escaped bracket
  (WI-0094).** CommonMark's "links may not contain other links, at any level of nesting" fires on any
  successful LINK, not only an inline one. The WI-0080 scanner (see the entry below) implemented that
  rule in its inline-destination branch only, so `[outer [ref] text](out.md)` with `[ref]:` defined
  reported `out.md` — a FALSE POSITIVE, and one the regex the scanner replaced did not produce. It is
  the shape that blocked the promotion of check (n) to `err`. Fixed by extending the rule to the three
  reference forms, each measured against the pinned `commonmark==0.9.2` reference and not read out of
  the spec: shortcut `[ref]`, collapsed `[ref][]` and full `[text][ref]` all deactivate the enclosing
  openers when they RESOLVE, and consume the span they matched — `[text][ref](x.md)` renders the
  reference link and leaves `(x.md)` as literal text, so a scanner that only deactivated would re-read
  `[ref](x.md)` as an inline link. Three measured details decide the shape of the fix and none of them
  is obvious: (1) a FAILED full reference does not fall back to the shortcut reading, so
  `[ref][nosuch]` renders no link at all even with `[ref]:` defined and the enclosing link survives;
  (2) an IMAGE reference (`![ref]`) resolves but is an image, so it leaves the enclosing link alone,
  exactly as WI-0091 established for the inline form; (3) whether the inner label RESOLVES is the ONLY
  thing separating this from `[a [b] c](t.md)`, WI-0080's central fixture, which must stay one ordinary
  link — so "deactivate whenever no inline destination follows" is not a repair, it is a regression.

  Deciding any of it needs the document's reference-definition labels, and CommonMark collects those
  for the WHOLE document before it parses any inline content — a definition may legally stand AFTER the
  link that uses it (measured). A single pass cannot answer the question at the moment it reaches the
  link, so the extractor now reads each index TWICE: pass 1 prints nothing and only collects labels,
  pass 2 does the extraction with the complete set. Two passes of the SAME program, not a cheap
  pre-scan for definition-shaped lines: whether a line IS a definition depends on its block context —
  inside a fence or an HTML comment it is not one, and it may not interrupt a paragraph, all measured —
  and that context is precisely what the record block already computes. Label matching follows the
  reference's normalisation (internal whitespace collapsed, ends trimmed, case-folded). Case-folding is
  `tolower()`, and what that does to NON-ASCII depends on the process LOCALE, not on this script: under
  a UTF-8 locale `[ÄÖ]:` and `[äö]` match and agree with the reference, under C/POSIX they do not and
  the enclosing link is reported. The test harness runs the script with a bare environment, i.e. in the
  C locale, so the corpus freezes the narrower answer while an interactive run gives the wider one.
  Measured both ways and filed as WI-0099; not fixed in this wave.

  WI-0094 is the sibling defect the same round exposed one function further along: reference
  definitions were recognised with `\[[^][]+\]:`, the very label class WI-0080 had already removed
  from the usage side. A definition whose label carries a backslash-escaped bracket
  (`[a\]b]: dest.md`, one definition at the reference) was therefore not a definition at all — its
  target went unchecked and its label stayed undefined for the rule above. Both sides now share one
  `parse_link_label()` implementing the reference's own label grammar, so the two cannot drift apart
  again. Eight further structural mutations were added on top of WI-0080's six, one per new rule — the
  refmap lookup forced to "yes" and to "no", the two label sources swapped, label collection restricted
  to pass 2 (a BACKWARD definition asserted still working, so the mutation discriminates the
  forward-reference claim and not the feature), the paragraph gate dropped, the consuming advance
  replaced by a one-byte one, an image reference made to deactivate, and the label grammar made to skip
  one byte per escape instead of two. Each was itself falsified once, by neutralising the mutation and
  confirming it goes red — a mutation test that cannot fail proves nothing.

  **Three divergences this round measured and did NOT close**, recorded in the corpus rather than left
  unnamed, all in the false-negative direction: `protect_link_destinations()` spans the text after ANY
  `](` occurrence, live opener or not and escaped or not, and since WI-0080 the scanner skips such a
  span WHOLESALE — so a wrong span now hides the real link inside it, where the previous regex simply
  re-read through it (WI-0095, two entries); a literal 0x03 byte in a source file pairs with the
  opening sentinel of the next real destination and eats the link between them (WI-0097, pathological
  input, one entry); and a definition-shaped line that cannot interrupt a paragraph still has its
  target reported, which may be the WI-0085 decision one shape further along or a defect, and is filed
  as an open question for the PO rather than assumed (WI-0096, one entry). Corpus 52 -> 65 entries; all
  52 previous entries are byte-identical after regeneration.

- **check (n) could not see any link whose label contained a bracket, at any nesting depth, and could
  not see the badge pattern at all (WI-0080, WI-0091).** The extractor matched links with the regex
  `\[[^][]*\]\([^)]*\)`. That label class excludes BOTH bracket characters, so `[a [b] c](target.md)`
  — one ordinary link per CommonMark — never matched, and neither did `[a\]b](target.md)`, where the
  inner `]` is backslash-escaped rather than balanced. Both were silent false negatives. Widening the
  class would not have fixed it: CommonMark link text is a BALANCED construct of arbitrary depth, and a
  regular expression cannot count — the reference renders one link at nesting depth 1, 2, 3, 5, 10, 20,
  50 and 100, with no ceiling (measured, not assumed). The regex is therefore replaced by a scanner with
  an explicit opener stack, implementing four rules, each one measured against the pinned
  `commonmark==0.9.2` reference rather than read out of the spec: (1) `[` pushes, `]` pops, so balanced
  brackets in the label are ordinary content at any depth; (2) a backslash-escaped bracket neither opens
  nor closes, decided by backslash-run PARITY (`\\[x](t.md)` carries an escaped BACKSLASH and a live
  bracket) — the same parity now also decides the image marker, so `\![x](t.md)` is a LINK, not an image;
  (3) "links may not contain other links, at any level of nesting" — on a successful link every enclosing
  opener is deactivated, so the INNER link wins and the outer target is never reported; (4) an IMAGE in
  the link text does NOT disqualify the enclosing link. Rule 3 used to hold by accident, because the
  outer label could not match either — the corpus recorded an agreement no rule was responsible for; it
  is now explicit and pinned. Rule 4 is WI-0091, filed as its own item because its cause is separate:
  `[![build](badge.svg)](ci-url)`, the badge pattern, is a live link whose text is an image, and check
  (n) reported neither the link target nor anything else. It is also the shape that rules out every
  repair short of a real scanner — the LABEL itself contains a `](`, so any "split at the `](`" choice is
  wrong. Nothing is skipped by a match LENGTH any more — the scan only jumps over something it has
  RESOLVED (an opaque destination span, or a link it just consumed) and advances one byte everywhere
  else — so WI-0079's guarantee that a DISQUALIFIED construct cannot hide a real link later on the same
  line is now structural rather than hand-arranged. Mutation-checked by structure, never by deletion: escape parity
  replaced by a one-byte lookbehind, the escape probe moved one byte past each bracket in turn, the
  deactivation predicate INVERTED, the deactivation moved OUT of the image branch so an image disqualifies
  too, and the opener stack CAPPED at one entry (with the flat case asserted still green, so the mutation
  discriminates depth specifically) — six mutations, each confirmed to flip its own fixture, the real
  script untouched and md5-verified. Corpus 46 -> 52 entries; three lose their `known_divergence`
  (`nested_brackets_in_link_text_simple`, `nested_brackets_in_link_text_mid_sentence`,
  `backslash_escaped_bracket_in_link_text`), the other 43 are byte-identical after regeneration, and the
  six additions cover three-level nesting, an unbalanced-bracket negative pin, inner-wins-beside-a-later-link,
  the badge pattern, two nested images, and an image with a bracketed alt text.

  **Upgrade note:** against the last RELEASE (`v0.2.1-beta`) this wave removes no finding — measured,
  with both scripts, on every shape this wave discusses, including the three it regresses on internally
  (below): `v0.2.1-beta` reported none of them either. Against the INTERMEDIATE state `4f2ffa7`, i.e.
  for anyone tracking `main` rather than releases, the claim does not hold and the difference is not
  cosmetic — the WI-0080 scanner skips a `dest_mark` span wholesale where the regex it replaced re-read
  through it, and that costs three shapes, all measured: `x](y [a](t.md) z)` and its escaped twin
  `x\](y [a](t.md) z)` (WI-0095, two corpus entries, `4f2ffa7` reported the inner link, this version
  does not), and a literal 0x03 byte in the source, which now swallows the rest of its paragraph
  (WI-0097, two corpus entries, one defect — `4f2ffa7` reported both links, this version reports
  neither). All three stay open. WI-0098's traded false negative is NOT in this list: `4f2ffa7` did not
  report that shape either, so it is a divergence from CommonMark, not a loss on upgrade.

  Otherwise the direction is additive: it ADDS findings on unchanged content — a store nobody has
  touched can start reporting dead links after the upgrade, because those links were always dead and the
  extractor simply could not see them. On its own this change does not move the EXIT CODE: check (n) was
  filed under `warn` by default (`MEMORY_INDEX_LINK_SEVERITY`), so the new findings landed in Warnings
  and a run that exited 0 still exited 0 unless it already had warnings. **Corrected after this entry
  originally shipped (WI-0005):** it went on to say "the breaking moment is the promotion of check (n) to
  `err`, not this change" — and that promotion is no longer a later release. It is in THIS one, under
  `Changed`. Read together, the exit code does move: a store nobody has touched can go from **exit 0 to
  exit 2** on upgrade, because this entry supplies the new findings and the promotion files them as
  errors. `MEMORY_INDEX_LINK_SEVERITY=warn` restores the severity this entry assumed. Expect
  it wherever an index uses brackets inside link text (`[Release state [measured]](file.md)`) or the badge
  pattern. Measured against four live memory stores with both script versions on the same day: identical
  in all four, because the constructs are almost absent there — a null result that proves nothing, so the
  evidence is a discriminating probe on a COPY of a real memory tree instead, where the old script
  reported 2 warnings and the new one 4, the two additions being exactly the dead nested-label and dead
  badge targets, with the live ones and both image sources correctly silent.
- **check (n)'s paragraph buffer missed three block boundaries CommonMark honours, swallowing real
  links across the merged blocks (WI-0086, WI-0082).** The buffer accumulates a paragraph across
  physical lines so a code span may straddle them, and it flushes only at a boundary it recognises. A
  boundary it did not recognise merged two blocks, letting two backticks that each belonged to a block
  of their own pair across the merge and hide a real link — a false negative in all three cases.
  Closed: (1) a CARRIAGE RETURN is now stripped from every record before any boundary test runs.
  CommonMark counts `\r\n`, `\r` and `\n` all as line endings; awk splits on `\n` only, so on a
  CRLF file — anything authored on Windows, or any checkout with `core.autocrlf=true` — every
  `$`-anchored regex in the extractor silently stopped matching, not just the blank-line test — an empty
  ATX heading, a fence close, and a reference definition carrying a quoted title (`[ref]: x.md "t"`,
  whose destination was then never checked at all) were each confirmed broken by the same cause, the
  last of them in the one branch that does not test the record directly. (2) a THEMATIC BREAK
  (`***`, `---`, `___`, with optional spaces or tabs between the markers) is now a boundary, and
  deliberately an UNGATED one — a break really does end an open list item, measured
  (`<ul><li>...</li></ul><hr />`), so gating it would hide links inside the item. (3) a
  SETEXT-HEADING UNDERLINE is now a boundary, but only where CommonMark actually ends a paragraph
  with one: with the buffer empty the same line is ordinary paragraph text, and with a list item or a
  block quote open the reference keeps a `=`-run as lazy continuation inside that container —
  flushing there would have traded the fixed false negative for a new false positive. That container
  rule is specific to the `=`-runs and the one- and two-dash runs that actually reach the setext
  branch; it does NOT generalise to `---`, which the thematic-break branch claims first and which the
  reference does not treat as lazy continuation either. The guard also has to survive a block quote
  that INTERRUPTS an open paragraph rather than opening it — a review caught the first version keying
  off what opened the paragraph buffer, which reported a code-span-buried link on a shape that had
  been correct before this change; the reference reading (`<code>q [a](...) === closer</code>`) is now
  pinned by a behaviour test and a pre-form-restoration mutation. All container rules were measured
  against the pinned `commonmark==0.9.2` reference, not derived from the
  spec text. The thematic-break branch is deliberately ordered BEFORE the list-marker branch, because
  `- - -` satisfies both patterns and CommonMark gives the break precedence; that ordering closed a
  fourth, previously unrecorded divergence found while measuring — a `- - -` line followed by an
  indented code block used to report the bracketed text inside the code block as a dead link
  (false positive), because the list branch buffers its own line and thereby defeats the indented-code
  branch's empty-buffer gate. Mutation-checked, and by structure rather than deletion: the branch order
  was PERMUTED (both branches still present), the setext gate WIDENED to the naive form the reference
  falsifies, the block-quote guard RESTORED to its exact pre-fix shape, and a pbuf_para gate ADDED to
  the thematic-break branch that must not have one — each confirmed to flip its own fixture, real
  script untouched (md5-verified). The last two came out of the review: nothing had pinned the
  thematic-break branch as ungated, and adding the gate left the whole suite green.
  Re-measured against four live memory stores with both script versions on the same day: identical
  findings in every one, including the 14 persona indexes whose YAML frontmatter CommonMark reads as a
  thematic break plus a setext underline — inside the extractor both `---` lines are claimed by the
  thematic-break branch, which runs first, so the effect is the same but the attribution is not;
  verified by probe links inside and after real frontmatter, found by both versions, not by a bare
  "no new findings" count. Three corpus entries lose their `known_divergence` and two entries are
  added for the container-vs-boundary shapes above; the other 41 are byte-identical after
  regeneration.

  **Upgrade note:** this is a false-negative fix, so a store that has not changed at all can start
  reporting dead links it never reported before — they were always dead, merely hidden by a paragraph
  merge. Expect that on CRLF checkouts and on files using `***`/`---`/`===` between link-bearing
  blocks. **Corrected after this entry originally shipped (WI-0005):** it read "check (n) still defaults
  to `warn`, so such a finding does not fail a run today", and deferred the promotion to `err` to a
  later release under ADR-0001. That promotion is in THIS release, under `Changed`. A store that has not
  changed at all can therefore go from **exit 0 to exit 2** on upgrade — this entry supplies the finding,
  the promotion supplies the severity. `MEMORY_INDEX_LINK_SEVERITY=warn` restores the severity this
  entry assumed.
- **Five of round 2's seven false positives against check (n) closed; the round's one wrong-target
  row moved to a non-claim instead of a decode (WI-0084, WI-0081 remainder).** check (n)'s awk
  block-boundary list now tracks an indented code block (four spaces, or one leading tab — CommonMark
  never inline-parses either) and two non-comment HTML block types, copied from the pinned
  `commonmark==0.9.2` reference's own tag tables rather than guessed: type 1 (`script`/`pre`/`style`,
  closes on a matching closing tag anywhere in a LATER line, a blank line inside does not end it) and
  type 6 (`div` plus roughly sixty more block-level tags, closes at the next blank line — NOT at a
  matching closing tag, measured directly against the construction trap this distinction turns on: a
  link right after `</div>` with no blank line yet is still inside the block). Types 3–5 (processing
  instructions, declarations, CDATA) and type 7 (an arbitrary single tag alone on its own line) are
  deliberately excluded — zero measured field occurrences and a materially different mechanism,
  respectively; the boundary is named in the code, not left to "as complete as it happened to get."
  Separately: a destination containing an unresolved NAMED HTML entity (`&num;`, as opposed to the
  numeric forms already decoded) used to be resolved as raw text and reported as dead regardless of
  whether the entity-decoded target actually existed — a false claim in either direction, since check
  (n) never actually tested the file CommonMark says the link addresses. It is now filed as an `info`
  finding naming the raw target, absent from both Errors and Warnings, rather than asserting a verdict
  the check cannot back. Mutation-checked, all four guards individually reverted on an in-memory copy
  and confirmed to flip their own dedicated fixture, real script untouched (md5-verified). Re-measured
  against four live memory stores: zero occurrences of any of these constructs in the field today —
  this closes correctness gaps, not live findings. **No false-positive-direction divergence remains in
  the CommonMark corpus** after this round; the ten still-open divergences are all false negatives, and
  the two remaining unused-reference-definition rows are reclassified as intended (WI-0085, below), not
  left as unfixed bugs.
- **Two round-2 "false positives" reclassified as intended behaviour, not fixed (WI-0085).** An unused
  `[id]: dead.md` reference definition (no `[id]`/`[id][]`/`[x][id]` usage anywhere in the file) renders
  nothing at all per CommonMark — but check (n) checks its destination anyway, unconditionally. PO
  decision, 23.08.2026: this is deliberate. check (n)'s own contract is narrower than conformance — does
  the index still point at files that exist? — and a definition addressing a deleted file is a dead
  pointer, invisible on a normal read because it renders as nothing, which is exactly the failure mode
  this check exists to catch. No script change; the two corpus entries move from `known_divergence` to a
  new, mutually-exclusive `documented_intent` field (reason, PO decision date, work item) so a future
  round's own tooling can tell an open gap apart from one the PO has already closed.
- **check (n)'s label/destination matcher ignored CommonMark backslash-escapes and inline-resolved
  destinations, closing two of the WI-0079…WI-0083 divergences (WI-0079, WI-0081).** An escaped
  bracket pair (`\[not a link\](x.md)`) is no longer reported as a dead link — either bracket alone
  being escaped is enough to remove its structural meaning, checked by backslash-run parity so an
  escaped backslash (`\\[real](x.md)`) is not mistaken for an escaped bracket. A destination is now
  resolved the way CommonMark resolves it before it becomes a filename to check: an escaped closing
  parenthesis (`[x](a\).md)`) no longer truncates the target to `a\`, and a numeric character
  reference (`&#35;`, `&#x23;`) is decoded to its literal character instead of being checked
  undecoded — protected from the shell-side `#anchor` fragment-strip by a one-byte sentinel so a
  decoded `#` is not mistaken for a fragment separator, the mechanism that previously mangled
  `dead&#35;3-ent3.md` into the unrelated path `dead&`. **Not decoded**: named entities (`&num;`) —
  the full CommonMark named-entity table has roughly 2000 entries, disproportionate for a construct
  measured at zero occurrences across four live memory stores; the raw text is still checked, not
  further garbled. Re-measured against all four stores after the fix: no change — none of the fixed
  constructs occur in the field today.
- **`memory-lint.sh` check (f) resolved `related:` against the file's own directory only, the same
  question WI-0071 already answered for `phase-docs-lint.sh` (WI-0078).** Authors write `related:`
  entries project-root-relative (`docs/memory/foo.md`), not document-relative — a document-relative
  miss now falls back to `$PROJECT_DIR` before the entry is declared dead, mirroring WI-0071's fix
  exactly: same fallback base, same message wording, same severity split (a root-relative hit is
  `info`, naming both candidate paths, not silence — two bases without saying so is the unvalidated
  drift this lint exists to catch). Measured against a real store (consumer-b): the one file the
  defect was found on, `docs/memory/project_attribute-mapping-slice-b-gap.md`, still errors after
  this fix — its `related:` entry (`planning/sprint/S19-VALUEMAP-ARCH.md`) is written relative to
  `docs/`, not to the project root, so neither base resolves it. That is a genuinely different
  question from the one WI-0071's convention answers, and mirroring that convention here — rather
  than inventing a second, docs/-rooted fallback for this linter alone — was the explicit brief.
- **Ten divergences between check (n) and CommonMark, found by that corpus (WI-0079…WI-0083).** Two
  were predicted from the matcher `\[[^][]*\]\([^)]*\)` before the round ran and both confirmed: an
  escaped bracket pair `\[not a link\](x.md)` is reported although it is not a link (**false
  positive**, the direction that blocks promotion), and a label containing brackets `[a [b] c](x.md)`
  is missed although it is one. Eight were new. The destination is taken literally where CommonMark
  resolves it — an escaped `)` truncates the reported path, and a decimal entity `&#35;` is mangled
  into `dead&` by the fragment-stripping that exists for `#anchor` suffixes, a path that appears
  neither in the input nor in the reference's answer. A setext underline and a thematic break are not
  block boundaries, so a code span pairs across them and swallows a link. And a reference definition
  whose destination sits on the next line is not recognised at all, isolated by a single-line control
  that is found. **Not fixed here** — the round's product is the measurement, and the fix order is a
  decision that wants the whole table on the table first.
- **A second adversarial round against check (n), eight more divergences (WI-0005 round 2).** The
  first round's ten construct classes were deliberately not repeated; this round read check (n)'s own
  awk block-boundary list and searched what it has no case for at all. An indented code block (four
  spaces, or one leading tab) is literal text at the reference — check (n) has a boundary case for a
  fenced code block but none for the indented form, and reports the bracketed text inside as dead. An
  HTML block opened by anything other than `<!--` (`<div>`, `<pre>`, `<script>`) is raw, unparsed HTML
  at the reference for the same reason — check (n) only ever learned the comment form. A reference
  definition with no matching `[id]`/`[id][]`/`[x][id]` usage anywhere in the file renders nothing at
  all, but check (n) checks its destination unconditionally, straight off the definition line — the
  same mechanism that makes shortcut and collapsed reference-link usage, and case-/whitespace-
  insensitive label matching, merely *look* supported without check (n) ever resolving a usage.
  **The most consequential this round**: on a CRLF-terminated file, the blank-line boundary test
  (`$0 ~ /^[ \t]*$/`) does not match the bare `\r` a CRLF blank line leaves behind after `\n`-splitting
  — two paragraphs merge into one buffer and a stray backtick in each pairs across paragraphs it
  should never have reached, swallowing a link. Two further entries extend the already-settled
  WI-0060/WI-0061 empty-destination exception (`[x](<>)`) to the unbracketed forms `[x]()` and
  `[x]( )` — not new gaps, the same intentional "nothing to check" behaviour, confirmed to hold for
  the syntax most likely to actually occur. Eight constructs (blockquotes, ATX headings, emphasis in
  link text, the CRLF case's own non-confounding control) were measured and agree, kept as regression
  pins. Seven of the eight new divergences are false positives — the direction that blocks promoting
  this check to `err`; the corpus grew from 26 to 44 entries, all newly verified against both oracles.
  **Not fixed here**, same as round 1.
- **`memory-lint.sh` told readers to set a value that did nothing (WI-0074).** Its age warning read
  "consider setting `status='stale'`" — and `stale` was not in the suppression list, so following the
  advice produced the same warning on the very next run. Measured across all five cases: unset warns,
  `stale` warns, `archived` and `superseded` are silent. The consequence is visible in the field —
  **`status: stale` appears zero times across all five live memory stores**, because setting it never
  helped anyone. The obvious repair, adding `stale` to the suppression list, was rejected: it buys
  silence with a self-declaration, and "I know it is old" ending a message about being old is the
  ceremony this repo's anchor work spent a whole package refusing. Instead the value is **removed from
  the enum** — it rejects nothing, since nobody uses it — and the message now names the two values
  that legitimately end it (`archived`, `superseded`, both meaning "deliberately no longer
  maintained") and otherwise asks for the refresh it actually wants. The enum is enforced for the
  first time, at **error** severity, and that severity is measured rather than assumed: the single
  schema-foreign value in the field was corrected first, and a sweep of all five stores afterwards
  found nothing outside `{active, archived, superseded}`, so the check rejects nothing that exists.
  Modelled on the neighbouring `type` check rather than invented. `commands/cleanup.md` still cited
  the old suggestion and was corrected in the same pass.
- **The `code-reviewer` agent was told to run commands it has no tool for, and described as something
  it is not (WI-0073).** Its `Context Discovery` section opened every review with `git diff`,
  `git log` and `git diff --cached` in a shell block — while its tool set is `Glob, Grep, Read` plus
  `Edit`/`Write` restricted to its own memory files. No shell, so the first instruction of every
  review was unfollowable, which is why its reports kept explaining that they had read the current
  file state instead. The section now says plainly that there is no shell and names the three ways a
  diff can actually reach it, weakest last, with the instruction to say so when it falls back to
  reviewing current state — because then it cannot tell a new defect from a pre-existing one. Two
  sections were added from what this session's three reviews actually did well: how to hand back a
  finding that needs execution to settle (separate verified from inferred, and name the one command
  that would decide it — a suspicion arriving with its own discriminator gets settled in seconds),
  and where the work-item store is, since it is plain Markdown the agent can read but is gitignored
  and therefore easy to miss. `CLAUDE.md`'s agent table called it "read access only" — the only
  capability claim in a column that otherwise describes focus, and wrong in both directions: it does
  write (its memory silo, by design) and it cannot execute (which nothing said). Checked across every
  other shell-less agent: none had the same defect.
- **`freeze-phase-docs.sh` rewrote prose it had no business touching, and could not run on Linux at all
  (WI-0076).** Its single in-place edit was `sed -i '' -E "s/^status:…/status: frozen/"`. Two defects in
  one line. The empty argument after `-i` is BSD syntax — GNU sed reads a separate `''` as the script
  and pushes the real script into the filename slot, so on Linux the call fails, at the moment a gate
  passes. And `sed` works line-wise with no notion of where the frontmatter block ends: reproduced
  against the committed original, a **body** line reading `status: active` — the kind that appears in
  any document quoting a frontmatter example, as this repo's own schema does — was silently rewritten
  to `status: frozen`. Neither was caught by anything, because the shell sweep only runs `bash -n` and
  the script had no behavioural test module at all. Replaced by a portable `fm_set` (below) and covered
  by `scripts/tests/test_freeze_phase_docs.py`, 20 tests including the four terminal states it must
  skip, the index skip, the P5/P8 no-ops, and the body-protection case that was red against the
  original before the rewrite existed.
- **`related:` and `parent_index:` rejected paths that point at files which exist (WI-0071).** The
  schema documents these as document-relative and the lint resolved them that way; in the field authors
  write them from the repository root. Measured in one project: 13 findings of the form
  `related:'docs/CONSTITUTION.md' points to non-existent file (…/docs/reviews/docs/CONSTITUTION.md)` —
  the doubled `docs/` is the entire defect, and every one of those targets exists. False positives at
  error severity, the direction that breaks a correct run. Resolution is now document-relative first,
  then project-root, and a hit on the second attempt is reported as an **`info`** naming both
  candidates. Silence was the cheaper option and was rejected: two silently permitted bases are the
  unvalidated spread this package exists to stop, and an info finding costs nothing on the exit code
  while keeping the drift countable. Verified against the real project rather than only against
  fixtures — with the reviews profile temporarily widened, those 13 errors become 0 errors and 13 info
  findings.
- **Two shipped documents stated a five-value `status` enum the schema and the linter never had.**
  `templates/PHASE_DOC_SCHEMA.md` and `phase-docs-lint.sh` both carry six values — `living` is a real,
  documented status for detail files designed to keep growing (SPRINT-XX.md, RISKS.md) — while
  `CLAUDE.md` and `templates/PROJECT_CLAUDE_TEMPLATE.md` listed five. Found while measuring the
  precondition for ADR-0009, whose severity model keys off exactly this field: read through the short
  list, the design's `living` row would look like it rests on an invalid value. Every other statement
  of the enum in the repo — the Manual, all phase-command templates — already listed six, so these two
  were the outliers, not the majority. Corrected to six.
- **`PHASE_DOC_SCHEMA.md` claimed two index-consistency checks the linter does not perform.** It said
  "the lint also checks" that every frontmatter-carrying file is listed in its phase index, and that a
  `parent_index:` target must "exist **and list it**". The lint checks path existence and nothing more;
  neither index is ever parsed, and no other script does it either (verified — `parent_index` appears
  in exactly two files, one of them an example block). A statement about the code that was simply
  untrue, and the dangerous direction: a clean lint run read as evidence that index membership holds.
  The section now separates the one enforced check from the two conventions and says plainly that
  nothing validates them.
- **`install.sh --dry-run` announced a wholesale `docs/` copy the real run has not performed since
  WI-0018 (WI-0064).** Found by offering the dry-run as the cheap proof that the docs/ allowlist
  holds, then reading the branch: it exits 0 *before* the artifact loop and prints one
  `$SRC/$item -> $DEST/$item` line per entry. Accurate for the five wholesale artifacts, wrong for
  the sixth — `docs` is the one the loop special-cases into `install_docs()`, which filters every
  top-level child against `scripts/lib/docs-framework-allowlist.txt`. The offered proof would have
  shown the opposite of what it was offered for. The error direction is what made it worth fixing
  rather than noting: a preview exists so an adopter can see what an install will do, and this one
  *overstated* the blast radius in the single place where the answer is subtle, announcing exactly
  the copy the allowlist prevents. A maintainer reading it concludes their working state is about to
  ship and falls back to the clean-clone ritual WI-0018 made unnecessary — the feature stays
  invisible to the audience looking for it. `install_docs()` decided and copied in one pass, so the
  dry-run had nothing to call; the classification is now a side-effect-free `docs_partition()` and
  the skip paragraph a shared `docs_report_skips()`, so preview and run read one verdict and cannot
  drift. The dry-run lists what it would install, what it would skip, and still writes nothing. Six
  tests cover it, including a parity test asserting the dry-run's skip set equals the real run's on
  the same tree, and dotfile coverage (`.handover-archive`, `.DS_Store`) — `dotglob` handling moved
  with the loop, and a mutation removing it turns three tests red.

- **96 skill epilogues told the model to update `docs/HANDOVER.md` without ever telling it to
  replace its own previous block, or what to do when the file is already full (WI-0070).** Measured
  rather than assumed, after a first crude count got the right verdict for the wrong reason: of 115
  commands, 113 write to the HANDOVER and exactly one — `cleanup.md`, the command that enforces the
  cap — mentions it. The other seven apparent hits all referred to a different file's limit
  (CONSTITUTION.md's 8/25 KB, FRAME.md's 5 KB at the same number, the README body,
  `docs/planning/.handover-archive` as a different directory, `/cleanup`'s inbox marker,
  memory-lint's 30 KB topic cap). The obvious diagnosis is nonetheless wrong and is recorded in the
  work item so nobody fixes the wrong thing: `templates/HANDOVER_TEMPLATE.md` line 3 carries the cap
  as a blockquote, so every HANDOVER states it in its third line and any agent reading the file sees
  it. What was missing is that no epilogue names **stacking** as the growth mechanism — appending a
  second block per run rather than replacing the previous one — and none says to measure before
  adding. One run has been clocked at 1021 B, ~20 % of the cap, so five runs take a file from empty
  to breach, which is what the hook's 80 % warn threshold is calibrated against. All 96 epilogue
  sections now open with the same two rules, and the 88 that were boilerplate are normalised to one
  wording (they had drifted into four near-identical variants over `Next Steps`/`Next steps`,
  `useful`/`sensible`, `allowed`/`permitted`, `match`/`fit`). The eight command-specific epilogues
  (`constitution`, `cross-check`, `lean-frame`, `lean-learn`, `lean-promote`, `release-baseline`,
  `specialize`, `track-decision`) keep their own body verbatim and gain only the shared paragraph —
  flattening them into the boilerplate would have silently dropped instructions no other command has.

- **`/postmortem` told users to file ambiguous knowledge one memory tier too high, and refused to
  run on a session whose summary file was missing or stale (WI-0065, WI-0066).** Both found by
  auditing the skill against a run that had just worked around it. §5 instructed "When in doubt,
  prefer Tier 1 (visibility wins over isolation)" while pointing two lines earlier at CLAUDE.md as
  the "full definition" — and CLAUDE.md names that exact phrase as the tiebreaker it withdrew,
  because it caused persona-specific patterns to leak into the globally autoloaded file. The damage
  was directional and silent: nothing fails, the Tier-1 index just accretes, and the cost lands on
  every later session rather than the run that misfiled. Replaced with CLAUDE.md's three-step
  decision order verbatim, including the promotion threshold (3rd cross-reference from a different
  domain), so the two documents cannot drift apart again. Separately, §1 aborted on a missing
  `session-summary.json` — but that file is written at session end, so every postmortem of a running
  session hit it, and on the run before this one the file existed while holding a mid-session
  snapshot (190 tool calls against the session's actual ~3.500). The abort now fires only when all
  three log inputs are unusable, and the skill names the stale-summary case explicitly: a present
  summary is sanity-checked against `activity.jsonl` before its numbers are reported, because
  plausible-looking wrong figures are worse than none.

- **`/postmortem` documented a stored-instinct format that no shipped instinct uses, an archive
  write that `HISTORY.md` describes differently, and a closed list of five topic files
  (WI-0067, WI-0068, WI-0069).** §3's template (`### [ID] Short title` plus a bullet list of
  Confidence/Source/Rule/Context) matches nothing in `instincts/`, where blocks carry a colon in the
  heading, one pipe-separated metadata line, and **Why** plus **How to apply** — the two sections
  that make a stored rule operational, and the two the template omitted entirely. §3 is now labelled
  as the proposal format shown to the user for confirmation, and §6 carries the stored shape it was
  silently assuming, with a note to follow whichever form the target file already uses so one file
  never mixes both. §6 also said to "append a new `Previous:`-style block" to the archive, while
  `instincts-archive/HISTORY.md` states the convention as two moves — new block on top as the
  current head, previous head demoted to `Previous:` — which is what keeps the archive complete once
  the slim index drops a head; the skill now describes both moves and defers to the archive's own
  section. Finally, the write target was hard-coded as
  `~/.claude/instincts/{agents,files,workflow,shell-git,external}.md`. That is correct for the
  shipped starter set and wrong as a permanent contract: the set is designed to grow, and the growth
  pressure comes from inside this system (`memory-lint.sh` warns at a 30 KB soft cap; `/postmortem`
  adds the blocks that get a file there). The five are now presented as the starter themes,
  explicitly not exhaustive, with the instruction to list the directory and pick by theme — and to
  propose a new topic file rather than force an entry into the nearest fit.

- **`memory-lint.sh` check (n) both missed a dead angle-bracket link (WI-0060) and misreported a
  non-link as one (WI-0061) — the same shell-side target-handling case blocks, fixed together.**
  Found in sequence while settling `docs/memory/reference_commonmark-conformance.md`'s table for
  WI-0060: an explicit `\<*` case arm skipped CommonMark's bracket destination form
  (`[x](<target.md>)`) outright, alongside external schemes and in-page anchors it correctly belongs
  with — except the bracket form DOES address a file in the repository, so a dead target written that
  way passed silently, reaching neither the existence check nor even a report under the bracketed
  name. WI-0061, found while settling the same table, is the direction that matters more: the WI-0034
  comment concluding "a bare space is no delimiter, so `[x](my file.md)` keeps its space instead of
  collapsing to `my`" was right about not truncating, but wrong about what to do with the untruncated
  result — per the reference an unescaped, untitled space in an UNBRACKETED destination means the
  whole `[x](...)` construct is not a link at all, so `[x](my file.md)` was being reported as a dead
  target for content that was never a link, the direction `MEMORY_INDEX_LINK_SEVERITY`'s then-`warn`
  default existed to protect against. Fixed by unwrapping the bracket form before resolving (an
  UNCLOSED opener, `[x](<a.md)`, stays skipped — CommonMark reads it as literal text, not a link) and
  by treating a leftover space in an unbracketed target as "not a link" instead of "a target with a
  space in it". Nine fixtures (one per reference-table row, `docs/memory/reference_commonmark-conformance.md`)
  plus the reference-style-definition sibling path (`[id]: <target>`, which shares the same shell
  code) are wired into `scripts/tests/test_memory_lint.py`, each mutation-checked against a scratch
  copy of the pre-fix code restored byte-identical afterward.
- **`scripts/baseline.sh` archived HANDOVER.md into an undotted `docs/handover-archive/`
  directory no convention named (WI-0059).** Found by WI-0058's implementer as out-of-scope drift:
  three other places already agreed on the dotted spelling — `.gitignore` ignores
  `docs/.handover-archive/`, `commands/cleanup.md` documents it twice as the established
  convention, and the only such directory that exists on disk in a real project is the dotted one.
  `scripts/baseline.sh` was the outlier, and duplicated the wrong path a second time as a hardcoded
  literal string in its generated report rather than deriving it from the directory it actually
  wrote to — the duplication is how the two drifted without either being individually wrong-looking.
  Fixed by pointing `ARCHIVE_DIR` at the dotted directory and deriving the report line from that
  same variable instead of a second literal, so the two can no longer disagree. A pre-existing
  undotted directory from an older run is reported by name (contents listed nowhere are moved) and
  left completely untouched — moving a user's files without asking is the action that needs
  consent, leaving them alone does not. New `scripts/tests/test_baseline_archive_directory.py`
  covers the dotted destination, the report/actual-path agreement, the legacy-directory report +
  untouched-contents guarantee, and the pre-existing `docs/.baseline-prep.md` regression path, with
  inline mutation-proof tests for all three changed sites.
- **Twelve generated `docs/` artifacts were not gitignored anywhere they land (WI-0058).** A
  sweep of every `docs/.<name>` path shipped scripts and commands write literally (gate-preflight
  notes for P0–P7, session-context, quality-scan-report, cross-check-report, baseline-prep) found
  three independent gaps, not the one the item's own title named. (1) This repository's own
  `.gitignore` covered none of them — the shape that left `docs/.session-context.md` untracked
  after a verification run, carrying this repo's own git status and paths into the exact class of
  content the artifact gate exists to keep out. (2) `scripts/project-init.sh`'s generated
  `.gitignore` (what a new project actually receives) missed `docs/.cross-check-report.md`, even
  though that path is named explicitly in the "Standard block for `.gitignore` in CCPR projects"
  CCPR itself ships as instinct G-049 — the generator contradicted the rule the framework hands its
  users. (3) `docs/.baseline-prep.md` was in neither the generator nor the shipped standard block,
  newer than both — exactly the drift G-049 exists to prevent, and the block existed in two places
  (`templates/STARTER_INSTINCTS.md`, `instincts/workflow.md`) that had to be fixed together or stay
  disagreeing. Fixed with two different shapes deliberately: this repo's `.gitignore` uses a broad
  `docs/.*` pattern (verified no dotfile under `docs/` is tracked here today, so nothing is
  swallowed, and future generated artifacts need no further edit), while
  `scripts/project-init.sh`'s generated block stays an enumeration (a user's project may
  legitimately track a dotfile under `docs/` that this repo does not, so a broad pattern there
  would be a silent, unrequested behaviour change on every new project). A new
  `scripts/tests/test_docs_dotfile_gitignore_coverage.py` derives its expected set from the same
  sweep method rather than a hand-maintained list, so a script or command added tomorrow that
  writes a new `docs/.<name>` path fails the suite until it is listed in `.gitignore`, the
  generator, and both instinct-block carriers. Documented limitation: the sweep only finds paths
  spelled out literally in source — `scripts/gate-preflight.py`'s actual output path is built from
  an f-string variable, so the eight concrete `docs/.gate-preflight-pN.md` hits it finds come
  entirely from each `commands/gate-pN.md` file documenting that path, not from the generator
  itself; a path assembled purely at runtime and never spelled out anywhere would not be caught.
- **`scripts/log-cleanup.sh` could silently replace a real log with garbage instead of a trimmed
  copy (WI-0056).** Found and deliberately left unfixed by WI-0054's classifier as
  `known-risk-not-yet-fixed`: the trimmed log was written to a tmpfile by a bare
  `python3 -c "..." 2>/dev/null`, followed by an UNCONDITIONAL `mv`. MEASURED first, and the
  item's own headline mechanism did not reproduce: a python3 that FAILS (nonzero exit, via a PATH
  stub or `PYTHONHOME=/nonexistent`) already aborted the whole script under this file's own
  `set -euo pipefail` before the `mv` was ever reached — the log survived, just silently (empty
  stderr, no indication which of the three files failed or why). The actually reproducible shape
  was narrower: a python3 that returns EXIT 0 without doing the real work. Fixed by creating the
  tmpfile in the same directory as the target (atomic rename — a process kill either lands before
  it, original untouched, or after it, fully in place), capturing python3's exit status explicitly
  AND validating its stdout is a well-formed line count before trusting it (closes both the
  exit-nonzero and the exit-0-with-garbage-output shapes), skipping only the failed file instead of
  aborting the whole run, and printing a per-file `[ERROR]` instead of staying silent. A residual,
  deliberately unfixed gap remains: a python3 that returns exit 0 AND prints a plausible but wrong
  line count cannot be told apart from a legitimate full trim by any exit-status check — recorded in
  `docs/memory/senior-developer/scripts-conventions.md`, not silently closed.
- **`scripts/bootstrap.sh` could abort its whole session-context dashboard on a legitimate empty
  result (WI-0057).** Also found and left unfixed by WI-0054 as `known-risk-not-yet-fixed`: a bare
  `grep -E '^### \[' "${INSTINCTS_FILE}" | head -5 | while read ...` — under `set -o pipefail`, a
  grep that matches nothing exits 1 and takes the whole `{ ... } > "${OUTPUT_FILE}"` block down with
  it. MEASURED first: this repository's own current `~/.claude/instincts.md` (a bullet-point index,
  zero `### ` headings at all) never reaches this line — an earlier `count -eq 0` guard already
  returns first, so the item's summary read too broadly for that shape. The reproducible case is an
  instincts file that DOES have `### ` headings, just not in the `### [ID] ...` bracket form (the
  shape this repo's own topic files actually use: `### G-008: ...`, no leading bracket) — there,
  `grep -E '^### \['` legitimately matches nothing and the pipeline abort is pure `pipefail`, not
  SIGPIPE from `head -5` (verified: a 200-heading probe that `head -5` truncates hard still exits 0
  for the pipeline). Fixed by capturing the grep call's output and status explicitly and branching on
  grep's own documented exit-status contract (1 = ran fine, nothing matched; 2+ = grep itself
  failed) — deliberately not a blanket `|| true`, which would recreate the exact "failure read as
  empty result" confusion this fix exists to close, in the other direction, for a genuine grep
  failure.
- **`scripts/quality-scan.sh` could not be parsed by bash and silently exited 0 having scanned
  nothing (WI-0055).** A `python3 << 'PYEOF' ... PYEOF` heredoc was nested inside a `$(...)` command
  substitution (`grep_findings=$(python3 << 'PYEOF' ...)`); the heredoc body's SQL-injection pattern
  carried an apostrophe (`f\'`), and an ODD apostrophe count breaks bash's quote tracking while it
  scans for the substitution's closing `)` — this is the exact mechanism WI-0044 named for
  `memory-lint.sh`'s awk block, on a second shipped script. `bash -n` failed at the line carrying the
  pattern; running the script printed the same syntax error to stderr, wrote no report, and still
  reported exit 0 — traced to the EXIT trap's own `rm -rf` succeeding and silently becoming the
  shell's final exit status once a bash-level parse abort (which never sets `$?` to anything
  reflecting the abort) reached it. Escaping the apostrophe was rejected as the fix, on this
  repository's own history: it is the shape that left `memory-lint.sh` fragile for eight rounds and
  produced WI-0037 and WI-0044. Instead the heredoc body moved to a real file
  (`scripts/lib/quality_scan_sast_patterns.py`), invoked as a plain `python3 <path>` call — no
  parity to defend, independently `py_compile`-able. The other two heredoc-in-substitution-shaped
  blocks in the file were checked and are not affected: neither is nested inside a command
  substitution, so no closing `)` is ever scanned for while bash tracks their quoting. Also added an
  explicit end-of-run check that the report file is non-empty (`docs/quality-scan.sh` used to reach
  its final `cat` step even when nothing upstream had written anything), and a generalised `bash -n`
  gate (`scripts/tests/test_shell_script_syntax.py`) over every shipped script under `scripts/*.sh`
  and `scripts/lib/*.sh`, so the next unparseable script fails the suite instead of shipping quietly
  — the same enumeration `test_external_tool_exit_status.py` (WI-0054) already uses for the same 15
  files. `scripts/tests/test_quality_scan.py` pins that the script actually runs end-to-end across
  multiple scopes against a scratch fixture project (never this repository's own `docs/`), including
  a mutation proof that reintroduces the exact pre-fix construct in a scratch copy and confirms both
  the syntax gate and a real run reproduce the measured pre-fix symptom.
- **`/cleanup`'s unparseable-inbox-line rule rejected the shipped template's own blockquote
  lines.** §1a excluded blockquote lines from the check by requiring a trailing space after `>`,
  but `templates/HANDOVER_TEMPLATE.md` uses bare `>` lines (no trailing space) as paragraph
  separators inside the Open Points blockquote — two of them. An agent following the prompt
  literally would report a false positive on a freshly initialised HANDOVER. Fixed the rule to
  match a bare `>`, and the test mirror now derives the exclusion prefix from cleanup.md's own
  wording instead of a hardcoded literal, so the two cannot drift apart again undetected.
- **`memory-sync.sh promote` published its destination path without checking it.** The discipline
  gate examined the source file's *content* and then wrote the *destination* into a commit message
  that was pushed — so a file with clean content could still carry a tenant name into the shared
  repository through its filename, where it survives deleting the file and only a history rewrite
  removes it. This was the one irreversible path in the tool; everything else the gate protects is
  local. The destination is now checked against the same deny-list before anything is fetched,
  copied, staged or committed, and a match **refuses** rather than warns. Review then found the check
  was bypassable — a directory destination made `cp` append the source's own filename, so the string
  checked and the string published were different strings. Directory destinations are rejected as a
  usage error, which is what the documented contract always said, and that equality is now the reason
  the guard exists. Also fixed with it: ASCII-only case folding, NFC/NFD normalisation on macOS, and
  a missing `--` that let a destination named `--all` sweep unrelated files into the push. A later
  refinement closed one more shape: a destination whose name reads as a command-line flag (`--all`,
  `-n`, or a nested component like `instincts/-n`) exited 0 and published a file literally named
  that — not a leak by itself, since every consumer already treats the destination as a path
  regardless of a leading dash, but a file named that way reads as a flag again to any tool that
  later globs the directory it landed in. `require_file_destination` now refuses it the same way it
  already refuses `.`, `..` and a trailing slash, naming the actual mistake ("looks like a
  command-line flag") instead of reusing the directory-destination message.
- **`memory-sync.sh` failed on macOS's bash in its own usage hint.** `promote` without a destination
  printed `bad substitution` instead of the hint: the message interpolated a bash-4 lowercase
  expansion, and macOS ships bash 3.2. The error path errored. A sweep over all 22 tracked shell
  files found this as the only occurrence, and a regression test now guards everything a user runs.
- **`memory-sync.sh` let a failed `git clone`/`fetch`/`push` print the repository URL straight to the
  terminal, unmasked.** Every line the script emits itself goes through the same deny-list + `$HOME`
  mask `say()` uses — but git's own transport error text never passed through that function, and a
  failing clone or fetch prints the repository URL verbatim, which is exactly where a configured
  tenant/project name lives. Fixed by capturing the subprocess's stderr and re-emitting it through
  `die()`, the same mask path, instead of leaving it alone: the token git injects into the URL for
  auth was already confirmed to be stripped by git itself before this reaches the capture, but the
  host and repository path were not, and now are. Capturing a command substitution's own exit status
  on the same statement (`out="$(cmd 2>&1)" || rc=$?`) keeps a transport failure fatal — piping the
  capture into the mask would otherwise have reported the mask's exit status instead of git's.
  Note one deliberate behaviour change that follows: a transport failure now exits **2**, the script's
  own documented hard-error code, where it previously aborted with git's raw status (measured: 128 for
  a refused connection). The old status was never part of the contract the file's header states
  (`Exit: 0 ok, 1 gate/soft failure, 2 hard error`), so this aligns the script with its own promise —
  but a CI job keyed on 128 rather than "non-zero" will see the difference.
- **`memory-sync.sh`'s push gate read an internal scan failure as a clean file, not as a check that
  never ran (WI-0036).** `run_gate` tested whether `gate_scan_file`'s *output* was empty rather than
  consuming the exit status the function's own header comment already promised callers — a promise
  nothing was reading. An internal failure inside the scan (not "no findings", but "the check did
  not complete") produced the same empty result as a genuinely clean file. `run_gate` now captures
  `gate_scan_file`'s real exit status: an internal failure now reads as dirty where it previously
  read as silently clean, the safe direction for a push gate — fail closed, not open. Verified the
  ordinary paths are unaffected: a clean file still exits 0, a file carrying a bearer token still
  exits 1. The real behaviour change: a broken gate now blocks a push instead of waving it through.
- **`/p5-polish` wrote its `handover`-triage items into a section that did not exist.** It has always
  instructed agents to record blocked items in `docs/HANDOVER.md` "under Open Points", but no shipped
  template ever contained that heading — the flow dangled unless a project invented the section itself.
  The inbox now provides the destination, and `/p5-polish` writes the same entry format the `/cleanup`
  triage reads, so producer and consumer finally agree.
- **HANDOVER's Next Steps extraction no longer matches a field written mid-line (WI-0024).** The
  inbox WI-0002 added works only because the shipped template places `## Open Points` below
  `## Next Steps` — an unanchored `re.search` in `next_steps.py` picks the first match anywhere in
  the document, so an inbox finding whose text happened to contain `Next Steps:` followed by a
  `/command` reference could be read as the real next step. The extraction is now anchored to line
  start (`re.MULTILINE`), which makes the section order irrelevant instead of protected by
  convention. The narrowing is the fix — a field written mid-line
  (`Status ok. **Next Steps:** ... /cmd`) is no longer matched, only the line-start form and the
  `## Next Steps` heading are. The shipped template already uses the heading form, so nothing CCPR
  ships relies on the old match, but the change is silent for a hand-maintained HANDOVER.md that
  wrote its Next Steps field mid-line.
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
- **`doc-volume-check.sh` printed a broken report line and a stream of shell syntax errors for any file
  without an H2 heading (WI-0101).** `grep -c` PRINTS `0` and STILL exits 1 when nothing matched, so
  `h2_count()`'s `|| echo 0` arm fired on top of that printed zero and the function returned `"0\n0"`.
  Both `(( ))` tests in `split_suggestion()` then aborted with `((: 0\n0: syntax error in expression`,
  and the report line broke mid-sentence: `... (46 KB) → no obvious splitting point (0` on one line, the
  rest on the next. Against this repository's own `docs/` that was 8 lines on stderr and 2 truncated
  bullets. The arm now REPLACES the value instead of adding one
  (`count="$(grep -c ... )" || count=0`), the same shape `bootstrap.sh` already ships for the identical
  grep call.

  **What did NOT change is the verdict.** Both arithmetic tests failed, so the branch fell through to
  the `else` arm — and "no obvious splitting point" is the correct advice for a file with no H2 section
  to split at. Every file in a before/after run against `docs/` keeps its size band, its KB figure and
  its suggestion; the exit code stays 2. Only the rendered line and the stderr noise changed, which is
  why this is a PATCH under ADR-0001 ("bug fix in scripts ... that does not change any rule") even
  though the script is shipped. It matters because `/cleanup` §5 puts this output in front of a human
  reader, and a sentence that stops mid-line is a defect that reader sees.

  The script shipped with no test of its own; it now has one (`scripts/tests/test_doc_volume_check.py`),
  covering both sides of the defect's precondition — a zero-H2 file across all three size bands, an
  H3-only file (the shape that surfaced it), and H2-carrying positive controls that a fix which simply
  stopped counting could not pass.

### Performance
- **check (n) reads every index TWICE, unconditionally — including indexes with no reference definition
  in them at all.** This is the cost of the two-pass extractor (WI-0093): the awk program is invoked as
  `awk '...' "$INDEX_FILE" "$INDEX_FILE"`, so both the file I/O and the whole block machine — fences,
  HTML blocks, comments, the paragraph buffer, `protect_link_destinations()`, `resolve_paragraph()` —
  run a second time on every index, whether or not pass 1 found a single label. Measured on this repo
  (macOS 26, BSD awk 20200816, `LC_ALL=C`, median of 25 runs): a 46 KB persona index goes from 24.7 ms
  to 50.7 ms (factor 2.05, +26 ms); a 1.8 KB index from 3.5 ms to 4.5 ms, where process startup
  dominates. Across all five indexes in this repo, 54.6 ms -> 103.0 ms per lint run (+48 ms, factor
  1.88) — and **none of those five contains a single reference definition**, so the entire second pass
  is dead weight here today. It is accepted rather than optimised: a "skip pass 2 if refmap is empty"
  shortcut would need pass 1 to be trustworthy about a document it has not finished classifying, and a
  cheap pre-scan for definition-shaped lines is exactly the second block implementation the two-pass
  design exists to avoid. Recorded so the trade is visible if an index ever grows to a size where it
  matters.

### Added
- **A second round against check (n), on ground the first never touched (WI-0005).** The corpus grew
  26 → 44. Eight new divergences, and the interesting part is what they group into rather than the
  count. Five are one cause: the extractor tracks fenced code and HTML *comments*, but neither
  indented code blocks nor the other HTML block types — both contexts where CommonMark parses no
  inline content, so a link written there is not one. An index file is exactly the document that
  explains its own link syntax, which is why fence tracking exists at all; indented and
  HTML-wrapped examples are the same habit in a different notation. Two more are a **decision, not a
  defect**: an unused reference definition creates no link under CommonMark, but check (n)'s purpose
  is narrower than conformance — whether the index still points at files that exist — and a
  definition naming a vanished file is a dangling pointer nobody sees in the rendered document. The
  last is a false negative on CRLF blank lines, measured at zero occurrences today but not idle:
  this framework ships with Windows install guidance. Filed as WI-0084, WI-0085 and WI-0086. Eight
  further construct classes measured clean and kept as regression pins, including shortcut and
  collapsed reference links, block quotes, headings and emphasis in link text.
- **Sprint-review reports get a decided header schema (WI-0072).** `/p5-review-sprint` prescribed
  nothing more than "record the reviewed range in the report header" — measured in the field: five
  different header shapes across two real projects, including a bare `key: value` body with no `---`
  block at all (consumer-c, 4/4 files) and a project that had already written itself a convention
  document reacting to the same drift. `commands/p5-review-sprint.md` now prescribes YAML frontmatter
  (`kind: review`, `sprint`, `base_commit`, `reviewed_head`, `reviewer`, `last_updated`) in its write
  step and repeats it as a `## Result` acceptance criterion, mirroring `constitution.md`'s pattern.
  `templates/REVIEW_REPORT_TEMPLATE.md` is the skeleton. `phase-docs-lint.sh`'s `reviews` profile
  gains a required-fields check that fires **only** once a document self-identifies via `kind: review`
  — structural backward compatibility, not an assumed one: not one document in the three reference
  projects carries that literal value today, measured before and after the lint change. The base-of-
  reviewed-range field is validated as `base_commit` **or** `reviewed_base` — both already accepted,
  equally validated names in the pre-existing commit-anchor-family check — not `base_commit` alone;
  the template and command still prescribe `base_commit` for new reports (one form, not a choice), the
  alias exists purely so a corpus that already wrote `reviewed_base` under this exact schema is not
  forced into a rewrite. A migration script (`scripts/migrate-review-headers.sh`) backfills
  `kind`+`sprint` onto the exact `SPRINT-<N>-review.md` shape only — never the suffix variants.
  RECONSTRUCTING `base_commit`/`reviewed_head`/`reviewed_base` (inferring a value that is genuinely
  absent) stays forbidden — a wrong guess there lets `/gate-p5` treat a stale review as current, worse
  than the avoidable re-run a missing field costs — but MOVING a value the author already wrote is not
  a guess: a bare `<key>: <value>` body line for one of those three keys, matched only at the exact
  start of a line, is hoisted into frontmatter (the body line itself is never removed; a pre-existing
  frontmatter value is never overwritten, and a body value that contradicts one is reported, not
  silently dropped). `kind: review` is only ever set once every required field is present, counting
  both what the file already had and what this run just hoisted — a document that would still fail
  the required-fields check immediately after being marked is left unmigrated and reported by name
  instead, so a clean lint run never turns into a permanently red one with no path back. The script
  creates the frontmatter block itself where none exists, since `fm_set`/`fm_set_many` refuse to write
  into a file that has none. Running it against the real consumer-a corpus caught a live defect
  before any file was written: its zero-padded filenames (`SPRINT-03-review.md`) compared as a string
  against the project's own unpadded `sprint: 3`, producing a false conflict warning — fixed via
  base-10 arithmetic normalisation (`10#$n`, not a bare leading-zero literal, which bash reads as
  octal). A second run against the same corpus then caught the reconstruction-vs-moving conflation and
  the missing base-field alias above (22.08.2026 correction) before either had reached a shipped
  commit. A third pass, still before any commit, caught two more defects in the hoist step itself: a
  fenced code block illustrating the header schema (`commands/p5-review-sprint.md` is itself an
  example) was hoisted verbatim as if it were a real value — `reviewed_head` is exactly the field
  `/gate-p5` trusts for staleness detection, so a wrongly hoisted example is worse than a missing
  field — fixed with two independent checks: fence-tracking in the body extractor (mirroring
  `memory-lint.sh`'s own fence state machine) and a commit-SHA shape check (`^[0-9a-fA-F]{7,40}$`, the
  same form `phase-docs-lint.sh` already enforces) on whatever a fence gap lets through. The other two:
  the script's own temp-file write and the final `mv` into place were both unchecked — a write or move
  failure left an unexplained orphaned file in the caller's project tree with no error message tying
  it to what happened; both are now checked and named in the failure message, mirroring `fm_set`'s own
  write guard (`scripts/lib/frontmatter.sh`, which gained the equivalent `mv` check for the same
  reason).
- **A differential corpus measures check (n) against the CommonMark reference (WI-0005).** The
  promotion of the memory index's dead-link check from `warn` to `err` has been held three times on a
  criterion that is a **rate**, not a state — "a round that produces no new items" — and no round had
  been run since the last fix, so the criterion was neither met nor missed but untested. It is tested
  now. 23 constructs the six previous rounds never touched, each frozen with the reference parser's
  answer in `scripts/tests/fixtures/`, and a test that compares check (n) against that table **without
  importing the parser** — the suite has no third-party dependency, and a `skipIf` on a machine
  without the module would be silently green by skipping, which is the failure this repo keeps
  finding. Divergences are held as named `known_divergence` entries carrying their direction and work
  item, so they are counted rather than tolerated, and any behaviour change trips the test in both
  directions. That turns the promotion criterion into something measurable instead of remembered: a
  round with no new items now means the corpus grew and no new divergence appeared.
- **ADR-0009 is `accepted`.** Decided 18.08.2026, implemented across WI-0019…WI-0022, and completed
  by three addenda: the first correcting nine of its own statements against the shipped code before
  anything was built, the second resolving where the scope anchor lives, the third settling
  acknowledgement authority. Package B is closed.
- **Acknowledgements record who made them (ADR-0009 Addendum 3, WI-0022).** The ADR's fourth open
  point asked what acknowledgement authority means with more than one maintainer. The question hides
  two: *who made this assertion* and *who is allowed to*. This framework has no server and no
  enforcement point, so restriction could only ever be a convention — and a check that reads as
  enforcement without being it is exactly what this ADR refuses to do for agents. So: **record the
  actor, do not restrict them.** A sixth flat key `anchor_ack_by` joins the acknowledgement group in
  the same atomic write, filled from the repository's git identity and overridable with `--by`.
  Identity is keyed on **`user.email`**, and that is the substance of it: in the larger reference
  project two people appear under five display names while their addresses stay stable, so keying on
  the name would have recorded the drift instead of the person — verified, two names on one address
  collapse to one actor. Where no identity is configurable the field says so explicitly
  (`unattributable <no-git-identity>`, deliberately without an `@` so it can never be mistaken for an
  address) rather than being omitted, because a missing field and an unattributable acknowledgement
  must not look alike. And `anchor status` breaks its `asserted` count down by actor once more than
  one appears — the design's guard against acknowledgement becoming ceremony was always the statistic
  rather than a permission, and this is what carries that guard into a team. A test pins the
  **absence** of an authority check, so the decision cannot be quietly reversed into one.
- **The Manual documents the anchor, and a dormant CI template ships beside it (WI-0021).**
  `Manual/system/anchored-state.md` explains the mechanism the way the other `system/` chapters
  explain theirs — the problem, why the anchor sits on the phase index rather than on each document,
  why severity reads the document's own `status`, why the check is two-stage, and what "not verified"
  means — with each design choice carrying the measurement that settled it rather than an assertion.
  It states the agent clause's limit as plainly as the skill does. `templates/ci/anchor-check.ci.sh`
  follows the shipped precedent: POSIX `sh`, no forge named, nothing runs until someone wires it up.
  Two constraints are in its header because leaving them out would produce the message nobody reads:
  **CI can only do stage 1** — the judgement needs an agent, so the template reports a delta and is
  explicitly not a substitute for `/anchor` — and `check` **exits 0 with drift by design**, so a job
  reading only the exit code would report nothing, ever. It therefore reads the output, and says why.
  A run where every scope reports "not verified" is called out rather than passing quietly.
- **`/anchor` — the skill that turns the mechanical delta into a verdict (WI-0021).** Stage 1 is the
  script call and carries no severity; Stage 2 asks one narrow question per affected document — *does
  this delta invalidate a statement here?* — scoped to the changed paths rather than to the whole
  document, which is what keeps the common case (stale) from drowning the rare one (invalidated).
  Severity comes from the document's **own** `status`, never the index's. A confirmed invalidation at
  `active` or `frozen` opens one work item through the existing contract — no contract change — and a
  project that has not adopted the structured store gets the finding in its HANDOVER inbox instead.
  Every run closes with the acknowledgement statistic, because ADR-0009 requires it as the detector
  against the mechanism becoming ceremony. The skill states the exit-code contract explicitly, since
  `check` exits 0 **with** drift and non-zero only on an operational failure — read the other way
  round, a broken run would look like a clean one. The agent clause is binding and stated without
  varnish: `ack` refuses its interactive prompt without a terminal, but the flagged path needs none
  and nothing stops an agent with shell access from calling it, so the clause is prevention, the
  statistic is detection, and only both together are honest.
- **`/cross-check`'s R6 says what it does and what it does not.** The rule is titled
  "CONSTITUTION.md (Inviolable) ↔ ADRs / **Implementation**" and has never opened a code file — the gap
  that prompted ADR-0009 in the first place. Rather than bolt a code rule onto a Markdown-to-Markdown
  checker, R6 now names its own limit and points at `/anchor` for the half it does not cover.
- **`fm_set` and `fm_set_many` in `scripts/lib/frontmatter.sh`** — the first write path in a library
  that was read-only, and now the only in-place writer in the shipped scripts. Temp file in the same
  directory plus `mv`, never `sed -i`; scanning stops at the closing `---`, so the body is left
  byte-for-byte alone; a file without frontmatter is an error rather than a silent create; setting the
  same key twice is byte-identical. `fm_set_many` writes a whole group of keys in **one** awk pass and
  **one** rename, which is what makes an acknowledgement atomic as a unit rather than only per key.
  Four hardening fixes came out of review, three of them confirmed at the terminal before being
  believed: values reach awk through `ENVIRON` rather than `-v`, because `-v` applies escape
  processing — `awk -v v='a\nb'` yields a string of length **3** containing a real newline, so a
  reason mentioning a Windows-style path would have broken the frontmatter block one processing stage
  after the guard that exists to prevent exactly that; the original file's mode is carried onto the
  temp file before the rename, since `mktemp` creates at `0600` and a document checked out at `644`
  was silently becoming `600` on every write; a source file without a trailing newline keeps none,
  because awk's `print` adds one regardless; and keys are matched literally rather than as a regex.
- **`anchor set` and the freeze hook (WI-0021).** `freeze-phase-docs.sh` now writes `anchor_commit` and
  `anchor_date` onto the phase index — the one file it deliberately skips for `status:` — after
  freezing that phase's detail files. **It writes only when no anchor is there yet.** A second gate
  pass leaves the existing anchor alone and says so, because refreshing it silently would clear every
  accumulated drift without anyone having seen it, and ADR-0009 names that the highest-risk detail in
  the whole design. Verified end-to-end and by mutation: adding `--force` to the hook's call moves the
  anchor, wipes the drift, and turns exactly one test red.
- **`anchor ack` — the acknowledgement verb.** Renders the delta **before** it clears it, then writes
  five flat keys: the new `anchor_commit`, `anchor_date`, `anchor_ack` (`asserted` or `updated`),
  `anchor_ack_from` (the **old** SHA), and `anchor_ack_note`. `asserted` and `updated` stay separate
  fields on purpose — collapsing them would destroy the ability to ask later which anchors rest on
  nothing but an assertion, which is exactly what `anchor status` counts. A reason is mandatory in both
  the flag form and the interactive one; there is nothing to acknowledge without a delta, and the verb
  refuses then. Reach is declared structurally by the target file: an index is a bulk acknowledgement,
  a document with its own anchor is not. Measured: the acknowledgement counter really moves from 0 to
  1, so the detector against the mechanism turning into ceremony is live rather than planned. On a
  non-terminal stdin the interactive form reads EOF as **abort** and writes nothing — but a pipe does
  drive it, so the prompt is no barrier to a script or an agent. That is the ADR's own position: this
  harness has no hard boundary, so agents are kept out by an explicit clause plus the visible
  statistic, and the prompt is not a gate. Three review findings hardened it: the five keys are one
  atomic group write (an interrupt after a per-key `anchor_commit` would have left a document with a
  fresh anchor and no acknowledgement, which the status report reads as clean — drift gone with no
  record it was ever cleared, the exact failure ADR-0009 calls its highest-risk detail); a target
  outside the eight phase scopes is refused, because acknowledging one there succeeded while staying
  invisible to the very statistic that is the design's only detection fallback; and a non-terminal
  stdin without `--assert`/`--update` fails fast instead of blocking on a prompt nobody can answer.
  `anchor set` returns a distinct exit code **3** for "already anchored", so the freeze hook reads a
  contract rather than grepping another script's error text.
- **`scripts/anchor.sh` — stage 1 of the anchored state check (WI-0021).** `anchor status` and
  `anchor check` compute the delta between a recorded `anchor_commit` and the last **production-code**
  commit, and nothing else: no severity, no verdict, and **exit 0 whenever data was produced**, drift
  included — a non-zero exit means an operational failure only. That is the property the whole design
  rests on, since the event that fires constantly (staleness) must never reach the user as a verdict.
  The comparison point is not `HEAD`, because a third to a half of commits in real projects touch only
  documentation. Every report names the classification in force and its source, and **how many of the
  eight phase folders were actually found** — without that line, "0 anchored" on a project with no
  phase folders reads exactly like a fully anchored, drift-free one. Anchor resolution is the
  document's own before the index's, in both subcommands, so a document whose own anchor is current is
  not reported as affected; a scope with no index still reports its own-anchored documents rather than
  swallowing them, which matters because `quality/QA.md` is absent in all three reference projects
  while the folder exists. Six git edge cases are data, not crashes: no repository, shallow clone,
  unresolvable anchor, detached HEAD, dirty tree, and a repository with no commits. `ack` and `set` are
  explicit stubs for the write path. Three bugs were found while building it, each reproduced before
  it was fixed: `git log --pretty=format:` omits the trailing newline, so `while read` silently drops
  the last entry — invisible except in the single-commit case, i.e. exactly a `--depth 1` clone;
  a `[[ cond ]] && assignment` as the last command of a function leaves that function's exit status
  non-zero and kills the script under `set -e`; and `"${arr[@]:-}"` on an empty array in bash 3.2
  yields one phantom empty element rather than none — a silent wrong answer, distinct from the known
  crash on a bare `[@]`. 47 tests, suite 958 → 1020.
- **ADR-0009's one open design question is decided (Addendum 2).** The ADR anchors at the Gate-Go
  freeze and makes the scope index carry the bulk acknowledgement, while `freeze-phase-docs.sh` skips
  every index by design — so the freeze event could not write the anchor the design puts there. The
  scope anchor now lives on the **phase index**, written by a second, deliberate write path in the
  freeze; documents inherit it, may opt into their own, and **severity reads each document's own
  `status`, never the index's**. Three measurements settled it. The index's status is not
  machine-guaranteed: in one reference project all five phase indexes carry `frozen` although the
  freeze script skips them by name, so keying severity off the index would make every finding in that
  project error-grade and none in the other two. An index may be absent — `quality/QA.md` is missing in
  two of three projects while the folder exists — which resolves to the ADR's own "not verified" state
  rather than to silence. And the naming convention holds where an index exists, so the scope resolves
  by convention instead of by a registry, which would have been the second register the ADR rejects.
  The alternative — anchoring each frozen detail file — was cheaper to build and fails on coverage: the
  freeze runs only on a Go verdict, and at frozen shares of 12 %, 6 % and 90 % most documents would
  never receive an anchor. On the index, one gate pass per phase anchors the whole scope. Also settled:
  the comparison point is the last **production-code** commit, defined by **exclusion** (not under
  `docs/` or `.claude/`, not a Markdown file) because that travels between projects while a list of
  code directories does not — measured, it lands 1, 2 and 6 commits behind `HEAD` in the three
  projects, which is exactly the documentation-only base rate the design exists to defuse.
- **`covers:` — an optional, lint-validated list of the code paths a phase document describes
  (WI-0020).** Resolved against the **project root** only, with no document-relative fallback: these
  are code paths, not doc references. A path that does not exist is an error; a path that exists but
  contains no file at any depth is a warning, because ADR-0009 requires that a list which has quietly
  stopped covering anything cannot report clean — the first implementation answered "does this
  directory contain any entry", which let a tree of empty subdirectories pass, and now answers "does
  this path cover any code". A directory whose only content is a `.gitkeep` counts as covered; that is
  a deliberate non-decision recorded in place, since treating dotfiles specially is a rule nobody made.
  The check runs in every profile because it is purely opt-in — measured: `covers:` appears zero times
  across three real projects, so it costs a project nothing until it adopts the field.
- **The commit-anchor family CCPR already writes is validated (`base_commit`, `reviewed_head`,
  `reviewed_base`).** `/p4-sprint` writes `base_commit`, `/p5-review-sprint` records `reviewed_head`,
  and `/gate-p5` compares it against `HEAD` to decide whether a sprint review is stale — a recorded SHA
  on a phase document spanning a delta, shipped for months and never checked. In the field: 34
  documents across two projects, roughly ten spellings, none validated. When one of the three keys is
  set, the form is now checked (7–40 hex, error) and, inside a git repository, whether it resolves to a
  commit (warning — a shallow clone, a rewritten history or a foreign SHA are legitimate misses).
  Measured before shipping: all 47 occurrences are well-formed and resolvable, so the check costs zero
  findings today. The repository test initially missed linked worktrees and submodules, where `.git` is
  a **file** — the same unresolvable SHA warned in a main repo and stayed silent in its worktree.
- **`phase-docs-lint.sh` has test coverage for the first time (`scripts/tests/test_phase_docs_lint.py`,
  28 tests).** 207 lines that every CCPR project runs, shipped with nothing but the generic `bash -n`
  sweep and the exit-status inventory pointing at it. Two work items are about to change this exact
  script — a per-directory check profile and a new `covers:` check — so the surface those changes get
  measured against had to exist first. Covers all seven checks (a)–(g) individually with a negative
  control beside each, every required field on its own, **every** value of both enums separately
  (`P0`…`P8`, and the six statuses), both `related:` list syntaxes, all six `LIVING_FILES` names, the
  exit-code precedence, the report's own counts, and the argument edge cases. Every test was seen red
  through a mutation of the **script** — never by deleting the assertion — and the mutations were
  restored byte-identically (md5-checked). Two of them are deliberate boundary **pins** rather than
  requirements, and say so in place: today a document outside the eight `PHASE_FOLDERS` produces no
  finding by default, and `--scope` **does** reach it, because the two collection paths differ (the
  scoped one walks all of `docs/`). The upcoming profile work rewires exactly that switch, so both
  sides of the fence are now marked and it cannot move unnoticed in either direction.
- **ADR-0009 gained an addendum before a line of it was implemented (21.08.2026).** The decision was
  written from measurements on two CCPR-driven projects; re-measuring against three, and against the
  shipped scripts rather than their descriptions, falsified nine statements. The two that change the
  work most: the `status` enum is **already** enforced hard — check (d) errors and the script exits 2,
  and does so today against a real project — so the precondition is scope plus correction, not stricter
  validation; and **the anchor already exists under other names, written by CCPR itself** —
  `/p4-sprint` writes `base_commit`, `/p5-review-sprint` records `reviewed_head`, `/gate-p5` compares
  `reviewed_head` against `HEAD` as a staleness detector, across 34 documents in two projects and
  roughly ten unvalidated spellings. That is the same unvalidated-key rot the ADR cites as its warning
  example. `anchor_commit` stays a distinct key — a sprint base and a freeze point are different
  moments — but it now ships together with validation of the existing family, or the second-register
  objection would apply to its own field. Also corrected: the enum has six values, not five (`living`
  is in the schema and the linter; the five-value list in `CLAUDE.md` is the drifting statement), the
  frozen share is 90/12/6 percent across the three projects rather than one number, `covers:` is not an
  extension of the `related:` check (different base, different node type), and the `covers:` decay rate
  is understated by roughly a factor of five. One open design question is named rather than papered
  over: `freeze-phase-docs.sh` skips every index, so the freeze event cannot write the scope-level
  anchor the design puts there. **Design only — still no shipped surface changes.**
- **Every external-tool invocation in the shipped shell scripts is now pinned to a consumed exit
  status (`scripts/tests/test_external_tool_exit_status.py`, WI-0054).** Three prior rounds
  (WI-0049, WI-0051, WI-0053) closed one recurring defect — a crashing `grep`/`sed`/`awk`/`python3`/
  `git` read as "nothing found" instead of "this check did not run" — by enumerating call sites BY
  READING the source, and each pass kept missing at least one site the eye skipped. A new,
  self-contained shell scanner (no external parser dependency) re-enumerates every invocation in
  `scripts/*.sh` and `scripts/lib/*.sh` on every test run and asserts, in the positive form, that
  each one is either structurally checked (an `if`/`while` condition, a `$?`/`|| return` capture, a
  real `&&`/`||` chain) or carries an inline `# exit-status: exempt <category>` marker naming one of
  eleven shared, reasoned categories — so a newly added, unclassified invocation fails the very next
  run instead of waiting for a fourth sweep. Of 125 invocations found, 33 were already structurally
  checked and 92 needed a marker; two of those markers record a genuine, unfixed risk found while
  building the check (`bootstrap.sh`'s instinct-listing `grep` can abort the whole dashboard on a
  normal empty result; `log-cleanup.sh`'s log trim can silently replace a log with an empty file if
  `python3` crashes) rather than being silently absorbed as routine. The check's own docstring states
  its limitation plainly: it cannot see a status swallowed several call-frames up (WI-0053's own
  `gate_path_deny_index` site), only what it can see reading forward from each invocation.
- **CCPR can now gate its own shipped artifacts (`scripts/artifact-gate.sh`).** The Constitution
  forbids personal or tenant data in shipped artifacts, and that Inviolable was breached — a tenant
  project name sat in an instinct's rationale while the file's own header claimed such details were
  anonymised. Hand sweeps are what let it through. The existing memory gate could not simply be
  pointed at the repo: swept over 273 files it produced 77 files with findings and **zero** true
  positives, and it would not have caught the actual breach, because it has no concept of a tenant
  *name*. The gate is now split into a pattern library (`scripts/lib/discipline_gate.sh`) used by
  both entry points — `artifact-gate.sh` and `memory-sync.sh promote`'s destination check — with
  profiles selecting which checks run rather than what a pattern means. The generic 40-character
  rule — the source of every false positive — was replaced with shapes machine-generated credentials
  actually have, plus a dedicated check for a screaming-snake-case placeholder (`YOUR_TOKEN_HERE`,
  `TODO_INSERT...`) that would otherwise read as a bearer token or a keyword-assignment secret,
  scoped to those two checks only so a real vendor-shaped key (AWS's own `AKIA...EXAMPLE`) still
  fires unfiltered elsewhere. A deny-list of tenant and project names closes the real gap; it is
  read from personal config or an environment variable, never from the repository, matches are
  reported with file and line while the name itself is redacted from every emitted line (a CI log is
  a shipped artifact too), and it escalates to an NFC-normalised, case-folded comparison for a
  non-ASCII subject or name on both the path and — gated on the configured name only, so a pure-ASCII
  deny list costs nothing extra — the file content side; a fatally broken `python3` interpreter now
  falls back to the ASCII matcher with a warning instead of silently reading as a clean file. Every
  check the gate runs — the deny-list matchers, the shared scan-and-report loop, and the file-list
  filter — fails loudly (abort, exit 2, naming the check and the failing tool's exit status) if its
  underlying `grep`/`python3` call crashes, instead of the crash reading as "0 findings", "not text"
  (silently skipping a file already selected for scanning), or a narrower scan scope with no trace.
  A tracked symlink is treated as its own name rather than followed: a dangling one no longer drops
  out of the sweep silently, and a resolving one is never read through — its target's bytes are never
  opened, matching what `install.sh` actually ships for a symlink (the link itself, never its
  target); a `skipped_symlink` counter reports the count. The self-exemption that keeps the gate from
  flagging its own pattern definitions is bound to the resolved path of the one file that defines
  them, so an installed copy scanning a foreign checkout reports the reason a finding was not
  recognised as its own source, rather than unexplained "secret" findings. Ships with a dormant CI
  template (`templates/ci/artifact-gate.ci.sh`, syntax-checked and exercised against a fixture repo)
  that names no forge; its activation note correctly states that the sweep reads only
  `git ls-files`, not history, so a shallow checkout is sufficient. An unconfigured deny-list says so
  loudly instead of passing silently. The repo currently scans clean: 275 files, 0 findings.
- **The HANDOVER size cap is now watched automatically.** The ≤5 KB / 150-line cap was documented in
  the template and enforced by `/cleanup`, but nothing triggered it — the file drifted past its limit
  unnoticed until someone happened to run the command, and `doc-volume-check.sh` does not cover it
  (its thresholds start at 25 KB, five times the cap). `agent-monitor.py` now warns on session start
  and after any HANDOVER write, at **80 %** of the cap as well as above it. The threshold is derived,
  not chosen: one skill run was measured growing a HANDOVER by ~20 % of the cap, so a warning one
  run's growth below the limit is the last moment at which it is still preventive. The warning names
  the numbers and the remedy, and never blocks. `/cleanup` gained the matching level: at or above the
  threshold it *offers* to archive the oldest block, since the file is still legal there and declining
  is a valid answer. `/cleanup` reads the threshold from the hook rather than restating it, so the two
  cannot drift apart — and with no hook installed it falls back to its previous two branches instead
  of inventing a substitute value.
- **The HANDOVER template carries an append-only inbox (`## Open Points`).** Agents working mid-task
  keep finding things outside their assignment — stale docs, a missing check, a worthwhile follow-up —
  and the template offered exactly one collection point, the Open Decisions table. With only a decision
  table such findings either interrupt the task or are lost; this was reported from a productive
  multi-agent setup that has run its own inbox since July. Entries are one greppable line
  (`- INBOX | date | source | finding | ref`), triaged by a new `/cleanup` step into
  `backlog | decision | keep | drop`, with backlog items routed through the work-item adoption guard so
  a project with a ticket system gets a real item and a prose project gets a BACKLOG entry. Reaching
  the ceiling flags rather than blocks: refusing an append would reintroduce the loss the inbox
  prevents. `project-guide` surfaces the count; it may neither append nor clear.
- **`memory-lint.sh` now validates the Tier-1 index's own links, and every Tier-2 persona index's,
  catching a dead link nothing else in the lint saw (check `n`).** The lint checked
  cross-references in one direction only: it found memory files the index had forgotten (check
  `g`) and `related:` entries pointing at nothing (check `f`), but a link *inside* an index passed
  silently even when its target had been deleted. The check resolves every inline link
  (`[x](target)`) and reference-style definition (`[id]: target "title"`, all three CommonMark
  title delimiters — double quotes, single quotes, parentheses) against the file that carries it:
  the Tier-1 index (`docs/memory/MEMORY.md`) and every `docs/memory/{agent}/MEMORY.md` persona
  index (WI-0040) — a persona index carries far more links than the Tier-1 one, deep anchors into
  topic files, and nothing had validated those before. A relative target resolves against its own
  index's directory, not the Tier-1 memory dir; a leading `/` resolves from the project root.
  Comments and inline code spans are resolved paragraph by paragraph, left to right: whichever
  construct — an HTML comment opener or a run of backticks — opens first at a given position
  claims its whole span, and the other's delimiters inside it are literal text (WI-0048); either
  can cross a physical line break inside the same paragraph, stopping only at a real block
  boundary — a blank line, a list-item marker, a heading, a fence, or a block-level comment
  (WI-0050, WI-0052). A code fence or an HTML comment left open at end of file is correct
  CommonMark — the rest of the document genuinely is inside it — but the check no longer lets that
  silently shrink its own scope: both now emit their own warning naming the line where the
  construct opened, independent of severity (WI-0032, WI-0043). Images, in-page anchors and
  external URLs are skipped, correctly — none of them is a link to a file in the repository. A
  destination in CommonMark's angle-bracket form (`[x](<target.md>)`) is unwrapped and resolved like
  any other target (WI-0060, fixed after this entry originally shipped) — the reference parser reads
  it as an ordinary link to a file, so it belongs with the checked forms above, not with the skipped
  ones; an UNCLOSED opener (`[x](<target.md)`) stays skipped, because the reference reads that as
  literal text, not a link. This is a floor, not a full fix: it catches a target file that no longer
  exists, not a wrong anchor into a file that does — anchor resolution needs heading-to-slug
  modelling and is a separate, unbuilt item. Shipped
  at **warning** severity by default; `MEMORY_INDEX_LINK_SEVERITY` is the knob, validated up front so a
  bad value reports a configuration error (exit 3) instead of aborting with `command not found`
  (exit 127), indistinguishable from a findings result. **Corrected after this entry originally shipped
  (WI-0005):** both halves read the other way round in the shipped state. The default is `err` since
  24.08.2026 — the promotion this entry called "tracked separately and the SemVer-relevant step
  (ADR-0001)" is in THIS release, under `Changed` — and the documented escape hatch now points the other
  way, to `warn`.
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
- **The docs/ framework-vs-working-state boundary is now machine-enforced on both sides
  (WI-0018).** `install.sh` shipped every tracked path under `docs/` wholesale, so this repository's
  own working state — 17 work items about CCPR's own defects at the time of measurement, since grown
  to 63 — would reach every user's `~/.claude/docs/` looking like their own state; a checkout carrying
  that state (any long-running contributor's own working copy, not only a stale pre-gitignore clone)
  landed 852 KB of it, exit 0, no warning. `scripts/lib/docs-framework-allowlist.txt` is a new file
  naming the five framework paths currently tracked (`adr/`, `logo/`, `CONSTITUTION.md`,
  `NEXT_STEPS_REFERENCE.md`, `PROJECT_PHASES.md`) and is the single source of truth for both sides —
  neither script keeps its own copy of the list, which is the shape that produced WI-0059 once
  already (an archive path held in a variable and again as a literal). `scripts/artifact-gate.sh`
  fails a newly tracked `docs/` path that is not on the list (`[docs-boundary]`, naming both remedies:
  add it to the allowlist if it is framework documentation, or to `.gitignore` if it is working
  state). `install.sh` now copies only the allowlisted entries out of `docs/` and reports what it
  skipped, by name and approximate size, naming the likely cause — including dotfiles/dot-directories
  (`docs/.handover-archive/`), which a plain `*` glob would otherwise drop from both the install and
  the report silently. This is a separate mechanism from the existing `PROTECTED` stash-and-restore
  concept: `PROTECTED` preserves the *target's* user-owned files across a wholesale directory replace,
  this skips *source*-side working-state files from ever being copied in the first place.
  **Follow-up fix, same day:** the `[docs-boundary]` rule fired on every repository `artifact-gate.sh`
  swept, not only CCPR's own — a project adopting CCPR and running the shipped gate against its own
  `--repo` was told its own `docs/README.md` and `docs/workitems/` belonged in `.gitignore`. Scoped by
  self-detection, mirroring the gate's existing pattern-source self-exemption
  (`_GATE_PATTERN_SOURCE` in `lib/discipline_gate.sh`, which resolves the gate's own file path to
  recognise itself): the rule now only applies when the repository being swept is the SAME repository
  the running gate script lives in (`_GATE_OWN_REPO_ROOT` / `DOCS_BOUNDARY_APPLIES`), no new flag or
  configuration. An installed copy under `~/.claude` — ordinarily not a git repository itself — is
  correctly inert against any `--repo` it is pointed at. Known, accepted gap: a project that vendors a
  copy of this script into its own repository and points `--repo` at itself satisfies the equality too;
  self-detection by location cannot distinguish "the same location" from "CCPR's project identity".

### Changed
- **`last_updated`'s date check was one rule hand-typed twice, and the two copies had never agreed
  (WI-0107).** `phase-docs-lint.sh` check (e) matched the `DD.MM.YYYY[ (note)]` shape and stopped
  there; `memory-lint.sh` check (e) matched the identical shape and then ran the value through a
  real parse (`date_to_epoch`, WI-0106/WI-0087). Consequence, measured 26.08.2026: a well-formed
  value that names no real calendar day (`32.13.2026`, `99.99.9999`) was accepted by
  phase-docs-lint.sh and rejected by memory-lint.sh — the exact drift both linters' own comments
  already admitted, in one implementation each. Both the shape check and the parse now live once,
  in `scripts/lib/frontmatter.sh` (`fm_date_shape_ok` / `fm_date_to_epoch`, the latter moved
  verbatim from memory-lint.sh's `date_to_epoch`, only renamed for the library's `fm_` prefix
  convention), sourced by both scripts.

  **`phase-docs-lint.sh` now rejects an impossible date, and that is a promotion (ADR-0001), not a
  write-down.** It turns content that lints clean today into an error, so the blast radius was
  measured before shipping it, not assumed: neither reference project's `docs/<phase>/**` store nor
  this repository's own carries a shape-valid-but-impossible `last_updated` value. `memory-lint.sh`'s
  behaviour is unchanged — same two messages (`not in format 'DD.MM.YYYY' or 'DD.MM.YYYY (note)'`
  for a shape failure, `cannot be parsed as DD.MM.YYYY` for a shape-valid-but-impossible date), same
  verdicts, pinned by the existing `LastUpdatedFormTest`. `phase-docs-lint.sh` keeps its single
  message for both failure modes, since it never distinguished shape from date in its report.

- **check (n) — a dead Markdown link in a memory index is an ERROR by default (WI-0005, ADR-0001).**
  `MEMORY_INDEX_LINK_SEVERITY` still ships as the single knob that decides it; only its default moves,
  `warn` -> `err`. **Scope, stated plainly, because it is wider than the Tier-1 index:** since WI-0040
  check (n) reads the Tier-1 index `docs/memory/MEMORY.md` **and every Tier-2 persona index
  `docs/memory/{agent}/MEMORY.md`**, and the persona indexes are where the links are. Counted in this
  repo: 7 link constructs in the Tier-1 index against 66 across the four persona indexes, 52 of them in
  a single one. A project meets this promotion on the persona indexes first.

  Per ADR-0001 this is the SemVer-relevant step in the whole check (n) series, because it is the one
  that **rejects content that was previously accepted**: a project whose index points at a file that no
  longer exists now exits 2 where it exited 1. **The class is MAJOR.** ADR-0001's MAJOR row is
  "schema-breaking change in memory or phase-docs", illustrated with *"changing `memory-lint.sh` to
  reject previously-valid frontmatter"* — this is the same shape one field over: the same script
  rejecting index content it previously accepted. It ships inside a `0.x` MINOR under ADR-0001's own
  pre-1.0 caveat (semver §4), which permits a MAJOR-class change on a MINOR bump below v1.0. Naming the
  class here so the release cut does not have to re-derive it.

  **The criterion, and why it changed.** Promotion used to wait for "a round that produces no new
  items". That criterion was replaced by PO decision on 23.08.2026 because it was shown to be
  unreachable rather than merely unmet — two probing rounds against ground no earlier round had touched
  produced eighteen divergences, and the construct classes were not exhausted. CommonMark is large and
  an awk extractor will always diverge somewhere. The criterion in force is narrower and matches the
  reason ADR-0001 sets a threshold at all: **no known FALSE-POSITIVE divergence**. Only a false positive
  rejects previously accepted content; a false negative rejects nothing and breaks no run.

  **What satisfied it, measured:**

  | Measurement | Result |
  |---|---|
  | Conformance corpus (`scripts/tests/fixtures/commonmark_corpus.json`) | 76 entries, **0 false-positive** divergences, 12 false-negative, 3 `documented_intent`. **The zero is over a corpus WI-0100 was deliberately kept out of** — see below: adding it unasked would have moved the very number this round was judged by, so that call was left to the PO and the class is named in prose instead of counted here. |
  | Corpus regeneration against the flipped script | **byte-identical** to the committed file — the flip does not touch the extraction, and the instrument is stable |
  | Field measurement | 18 real index files, **131 link extractions, 0** targets the reference does not render |

  **Effect on real runs today: none.** Measured on four inventories, old default against new default,
  same script, same moment, only the knob differing:

  | Inventory | Findings | Exit (old default `warn`) | Exit (new default `err`) |
  |---|---|---|---|
  | ccpr-gh | identical | 1 | 1 |
  | consumer-b | identical | 2 | 2 |
  | consumer-c | identical | 1 | 1 |
  | consumer-a | identical | 1 | 1 |

  check (n) contributes zero findings in all four, so there is nothing for the severity to reclassify.

  **The caveat, named rather than footnoted — WI-0100.** A bounded random probe over 3000 lines of
  bracket soup produces **210 findings the reference never renders**, 178 of which already reproduce
  before the WI-0080 bracket scanner. The minimal witness is `[](()`, which check (n) reports with a
  target named `(`. The cause is WI-0095: `protect_link_destinations()` spans the text after ANY `](`
  without checking that a live opener precedes it. This class is **reachable but not reached** — that
  is exactly what the field measurement says, and all it says. A promotion that hid a known
  false-positive class would be the thing ADR-0001's threshold exists to prevent, so it is stated here
  and in the source comment above the assignment.

  **What this flip is not.** It makes the check **louder, not complete**. The 12 false-negative
  divergences stay in the corpus, named, each with its direction and work item, and are fixed on their
  own merits rather than as a precondition for this line.

  **One consistency the flip repairs in passing.** The source comment over check (n) has read "severity
  is `MEMORY_INDEX_LINK_SEVERITY`, mirroring check (f)" since the check was written. Check (f) — a
  `related:` cross-ref pointing at a file that does not exist — reports `err`. Under the `warn` default
  the comment was simply untrue: the same defect, a reference to a file that is gone, was an error in
  one check and a warning in the other, decided by nothing but which field it was written in. The two
  agree for the first time.

  **And its actual reach, stated plainly.** Measured across this framework: the only consumer of this
  script's exit code is **`/cleanup`** (`commands/cleanup.md` §3), which turns it into a status word —
  "0 clean / 1 warnings / 2 errors" — and holds 3 apart as a configuration error to be treated as a run
  failure rather than a findings result. There is no hook, no CI job and no gate that treats exit 2
  differently from exit 1. Today this change moves one word in one report. It is still the right change
  — the signal should be true before anyone builds on it — but the entry should not promise more than
  it delivers.

  **What the null result does NOT cover.** The four inventories above are the ones this framework is
  run against; they are not a sample of anyone else's. A foreign store meets this promotion through two
  changes in the same release, not one: the false-negative fixes further up **add findings on content
  nobody touched**, and this line files them as errors. The combination moves such a store from exit 0
  to **exit 2** without a single file having been edited. The zero measured here says the four
  inventories carry no check (n) finding to reclassify — it says nothing about a store that does.

  **Migration, for a run this catches off guard:** `MEMORY_INDEX_LINK_SEVERITY=warn` restores the
  previous behaviour exactly, and that is measured rather than asserted — on a throwaway project with
  one dead index link, the shipped default yields 1 error / exit 2 and the override yields the same
  finding as 1 warning / exit 1. Look for the dead targets in the persona indexes
  (`docs/memory/{agent}/MEMORY.md`) as well as in `docs/memory/MEMORY.md` — check (n) has covered both
  since WI-0040, and the persona indexes carry the deep links. The escape hatch is documented where a
  reader hits the word "error": `commands/cleanup.md` §3 and the Memory Lint checklist in
  `Manual/system/memory-instincts.md` and `Manual/SYSTEM_OVERVIEW.md`.

  The knob is validated before any work happens, so a bad value still exits 3 (configuration error)
  instead of being mistaken for a findings result — and **an EMPTY value now reaches that validation**.
  `MEMORY_INDEX_LINK_SEVERITY=` used to take the default branch (`${VAR:-err}`) and land silently on the
  strict side of the promotion it was reaching to escape, exit 2, no message. It is `${VAR-err}` now: an
  empty string is not a severity, so it exits 3 and says so. Emptying a variable is the most likely
  wrong grip on a knob that has no off position.

  `test_the_shipped_default_severity_is_warn` was **rewritten, not deleted** — it exists so this default
  cannot move silently, and it did its job: it went red on the flip before anything else was touched. It
  is now `test_the_shipped_default_severity_is_err_and_warn_remains_reachable` and pins the escape hatch
  in the same test as the default it qualifies. Both halves were confirmed load-bearing by mutation
  (restoring the `warn` default, and neutering the `warn` dispatch branch, each turn it red). Restoring
  the `warn` default turns **exactly one** test in `test_memory_lint.py` red — that one — and leaves the
  42 corpus tests untouched, which is the design the severity/extraction split exists for.
  `test_an_empty_severity_is_a_configuration_error_not_the_strict_default` is new alongside it and pins
  the `${VAR-err}` half.
- **`phase-docs-lint.sh` scans `docs/reviews/`, with a check profile of its own (WI-0019).** The
  status enum was never the weak part — check (d) already errors and exits 2, and had been doing so
  unnoticed against a real project for months. What let invalid values survive is that the scan only
  ever visited eight hard-coded folders, and `docs/reviews/` was not one of them. Taking it in with the
  full check set was measured first and rejected: it yields 47 errors in one project and 54 in another,
  almost all "required field missing" against a schema review reports never followed — only 13 of 30
  carry all four required fields, and in a third project four carry no frontmatter at all. Review
  reports are a genre of their own; their schema is tracked separately. So `reviews` gets a profile
  that runs **only** the status enum, and only when `status:` is set — including silence on missing
  frontmatter, without which one project would have moved from a clean exit to exit 1. The profile is
  derived from the file's path **after** the two collection paths converge, so `--scope 'reviews/*'`
  and the default walk agree on the same file (measured: that invocation went from 47 findings to 6).
  Implemented as a `case` dispatch, not an associative array — the platform's `/bin/bash` is 3.2.
  Backwards compatibility was measured, not asserted, before and after on three projects: one stays at
  exit 0, one gains exactly the six invalid values it was hiding and no other finding class, one gains
  exactly one. A mutation that lets the frontmatter check into the reviews profile turns four tests red
  **and** moves the clean project to exit 1 — the regression the constraint forbids is caught by the
  suite, not only by the manual run.
- **The Handover-Epilogue "Open points"/"Open items" bullet, shipped identically in 104 command
  prompts, named a destination without saying which of the two `docs/HANDOVER.md` sections it
  meant.** The template offers two places for a mid-task finding: the `## Open Decisions` table
  (what the PO must decide about THIS command's own assignment) and the `## Open Points`
  append-only inbox (a finding made OUTSIDE the current assignment). The bullet an agent actually
  followed just said "Open points" (91 files) or, in a further 12 files (`gate-p7*`, `p7-*`,
  `p8-*`), "Open items" — same block, same position, same three-bullet shape, same ambiguity,
  different word; found while measuring the first 92, initially treated as a separate finding and
  folded into the same fix on review, since the defect is the missing destination, not the literal
  string searched for. `/cleanup`'s unparseable-line report made the resulting drift visible
  rather than silently absorbing it. No ADR: the Constitution's Inviolable triggers on a change
  that *invalidates* an existing project artifact, and naming a destination more precisely
  invalidates nothing — settled against the volume of files touched, not the wording. 103 files
  carried a bare bullet, one (`p5-review-sprint.md`) a suffixed sibling keeping its own
  CRITICAL/HIGH qualifier; all 104 now name the `## Open Decisions` table for a PO decision and
  the `## Open Points` inbox for an out-of-scope finding explicitly, applied as two scripted
  substitutions (not 104 hand edits) with a five-point integrity proof run over each tranche:
  before/after occurrence counts, `git diff --stat` at exactly 1 insertion + 1 deletion per file,
  a diff-line filter proving no neighbouring line moved, and a byte-count delta check per file.
  Pinned by a new `scripts/tests/test_handover_epilogue_bullet.py`, which asserts the positive
  form (every Handover-Epilogue "Open ..." bullet is the disambiguated wording or the one, named,
  genuinely unrelated `specialize.md` exception) rather than merely the old string's absence — an
  allowlist for files carrying the same defect the test exists to prevent was rejected as reading
  like a sanctioned exception rather than a gap.

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

[Unreleased]: https://github.com/jonase47/ccpr/compare/v0.3.0-beta...HEAD
[v0.3.0-beta]: https://github.com/jonase47/ccpr/compare/v0.2.1-beta...v0.3.0-beta
[0.2.1-beta]: https://github.com/jonase47/ccpr/compare/v0.2.0-beta...v0.2.1-beta
[0.2.0-beta]: https://github.com/jonase47/ccpr/compare/v0.1.0-beta...v0.2.0-beta
[v0.1.0-beta]: https://github.com/jonase47/ccpr/releases/tag/v0.1.0-beta
