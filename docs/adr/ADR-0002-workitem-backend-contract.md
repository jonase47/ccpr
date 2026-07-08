---
kind: adr
adr_id: ADR-0002
status: proposed
last_updated: 08.07.2026
related:
  - ../CONSTITUTION.md
  - ADR-0001-versioning-and-distribution.md
  - ../../CHANGELOG.md
---

# ADR-0002: Work-Item Backend Contract (backend-neutral work state)

**Status:** Proposed (08.07.2026)
**Decision-makers:** Repo owner (Jonas), early tester (Olli, @OlArtTro)

## Context

Today CCPR's work state lives in `BACKLOG.md`, `SPRINT.md`, and `HANDOVER.md` — prose Markdown files
read and written **directly** by 50+ commands and agents. That works for a solo developer with a
single machine, but two forces pull beyond it:

1. **Team use.** When two or more people (and, later, AI runners) work the same project, the work
   state has to be **shared state between parallel CCPR instances** — who has claimed what, what is in
   progress, what is done — not a file each person edits and merges.
2. **Solo-dev must stay first-class.** A freshly cloned CCPR must keep working with no server, no
   tokens, no setup. The entry bar of the public framework must not rise.

The current files are not a per-item store. Answering "what is the status of item X?" or "set item X
to *In Progress*" means parsing prose — and prose is unreliable in both directions (status hides in
narrative and parenthetical suffixes, ID namespaces collide, a "done" marker can be contradicted by
the code). Building the team/runner workflow on top of prose parsing would bake that fragility in.

We need **one abstraction that works with or without a ticket system**, with the local file mode as
the default and first-class path.

## Decision

CCPR gains a **backend-neutral work-item contract**. The core speaks only to the contract; where the
items physically live is the configured backend's concern.

### The contract

Six operations, nothing tool-specific:

| Operation | Meaning |
|---|---|
| `create(fields)` | create a new item; the **backend assigns** a stable `id` (callers never supply one) |
| `list` | enumerate work items (optionally filtered by status/owner) |
| `get(id)` | fetch one item |
| `claim(id)` | take ownership / mark active (see Claiming) |
| `set-status(id, status)` | move an item through its lifecycle |
| `append-result(id, result)` | attach a result reference (e.g. a PR/commit link) |

`create` is the single-item path (a planning command creating one item); `lift` (ADR-0004) is the
bulk path. The backend owns id assignment — `local` hands out the next monotonic `WI-NNNN`, a remote
backend returns the tracker's id.

**Core model (minimal, backend-neutral):** `id, title, status, description, result-link, owner`
(`result-link` **accumulates** — `append-result` adds refs, so an item can carry several PR/commit
links). Every backend must map exactly these. Backends may expose richer fields (milestones, cycles, links),
but **the CCPR core never relies on backend-specific fields** — that is what prevents a tool-lock-in
from creeping into the public framework.

**Status vocabulary:** `Backlog → Ready → In Progress → Parked → Waiting for Approval → Done`, with
`Blocked` and `Cancelled` crosscutting. Backends map their own states onto this set.

### Provider selection

`settings.json` carries `workitems.provider` (default: `local`). Remote-backend credentials come
**exclusively from environment variables, never from the repo**.

### Backends are helper scripts; commands call the helpers

Each backend is a helper (script) implementing the contract. Commands and agents call the helper —
they **stop reading the Markdown files directly**. `local` is both the **reference implementation**
and the **test fixture**: every contributed backend runs against the same contract tests.

### The `local` backend format

A **structured store**, not the old prose files: one file per item at `docs/workitems/<id>.md`, with
typed frontmatter (`id, status, owner, type, refs, …`) and a body (description + acceptance criteria).
This is the "formal local format". It is git-diff-friendly per item and symmetric with structured
remote backends.

`BACKLOG.md` / `SPRINT.md` become **human-facing planning views** over the items (roadmap narrative);
`HANDOVER.md` shrinks to narrative + item references. Existing projects reach the structured format by
running `ccpr workitems lift` once (ADR-0004) — the format formalises, the workflow stays all-local.

### No bidirectional sync

Exactly **one active backend (source of truth) per project**. Moving solo→team is a **one-time
migration** (`ccpr workitems migrate`, ADR-0004), not a continuous sync — continuous sync would create
merge conflicts in a new dimension.

### Claiming

Claiming is **mandatory for remote backends** (a team needs to know who holds an item) and a **no-op
for `local`** (a solo developer with local files has nothing to lock). The full protocol —
`Parked` state, `ticket/<id>` branches, runner heartbeat — is deferred to ADR-0005.

### Write-loop: workflow-driven, hook safety-net

The contract operations (`claim` / `set-status` / `append-result`) are invoked **by the CCPR commands
at defined workflow transitions** — claim at implementation start, `set-status` at gates,
`append-result` (the PR link) at completion. Because CCPR *is* the workflow, the update happens
because the command runs it, not because an agent remembers to. A **hook** provides the safety net for
out-of-band events (a commit on a `ticket/<id>` branch, session end). Status stays accurate
**structurally, not by discipline** — this is the deliberate counter to work-state drift.

## Consequences

- **Solo-dev unchanged in spirit:** `local` is the default; no server, no token; still all-local
  Markdown. The file *format* formalises (structured items instead of prose), which existing projects
  adopt with a single `lift` run.
- **Breaking skill-interface change.** Per Constitution Inviolable #5, this needs an ADR + migration
  path; this ADR plus ADR-0004 (`lift` / `migrate`) provide it. The 50+ commands migrate to the
  contract **incrementally** — the old and new models coexist during the transition.
- **Backend symmetry.** Because `local` is a structured store like the remote backends, the contract
  is genuinely backend-neutral; there is no prose-vs-structured seam.
- **Roles shift:** `BACKLOG.md`/`SPRINT.md` become views, `HANDOVER.md` becomes narrative — documented
  in the Manual.
- **Testability.** New backends are validated against the `local` contract tests, so a contributed
  backend can't silently diverge from the contract.

## Alternatives considered

- **Reuse the prose files** (implement the contract by parsing `BACKLOG/SPRINT/HANDOVER`): rejected.
  Parsing prose on every operation bakes in the exact fragility this design exists to avoid, and it
  leaves the `local` backend asymmetric with structured remote backends.
- **Bidirectional sync** between local and a remote backend: rejected — merge conflicts in a new
  dimension; a one-time migration is enough for the solo→team transition.
- **Pure agent-convention** for status writes ("the agent updates status when it remembers"): rejected
  — manual discipline is the drift failure this design is meant to prevent.

## Follow-ups

- **ADR-0003** — the first remote backend (a self-hosted issue tracker, e.g. YouTrack): REST mapping,
  the state-set, owner/assignee, claiming.
- **ADR-0004** — `ccpr workitems lift` (heterogeneous ToDos → the local format; dry-run default,
  idempotent, original text preserved) and `migrate` (local → remote, with an id-mapping written into
  the repo).
- **ADR-0005** — the claiming / branch-runner protocol (`Parked`, `ticket/<id>`, heartbeat).
