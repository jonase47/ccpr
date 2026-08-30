---
kind: adr
adr_id: ADR-0011
adr_status: accepted
status: active
last_updated: 30.08.2026
related:
  - ADR-0010-conformance-runs-against-consumers.md
  - ../CONSTITUTION.md
---

# ADR-0011: bash 3.2 stays the floor

**Status:** Accepted (30.08.2026)
**Decision-makers:** Repo owner (Jonas)

## Context

CCPR ships 28 shell scripts. Twenty-six of them target bash, and the language subset they
use has been held to **bash 3.2** — the version Apple ships as `/bin/bash` — since the
beginning. That constraint is real and enforced, but it had never been decided. It lived
in two places:

- **A static guard test.** `NoBash4ConstructsInShippedScriptsTest`
  (`scripts/tests/test_memory_sync_promote.py:450`) scans `scripts/**/*.sh` plus
  `install.sh` for `${…,,}` / `${…^^}`, `mapfile` / `readarray`, `declare|typeset -*A` and
  `local -n`, and has a companion test asserting the scan's scope is non-empty. Measured
  30.08.2026: **zero** bash-4 constructs in shipped scripts. `templates/ci/*.sh` is
  deliberately out of scope — those run on a CI image whose interpreter the consuming
  project chooses.
- **Roughly a dozen inline comments** naming the constraint at the point where it costs
  something — `check-all.sh:118-120` (parallel arrays instead of an associative one),
  `check-all.baseline.tsv:6` (`IFS=$'\t' read` as the parser), `migrate-review-headers.sh:181`
  ("this repo's target platform"), and others in `quality-scan.sh`, `run-tests.sh`,
  `memory-sync.sh`, `manual-lint.sh`, `instinct-check.sh`, `phase-docs-lint.sh`, `anchor.sh`,
  `install.sh`.

**What forced the decision.** This repository is getting its first CI. A CI has to pick
runners, and picking only `ubuntu-latest` would make bash 5 the de-facto floor — not by
decision, but by omission, with a green badge on top. The worst answer to this question is
the one nobody makes.

**What we found while asking it, and it changes the reasoning.** The shebang does not
carry the floor. All 26 scripts start with `#!/usr/bin/env bash`, not `#!/bin/bash` —
`env` resolves to the **first bash on `PATH`**. On the maintainer's machine that happens
to be `/bin/bash` 3.2.57 (measured 30.08.2026; no Homebrew bash installed), so the floor
holds by accident of environment, not by construction. On any machine with a newer bash
ahead of `/bin` on `PATH` — a Homebrew install, and by all accounts the GitHub macOS
runner images — the very same scripts run under bash 5.

So the floor is a promise about **which language features the scripts use**, not a promise
about which interpreter executes them. That distinction is the substance of this ADR.

## Decision

### 1. bash 3.2 remains the floor. It is not raised, not even in steps.

Reasons, recorded so the question is not re-litigated:

- Apple ships `/bin/bash` as 3.2 and will not replace it, for GPLv3 licensing reasons. A
  Homebrew bash 5 installs to `/opt/homebrew/bin/bash` and leaves `/bin/bash` untouched.
  Any user, hook, or agent that reaches `/bin/bash` on macOS gets 3.2 — and a framework
  whose scripts are mostly invoked by an agent is exactly where such an assumption gets
  undercut quietly.
- Moving to 5 would mean auditing every invocation path for an interpreter we do not
  control, in exchange for features this repository does not need. The direction of travel
  is toward Python anyway; the gain would be limited to future shell code.

### 2. The static guard is the enforcement, not the shebang.

`NoBash4ConstructsInShippedScriptsTest` is what actually holds the line, because it is
independent of which interpreter runs. The shebang stays `#!/usr/bin/env bash` — changing
it to `#!/bin/bash` would pin macOS to 3.2 but break Linux, where bash lives at
`/usr/bin/bash` and `/bin` is often a symlink we should not rely on.

### 3. The CI must measure the interpreter it actually used, and must include macOS.

A job that runs `bash scripts/check-all.sh` on a macOS runner picks up whatever bash is
first on `PATH` — which is expected to be Homebrew's 5.x, not the 3.2 the floor is about.
Therefore:

- The macOS job **selects the interpreter explicitly** rather than inheriting `PATH`.
- Its first step **prints the interpreter version actually in use and fails if it does not
  start with `3.2`**. Runner images change; an assertion survives that, a comment does not.
- Coverage is measured, never asserted from runner documentation.

### 4. Linux stays in the matrix, because it covers a different set.

`test_memory_sync_promote.py:407` skips its bash-4 behavioural tests when `/bin/bash` is
older than 4. On macOS those skip; on Ubuntu they run. The two jobs therefore verify
**different subsets** of the suite, and neither is a superset of the other. That is an
argument for both jobs, not a redundancy to trim.

## Consequences

- A macOS runner is mandatory for `check-all.sh`. Standard GitHub-hosted runners are free
  and unmetered for public repositories, macOS included, so this costs nothing.
- New shell code may not use bash-4 constructs; the guard test fails the build if it does.
  Contributors get the failure at the guard, not at a user's cryptic `bad substitution`.
- An entry-point version guard reports the running version and aborts with a clear message
  rather than letting a user fall into a syntax error — it also documents which interpreter
  actually took effect, which is the thing the shebang does not tell you.
- BSD-vs-GNU userland differences remain a second, independent reason for the macOS job.
  One had already materialised: `mktemp` templates with a suffix after `XXXXXX` are
  returned literally by BSD `mktemp`, which is a real defect in `scripts/run-tests.sh`
  found before this CI existed.

## Alternatives considered

**Raise the floor to bash 5.** Rejected. It requires every invocation path to guarantee a
newer bash on `PATH` — including the environment in which an agent starts hooks and
scripts. That guarantee cannot be given, and its absence would be silent.

**Pin the shebang to `#!/bin/bash`.** Rejected. It would make macOS deterministic at the
cost of Linux portability, and it addresses the symptom (which interpreter) rather than
the constraint (which features).

**Linux-only CI.** Rejected — this is the outcome this ADR exists to prevent. It would
make bash 5 the effective floor by omission and leave the 3.2 path as unverified as it is
today, while displaying a green badge.

**Drop the floor and require a bash version at install time.** Rejected as a change of
product scope: CCPR installs on a clean machine without prerequisites, and adding one
would collide with the Constitution's *No external services for distribution* posture.

## Vendor coupling

GitHub Actions is a vendor. The Constitution's *No vendor lock-in* Inviolable is respected
by shape rather than by abstinence: **`scripts/check-all.sh` is the provider-neutral body**
and the workflow is a thin caller that runs it. Moving to another provider means writing a
new caller, not rewriting the checks. The *No external services for distribution*
Inviolable is not engaged — it governs what an adopter needs to install and run CCPR, not
how this repository verifies itself.

## Follow-ups

- Add the entry-point version guard (decision 3's last consequence).
- The first CI run must be read, not just its badge: confirm the printed interpreter
  version on the macOS job, and confirm the Ubuntu job runs the bash-4 tests that macOS
  skips.
