---
kind: adr
adr_id: ADR-0005
status: proposed
last_updated: 08.07.2026
related:
  - ADR-0002-workitem-backend-contract.md
  - ADR-0003-youtrack-backend.md
  - ../CONSTITUTION.md
---

# ADR-0005: Claiming and the branch-runner protocol

**Status:** Proposed (08.07.2026)
**Decision-makers:** Repo owner (Jonas), early tester (Olli, @OlArtTro)

## Context

ADR-0002 makes claiming **mandatory for remote backends** and a **no-op for `local`**, and defers the
protocol to here. ADR-0003 exposes the hooks a backend needs (set assignee, set state, read/write a
runner tag).

In a team, several **runners** — humans, and AI agents on different machines — may work the same
project at once. Two problems arise that a solo developer never has:

1. **Collision** — two runners must not silently work the same item.
2. **Abandonment** — a runner can die mid-item (crash, closed laptop, killed session). Its item must
   not be stuck "In Progress" forever; the started work must be **resumable**, not lost.

Runners are **dispatched manually** (there is no auto-scheduler). So the protocol needs **visibility**
(who is working what) and **abandonment detection**, not a hard transactional lock — which backends
cannot all guarantee anyway.

## Decision

### Owner vs. runner

- **Owner** = the responsible human (the `Assignee`, ADR-0003). Stable.
- **Runner** = the process actively executing the item *right now* — a machine/agent identity
  (`runner:<id>`; ids come from the machine register, ADR-0007).

They are distinct: an item **owned** by a human is often **executed** by an agent. Conflating them
would lose the abandonment signal.

### Claiming

To work an item, a runner **claims** it:
1. status → `In Progress`,
2. set the `runner:<id>` signal + start a **heartbeat**,
3. work on a `ticket/<id>` branch.

Claiming is **mandatory for remote backends** and a **no-op for `local`** (a solo developer with local
files has nothing to lock).

### Branches

- **One `ticket/<id>` branch per claimed item**; runners push directly to the remote.
- **`main` is protected / PR-only.** Completion is a PR (`Waiting for Approval` → review → merge →
  `Done`).
- This gives isolation, a resumable line of work, and a visible "has commits" signal.

### Heartbeat and `Parked`

- The runner **refreshes a liveness signal** (the `runner:<id>` tag + a heartbeat timestamp) at a
  configurable interval (`workitems.claiming.heartbeatInterval`).
- If an `In Progress` item's heartbeat goes **stale** (no refresh within `workitems.claiming.staleAfter`)
  **and** its `ticket/<id>` branch has commits, the item transitions to **`Parked`**: work exists, no
  live runner, resumable.
- `Parked` ≠ `Blocked` (an external dependency) ≠ `In Progress` (a live runner).
- The transition is performed by the backend's liveness mechanism — a tracker-side workflow **or** a
  CCPR-side sweep command; the protocol defines the **signals and the rule**, the backend supplies the
  mechanism.

### Resuming

Any runner may **resume** a `Parked` item: re-claim it (`In Progress` + its own `runner:<id>`) and
continue on the existing `ticket/<id>` branch. No work is thrown away.

### Visibility over locking

Because runners are dispatched manually, the protocol relies on **visible signals** (runner tag +
branch + state) that make a collision *detectable and resolvable*, not on a hard lock. Manual dispatch
avoids most races; the signals catch the rest.

### Constitution rule

**Claiming is mandatory for every remote backend and a no-op for `local`.** This is proposed as a
**Constitution rule** (the same class of boundary as CCPR's other Inviolables — it protects the
integrity of shared team state). A remote backend that cannot express the claim signals does not
satisfy the contract.

## Consequences

- **No stuck or lost work:** an abandoned claim becomes `Parked` and is resumable from its branch.
- **Ownership and execution are cleanly separated** (human owner vs. runner), which is what makes
  abandonment detectable.
- **Solo is unaffected:** claiming is a no-op on `local`; no branches, no heartbeat, no server.
- Backends implement the liveness signals; the protocol is the shared contract they honour.

## Alternatives considered

- **Hard transactional locking:** rejected — not all backends support atomic compare-and-set; manual
  dispatch + visible signals are sufficient and portable.
- **No heartbeat** (a claim holds until manually released): rejected — a dead runner would strand its
  item indefinitely.
- **A single field for owner and runner:** rejected — an item owned by a human is routinely executed
  by an agent; merging the two loses the abandonment signal and the resume path.

## Notes

A concrete heartbeat implementation exists as a private tracker-side workflow; it is one mechanism for
the signals defined here, not part of this generic protocol. Runner identities and the machine
register are specified in ADR-0007.
