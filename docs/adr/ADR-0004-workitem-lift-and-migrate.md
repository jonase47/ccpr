---
kind: adr
adr_id: ADR-0004
adr_status: proposed
status: draft
last_updated: 08.07.2026
related:
  - ADR-0002-workitem-backend-contract.md
  - ../../Manual/WORKITEMS.md
  - ../CONSTITUTION.md
---

# ADR-0004: `ccpr workitems lift` and `migrate`

**Status:** Proposed (08.07.2026)
**Decision-makers:** Repo owner (Jonas), early tester (Olli, @OlArtTro)

## Context

ADR-0002 introduces the structured work-item format and the backend contract. Two gaps remain before
projects can actually adopt it:

1. **Onboarding.** Existing projects carry heterogeneous, prose work state — scattered ToDos, a
   `BACKLOG.md`/`SPRINT.md`/`HANDOVER.md` narrative, sometimes findings registers with their own
   status columns. They need a ramp **into** the structured local format.
2. **Solo→team.** A project that grows from one developer to a team needs to move its items from the
   `local` backend to a remote one.

This is also the migration path ADR-0002 requires (a breaking skill-interface change needs an ADR +
migration path per Constitution Inviolable #5).

The hard, non-obvious lesson — from a real migration of a mature codebase into a tracker — is that
**the documented work state and the real state diverge, silently, in both directions.** A naive
importer that trusts prose status produces *ghost* items (long-done work imported as "open") and
*misses* hidden-done work. So `lift` cannot be a blind parse. The meta-rule is: **verify against
ground truth (the code / the VCS), never trust prose status.**

## Decision

Two tools, a pipeline: **`lift`** (heterogeneous → local format) then optionally **`migrate`**
(local → remote).

### `ccpr workitems lift`

Scans the existing work state and proposes normalized items in the local format
(`docs/workitems/<id>.md`). Its design constraints each answer a real failure mode observed in
practice:

| Constraint | The failure it prevents |
|---|---|
| **Dry-run by default** | writing ghosts before a human has confirmed |
| **Idempotent** (stable IDs, dedup) | re-running duplicates items |
| **Original preserved** (source archived, never destroyed) | losing rationale / rollback |
| **Verify claims against code/VCS, both directions** | "open" that is done; "done" with gaps |
| **Enumerate the full source set** | a register not read silently drops open (often high-severity) work |
| **Allow-list item-bearing ID namespaces** | most IDs are references (decisions, features), not items |
| **Exclusion list with reasons** | trade-offs / ops-notes / non-goals imported as tickets |
| **Report cross-source contradictions** | one source's "accepted trade-off" is another's "open finding" |
| **Deduplicate by behaviour described, not by ID** | the same fix under two IDs becomes two items |
| **Provenance (`source` anchor) on every item** | the lift is not auditable or re-runnable |
| **Confidence marker + defer to human** | inventing a status the source cannot settle |
| **Close as often as create** | a lift that only inserts reproduces every stale entry |
| **Parse its own emitted output before success** | a serialization that silently ships unparseable |
| **Severity re-derived or flagged `unverified`** | an unverified `High` misdirects priority |

Output (dry-run): the proposed item files **plus a report** — contradictions found, items marked
low-confidence for human decision, and the exclusion list with reasons. Writing happens only on
confirmation.

`lift` is deliberately **semi-automated, not blind**: high coverage where a claim is verifiable
against the code, explicit human decisions where it is not. That is the honest answer to work-state
drift, not a limitation.

### `ccpr workitems migrate <from>→<to>`

Moves items between backends (e.g. `local → youtrack`):

- Writes an **id-map** (`docs/workitems-idmap.yml`, `local-id ↔ remote-id`) so references in
  `HANDOVER.md` and learnings stay resolvable across the switch, and puts the source id in each remote
  item's description (reverse lookup / provenance).
- **Archives** the old store (never deletes) — this is the rollback path: **restore the archived
  store, then set `provider` back** and keep working (setting the provider alone is not enough — the
  source was moved aside, so it must be restored too; `migrate` prints the exact restore command).
- Leaves exactly **one active backend** afterward (no bidirectional sync — ADR-0002).

### The pipeline

`lift` (heterogeneous → local) → optionally `migrate` (local → remote). A project that runs only
`lift` is already migrated — onto the formal `local` backend, which is all a solo project needs.

## Consequences

- **Adoption ramp** for the public framework: existing projects (ours and external users') onboard to
  the structured model with a guided, dry-run, verify-first tool instead of a hand migration.
- **Fulfils the ADR-0002 migration-path requirement** for the breaking change.
- **`lift` keeps a human in the loop by design.** It surfaces contradictions and low-confidence items
  rather than guessing — the feature, not a gap.
- `migrate` makes the solo→team switch a single, reversible step.

## Alternatives considered

- **A fully-automatic importer** (parse ToDos → items, trust the status): rejected — trusting prose is
  the exact failure this tool exists to survive; it produces ghosts and misses hidden-done work.
- **Continuous local↔remote sync** instead of one-time `migrate`: rejected (ADR-0002) — merge
  conflicts in a new dimension; a reversible one-time migration is enough.
- **Deduplicate by ID**: rejected — the same work recurs under different IDs across sources; dedup must
  key on the behaviour described.

## Notes

The constraints above are distilled from a real migration of a mature, multi-source codebase; they are
"the patterns a naive lifter gets wrong". The reference implementation that surfaced them is
project-specific tooling kept in a private repo; the public `ccpr workitems` commands are built
generically from these constraints, not ported from that tooling.
