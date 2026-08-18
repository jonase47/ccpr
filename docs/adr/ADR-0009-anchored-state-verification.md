---
kind: adr
adr_id: ADR-0009
status: proposed
last_updated: 18.08.2026
related:
  - ADR-0002-workitem-backend-contract.md
  - ADR-0008-typed-workitem-links.md
  - ../../templates/PHASE_DOC_SCHEMA.md
---

# ADR-0009: Anchored state verification for phase documents

**Status:** Proposed (18.08.2026)
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
phase: 3
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
4. **Acknowledgement authority with more than one maintainer** is undefined.
5. **`covers:` decay under a refactoring-heavy working style** is unmeasured; the observed rate comes
   from two projects with stable paths.
