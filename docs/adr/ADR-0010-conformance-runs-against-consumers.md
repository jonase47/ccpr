---
kind: adr
adr_id: ADR-0010
status: accepted
last_updated: 27.08.2026
related:
  - ADR-0009-anchored-state-verification.md
  - ../CONSTITUTION.md
---

# ADR-0010: Conformance runs against consumers

**Status:** Accepted (27.08.2026)
**Decision-makers:** Repo owner (Jonas)

## Context

On 27.08.2026, four shipped defects were found in one session. Every one was structurally invisible
from inside this repository, and the test suite reported green throughout:

- `.gitkeep` satisfied `covers:`'s emptiness check. The field `covers:` appeared in **zero** documents
  across all three reference projects this repository is measured against, so the check had nothing to
  check. The suite said 1478 tests, OK, while this was live.
- A `.gitignore`-only commit set the anchored-state comparison point. The check was never run against a
  repository whose newest commit was hygiene rather than code — two of the three reference projects
  were in exactly that state at the same time.
- `senior-developer`'s shipped tool list lacked the `Agent` entry, while its own body makes invoking
  `code-reviewer` mandatory. The maintainer's local `~/.claude` copy carried the missing entry, patched
  by hand at some earlier point, so the shipped gap ran invisibly for however long it existed.
- ADR-0009's follow-up 4 read "undefined" for six days after Addendum 3 had already answered it — a
  reader working from the follow-up list alone never reached the addendum that closed it.

The fourth item is a documentation-staleness failure, not a conformance-run failure, and this ADR does
not claim the mechanism below would have caught it. It is cited here for the generalisation it shares
with the first three: **a rule is only as true as the strongest thing that could have refuted it and
did not.** `covers:` was never tested against a document that used it. The comparison-point default was
never tested against a repository whose newest commit was pure hygiene. The tool list was never tested
against an unpatched install. A rule written in the repository that defines it is a hypothesis until it
runs against something that consumes it.

Today's discovery was a manual, ad hoc survey — it happened because something else prompted someone to
run a shipped check against a real project by hand. This ADR makes that survey a designed part of
verification instead of an occasional accident, and settles the three questions that make the difference
between a useful mechanism and a second alarm nobody reads: whose fault a finding is, what the run
promises when nothing is configured, and where the boundary of what it can and cannot catch actually
sits.

## Decision

### 1. Conformance runs are part of verification, not a manual survey

The shipped checks — the lints, the gates, the anchor mechanism, and whatever else this repository ships
that inspects a project's documents or history — run against real consumer projects as part of this
repository's own verification. A check's correctness claim is a hypothesis about a document shape or a
commit history it has never actually been tested against; running it here, against fixtures this
repository itself authored, only tells us the check agrees with its own author's expectations.

### 2. The attribution rule

**A finding is attributed to CCPR only when the evidence for it lies in the check's own contract, or in
a difference the consumer did not cause. Everything else is attributed to the consumer.**

Every finding a conformance run produces is sorted into exactly one of four classes:

| Class | Meaning | Example shape |
|---|---|---|
| **C1** — contract violation | The check's own behaviour disagrees with what it documents about itself | exit code outside the check's own documented set; non-zero exit with **both streams** empty (see Addendum 1 — stdout alone misclassifies a deliberate abort); a mandatory report-skeleton line missing; the report's self-declared `**Exit:** N` disagreeing with the process's actual exit status; internal contradiction (`0 errors, 0 warnings` alongside a non-zero exit); an interpreter-fatal shape on stderr (traceback, `SyntaxError`, `command not found`) |
| **C2** — zero scope over a non-empty target | The check reports it scanned nothing, while an independent per-check candidate probe finds candidates it should have seen | `Files scanned: 0` against a directory the probe shows is non-empty for that check's own kind of input |
| **C3** — a pinned expectation violated | A concrete, dated, per-consumer expectation (declared in personal config, §5) disagrees with what the check actually produced | a pin says "check X must warn on file Y in consumer Z"; the run's output does not contain that warning |
| **P** — everything else | A finding about the consumer itself | any other lint/gate finding in a consumer's real documents |

Only C1, C2 and C3 are CCPR-attributable and can affect exit status. P-class findings are reported, under
their own heading, and never escalate a run's exit code — attributing a consumer's real document
irregularity to this repository is exactly the "alarm nobody can act on" this design exists to avoid.

**Worked example — two runs, because the honest illustration needs both halves.** Both are measured,
27.08.2026, against reference projects.

*A run that is all P and must exit 0.* The index/detail link checker over reference project B produced
25 warnings in one run: 21 for `kind:` values outside the shipped vocabulary, 4 for an index not linking
back to a document that names it as parent. Every one of the 21 names a real, legitimate document genre
that project invented — the shipped list is documented as the KNOWN set, not the ALLOWED set, so firing
on them is the check doing its job precisely. Of the 4 link findings, 3 were genuine defects in that
project's own indexes and 1 was a document pointing at the wrong index entirely. All 25 are class **P**.
A conformance run over that project must report them, attribute them to the consumer, and **exit 0**.
An implementation that escalated on "any finding" would report a CCPR regression here, every run,
forever.

*A run whose CCPR finding is an absence.* The phase-document linter over reference project A, at the
commit before the fix, reported `0 errors, 0 warnings` for a `covers:` entry pointing at a directory
whose only content is a `.gitkeep`. The check's own emptiness probe is `find -type f`, and a `.gitkeep`
is a file, so the directory counted as covered and the warning that the case exists to raise never
fired. Nothing in the output is wrong; the defect is what is missing. That is class **C3**, and it is
reachable only through a pin — a recorded expectation that this directory must be reported as holding
nothing but a placeholder. After the fix the same run reports that warning, and the pin is satisfied.

The two together are the attribution rule in practice: 25 findings that must not move the exit code, and
one absent finding that must. A mechanism that could not tell them apart would bury the second under the
first.

### 3. Exit contract

| Exit | Meaning |
|---|---|
| `0` | A report was produced and it contains no CCPR-attributable finding. This includes the not-configured clean skip (§4) and a run whose only findings are class P. |
| `1` | At least one CCPR-attributable finding (C1, C2 or C3), **or** `--require-consumers` was given and zero consumers are configured. |
| `2` | The run could not be performed as asked: bad usage, a configured consumer path that does not exist or is not readable, a malformed config (§5), or an unusable pin. |

There is deliberately **no exit 3**. `memory-lint.sh` and `anchor.sh` each carry a dedicated non-2 exit
code, and each states its own reason: memory-lint's 3 exists because a single misconfiguration
(`MEMORY_INDEX_LINK_SEVERITY` outside `{err,warn}`) must not be mistaken for a clean or a failing lint
result by a caller inspecting only the exit code, and `anchor.sh`'s 3 exists so `freeze-phase-docs.sh`'s
anchor hook can tell "the index already carries an anchor and `--force` was not given" apart from every
other `set` failure by exit code alone, without a message grep. Both codes exist for a **named caller**
that needs that specific distinction from the exit code and nothing else. No caller of this run needs
to tell a malformed pin apart from an unreadable consumer path, or a config error apart from a bad
command-line argument, by exit code alone — every distinction a future caller might need is already in
the report body. Should such a caller appear, record the new code and its reason here, in this
decision, rather than reusing `2` for two things that turn out to need to be told apart — this is the
change that would falsify decision 3 as written, and it belongs in this file when it happens, not as a
silent reinterpretation of an existing status.

### 4. Not-configured is exit 0 with a loud statement, not a failure

The consumer list is personal, non-distributed configuration (§5). A clean install of CCPR never has
one, so a run with nothing configured is the default state of every fresh install, not an edge case.
Failing by default would make this run's first act on every new machine a refusal — the same reasoning
`artifact-gate.sh` already states for its own deny-list default, and it applies here without change.

What the not-configured case owes its reader is not silence but a statement of scope: a summary line
naming how many consumers were covered (zero) and why, printed the same way `artifact-gate.sh` already
prints its own not-configured notice — to stderr, so a caller that treats stdout as its findings report
cannot lose it, and worded so that "0 consumers configured" cannot be misread as "0 findings, all
clean" (KA-G-017: a run reporting no scope is not a pass). `--require-consumers` is the opt-in that
turns an empty consumer list into a finding — the same shape as `artifact-gate.sh --require-denylist`,
for the same reason: a CI job that wants "nobody set this up" to be a failure asks for that explicitly,
rather than the tool assuming it on everyone's behalf.

### 5. Where consumers are configured

Consumers are declared in the same personal, non-distributed config `artifact-gate.sh` and
`memory-sync.sh` already read (`gate_config_path()`, `scripts/lib/discipline_gate.sh:234-236`), under a
new top-level `conformance` key — not nested under the existing `gate` key, which is
`_gate_read_config`'s own key for deny-list and IP-allowlist configuration and has nothing to do with
running checks against a project. Each entry carries an operator-chosen `id` and a local filesystem
`path`; nothing is fetched over a network, and a consumer behind a VPN or with no public remote at all
is exactly as usable as one that has both.

```json
"conformance": {
  "_comment": "Local paths only -- nothing here is fetched. Each consumer is a real project this operator maintains, read-only for this purpose. Reports refer to a consumer by its id, never by its path.",
  "consumers": [
    { "id": "reference-a", "path": "/local/path/to/project-a" }
  ],
  "pins": [
    { "consumer": "reference-a", "check": "memory-lint", "expect": "...", "why": "..." }
  ]
}
```

Reports name a consumer only by its configured `id`, never by its path — the path is a local
filesystem detail with no reason to appear in an output the operator might paste or share, and keeping
it out of the report is cheaper than relying on every reader to redact it correctly. A pin without a
`why` is a configuration error, not a lenient pin: `why` is what turns a C3 finding into something a
reader can act on without first reconstructing the reasoning that produced the pin. This mirrors
`artifact-gate.sh`'s own convention for its deny-list — a configured control that cannot explain itself
in the report is a control nobody downstream can evaluate.

**Deliberate divergence from `_gate_read_config`.** `_gate_read_config` treats a malformed config file
as absent — `except Exception: sys.exit(0)` — and that is the right choice there, because a broken
config in that path means "use the default deny-list behaviour", which is itself a safe, documented
state. It is the wrong choice here: a malformed `conformance` block does not mean "run with no
consumers configured", it means the configured scope is **unknown** — some consumers may be readable and
some pins may be silently dropped, and reporting that as a clean not-configured skip would produce
exactly the false-clean result this ADR exists to close. A malformed `conformance` config is therefore
`2`, not `0`.

## What this cannot catch

- **The first instance of a defect in a check nobody has pointed at a real project yet.** This mechanism
  converts a discovered defect into a permanently reproducible one, and makes a newly introduced
  regression visible against the same consumers. It does not discover a defect that has never been
  pinned and that no candidate probe (C2) or contract check (C1) happens to surface. What finds the
  first instance is a human reading a real project — this mechanism exists so that reading has to happen
  only once per defect, not so it never has to happen.
- **A check that fires correctly but says something useless.** Wording quality, an unhelpful message, or
  a technically-correct-but-unactionable finding are not contract violations and this run has no opinion
  on them.
- **Stage-2 judgment**, unchanged from ADR-0009: whether a finding this run surfaces actually matters to
  the project it was found in is a question for whoever reads the report, not for the exit code.
- **The `senior-developer` tool-list defect is explicitly out of scope for this mechanism.** It is a
  divergence between the shipped tree and a maintainer's locally patched installed tree, not a defect a
  check's output would ever surface by running against a consumer's documents — a consumer's copy of
  `senior-developer.md` is whatever `install.sh` last wrote there, indistinguishable from correct by any
  document-inspecting check. It needs its own instrument (comparing a shipped agent definition against
  what actually got installed) and its own work item; this ADR does not claim the mechanism decided here
  would have caught it, and implementation must not imply otherwise.
- **Coverage equals the operator's configuration, exactly.** Three consumers is not "consumer projects
  in general", and a report must never phrase its result as broader than the `id`s it actually ran
  against.
- **A pin can go stale when a consumer legitimately changes.** The `.gitkeep` pin in the worked example
  above is true only while that directory stays reserved-but-empty; if the consumer project ever builds
  the component that directory was reserved for, the `.gitkeep` disappears on its own and the pin starts
  firing a false CCPR alarm — the check would then correctly find nothing, and the pin, not the check,
  would be wrong. This is not fully solvable by the design decided here: a pin's own expiry is not
  detectable without re-reading the consumer's intent, which no automated check can do. It is recorded
  as a known limitation rather than papered over (see follow-up 3).

## Addendum 1 (27.08.2026): C1 rule 2 corrected, and the class it was hiding

Decision 2's C1 rule "non-zero exit with empty stdout" is wrong as first written, and the implementation
found it before any acceptance run did.

### What it collides with

Every shipped check in this repository aborts through a `die()`-style path that writes its reason to
stderr and exits non-zero **before** the report is opened — a pre-flight refusal of an unsuitable target
is not a malfunction, it is the check declining to guess. A consumer that is not a git repository, or
has no `docs/`, produces exactly that. Under the rule as written, every such refusal was a CCPR contract
violation.

### The discriminator, measured 27.08.2026

| | exit | stdout | stderr |
|---|---|---|---|
| a check refusing an unsuitable target | 2 | 0 bytes | 166 bytes — it says why |
| the silent death this rule exists to catch | 1 | 0 bytes | 0 bytes |

**A deliberate abort speaks; a silent death is silent on both streams.** C1 rule 2 therefore requires
stdout **and** stderr to be empty. That is observable behaviour, not a prior judgement about whether a
consumer is a suitable target — which the run is in no position to make.

### The class the collision was hiding

Correcting the rule is the smaller half. A check that refuses a target **did not run**, and until now the
run had no way to say so: such a check fell through to P or vanished. Both are wrong, and the second is
this ADR's own opening failure one level down — a run that silently did not check something must not
read like a run that checked it and found nothing.

A fourth reported class is therefore added, `could-not-run`. It is **not C1** (the check behaved
correctly and said why) and **not P** (it is not a finding about the consumer's documents). It carries
the check, the consumer id and the reason from stderr, and — the part that matters — it appears in the
scope accounting: the summary states how many checks were invoked and how many actually ran, not only
how many consumers were covered. It does not escalate the exit status on its own; a correctly-behaving
check is not a defect. Being impossible to miss in the report is what it owes instead, which is the same
answer decision 4 gives for the not-configured state.

### Why this is recorded here rather than by editing decision 2 silently

The rule was wrong for six hours, not six days, and nothing was built on it before the correction. It is
recorded in place anyway, because the alternative — a quiet edit — removes the only evidence that a rule
this repository wrote about its own checks did not survive first contact with them. That is the same
argument this repository applied to ADR-0009's follow-up 4 on the same day.


## Consequences

**Positive.** The mechanism reuses precedent this repository already has for every non-trivial piece of
it: the personal-config pattern, the not-configured-is-a-loud-`0` pattern, and the "state the scope of
what was covered" discipline all come from `artifact-gate.sh` and `discipline_gate.sh` unchanged. Nothing
new has to be invented except the C1/C2/C3/P classification, which is the one genuinely new idea this
ADR contributes. All four of 27.08.2026's structurally-invisible defects except the tool-list one
(explicitly out of scope, above) become things a configured operator would have caught the next time the
run executed, because each is expressible as a C1, C2 or C3 finding against the reference projects that
already exhibited it.

**Negative.** A fourth exit-code contract now lives in this repository, alongside `artifact-gate.sh`'s,
`memory-lint.sh`'s and `anchor.sh`'s, each numerically similar but differently scoped — a maintainer who
assumes exit codes generalise across this repository's own scripts will be wrong, and each script's own
header has to keep saying so, as `anchor.sh`'s already does relative to `phase-docs-lint.sh`. A pin adds
a second thing that can go stale (the pin itself, see "What this cannot catch") on top of the thing it
protects. And the mechanism cannot run in this repository's own CI or on a contributor's machine without
that contributor's own consumer configuration — its coverage is permanently gated on whoever runs it
having real projects to point it at, which for most contributors is nobody at project-import time.

## Alternatives considered

**Treat every consumer finding as a CCPR finding, with no attribution split.** Rejected: this is the
"alarm nobody can act on" failure named directly in WI-0124's design questions and reproduced by the
worked example above — 21 legitimate P-class findings would have buried the one C3 finding that
mattered, in the same run, on the same day this decision was made.

**A dedicated exit code (3, or a new value) for a malformed conformance config.** Rejected on the same
reasoning as decision 3's rejection of exit 3 generally: no caller of this run needs a config error told
apart from every other "could not run as asked" failure by exit code alone. `2` already exists for
exactly that meaning and gains nothing from a sibling.

**Fail hard when no consumers are configured.** Rejected on the same grounds `artifact-gate.sh` already
states for its own deny-list: the config is personal and non-distributed, so a clean install never has
one, and this run's first act on every new machine would be to refuse rather than to run.

**Fetch consumer state from a hosted service (a forge's REST API, a CI artifact store) instead of a
local path.** Rejected for the same reason ADR-0009 rejects querying a forge's REST API for repository
state: it makes a hosted service a prerequisite, which the Constitution's distribution Inviolable
forbids, and it would not work from behind a VPN with no public endpoint — one of WI-0124's own design
questions.

**Nest consumer configuration under the existing `gate` key.** Rejected: `gate` is `_gate_read_config`'s
own key, scoped to deny-list and IP-allowlist configuration for the artifact sweep. Consumer paths and
pins answer a different question and belong beside it as their own top-level key, not folded into a key
whose documented meaning would then no longer match its contents.

**A pin without a mandatory `why`.** Rejected: an unexplained pin is a silent piece of configuration
debt — it fires or stays quiet with no record of the reasoning that put it there, and the next person to
read a C3 finding would have to reconstruct that reasoning from scratch or discard the pin without
understanding what it protected.

## Follow-ups

1. ~~**Which shipped checks run under this mechanism in its first implementation wave is not decided
   here.** This ADR settles the attribution rule, the exit contract and the configuration shape; it does
   not enumerate which of this repository's checks (memory-lint, phase-docs-lint, anchor, artifact-gate,
   manual-lint, or others) the first conformance run actually invokes. Record the initial list, and the
   reasoning for what is included or deferred, here when the implementation wave settles it.~~
   **Half resolved in Wave 2 (27.08.2026). The list:** `memory-lint`, `phase-docs-lint`,
   `manual-lint`, `doc-volume-check`, `anchor` — pinned as `CHECK_NAMES` in
   `scripts/conformance-run.sh`, whose own comment names this follow-up as the question it settles.
   **The reasoning half is still open:** `artifact-gate.sh` is named as a candidate above, is not in
   the table, and nothing anywhere records why it was deferred. Record that here.
2. **Where the run lives — a local skill only, or a dormant CI hook mirroring ADR-0009 §7's two-tier
   local-default/CI-optional split — is undecided.** WI-0124 does not ask this question and this ADR does
   not answer it. Record the choice here when it is made, rather than defaulting to one shape by
   implementation accident.
3. **Pin staleness has no detection mechanism.** "What this cannot catch" above records the failure
   mode — a consumer's legitimate change turns a correct pin into a false CCPR alarm — without a fix.
   Revisit once real pins exist and a stale one has actually been observed; a mechanism designed against
   a hypothetical staleness pattern before one is measured would repeat this ADR's own opening argument
   against itself.
