---
kind: adr
adr_id: ADR-0002
status: proposed
last_updated: 09.07.2026
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

**Status vocabulary:** `Backlog → Ready → In Progress → In Review → Waiting for Approval → Done`, with
`Parked`, `Blocked`, and `Cancelled` crosscutting. Backends map their own states onto this set. The two
gates are distinct states: `In Review` (code review pending) precedes `Waiting for Approval`
(acceptance pending).

### Provider selection

The project's `.claude/settings.json` carries `workitems.provider` (default: `local`; a
`.claude/settings.local.json` overrides it locally). Remote-backend credentials come
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

## Addendum (09.07.2026): Item-maintenance operations (`comment`, `set-description`, `set-title`, `set-type`)

### Context

The original six operations cover **creation and pass-through** (create → claim → set-status →
append-result) but not **maintenance of an item already in flight**. Two gaps surfaced from live
YouTrack usage:

1. `append-result` writes a marker-tagged comment (`<!-- ccpr:result -->`, ADR-0003) surfaced as
   `result-link`; there is no channel for a **plain human comment** (a correction, a note), and `get`
   silently drops every comment that isn't marker-tagged — human discussion on the issue is unreadable
   through the contract.
2. `description` is writable only at `create` time. A stale block inside it (e.g. an outdated
   `[conflict]` note) has no CLI path to fix — the only way out is editing the tracker by hand, which
   defeats the point of a backend-neutral contract.

The same one-shot-at-creation gap exists for `title` and `type`: both are set once, at creation, with
no maintenance path.

### Decision

Four new per-backend operations, on **both** backends (they share one contract fixture — see
"Backends are helper scripts" above):

| Operation | CLI | Meaning |
|---|---|---|
| `comment` | `workitems comment <id> <text>` | append a plain human comment — **no marker**, never surfaced as `result-link` |
| `set-description` | `workitems set-description <id> <text>` | replace the description in full (empty string clears it) |
| `set-title` | `workitems set-title <id> <text>` | replace the title (non-empty, same rule as `create`'s `title`) |
| `set-type` | `workitems set-type <id> <type>` | replace/set the `type` extension field (non-empty) |

**Core model extension:** `get`/`list` gain a `comments` field — `List[str]`, plain comment texts,
**disjoint from `result-link`** (a comment carrying the `append-result` marker is never duplicated into
`comments`, and vice versa; each backend's comment stream partitions cleanly into the two channels by
marker presence — see below).

#### `comment` vs. `append-result` — same channel, different marker

Both write to the same underlying comment stream on `youtrack` (`POST /api/issues/<id>/comments`). The
only difference is the machine marker (`<!-- ccpr:result -->`, unchanged from ADR-0003): `append-result`
prepends it, `comment` never does. `get` partitions by that marker — marked → `result-link`, unmarked →
`comments`. This is a hard **either/or** partition, never both: a marker comment is a machine-authored
result reference, not discussion, so it does not also appear in `comments`. On `local`, the two channels
are structurally separate from the start — a `## Comments` section in the item body, parallel to the
existing `## Result` section — so no marker/partition logic is needed there; `comment` appends to
`## Comments`, `append-result` keeps appending to `## Result`.

#### `comments[]` element form: plain strings, not `{text, author, created}`

`youtrack` comments carry `author`/`created` natively; `local` has no server identity to attach (no
login, no server-assigned timestamp). The **smallest common shape that round-trips cleanly on both** is
a bare list of comment text strings — the same shape `result-link` already uses. Adding
`author`/`created` today would mean `local` either fabricates values it doesn't have (a fake "local"
author, `None` timestamps a consumer must special-case) or the field becomes backend-conditionally
richer, which is exactly the "core model held to the least common denominator" principle this ADR
already applies to `result-link`. No CCPR command today consumes comment authorship or timing — extend
the shape when a real consumer needs it, not speculatively (YAGNI).

#### `set-type`: dedicated call fails hard; `create`'s best-effort stays as-is

`create`'s best-effort type-setting (ADR-0003 implementation notes: warn + continue on a YouTrack 400)
stays exactly as it is — unchanged by this addendum. A **dedicated** `set-type` call is a different
situation: the user (or a command) explicitly asked to set this one field, with nothing else committing
alongside it. There is:

- **no atomicity to protect** — unlike `create`, where the issue itself already exists and a rejected
  `Type` command must not fail the whole (already-committed) creation, `set-type` touches nothing else;
  a rejection has nothing to roll back and nothing else to protect,
- **no silent-degrade justification** — `create`'s best-effort exists because CCPR's own type vocabulary
  (`feat/fix/refactor/docs/chore`) routinely doesn't match a project's actual `Type` bundle, making a 400
  the *expected*, not exceptional, case; `set-type` is called with a type the caller explicitly chose, so
  a rejection is a real error the caller needs to see, not routine friction to paper over.

`set-type` therefore raises `WorkItemError` on a rejected `youtrack` Command API call (`Type <name>`,
run directly, not wrapped in the create-time best-effort helper). This matches the existing hard-fail
behaviour of `set-status` (invalid status raises) and the new `set-title`/`set-description` (unknown id
raises) — every *dedicated, explicit* mutation in the contract fails loudly; only `create`'s bundled
optional fields stay best-effort. `local` has no `Type` bundle to validate against, so it has nothing to
reject — `set-type` there always succeeds (same freeform-string behaviour `create` already has for
`type` on `local`).

#### Error semantics

- `comment` / `set-description` / `set-title` / `set-type` on a **non-existent id** → `WorkItemError`,
  same as `get`/`set-status` (both backends already resolve/validate the id before mutating).
- `set-description` with an **empty string is allowed** — the concrete motivating case (a stale
  `[conflict]` block) requires the ability to clear the description, not just replace it with other
  non-empty text.
- `set-title` with an **empty string is rejected** (`WorkItemError`, "title is required") — mirrors
  `create`'s existing validation; a title is a mandatory core-model field, never legitimately blank.
- `set-type` with an **empty string is rejected** (`WorkItemError`, "type is required") — a dedicated
  call communicates an explicit value; clearing a type entirely is out of scope for this addendum (no
  generic "no type" representation exists across arbitrary YouTrack `Type` bundles) — revisit if a real
  need surfaces.
- `comment` with an **empty string is rejected** (`WorkItemError`, "comment text is required") — an
  empty comment carries no information and would leave a bare, meaningless entry in either backend's
  comment channel.
- `comment` with text **starting with the result marker** (`<!-- ccpr:result -->`) is rejected
  (`WorkItemError`) — **on both backends**, review follow-up (09.07.2026). Without this, a human typing
  the marker into a plain comment could forge a `result-link` entry on `youtrack` (the marker is what
  `get` uses to tell a result reference from discussion). `local` isn't structurally vulnerable to this
  itself (Result/Comments are separate sections there, not a marker split), but the rejection is applied
  uniformly so `comment`'s semantics don't depend on which backend a project happens to run — a caller
  shouldn't have to know which backend enforces this and which doesn't. Enforced by one shared helper
  (`workitems.reject_result_marker`), not duplicated per backend, and covered by a shared contract test.

### Backend mapping

| Operation | `youtrack` | `local` |
|---|---|---|
| `comment` | `POST /api/issues/<id>/comments` `{"text": <text>}` — **no marker** | append a line to the `## Comments` section (new; parallel to `## Result`) |
| `set-description` | `POST /api/issues/<id>` `{"description": <text>}` (direct field write — same endpoint shape `create` already uses for the initial `description`) | rewrite the free-text block before the first `## ` heading |
| `set-title` | `POST /api/issues/<id>` `{"summary": <text>}` | rewrite the `title` frontmatter field |
| `set-type` | Command API `POST /api/commands` `{"query": "Type <type>", ...}`, run directly (not best-effort) | rewrite the `type` frontmatter field (always succeeds — no bundle to validate against) |

### Alternatives considered

- **Overload `append-result` for plain comments** (drop the marker requirement, let every comment count
  as a result-link): rejected — conflates machine result references with human discussion; a gate that
  reads `result-link` to find "what was delivered" would then have to filter prose out of it again,
  recreating the exact ambiguity ADR-0003 already solved with the marker.
- **`comments[]` as `{text, author, created}`**: rejected for now (see above) — no consumer needs it yet
  and `local` has no author/timestamp to offer honestly; adding it speculatively would either fabricate
  data or make the core model backend-conditionally shaped, both of which this contract explicitly
  avoids for `result-link` already.
- **`set-type` best-effort (warn + continue), matching `create`**: rejected — a dedicated call has no
  atomicity to protect and no "expected friction" justification; failing silently would mean the caller
  believes the type changed when it didn't, with no signal to notice.
- **Single generic `set-field <id> <field> <value>` op instead of three dedicated ops**: rejected — the
  three fields (`description`, `title`, `type`) have different validation rules (empty allowed only for
  `description`) and different backend mappings (direct field write vs. Command API); a generic op
  would either lose that per-field validation or need a field-keyed branch inside one op, which is the
  same amount of code with a worse, stringly-typed call site and no CLI-time guard against a typo'd
  field name.

### Consequences

- **Contract fixture grows by four ops × two backends**, plus assertions that `comments[]` and
  `result-link` never overlap for the same underlying comment stream (a regression test for the
  marker-partition logic, not just a new-field-exists check).
- **`local`'s Markdown format gains one more optional section** (`## Comments`), following the same
  "absent section → empty list" convention `## Result` already uses — an existing item file with no
  `## Comments` section round-trips as `comments: []`, no migration needed.
- **No change to `create`**: its best-effort `type`/`owner` handling (ADR-0003) is unchanged; this
  addendum only adds a *harder* path alongside it for explicit, standalone type changes.
- **`youtrack`'s `set-description`/`set-title` use the direct field-write endpoint**, not the Command
  API — matches ADR-0003's own precedent (the original `description` write in `create` already uses
  `POST /api/issues/<id>` directly), not a new access pattern for this backend.
