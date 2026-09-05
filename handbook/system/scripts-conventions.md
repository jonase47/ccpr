---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: scripts-conventions
last_updated: 20.08.2026
---

# Conventions for the Shipped Scripts

This page is for anyone **editing** a file under `scripts/*.sh` or
`scripts/lib/*.sh` — not for using the scripts (see
[monitoring-scripts.md](monitoring-scripts.md) for that). Two conventions are
enforced by the test suite for every shipped shell script. Both fail on a
fresh, unmodified addition — you decide the right answer once, then record
it; the tests do not accept a blanket workaround.

Enforced scope, both conventions: `scripts/*.sh` + `scripts/lib/*.sh`. A file
added to either directory enters scope automatically — no registration step
beyond adding the file. `scripts/local-llm/*.sh` is out of scope (user-owned
and hardware-specific, never overwritten by `install.sh --update`).
`templates/ci/*.sh` has its own, separate syntax gate.

## 1. Every external-tool invocation must have a decided exit status

Enforced by `scripts/tests/test_external_tool_exit_status.py`.

Every `grep`, `awk`, `sed`, `python3`, or `git` invocation in the shipped
scripts must end up in one of two states:

- **Structurally checked** — it is the tested command of an
  `if`/`elif`/`while`/`until`, its status is captured (`$?` or `|| return`),
  or a real `&&`/`||` branch follows it (not just `|| true`).
- **Exempted with a marker** — a trailing comment,
  `# exit-status: exempt <category>`, naming one of the categories below.
  The marker must sit somewhere between the invocation's own line and the
  line its statement finishes on (relevant for a `\`-continued statement,
  where it cannot go on a continuation line without being swallowed).

An invocation with neither — no structural check and no marker — fails the
test. That is deliberate: a new `grep` added tomorrow starts unclassified and
stays red until a human decides which of the two states it belongs in.

### Choosing a category: what it is FOR, not what makes it pass

The test does not care which category you pick, only that it is registered.
That is exactly the failure mode this convention exists to prevent: a marker
chosen because it makes the suite green, rather than because it is true of
this invocation, turns the exemption list into boilerplate nobody reads
again. Pick the category whose description actually matches your call site;
if none does, that is a signal to add a genuinely new one rather than
stretch an existing one.

| Category | Use when… |
|---|---|
| `set-e-sufficient` | `sed`/`awk`/`python3`/`git` (unlike `grep`) have no "1 = no match" convention to confuse with a crash; an unguarded failure already aborts the script under its own `set -euo pipefail`, and that abort is the correct, decided response. |
| `grep-empty-is-valid` | `grep` exits 1 on no match, and here that is a normal, already-handled empty result (a zero count, an empty ID list) — not a crash signal. |
| `downstream-checks-result` | The exit status itself is not inspected, but the very next line tests the *output* for emptiness or shape and branches on a missing/malformed result. |
| `doc-field-extraction` | Extracts one optional section from a project doc (`HANDOVER.md`, `CLAUDE.md`, `PROJECT_PLAN.md`) for a generated summary; a missing/malformed section degrading to blank output is the by-design fallback. |
| `best-effort-status-display` | Produces a cosmetic status/log/file-listing for a human-facing dashboard or startup summary; a failure degrades the display, it does not corrupt state. |
| `propagates-as-function-return` | The tail command of a small shell helper (e.g. `_gate_hits`, `fm_extract`) — the function's own exit status *is* this invocation's exit status by design, and every caller checks the function's return, not this line. |
| `internal-record-parsing` | `awk` parsing this same script's own well-formed, internal record format — not external or adversarial input. |
| `git-cache-refresh` | Part of `memory-sync.sh`'s overlay-clone maintenance, already deliberately `|| true`'d because the following statement re-derives the needed state regardless. |
| `test-runner-output-capture` | The underlying test runner (pytest/npm) exits nonzero on a normal test *failure*, which this wrapper exists to capture and report as JSON — not a crash signal. |
| `proc-subst-unobservable` | Inside a `<(...)` process substitution: bash does not expose this command's exit status to the consuming loop at all — there is no syntax available to check it. |
| `optional-config-read` | Reads an optional external config file that may not exist or be malformed; the caller's own defaults are the intended fallback. |
| `known-risk-not-yet-fixed` | A real, unfixed risk found while auditing exit-status handling. Report it to the PO — this category exists to surface a finding, not to silently absorb it. Do not add a new site under this category to make a test pass; it is reserved for a genuine, disclosed risk. |

A category not in this list fails a second, independent test
(`ExemptionMarkersAreWellFormedTest`) that checks every marker actually
present in the shipped files — a typo'd category name is caught on its own,
regardless of whether that specific line is currently classified as needing
an exemption at all.

## 2. Every shipped script must pass `bash -n`

Enforced by `scripts/tests/test_shell_script_syntax.py`.

`bash -n <script>` parses the file without executing it. A script that fails
this can still exit 0 when run — a broken piece inside it (for example an
unparseable heredoc nested inside a command substitution) prints its own
syntax error to stderr and is silently skipped, with no other test catching
it. `bash -n` only proves the file *parses*; it says nothing about whether
the script does the right thing.

There is no exemption mechanism for this one — every file in scope must
parse, unconditionally.

## Running both locally

Both are part of the project's own test suite:

```bash
python3 -m unittest discover -s scripts/tests -t .
```

Run from the repo root; `-t .` sets the top-level directory the test
modules are discovered under.
