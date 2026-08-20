---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: discipline-gate
last_updated: 20.08.2026
---

# Discipline Gate

> **Not shipped in any tagged release yet.** `scripts/artifact-gate.sh` and
> `scripts/lib/discipline_gate.sh` are absent from `v0.2.1-beta` (CCPR's most
> recent tag) — they exist on the repository's main branch and ship with the
> next release. If you installed CCPR from a tagged release, your
> `~/.claude/scripts/` does not have them yet.

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
