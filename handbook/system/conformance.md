---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: conformance
last_updated: 27.08.2026
---

# Conformance Runs Against Consumers

> **Not yet in any tagged release.** `scripts/conformance-run.sh` and
> `docs/adr/ADR-0010-conformance-runs-against-consumers.md` are absent from
> `v0.3.0-beta` and every earlier tag. If your installation is pinned to a
> tagged release, your `~/.claude/scripts/` does not have this script yet —
> re-run the install step once a newer tag ships it.

Runs this repository's own shipped checks — the lints, the anchor mechanism
— against real projects that consume them, as part of this repository's own
verification. Built after a gap named in
`docs/adr/ADR-0010-conformance-runs-against-consumers.md`: on 27.08.2026, four
shipped defects were found in one session, and every one was structurally
invisible from inside this repository while its test suite reported green.

## The problem

CCPR's shipped checks are rules about documents. A rule written and tested
only inside the repository that defines it is a hypothesis until it runs
against a project that actually consumes it — this repository's own fixtures
only confirm that a check agrees with its own author's expectations. One
example from that session: `covers:`'s emptiness check accepted a directory
holding only a `.gitkeep` as "covered", because its probe was `find -type
f` and a `.gitkeep` is a file. `covers:` appeared in **zero** documents
across every reference project this repository was measured against, so
nothing had ever exercised that probe against a real case — while 1,478
tests passed.

`conformance-run.sh` closes that gap by making the survey a designed,
repeatable part of verification instead of an occasional manual accident.

## Configuring consumers

Consumers are declared in the same personal, non-distributed config
`artifact-gate.sh` and `memory-sync.sh` already read: `~/.claude/memory-sync.json`
(overridable via `$MEMORY_SYNC_CONFIG`), under a top-level `conformance` key.
Each entry is a **local filesystem path** — nothing is ever fetched over a
network, so a consumer behind a VPN, or with no public remote at all, is
exactly as usable as one that has both. This is the whole answer to "does it
run offline": yes, because there is nothing else it could do.

A minimal working config:

```json
{
  "conformance": {
    "consumers": [
      { "id": "reference-a", "path": "~/path/to/a-project" }
    ]
  }
}
```

- `id` is what reports show. `path` never appears in a report unless
  `--show-paths` is given — the path is a local filesystem detail
  (frequently a home directory) with no reason to appear in output an
  operator might paste or share.
- `optional: true` on a consumer means a missing path is reported as
  not-covered instead of failing the run — useful for a consumer that only
  lives on some of the machines this config is also used from.
- `_comment` is legal at every level of this block (top-level, each consumer,
  each pin) — the same convention `gate.denyNames`'s config already uses.

**Unknown keys are refused, not silently ignored, at all three levels** —
the top-level `conformance` object, each consumer object, each pin object.
This was measured directly: a hand-written config that nested `pins` inside
a consumer object instead of at `conformance.pins[]` produced "0 checked, 0
satisfied", exit 0, silently discarding every expectation the operator had
written. A malformed `conformance` block is therefore refused outright
(exit 2, see "The exit contract" below) rather than treated as "no consumers
configured" — the scope is unknown, not narrowed.

## What a run reports

Every finding falls into exactly one of four classes. Only the first three
are CCPR-attributable; the fourth is never attributed to CCPR and never
moves the exit code.

| Class | Meaning |
|---|---|
| **C1 — contract violation** | The check's own behaviour disagrees with what it documents about itself: an exit code outside its documented set, a mandatory report line missing, a self-declared `**Exit:**` line disagreeing with the process's real exit status, an internal contradiction (`0 errors, 0 warnings` next to a non-zero exit), or a crashed interpreter on stderr. |
| **C2 — zero scope over a non-empty target** | The check reports `Files scanned: 0`, while an independent probe — reading the filesystem directly, never the check's own report — finds real candidates it should have seen. |
| **C3 — a pinned expectation violated** | A concrete, dated, per-consumer expectation the operator recorded (see "Writing a pin" below) disagrees with what the check actually produced this run. |
| **P — consumer finding** | Everything else: a real finding in the consumer's own documents. Reported, but attributed to the consumer, never to CCPR. |

**A P-class finding never moves the exit code.** Attributing a consumer's
real document irregularity to this repository is exactly the "alarm nobody
can act on" this mechanism exists to avoid.

**Two runs, worked, because the honest illustration needs both halves**
(measured 27.08.2026, against reference projects):

*A run that is entirely P and must exit 0.* An index/detail link checker
over a reference project produced 25 warnings in one run: 21 for `kind:`
values outside the shipped vocabulary — every one of them a real,
legitimate document genre that project invented, since the shipped list is
documented as the *known* set, not the *allowed* set — and 4 for an index
not linking back to a document that names it as `parent_index`, all genuine
defects in that project's own indexes. All 25 are class P. The run reports
them under their own heading and **exits 0**. An implementation that
escalated on "any finding at all" would report a CCPR regression here, every
run, forever.

*A run whose CCPR finding is an absence.* Before the `.gitkeep` fix
described above, a phase-document linter run over a reference project
reported `0 errors, 0 warnings` for a `covers:` entry pointing at a
directory holding nothing but a placeholder file. Nothing in the output was
wrong; the defect was what was *missing*. That is class C3, reachable only
through a pin — a recorded expectation that this directory must be reported
as holding nothing but a placeholder. The run **exits 1**. After the fix,
the same pin is satisfied.

## Could-not-run

A check can refuse to run against a target it considers unsuitable — no git
repository, no `docs/` directory — and say so on stderr. That refusal is
**not** a contract violation (the check behaved exactly as documented: an
unsuitable target, refused, reason given) and **not** a P-class finding
(there is no report about the consumer's documents to attribute, because
there is no report at all). It is reported under its own heading,
`Could Not Run`, carrying the check, the consumer id, and the reason.

It does not fail the run on its own — punishing a check for correctly
declining would be wrong. What it owes the reader instead is being
impossible to miss: every report's top line accounts for it explicitly,

```
**Checks:** N invoked, M ran, K could not
```

so a run that silently skipped part of its own coverage can never read like
a run that checked everything and found nothing.

## Writing a pin

A pin is a concrete, dated, per-consumer expectation — the mechanism behind
class C3. Configure it under `conformance.pins[]`, naming a `consumer` and a
`check` (one of `memory-lint`, `phase-docs-lint`, `manual-lint`,
`doc-volume-check`, `anchor`), and exactly one of:

- **`expectFinding`** — a substring (or, with `regex: true`, a POSIX ERE)
  that must appear on at least `minCount` (default 1) lines of that check's
  report for that consumer.
- **`expectField`** — one of `exit`, `errors`, `warnings`, `info`,
  `filesScanned`, compared against `value`. `filesScanned` is a **floor**
  (`>=`) — a growing consumer only strengthens it. Every other field is
  exact equality.

```json
{
  "consumer": "reference-a",
  "check": "phase-docs-lint",
  "expectFinding": "holds only a placeholder",
  "why": "this consumer's reserved-but-empty module directory (a .gitkeep only) must keep reporting as such; if this stops firing, either the module got built (fine) or phase-docs-lint's covers: emptiness check regressed (not fine)"
}
```

**A pin's subject must be something CCPR controls.** A fact about the
consumer's *own* state is never a valid pin, whatever the comparison — this
is not a style preference, it was shipped once and then removed. Two
anchor-only fields, `anchors.stale` and `anchors.maxBehind`, described how
far a consumer's checked-out docs trail its own production-code commit —
consumer state, never CCPR behaviour. The moment that consumer made a
routine commit, the pin would fire as a false CCPR alarm; a comparison
operator instead of equality would only have delayed that, not prevented
it. Both fields were removed. Apply the same test before adding a new field
or a new pin: does the expected value change on its own when the consumer
does its own normal work, independent of anything this repository ships? If
yes, it is not a valid pin.

**Every pin needs a `why`, and it is printed beside the finding.** A pin
without one is a configuration error (exit 2), not a lenient pin — an
unexplained pin is silent configuration debt, firing or staying quiet with
no record of the reasoning that put it there.

A pin whose named check produced no report for that consumer this run
(because it could-not-run, or hit the rare empty-both-streams C1 shape) is
**not evaluated** — reported under its own `Pins Not Evaluated` heading,
never silently counted as satisfied.

## The exit contract

| Exit | Meaning |
|---|---|
| `0` | A report was produced with no CCPR-attributable finding. This includes the not-configured skip below, and a run whose only findings are class P. |
| `1` | At least one CCPR-attributable finding (C1, C2, or C3 — a violated pin), or `--require-consumers` was given and zero consumers are configured. |
| `2` | The run could not be performed as asked: bad usage, a non-optional consumer whose path does not exist or is not readable, a malformed `conformance` config, or a malformed pin. |

**Not-configured is a loud 0, never a silent one.** The consumer list is
personal, non-distributed configuration — a clean install of CCPR never has
one, so a run with nothing configured is the default state of every fresh
install, not an edge case. Failing by default would make this run's first
act on every new machine a refusal. What the not-configured case owes its
reader is not silence but a statement of scope: the summary line names how
many consumers were covered (zero) and why, and a stderr notice names the
config path — worded so "0 consumers configured" cannot be misread as "0
findings, all clean". `--require-consumers` is the opt-in that turns an
empty consumer list into a finding, for a CI job that wants "nobody set
this up" to be a failure explicitly, rather than the tool assuming it.

### Flags

```
conformance-run.sh [--require-consumers] [--consumer <id>] [--show-paths] [--help]
```

- `--require-consumers` — treat zero configured consumers as a finding
  (exit 1) instead of the default loud 0.
- `--consumer <id>` — restrict the run to one already-configured consumer.
  An id that does not resolve is a usage error (exit 2), not a silent
  narrowing to zero.
- `--show-paths` — reveal each consumer's local filesystem path in the
  report. Without it, reports name a consumer only by its `id`.

## What it cannot catch

- **The first instance of a defect in a check nobody has pointed at a real
  project yet.** This mechanism converts a *discovered* defect into a
  permanently reproducible one, and makes a newly introduced regression
  visible against the same consumers going forward. It does not discover a
  defect that has never been pinned and that no C1/C2 probe happens to
  surface on its own. Finding the first instance still takes a human reading
  a real project — this mechanism exists so that reading has to happen only
  once per defect, not so it never has to happen.
- **Coverage equals the operator's configuration, exactly.** Two or three
  consumers is not "consumer projects in general" — a report never claims
  broader coverage than the `id`s it actually ran against.
- **A pin can go stale when a consumer legitimately changes.** The
  `.gitkeep` pin in the worked example above is true only while that
  directory stays reserved-but-empty; if the consumer project ever builds
  the component that directory was reserved for, the `.gitkeep` disappears
  on its own and the pin starts firing a false CCPR alarm — the check would
  then correctly find nothing, and the pin, not the check, would be wrong.
  There is no detection for this yet; it is a known, recorded limitation
  rather than something papered over.

## See also

- `docs/adr/ADR-0010-conformance-runs-against-consumers.md` — the full
  design decision: the attribution rule, the exit contract, the
  configuration shape, and Addendum 1 (the `could-not-run` correction).
- `docs/adr/ADR-0009-anchored-state-verification.md` — the sibling decision
  this one follows precedent from (the personal-config pattern, the loud-0
  not-configured pattern).
- [Cross-Cutting Mechanisms → Anchored State Verification](../SYSTEM_OVERVIEW.md#5-cross-cutting-mechanisms) —
  the mechanism this one runs alongside, not against: `anchor` compares
  docs to code inside one repository, `conformance-run.sh` compares a
  check's own claims to its behaviour against other repositories.
