---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: discipline-gate
last_updated: 20.08.2026
---

# Discipline Gate

> **Shipped since `v0.3.0-beta`.** `scripts/artifact-gate.sh` and
> `scripts/lib/discipline_gate.sh` are absent from `v0.2.1-beta` and every
> earlier tag. If your installation predates `v0.3.0-beta`, your `~/.claude/scripts/`
> does not have them — re-run the install step against the newer tag.

Enforces the Constitution's Inviolable "No personal or tenant data in
shipped artifacts" mechanically instead of by hand review. Built after that
Inviolable was breached: a tenant project name sat in an instinct's own
rationale while the file's header claimed such details were anonymised, and
hand sweeps are what let it through.

## What it checks

The pattern definitions live once, in `scripts/lib/discipline_gate.sh`,
shared by two entry points that select which checks run via a *profile* —
the patterns never change meaning between them:

| Check | `artifact` profile (`artifact-gate.sh`) | `memory` profile (`memory-sync.sh promote`) |
|---|:---:|:---:|
| secret — credential assignments, bearer tokens, vendor-shaped keys, a screaming-snake-case placeholder filter | yes | yes |
| personal — session hashes, home paths, real emails | yes | yes |
| network — IP literals, allowlist-aware | yes | yes |
| denylist — configured tenant/project names | yes | yes |
| context — colour-vision/accessibility vocabulary (a de-personalisation rule specific to memory content; ordinary in a TDD/a11y skill prompt) | no | yes |
| type-user — a promotion rule about where a memory file may go, not about leaked data | no | yes |
| content — "Next Steps" headings/checkboxes, legitimate skill-prompt structure | no | yes |

The secret check no longer relies on a generic "40+ character string" rule —
that was the source of every false positive when the gate was first pointed
at this repository (77 files flagged, zero real findings). It now looks for
the shapes real machine-generated credentials actually have.

## The tenant/project deny list

`denylist` is the check that closes the gap a generic secret scanner cannot:
a tenant or project *name* is not a secret pattern. The list is configured,
never shipped:

- `gate.denyNames` in `~/.claude/memory-sync.json` (personal, non-distributed
  config — template: `templates/memory-sync.example.json`), or
- the `CCPR_GATE_DENY_NAMES` environment variable (newline- or
  comma-separated) — for a CI job that supplies the list from its own secret
  store instead of a file.

Matching is case-insensitive, escalates to NFC-normalised, case-folded
comparison for a non-ASCII name, and checks both a file's **path** and its
**content** — a file simply *named* after a tenant is reported even with
clean content inside. A match is never printed: findings name the file and
line, the configured name itself is redacted from every line the gate
emits, including its own usage text and error messages. Running with no
deny list configured is not silent — the gate says so out loud in its
summary line instead of passing quietly.

## `artifact-gate.sh`

```
scripts/artifact-gate.sh [--repo <dir>] [--require-denylist] [<file> ...]
```

Sweeps every file `git ls-files` tracks in a repository (default: the git
root of the current directory), or the files named on the command line. A
tracked symlink is reported by its own name and never followed — matching
what `install.sh` actually ships for a symlink (the link itself, never the
target's bytes).

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Nothing found, over a scope that was actually read |
| 1 | Findings — or, with `--require-denylist`, an unconfigured deny list |
| 2 | The run could not be performed as asked: bad usage, an unreadable file, an unusable deny-list entry, or an empty scan scope |

A run that scanned zero files exits 2, not 0 — "0 findings" over an empty
scope looks identical to success unless the tool says so itself.

### Where the output goes, and why the deny-list notice is on stderr

Findings go to **stdout**. Statements about what the run could *not* do go to
**stderr**: the empty-scope warning, `--require-denylist`'s failure line, and —
since WI-0090 — the notice that no deny-list was configured:

```
artifact-gate: deny-list NOT CONFIGURED -- no tenant/project names were checked.
```

That last one used to sit on stdout, among the findings. A caller that keeps
stdout as its findings report, or discards it, then lost the one line saying the
headline check never ran. Measured over this repository before the move:
`artifact-gate.sh --repo . >/dev/null` printed nothing at all and exited 0 —
byte-identical to a fully configured clean run redirected the same way.

So a wrapper that captures only stdout sees a clean report and cannot tell it
from a run where the deny-list check did not happen. Capture both streams, or
read the exit code: a missing deny-list is a notice and exit 0 by default, and
becomes a finding and exit 1 only with `--require-denylist`.

### Which copy to run — it matters only for CCPR's own repository

Two invocations exist and both are correct, for different targets:

| Target | Invocation |
|---|---|
| Any project other than CCPR | the installed copy, `~/.claude/scripts/artifact-gate.sh --repo <dir>` |
| CCPR's own repository | the repo-local copy, `scripts/artifact-gate.sh --repo .` |

The reason is the pattern-source self-exemption. `lib/discipline_gate.sh` spells
out what the gate looks for, so it necessarily contains the shapes it hunts —
`/Users/<name>/` cannot be written down without writing it down. Those lines
carry the `gate-pattern-source` marker and are blanked while scanning **that
file**, identified by its absolute path (`discipline_gate.sh`, the
`_GATE_PATTERN_SOURCE` comparison).

An installed gate pointed at a CCPR checkout is therefore scanning a *different
copy* of its own pattern library: same content, different absolute path, so the
exemption does not apply. Measured 25.08.2026 over a fresh clone:

```
~/.claude/scripts/artifact-gate.sh --repo .   → 3 findings in 1 file, exit 1
scripts/artifact-gate.sh --repo .             → 0 findings,           exit 0
```

Both runs are right about what they saw. The three findings are the gate's own
pattern definitions, and the finding text says so — it asks you to verify
whether the file is "a foreign or differently-resolved copy" before treating it
as a leak. For any other project the question does not arise, because that
project does not contain `lib/discipline_gate.sh`.

This is a deliberate trade-off, not an oversight: identifying the file by
content rather than by path would let a foreign file carrying a forged marker
exempt itself. `artifact-gate.sh` records the same reasoning for the related
case of a project that vendors a copy of the gate.

## CI template

`templates/ci/artifact-gate.ci.sh` is a dormant, forge-agnostic POSIX shell
template — CCPR's Constitution forbids a hosted service as a distribution
prerequisite, so it names no specific CI provider. Copy it into your
repository, wire it into your CI configuration as a job whose only command
is the script, and optionally expose your deny list to CI via
`CCPR_GATE_DENY_NAMES` plus `REQUIRE_DENYLIST=1` inside the copy. A shallow
checkout is sufficient — the sweep reads `git ls-files`, not history.

## The sibling entry point: `memory-sync.sh promote`

`memory-sync.sh promote` runs the same discipline gate (`memory` profile)
against a file before sharing it into an org-tier repository — see
[memory-instincts.md → Team Sharing (Org Tier)](memory-instincts.md) for the
full command reference. Unlike the artifact gate, `memory-sync.sh` itself
has shipped since v0.2.0-beta; what has not yet shipped is this gate now
running through the same, shared pattern library rather than its own copy,
plus destination-path hardening landing in the same release: the
destination is checked against the deny list before anything is fetched,
copied, staged or committed, a directory destination is rejected outright (so
the string checked and the string actually published can never differ),
and a destination that merely reads like a command-line flag (`--all`,
`-n`) is refused the same way.

## Both are a client-side lint, not a server-enforced backstop

Both entry points run locally, before a commit or a push exists. Add a
CI/pre-receive backstop (the template above, or your own) before relying on
either as the only line of defense for a shared or distributed repository.
