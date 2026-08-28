---
kind: adr
adr_id: ADR-0009
adr_status: accepted
status: active
last_updated: 27.08.2026
related:
  - ADR-0002-workitem-backend-contract.md
  - ADR-0008-typed-workitem-links.md
  - ../../templates/PHASE_DOC_SCHEMA.md
---

# ADR-0009: Anchored state verification for phase documents

**Status:** Accepted (21.08.2026) — decided 18.08.2026, implemented across WI-0019…WI-0022;
four addenda below correct and complete the decision
**Decision-makers:** Repo owner (Jonas)

## Context

CCPR checks its artifacts against each other and never against the thing they describe.
`/cross-check`'s rule catalogue pairs Markdown with Markdown in all seven rules; R6 is titled
"CONSTITUTION.md (Inviolable) ↔ ADRs / **Implementation**" and its source list contains no code at all.
The execution step is "Read phase indexes". External feedback put the gap precisely: comparing
documents only to other documents produces *consistency*, not *currency*. A fully self-consistent
documentation set can be stale against the implementation while every gate passes.

Nothing in P0/P1 reads repository state, and `gate-preflight.py` reads files and the constitution but
never git. The repository does touch git in later phases (sprint review, polish, dependency checks),
but always as a **delta** view ("what changed this sprint"), never as a verification of a recorded
assumption.

### What the codebase forces

Four properties of the existing code constrain any solution, and three of them contradict the shape a
naive design would take:

1. **Both frontmatter parsers are strictly flat.** `scripts/lib/workitems/frontmatter.py` splits on
   `line.partition(":")` with no indent handling, and `scripts/lib/frontmatter.sh` matches the first
   line carrying `key:` via awk. A nested YAML block cannot be stored without adding a YAML
   dependency, and the failure is silent rather than loud: reading a nested key returns empty, and a
   list read of the parent returns the child's entries.
2. **`BASELINE.md` cannot carry this.** It is listed in `LIVING_FILES` in `phase-docs-lint.sh` and
   explicitly excluded by `PHASE_DOC_SCHEMA.md`, so no linter validates it — and it only exists after
   gate-P7, so it cannot participate in a phase-entry check. Its Baseline-Mode semantics also point the
   opposite way: the mechanism exists to make agents *stop reading* those documents.
3. **There is no Conditional-Go condition-ID mechanism.** The verdict "Conditionally Done" exists in
   the sprint gate, but no command, template or script persists or re-checks a condition ID. Tracked
   conditions are a behavioural rule, not shipped machinery.
4. **No command consumes a script exit code.** A "blocking" verdict is today a word in a prompt with
   exactly the enforcement of a warning.

### What two real projects show

Measured across two projects built with CCPR — project A mid-sized, project B large and actively
developed:

| Metric | Project A | Project B |
|---|---|---|
| Markdown files under `docs/` | 112 | 354 |
| of those carrying phase frontmatter | 89 | 226 |
| Documentation-only share of the last 30 commits | 40 % | 33 % |
| Code-path renames / deletions | 0 / 0 (172 commits) | 1 / 9 (2080 commits) |

Three consequences. The upkeep surface of a per-document scheme is 226 files in the larger project and
grows with it. **A third of commits touch documentation only**, so an anchor compared against `HEAD`
would report drift almost permanently during active development — this is the design's central
constraint, not an edge case. And code paths do move, at roughly one event per 200 commits, so a
declared path list decays slowly but really.

One further measurement decides the severity model: in project B the `status` field carries four
values outside the schema (`final`, `complete`, `done`, `pre-merge`) and only 12 % of phase documents
are `frozen` against 73 % `active`.

## Decision

### 1. The term is *anchor*, and it is a new one

`BASELINE.md` and Baseline Mode keep their present meaning — the post-release frozen/active
documentation split. The new mechanism is an **anchor**: it records *what* is fixed, a point in the
code's history, not *when* it was fixed. That distinction is exactly what separates the two concepts,
and merging them would require reversing both an explicit schema exclusion and an explicit lint skip
in order to place a live tracker inside a file whose documented purpose is to stop being read.

### 2. The carrier is phase-document frontmatter, with flat keys

```yaml
---
phase: P3
subskill: arch-components
status: frozen
last_updated: 18.08.2026
anchor_commit: a3f9c21
anchor_date: 18.08.2026
covers:
  - internal/auth/
  - cmd/gateway/
---
```

Flat keys only, following this repo's own precedent of flattening rather than introducing YAML.
`phase-docs-lint.sh` is extended next to its existing `related:` and `parent_index:` checks. No third
schema and no new state file: a separate register would either need its own linter or become the very
second-register drift this feature exists to detect.

### 3. Granularity: one anchor per scope, `covers:` as a validated opt-in

The default is one anchor per phase/scope. `covers:` is opt-in per document, for the few documents
where document-exact resolution changes what a reader does — typically component, data-model, API and
auth documents. Three binding qualifications:

- A document without `covers:` reports **"not verified"** — neither pass nor fail.
- `covers:` **refines** the scope signal and never replaces it, so a list that has silently stopped
  covering anything cannot report clean.
- Every `covers:` entry is path-existence-checked by the linter **from day one**. An unvalidated
  opt-in reproduces a rot pattern this repository already contains elsewhere.

### 4. The check is two-stage, and staleness is never itself a verdict

| Stage | Does | Produces |
|---|---|---|
| 1 — mechanical | anchor vs. the last **production-code** commit; lists changed covered paths, and changed paths claimed by no document | data |
| 2 — agent, scoped to that delta | "does this delta invalidate a statement in these documents?" | the severity |

This mirrors the pipeline `/cross-check` already uses (mechanical source check → rule evaluation →
severity) and defuses the base-rate problem at its root: the event that fires constantly — staleness —
never reaches the user as a verdict, while the rare event, an invalidated claim, does.

Severity keys off the document lifecycle, which already exists and is already script-maintained:

| `status` | Severity | Reasoning |
|---|---|---|
| `living` | info | movement is expected during a sprint |
| `active` | warning + work item | the normal case |
| `frozen` | error | the code moved under a document declared final — the one case where "nothing moved" is genuinely supposed to hold |

The release-baseline cut is the second blocking point, for the same reason.

### 5. Escalation goes through the work-item contract

A drift finding is recorded via the contract from ADR-0002 with the `local` backend as default: a
`create` plus a tag. **No contract change.** The typed links of ADR-0008 are the wrong shape — they
relate item to item, and a drift state has no item on the other end. The work-item store is the right
home for the *finding*; it is never the home for the *anchor*.

### 6. Acknowledgement is a dedicated verb that shows the delta first

Detection without a clearance path is not a mechanism but a ritual. Re-anchoring is therefore its own
operation and **never a side effect of another command** — the single highest-risk detail in the whole
design, because a skill that silently refreshes an anchor while doing something else kills the signal
without anyone noticing.

```
$ anchor ack docs/architecture/AUTH.md

  Anchor  a3f9c21  (18.08.2026)
  HEAD    b7e1004  (20.08.2026)

  Changed covered paths (3): …

  Does the document's claim still hold?  [asserted/updated/abort]
  Reason: _
```

It writes five flat keys beside the anchor:

```yaml
anchor_commit: b7e1004
anchor_date: 20.08.2026
anchor_ack: asserted            # asserted = reviewed, nothing changed
anchor_ack_from: a3f9c21        # updated  = documentation brought in line
anchor_ack_note: refactor touched only internals, no API change
```

The two clearance kinds are kept apart deliberately: `asserted` is a human assertion, `updated` is
evidence. Collapsing them into one field would destroy the ability to ask later *which anchors rest on
nothing but an assertion* — different grades of evidence do not share a field.

The acknowledgement's **scope is declared structurally**: because anchors sit at scope level by
default, the location of the acknowledgement states its reach. An acknowledgement on a scope index is a
bulk acknowledgement and is visible as one; an acknowledgement on a `covers:`-carrying document is not.

Agents are kept out **two-tier**, since this harness offers no hard technical boundary: prevention
through an explicit clause in the skill prompt and in subagent briefings ("never run `anchor ack`
yourself — report the delta, let the user decide"), and detection through statistics emitted by **every**
check run, not by a separate call:

```
anchor status → 42 anchored · 7 asserted without doc change · 3 stale
```

A rising count of assertions without documentation changes is the early warning that the mechanism has
turned into ceremony. A clause on its own would be self-report without a counter-check, which this
project's evidence discipline rejects.

### 7. Where it runs: local by default, CI optional

A local skill is the normal path. A CI workflow ships **dormant**, with an activation note, following
the two-tier preventive/detective split this project already uses elsewhere. The shipped artifact names
no forge and requires no hosted service, so the distribution Inviolable holds. Deployment specifics
belong in a personal, non-distributed config file.

### 8. Two preconditions

Both are small, both are independently useful, and the design leans on both:

1. The `status` enum is enforced by `phase-docs-lint.sh` and existing invalid values are corrected —
   the severity model is only as trustworthy as the field it reads.
2. `covers:` path-existence checking lands with the first `covers:` entry, not later.

## Consequences

**Positive.** The mechanism invents almost nothing: the freeze event, the `status` field, the
two-stage delta pattern, the work-item store and the lint hooks all exist. Anchoring at the Gate-Go
freeze answers "who refreshes it, and when?" with an already-wired scripted event rather than with
discipline — freezing a document and recording what the code looked like when we stopped reading it are
the same moment. R6's unmet promise of checking against "Implementation" becomes redeemable.

**Negative.** One more term in a framework that already has many. Two new frontmatter keys plus three
acknowledgement keys on documents that opt in. The linter grows a path-existence check whose cost is
proportional to the number of `covers:` entries. And the acknowledgement path depends on a clause plus
a statistic rather than on an enforceable boundary — an honest limitation, stated rather than papered
over.

**Migration.** The anchor field is **optional**. No existing project artifact becomes invalid, no
command template has to change, and adoption is per document and per scope. This is deliberately the
migration path this repository's own Inviolable would require if the field were ever made mandatory —
"not verified" is a first-class state precisely so that the unmigrated majority is neither pass nor
fail.

## Alternatives considered

**Merge into the existing release-baseline mechanism.** Rejected: that file is skipped by both linters,
only exists after the release gate, and its documented purpose is to make agents stop reading. Adding a
release commit hash to it remains a sensible small fix on its own merits, and is explicitly not part of
this decision.

**One anchor per document.** Rejected on measured cost: 226 documents in the larger reference project
plus every command template that authors a phase block, which is a skill-interface change requiring its
own migration — for a resolution gain that only matters on a handful of documents.

**Blocking on drift.** Rejected: no command consumes an exit code, so it is either cosmetic or the most
expensive item in the design, and it would stop work on the third of commits that touch documentation
only.

**Warning only, single-stage.** Rejected: it reproduces the failure this ADR is written against — a
message nobody reads — for the same base-rate reason.

**Tracked condition IDs.** Rejected: the mechanism does not exist and would have to be built first.

**A separate state file.** Rejected as a *second* register alongside the documents. If it were ever
chosen, it would have to be the **sole** register, with no hash in the documents at all — a hash in two
places is the drift this feature detects.

**Querying a forge's REST API for the repository state.** Rejected: it makes a hosted service a
prerequisite, which the distribution Inviolable forbids. A local git comparison needs no network, no
token and no vendor.

## Follow-ups

1. **Structural scope coverage needs re-testing.** The acknowledgement's reach is guaranteed by where
   it is written rather than by a stored field — invisible in the record. Re-examine once real
   acknowledgements exist.
2. **Git edge cases are unexercised:** shallow clones, detached HEAD, submodules, missing refs, dirty
   trees. The largest remaining implementation risk.
3. **Separate documentation and code repositories.** Both reference projects keep them together, so
   this ships for the same-repo case; the anchor records repository identity so the split case can be
   added later without a schema break. There is no vendor-neutral mechanism for it yet.
4. ~~**Acknowledgement authority with more than one maintainer** is undefined.~~ **Resolved in
   Addendum 3 (21.08.2026): record the actor, do not restrict them.** Kept in this list, struck
   through rather than deleted, because the open wording outlived its answer by six days and was
   read as still-open on 27.08.2026 by someone working from this list — a reader who skims the
   follow-ups as a work queue never reaches the addendum that closes one.
5. **`covers:` decay under a refactoring-heavy working style** is unmeasured; ~~the observed rate comes
   from two projects with stable paths.~~ **Premise superseded in A5 (21.08.2026): measured across
   three projects, not two — 15 renames and 57 deletions for project B alone, roughly five times the
   rate recorded above, with project A at 0/0 and project C at 3/3.** The question itself stays open;
   only its stated basis was stale.

---

## Addendum (21.08.2026): what the measurement changed before the first line of code

### Context

This ADR was written on 18.08.2026 from measurements taken on two CCPR-driven projects. Before
implementing it, both preconditions and the mechanism itself were re-measured — this time against
**three** projects, and against the shipped scripts rather than against their descriptions. Project A
(mid-sized) and project B (large, actively developed) are the two already cited above; project C is a
third CCPR-driven project, comparable to B in documentation volume but with a small, sharply layered
code tree.

Nine statements did not survive that pass. Six of them are in this ADR or in the two precondition
items; three are gaps nobody had recorded. They are listed here rather than silently corrected in
place, because the precondition items were written against the original wording and an implementer
reading only the body would build the wrong thing.

### A1 — The `status` enum is already enforced, hard

Precondition 1 states that the linter "validates the field today but does not reject unknown values
hard enough to have prevented this". It does. Check (d) in `phase-docs-lint.sh` raises an **error**
and the script exits 2. Run against project B today it reports four such errors, and has been doing so
unnoticed.

The drift therefore survives for two entirely different reasons, and only these two matter for the
work:

1. **Scan scope.** ~~`PHASE_FOLDERS` names eight directories. Review reports live outside them and are
   never read, which is where **six of the ten** invalid values sit.~~ **True when measured, and
   made false by the change it caused:** `f6cdbe1` (21.08.2026, WI-0019) added `reviews` to
   `PHASE_FOLDERS`, which now names **nine** directories, and review reports are read. The
   measurement is kept as the reason the ninth folder exists; only its present tense was stale.
2. **Nothing consumes the exit code** — already recorded in this ADR's context as the fourth
   constraint, but not connected to precondition 1 when it was written. An enforced enum whose verdict
   nobody reads enforces nothing.

Consequence: precondition 1 is still required, but the work is scope plus correction, not stricter
validation.

### A2 — The enum has six values, not five

Both this ADR's precondition and the source measurement quote the schema as
`{skeleton, draft, active, frozen, archived}`. The schema and the linter both carry a sixth value,
`living`, with its own documented meaning. The five-value list appears in the project `CLAUDE.md` and
in the shipped project-CLAUDE template — **that** is the drifting statement, not the schema.

This matters for the severity table above: its `living` row is sound, because `living` is a real,
schema-valid status. Left uncorrected, an implementer reading the short list would conclude the
severity table keys off an invalid value.

Three further off-schema values were found that the original measurement missed: `superseded` and
`superseded-within` (both in memory files, which follow a different schema and are out of scope here)
and one more `final` in project C.

### A3 — The frozen share is not one number, and the spread inverts the argument

Measured share of phase documents at `status: frozen`:

| | Project A | Project B | Project C |
|---|---|---|---|
| frozen | **90 %** | 12 % | 6 % |

This ADR argues from the 12 % figure that "a blocking carve-out limited to frozen documents covers
very little of a live project". That holds for two of the three projects and is **inverted** in the
third, where nearly every phase document is frozen and therefore nearly every drift finding would be
error-grade. The severity model is not wrong, but its practical effect is a property of the project,
not of the design. An implementation must not assume the 12 % regime.

### A4 — `covers:` is not an extension of the `related:` check

Precondition 2 calls the path-existence check "an extension of an existing check rather than a new
mechanism". Two differences make it a new one:

- `related:` resolves against the **document's own directory**; `covers:` entries are code paths from
  the **repository root**. Different base.
- `related:` tests with a file predicate. `covers:` entries are typically **directories**, for which a
  file test always fails. It also needs a decision on whether a directory that exists but is empty
  counts as covered.

And the base question is already live for `related:` itself: in project B, `related:` entries are
written repository-root-relative in review documents while the linter resolves them
document-relative, producing **13 findings against files that exist**. The two keys must be decided
together — one answer, two keys — which is why this is now tracked as its own item alongside
precondition 2.

### A5 — The `covers:` decay rate is understated by roughly a factor of five

This ADR records "1 rename and 9 deletions across 2080 commits" for project B. Measured across that
project's actual code directories over its full history: **15 renames and 57 deletions**. Project A
shows 0/0 and project C 3/3, so the spread between projects is larger than the spread this ADR
assumed between "slow but real" and "useless".

The direction of the correction favours the design — path-existence checking earns its place as a
precondition more clearly than before — but it also raises the upkeep cost of `covers:`, which is the
side of the trade-off the granularity decision leaned on.

### A6 — The anchor already exists, under other names, written by CCPR itself

`/p4-sprint` writes `base_commit: <sha>` into sprint frontmatter. `/p5-review-sprint` reads it and
records `reviewed_head`. `/gate-p5` compares `reviewed_head` against the current `HEAD` and re-runs
the review when they differ. That is a recorded SHA on a phase document, spanning a delta, used as a
staleness detector — the same mechanism this ADR proposes, already shipped and already in the field:
**26 documents in project B, 8 in project C**, across roughly ten spellings
(`base_commit`, `reviewed_head`, `reviewed_base`, `commits`, `scope_commits`, and several one-off
pass-specific variants), none of them validated.

This is precisely the unvalidated-key rot pattern precondition 2 cites as its warning example — and
CCPR generates it. Placing `anchor_commit` beside it without further action would make the new key the
next unvalidated spelling.

**Decision:** `anchor_commit` stays as a distinct key — a sprint base and a freeze point are different
moments and conflating them would break the sprint review — **and** the linter validates the existing
family (`base_commit`, `reviewed_head`, `reviewed_base`) for SHA form and resolvability whenever the
key is present. The new key ships together with validation of the old ones, or the second-register
objection this ADR raises elsewhere applies to its own field.

### A7 — The freeze event cannot write a scope-level anchor

This ADR anchors the mechanism at the Gate-Go freeze and makes the scope index the carrier of a bulk
acknowledgement. `freeze-phase-docs.sh` **explicitly skips every phase index and sub-index** — by name
list and by a `## Detail Files` heading — so that they stay active for cross-phase updates. The freeze
hook therefore never touches the document the design puts the scope anchor on.

Two further limits of the same hook: it is a no-op for P5 and P8, and it runs only on a Go verdict. In
the two projects with a 6–12 % frozen share, most documents would never receive an anchor through this
path.

Open for the implementation wave, and it is a design question rather than an implementation detail:
either the anchor is written on the frozen detail documents (per-document granularity, which this ADR
rejected on cost) or the scope anchor needs a second, deliberate write path onto the index.

### A8 — The existing frontmatter writer is not portable

`freeze-phase-docs.sh` edits in place with a BSD-only `sed -i ''` invocation. The acknowledgement verb
writes five keys and must not copy that pattern; a shipped framework cannot assume the maintainer's
platform.

### A9 — "The last production-code commit" has no definition and no implementation

The two-stage check compares the anchor against the last production-code commit rather than `HEAD`,
which is what defuses the documentation-only base rate. Nothing in the repository classifies a path as
production code or not, and the three reference projects have three unrelated code trees. This needs a
per-project, configurable path classification with a documented default, and it belongs in the first
implementation sub-wave rather than being discovered inside it.

**Resolved in Addendum 2's "The comparison point, measured" (21.08.2026), refined by Addendum 4
(27.08.2026): the default is an EXCLUSION** — a commit is production code if it touches at least one
path that is neither under `docs/` nor `.claude/` nor a Markdown file — configurable per project, and
it did land in the first implementation sub-wave as this entry asked. Recorded here rather than
deleted: the answer lives in an addendum whose heading names only A7, so a reader working down this
list never reaches it (WI-0127).

### Consequences for the preconditions

Both preconditions stand. Their content changes:

- **Precondition 1** becomes: introduce per-directory check profiles so review reports can be scanned
  for the status enum **only**, correct the invalid values, and re-measure the frozen share.
  Backwards compatibility is binding and is a **measurement**, not an assurance: no project may move
  from a clean exit to a failing one except through the invalid values being sought.
- **Precondition 2** becomes: the `covers:` check with root-relative resolution and directory support,
  decided together with the `related:` base question, and shipped alongside validation of the existing
  commit-anchor family (A6).

Two items are added: the frontmatter path-base defect (A4) and a schema plus migration script for
review reports, which are a genre of their own and were never phase documents — that item also owns
the commit-anchor family, since the family lives there.

Nothing in the decision itself is withdrawn. The anchor, the granularity, the two-stage shape, the
severity model and the acknowledgement verb all stand as decided; A7 is the one open design question
the implementation must close before it writes an anchor anywhere.

---

## Addendum 2 (21.08.2026): A7 resolved — where the scope anchor lives

A7 in the first addendum named the one open design question: the ADR anchors at the Gate-Go freeze
and makes the scope index the carrier of the bulk acknowledgement, while `freeze-phase-docs.sh`
skips every phase index and sub-index by design. Decided now, because everything downstream depends
on it.

### Decision

**The scope anchor lives on the phase index. Severity comes from each document's own `status`.**

- `freeze-phase-docs.sh` gains a **second, deliberate write path** that targets the phase index it
  otherwise skips, writing `anchor_commit` and `anchor_date` there after the detail files of that
  phase have been frozen. The existing skip stays — the index's `status` is still not touched.
- Every document under that scope **inherits** the index's anchor.
- A document may carry its **own** `anchor_commit`, opt-in, typically alongside `covers:`. Resolution
  is: the document's own anchor if present, otherwise its phase index's. No third tier — sub-indexes
  are documents like any other and opt in the same way.
- **Severity reads the document's own `status`,** never the index's: `living` info, `active` warning
  plus a work item, `frozen` error. The severity table above is unchanged; what is now settled is
  *which* document's status it reads.

### Why not the alternative

Writing the anchor onto each frozen detail file was the cheaper build — the freeze already writes
`status:` into exactly those files, so it is one more line in an existing write, and the ADR's
cost objection to per-document granularity (226 documents) was about **hand** maintenance, which does
not apply to a machine-written field.

It fails on coverage. The freeze runs only on a Go verdict and is a no-op for P5 and P8, and the
frozen share is 12 %, 6 % and 90 % across the three reference projects. In two of the three, the large
majority of documents would never receive an anchor at all. With the anchor on the index, **one gate
pass per phase produces one anchor for the whole scope**, regardless of how few detail files happened
to be in a freezable state. The coverage problem named in A7 is solved by the same decision that
resolves A7's conflict, rather than being carried forward.

It also removes the bulk acknowledgement, which requirement 4 of the acknowledgement design meets
*structurally* — an ack on a scope index is a bulk ack because of where it is written. Per-document
anchors leave that requirement with nothing to stand on.

### Three measurements that shaped it

**The index's `status` is not machine-guaranteed, so severity must not read it.** In one reference
project all five phase indexes carry `status: frozen`, even though `freeze-phase-docs.sh` skips them
by name — they were frozen some other way, by hand or by an earlier version. Had severity keyed off
the index, that project would treat every drift finding in every scope as error-grade, and the two
other projects — whose indexes are `active` — would never produce an error at all. Reading the
document's own status makes the model independent of a field nothing maintains.

**An index may not exist.** `quality/QA.md` is absent in two of the three projects while
`docs/quality/` exists and holds documents. A scope with no index has nowhere to carry an anchor, and
that resolves to the ADR's own first-class state: **"not verified"** — neither pass nor fail. It must
not be an error, and it must not be silence either; the check reports the scope as unanchored.

**The phase-index naming convention holds where the index exists.** `DISCOVERY.md`, `CONCEPT.md`,
`VALIDATION.md`, `ARCHITECTURE.md` and `PROJECT_PLAN.md` are present under their respective folders in
all three projects. So the index can be resolved by convention rather than by a new registry — which
matters, because a registry would be the second register this ADR rejects elsewhere.

### The comparison point, measured

Stage 1 compares the anchor against the last **production-code** commit rather than `HEAD`. That
commit needs a definition, and the repository had none. The default is an **exclusion**: a commit is
production-code if it touches at least one path that is neither under `docs/` nor `.claude/` nor a
Markdown file. Defining what is *not* code travels between projects; enumerating what *is* code does
not — the three reference projects have three unrelated code trees (`cmd/ internal/ frontend/`,
`src/ alembic/`, `src/ poc/ tools/`).

Measured against all three, the default lands on a real code commit 1, 2 and 6 commits behind `HEAD`
respectively — which is precisely the documentation-only base rate this design exists to defuse. The
exclusion list is configurable per project; the default is what ships.

---

## Addendum 3 (21.08.2026): Acknowledgement authority — attribution, not restriction

Follow-up 4 asked what acknowledgement authority means with more than one maintainer. Answered here
rather than left open, because it is a decision and would not have resolved itself through use.

### The distinction the question hides

Two questions get conflated under "authority":

- **Attribution** — *who made this assertion?*
- **Restriction** — *who is allowed to make it?*

This framework has no server, no authentication and no enforcement point. Restriction can therefore
only ever be a convention, and a check that looks like enforcement without being it is precisely what
this ADR rejects elsewhere when it refuses to claim a boundary for agents that does not exist. The
same standard applies here. Attribution, on the other hand, is reachable.

### Decision

**Record the actor. Do not restrict them.**

A sixth flat key joins the acknowledgement group:

```yaml
anchor_ack_by: name <email>
```

Filled automatically at `ack` time from the repository's git identity, overridable with `--by`. When
no identity is configurable — a CI job, a fresh container — the field records that plainly rather than
being omitted, because a missing field and an unattributable acknowledgement must not look alike.

**Identity is taken from `user.email` first.** That is not a detail: in the larger reference project
two people appear under five names (`olarttro`, `Jonas`, `jonas`, `Oliver Trossen`, `god`) while their
addresses are stable. Keying on the display name would have recorded the drift instead of the person.
The name travels with the address for readability, in the same `name <email>` form git already writes
into every commit touching the file.

**And the statistic learns to count by actor.** Where more than one actor appears, `anchor status`
breaks its acknowledgement line down:

```
42 anchored · 7 asserted without doc change · 3 stale
   asserted by: a@example.org (6), b@example.org (1)
```

That is the whole authority model, and it is deliberate. The design's guard against acknowledgement
becoming ceremony was always the statistic, not a permission; making it actor-aware is what carries
that guard into a team. A single person's assertions dominating the count is visible without anyone
having had to declare who was entitled to make them.

### Why not a configured authority list

An `anchor.ackAuthority` list in project configuration was considered and rejected on this project's
own terms. It is bypassable by editing the file it lives in, so it stops an accident and nothing else
— while *reading* as a control. It also adds a second register that has to be maintained, and drifts
the moment someone joins. If a team wants a rule about who acknowledges, that rule belongs in the
team's working agreement, where it is honestly a convention, and the per-actor statistic is what makes
adherence visible.

### Why git blame is not sufficient

Requirement 7 of the acknowledgement design already stores acknowledgements durably and diffably in
frontmatter, so `git log -p` on the document shows the change. That is not the same as knowing who
acknowledged. An `ack` produces a working-tree change; the commit that carries it may be made by
someone else, later, bundled with unrelated work — a pattern this project produces routinely, since
delegated work is committed by whoever is orchestrating. The committer is evidence about the commit,
not about the assertion.

### Consequence

One more flat key on documents that carry an acknowledgement, and one more line in the status report
when a project has more than one acknowledging actor. No schema break: the field appears only where an
acknowledgement exists, and an acknowledgement written before this addendum simply has no actor
recorded — which the statistic reports as unattributed rather than silently folding into someone's
count.

---

## Addendum 4 (27.08.2026): The comparison point, measured again — repo/editor hygiene is not code

The default classification in "The comparison point, measured" excludes `docs/`, `.claude/` and
`*.md`. Everything else counts as production code, including a file that changes nothing about the
system that runs.

### The measurement

Two of the three reference projects hit this the same week, independently:

- consumer-c's reported last production-code commit was a `chore(claude): stop tracking the
  machine-local permission allowlist` commit that also touched seven lines of `.gitignore`. The real
  last code change was 14 days earlier.
- consumer-b's reported last production-code commit was `chore(gitignore): catch every .env variant,
  not only the expected ones` — one file, five added lines, nothing else. The real last code change
  was 8 days earlier.

What matters is not how often a hygiene-only commit occurs, but how often it is the *newest* commit —
because that is the one Stage 1 compares every anchor against. The answer, measured on the same day
across the three reference projects, was two out of three.

### The criterion

Not "exclude every dotfile at the repository root" — the original "comparison point, measured" section
already rejected that direction: `.dockerignore` and `Dockerfile` land together in a real consumer-c
commit (`fe94c16`), and a rule that swept dotfiles wholesale would trade the too-recent-comparison-point
problem for the opposite, worse one — a comparison point that is too OLD, which silently under-reports
drift instead of over-reporting it.

The line drawn instead, one question, decided by the PO 27.08.2026:

> **Does this file describe the system that runs, or only how the repository or the editor is
> handled?**

A file that only tells git or an editor how to behave is hygiene, not code, regardless of where in the
tree it sits or how often it changes. A file that shapes what ships, what the runtime needs, or how the
system is configured is code, even though it is neither source nor a build artifact itself.

**Excluded (joins the shipped default's `EXCLUDE_SUFFIXES`):**

| File | Why it answers "only how the repo/editor is handled" |
|---|---|
| `.gitignore` | Tells git which paths not to track. No effect on anything that runs. |
| `.gitattributes` | Tells git how to diff/merge/checkout paths (line endings, filters). Same category. |
| `.editorconfig` | Tells editors indentation/charset conventions. Advisory to a tool, not to the runtime. |
| `.prettierignore` | Tells a formatter which paths to skip. Governs a dev-time tool, not the shipped system. |

**Deliberately NOT excluded** — each is a real counter-example to "root-level dotfile ⇒ hygiene", kept
production-relevant on purpose:

| File | Why it answers "the system that runs" |
|---|---|
| `.dockerignore` | Determines what goes into the image that ships. A change here changes the artifact. |
| `.env.example` | Declares which configuration the system requires to run. Documents the runtime contract. |
| `.nvmrc` / `.tool-versions` | Pin the runtime version the system executes under. A bump is a real change to what runs it. |

`.env*` needed no rule: across all four repositories measured (the three reference projects plus this
one), no real `.env` file is tracked anywhere. A tracked `.env` would be a secrets finding for
`security-master`, not a classification question for this ADR. Machine-local files are already covered
by the existing `.claude/` prefix exclusion and needed no new entry.

### Why the shipped default, not a per-project exclusion

`anchor.excludePaths` (`.claude/settings.json`) exists precisely for project-specific hygiene calls —
`tests/` is the example already in this document, because whether it counts as code is genuinely
project-dependent. `.gitignore` and its three siblings are not project-dependent: they exist in every
project this framework targets and are production-relevant in none of them. Leaving the exclusion
per-project means every adopter discovers the same misleading measurement once, independently, the way
two of the three reference projects just did on the same day. A shipped default closes it for everyone
at once.

This also means the boundary drawn here cannot be walked back by a project: `load_exclude_config`
*extends* `EXCLUDE_PREFIXES`/`EXCLUDE_SUFFIXES` rather than replacing them (Addendum "the comparison
point, measured", and enforced in `scripts/anchor.sh`'s own header comment) — a project can add
exclusions but not remove the shipped ones. That additive-only semantics is why the four names above are
argued individually rather than assumed: once shipped, no project gets to disagree file-by-file, only
the framework's next ADR revision does.

### Consequence

`EXCLUDE_SUFFIXES` in `scripts/anchor.sh` gains `.gitignore`, `.gitattributes`, `.editorconfig`,
`.prettierignore` alongside `.md`. Re-measured: consumer-c's reported last production-code commit moves
from the `.gitignore`-touching chore to the real last code commit 14 days earlier; consumer-b's moves
similarly, 8 days earlier. The third reference project (`consumer-a`) is unaffected — zero
hygiene-only commits in its last 110.

The next candidate for this list is decided by the same question, not by resemblance to the four names
already here — a file "looking like tool config" is not the test; whether it changes the system that
runs is.
