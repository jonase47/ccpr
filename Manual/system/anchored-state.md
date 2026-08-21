---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: anchored-state
last_updated: 21.08.2026
---

# Anchored State Verification

> **Not shipped in any tagged release yet.** `scripts/anchor.sh` and `commands/anchor.md`
> are absent from `v0.2.1-beta` (CCPR's most recent tag) — they exist on the repository's
> main branch and ship with the next release. If you installed CCPR from a tagged release,
> your `~/.claude/scripts/` and `~/.claude/commands/` do not have them yet.

Checks phase documents against the **code** they describe, not against other documents.
Built after a gap named in `docs/adr/ADR-0009-anchored-state-verification.md`: every
mechanism CCPR shipped before this one compares Markdown to Markdown.

## The problem

`/cross-check`'s rule catalogue pairs Markdown with Markdown in all seven of its rules.
Rule R6 is even titled "CONSTITUTION.md (Inviolable) ↔ ADRs / **Implementation**" — and
its own source list contains no code file at all; its execution step is "read phase
indexes." A fully self-consistent documentation set can pass every gate while being stale
against the implementation, because nothing in the pipeline ever opens the code. External
feedback on the project put it precisely: comparing documents only to other documents
produces *consistency*, not *currency*.

`/anchor` closes that specific gap. It does not replace `/cross-check` — the two rule sets
do not overlap. `/cross-check` still finds Markdown-vs-Markdown drift; `/anchor` finds
docs-vs-implementation drift.

## The anchor

The carrier is frontmatter, flat keys only — this repo's own precedent, since both
frontmatter parsers (`scripts/lib/workitems/frontmatter.py` and `scripts/lib/frontmatter.sh`)
are strictly flat and a nested YAML block would fail silently under either:

```yaml
anchor_commit: a3f9c21
anchor_date: 18.08.2026
```

The anchor lives on the **phase index** (`docs/<folder>/<INDEX>.md`, e.g.
`docs/architecture/ARCHITECTURE.md`), written there by the Gate-Go freeze
(`freeze-phase-docs.sh`, second write path — see "The protection against silent deletion"
below). Every document under that scope **inherits** the index's anchor. A document may
carry its **own** `anchor_commit`, opt-in and typically alongside a `covers:` list of the
code paths it claims. Resolution order: **a document's own anchor first, the phase index's
anchor otherwise. No third tier.**

`covers:` **refines** the scope signal, it never replaces it — a document without
`covers:` inherits the whole scope's delta rather than claiming nothing, so a `covers:`
list that has silently stopped covering anything can never report clean by omission.

## Why the index, and not every document

The cheaper build was writing the anchor onto every frozen detail file — the freeze
already writes `status:` into exactly those files, so it would have been one more line
in an existing write. It fails on coverage, measured: the freeze runs only on a Go verdict
and is a no-op for P5 and P8, and the share of phase documents at `status: frozen` across
three reference projects is **90%, 12% and 6%**. In two of the three, the large majority
of documents would never receive an anchor through the per-document path at all. Anchoring
the index instead means one gate pass per phase produces one anchor for the whole scope,
regardless of how few detail files happened to be in a freezable state.

## Why severity reads the document's own status, never the index's

The phase index's own `status` field is not machine-guaranteed to reflect the freeze at
all. In one reference project, all five phase indexes carry `status: frozen`, even though
`freeze-phase-docs.sh` explicitly **skips every phase index by name** — they were frozen
some other way, by hand or by an earlier tool version. Had severity keyed off the index's
`status`, that project would treat every drift finding in every scope as error-grade,
while the two other reference projects — whose indexes stay `active` — would never
produce an error at all. A field nothing maintains cannot carry a severity decision, so
severity always reads the **affected document's own** `status`:

| Document's own `status` | Severity |
|---|---|
| `living` | info |
| `active` | warning + work item |
| `frozen` | error + work item |

## The two stages, and why staleness is never itself a verdict

**Stage 1 (mechanical)** compares the anchor against the last production-code commit and
lists changed covered paths plus changed paths claimed by no document. It never renders a
judgement, and its exit code says so explicitly: `check` and `status` exit **0** whether or
not drift was found — a drift finding is data, not a failure. A **non-zero exit is always
an operational failure** (no git repository, no `docs/` structure, a bad argument), never a
content finding.

**Stage 2 (agent-scoped)** asks exactly one question per affected document, scoped to that
document's delta only: *"Does this delta invalidate a statement in this document?"* Only a
"yes" carries severity, resolved from the table above.

The reason for the split is a measured base rate. Across the reference projects, 40% and
33% of the last 30 commits touched documentation only — roughly a third of all commits.
If staleness itself were the verdict, a warning would fire on close to a third of all
commits during active development, which is exactly the "message nobody reads" failure
mode this mechanism exists to avoid. Splitting the check keeps the common event
(staleness) silent as data and reserves the rare event (an invalidated claim) for a
verdict.

## The comparison point

Stage 1 compares against the last **production-code** commit, not `HEAD` — comparing
against `HEAD` would reintroduce the documentation-only base rate the two-stage split just
defused. "Production-code commit" is defined by **exclusion**, not inclusion: a commit is
production-code if it touches at least one path that is neither under `docs/`, nor under
`.claude/`, nor a Markdown file. Inclusion lists do not travel between projects — the three
reference projects have three unrelated code trees (`cmd/ internal/ frontend/`,
`src/ alembic/`, `src/ poc/ tools/`) — while every CCPR-driven project shares `docs/` and
`.claude/`.

The exclusion list is configurable per project, additively, via `.claude/settings.json`:

```json
{ "anchor": { "excludePaths": ["vendor/", "*.gen.go"] } }
```

A project can only **extend** the default, never replace it — narrowing the exclusion
would silently start treating `docs/` or `.claude/` as production code, which no project
intends by adding its own entry. Measured against all three reference projects, the
default lands on a real code commit **1, 2 and 6 commits behind `HEAD`** respectively —
which is the documentation-only base rate made concrete.

## "not verified" is a state, not a silence

A scope with no phase index, or an index with no `anchor_commit`, is reported exactly as
that — **neither pass nor fail**:

```
not verified — no phase index
not verified — index has no anchor_commit
```

The migration path leans on this: the anchor field is optional, no existing project
artifact becomes invalid by adopting `/anchor`, and adoption is per document and per
scope. "Not verified" is what an unmigrated majority looks like, deliberately distinct
from both a clean report and a finding.

## Acknowledging drift (`anchor ack`)

Detection without a clearance path is a ritual, not a mechanism — so re-anchoring is its
own operation and **never a side effect of another command**. `anchor ack` renders the
delta first, then asks:

```
Does the document's claim still hold?  [asserted/updated/abort]
Reason: _
```

It writes five flat keys: the new `anchor_commit` and `anchor_date`, plus `anchor_ack`
(`asserted` — reviewed, nothing changed — or `updated` — the documentation was brought in
line), `anchor_ack_from` (the old SHA), and `anchor_ack_note`. `asserted` and `updated`
stay two separate values on purpose: collapsing them into one field would make it
impossible to ask later *which anchors rest on nothing but an assertion* — different
grades of evidence do not belong in one field. A reason is mandatory in both the
interactive and the flagged (`--assert`/`--update`) path; without a delta to acknowledge,
`ack` refuses outright (exit 2) rather than let acknowledging-nothing look like a review.

The acknowledgement's **reach is structural**: whichever file is passed as the target is
the file that gets acked. Acking a phase index is a bulk acknowledgement because that is
where the scope anchor lives; acking a document with its own `anchor_commit` acknowledges
only that document.

## The agent clause, and its limit — stated honestly

**Never run `anchor ack` yourself. Report the delta, let the user decide.** — every
`/anchor` skill prompt and subagent briefing carries this clause verbatim.

State the limit plainly rather than implying a guarantee that is not there: **there is no
hard technical boundary.** `anchor ack` does refuse its interactive fallback prompt
without a terminal on stdin (`[ -t 0 ]`) — a plain pipe with no flags dies with exit 2 and
writes nothing. But the flagged path, `anchor ack <target> --assert --note "…"` (or
`--update`), needs no terminal at all and runs to completion non-interactively. Nothing in
the script stops an agent with Bash access from calling it that way. So the clause above is
**prevention**, not enforcement. The counterweight is **detection**: every `/anchor` run —
`check` or `status` alike — closes with the acknowledgement statistic:

```
**Anchors:** N anchored · M asserted without doc change · K stale
```

A rising ratio of "asserted without doc change" relative to "anchored" is the early
warning that acknowledgement has turned into ceremony. Prevention without a counter-check
would be self-report with nothing behind it; only the clause and the statistic **together**
are the honest construction ADR-0009 asks for. Do not claim a safety that does not exist.

## The protection against silent deletion

`freeze-phase-docs.sh`'s anchor write path writes `anchor_commit`/`anchor_date` onto the
phase index **only when it does not already carry one**. A second gate pass on an already
anchored index leaves the anchor untouched and says so (`anchor set` exits with a
dedicated code, 3, distinct from every other usage error). Without that guard, every
routine gate pass would silently re-anchor to the newest commit and erase all accumulated
drift before anyone had a chance to see it — the ADR calls this "the single highest-risk
detail in the whole design," one gate-command earlier than `ack`'s own version of the same
risk.

## A walkthrough, start to finish

> The commands below were **not executed in a live shell this session** — this agent ran
> without Bash tool access. Every literal line quoted here is either copied verbatim from
> a passing assertion in `scripts/tests/test_anchor.py` (the shipped script's own test
> suite) or is the exact `echo`/`printf` format string read directly from
> `scripts/anchor.sh`'s source with placeholder values filled in — never a free-form
> invented example. Treat the SHAs and dates as illustrative placeholders; treat the
> surrounding text as real, sourced output shape.

**1. Gate-Go freeze sets the anchor.** `freeze-phase-docs.sh` calls `anchor set` on the
phase index after freezing that phase's detail files (source: `cmd_set` in
`scripts/anchor.sh`):

```
anchor set: docs/architecture/ARCHITECTURE.md -> a3f9c21 (18.08.2026)
```

**2. Code changes under that scope.** A later commit touches a path claimed by
`docs/architecture/AUTH.md`'s `covers: [src/]`.

**3. `/anchor check` shows the delta** (`bash scripts/anchor.sh check <projectdir>` —
literal lines from `CheckDeltaReportTest`):

```
**Scope:** architecture
**Scopes found:** 1 of 1 phase folder (scope: architecture)
**Classification:** exclude prefixes: docs/,.claude/ · exclude suffixes: .md (source: default)
**Last production-code commit:** b7e1004 (20.08.2026)

## architecture

**Anchor:** a3f9c21 (18.08.2026)
**Changed production-code paths (1):**

- src/a.go — claimed by docs/architecture/AUTH.md

**Affected documents:**

- docs/architecture/AUTH.md — status: active

**Exit:** 0 (Stage 1 — data only, never a verdict)
```

**4. Stage 2 asks the one question.** "Does this delta invalidate a statement in
`AUTH.md`?" — for this walkthrough, assume the answer is **no**: the change is an internal
refactor, no auth-flow claim in the document became false. No finding, no work item —
staying stale with no invalidated claim is the expected majority case.

**5. Quittance line** (`bash scripts/anchor.sh status <projectdir>` — literal counts from
`AnchorInheritanceTest`, one scope, index + one inheriting document, nothing acked yet):

```
**Anchors:** 2 anchored · 0 asserted without doc change · 1 stale
```

**6. The reviewer acknowledges anyway**, to clear the "stale" count deliberately
(`anchor ack docs/architecture/AUTH.md --assert --note "reviewed, no invalidated claim"` —
literal echo format from `cmd_ack`):

```
Anchor  a3f9c21  (18.08.2026)
Last production-code commit  b7e1004  (20.08.2026)

Changed production-code paths (1):
  - src/a.go

anchor ack: docs/architecture/AUTH.md -> asserted (a3f9c21 -> b7e1004)
```

A re-run of `status` now reports the same document as `1 asserted without doc change`
instead of stale — visible, not silently cleared, and countable against the ceremony
warning in "The agent clause" above.

## Where this differs from `BASELINE.md` / Baseline Mode

Two different concepts, deliberately kept apart (ADR-0009 §1): the anchor records **what**
is fixed — a specific point in the code's history. Baseline Mode records **when** the
project stopped actively reading a set of documents. `BASELINE.md` cannot carry an anchor
even if it wanted to: it is excluded from both linters (`phase-docs-lint.sh`'s
`LIVING_FILES`, `templates/PHASE_DOC_SCHEMA.md`'s schema) and only exists after
`/release-baseline`, so it cannot participate in a phase-entry check the way a phase index
does. Merging the two would mean reversing both exclusions to place a live tracker inside a
file whose whole documented purpose is to make agents *stop* reading it.

## See also

- `docs/adr/ADR-0009-anchored-state-verification.md` — the full design decision, including
  both addenda (18.08.2026 / 21.08.2026), which correct nine statements the ADR's own body
  made before implementation.
- `commands/anchor.md` — the command surface: arguments, Stage 1/Stage 2 execution steps,
  the escalation path into `Manual/WORKITEMS.md`, and the Handover epilogue rule.
- [Cross-Cutting Mechanisms → Cross-Check](../SYSTEM_OVERVIEW.md#5-cross-cutting-mechanisms) —
  the Markdown-vs-Markdown neighbour this mechanism does not replace.
