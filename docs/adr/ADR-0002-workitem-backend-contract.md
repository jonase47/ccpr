---
kind: adr
adr_id: ADR-0002
status: proposed
last_updated: 09.07.2026
related:
  - ../CONSTITUTION.md
  - ADR-0001-versioning-and-distribution.md
  - ADR-0008-typed-workitem-links.md
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

- ~~**ADR-0003** — the first remote backend (a self-hosted issue tracker, e.g. YouTrack): REST mapping,
  the state-set, owner/assignee, claiming.~~ **Written: `ADR-0003-youtrack-backend.md`.**
- ~~**ADR-0004** — `ccpr workitems lift` (heterogeneous ToDos → the local format; dry-run default,
  idempotent, original text preserved) and `migrate` (local → remote, with an id-mapping written into
  the repo).~~ **Written: `ADR-0004-workitem-lift-and-migrate.md`.**
- ~~**ADR-0005** — the claiming / branch-runner protocol (`Parked`, `ticket/<id>`, heartbeat).~~
  **Written: `ADR-0005-claiming-runner-protocol.md`.**

All three follow-ups are discharged. Struck through rather than deleted (WI-0127): a follow-up list
that still reads as open is read as a work queue, and this one had stood so for months.

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

## Addendum 2 (09.07.2026): Tags, queryable `list`, and planning custom-fields (`sprint`/`priority`/`estimate`)

### Context

Live use against a real YouTrack project surfaced three more gaps in daily (not just create→done)
work: no writable tags (`needs:feedback`, `security` degrade to description-prefix hacks), no way to
answer "what's in sprint N / what's High priority / what's tagged X" without a full-list client scan,
and no planning fields at all (dependencies, priority, estimates). The costliest of the three is
sprint membership — several commands (`/guide`, `/gate-p5`, `/p4-sprint`) reconstruct "current sprint"
by parsing `SPRINT.md` prose plus client-side filtering, exactly the fragility this whole contract
exists to remove.

The key design move: sprint membership needs **no** CCPR-side code against YouTrack's Agile Board API
(`/api/agiles`) — out of scope per ADR-0003's own boundary (a work-item store, not a board renderer).
It is instead modeled as an ordinary **Enum custom field** (`Sprint`), written through the same
Command-API-by-name mechanism `set-status`/`set-type` already use. A YouTrack project configures its
Agile Board **field-based** on this `Sprint` field (an admin, UI-side setup step, not CCPR code) — the
board becomes a *consumer* of the field CCPR writes, so full board functionality (burndown, drag-drop)
comes for free without a second write path.

Typed links (dependencies) are **not** part of this addendum — see the new **ADR-0008**, which gives
them their own decision (direction normalization and a dedicated local encoding are structural enough
to warrant it, unlike the field-mapping ops below, which all follow the existing `set-type` shape).

### Decision

Seven new operations, on **both** backends (same contract fixture):

| Operation | CLI | Meaning |
|---|---|---|
| `add-tag` | `workitems add-tag <id> <tag>` | attach a tag (idempotent) |
| `remove-tag` | `workitems remove-tag <id> <tag>` | detach a tag (idempotent) |
| `set-sprint` | `workitems set-sprint <id> <n>` | set the `Sprint` field (single-valued — a later set overwrites, never accumulates) |
| `set-priority` | `workitems set-priority <id> <priority>` | set `priority` (closed vocabulary, see below) |
| `set-estimate` | `workitems set-estimate <id> <points>` | set `estimate` (non-negative integer story points) |

Plus two extended existing ops: `create` gains repeatable `--tag`, and `list` gains `--tag`
(repeatable), `--type`, `--sprint`, `--priority`, and `--query`.

**Core model extension:** `get`/`list` gain `tags` (`List[str]`, default `[]`), `sprint`
(`str | None`), `priority` (`str | None`), `estimate` (`int | None`). None of the four is ever
absent from the dict — an unset field reads as `None` (or `[]` for `tags`), on both backends, the
same "never a missing key" discipline the existing `comments`/`result-link` fields already follow.

#### Tags

- **Charset:** `^[A-Za-z0-9_:.-]+$` — no spaces, because the YouTrack Command API tokenizes on
  whitespace (`tag <name>`), and a space-containing tag would either need quoting (an extra parsing
  mode this contract doesn't otherwise have) or silently split into two tokens.
- **Reserved namespace:** the `runner:`/`heartbeat:` prefixes (ADR-0005/ADR-0003) are lifted from
  `youtrack.py` into `workitems/__init__.py` as `RESERVED_TAG_PREFIXES` — the **single source of
  truth**, since both the claiming protocol (which writes these tags directly via `_run_command`, not
  through the public `add_tag`) and the new `add-tag`/`remove-tag` (which must refuse them) need the
  same list. `add-tag`/`remove-tag` reject a reserved tag with `WorkItemError`; the claiming protocol's
  internal writes are unaffected (they bypass the public method entirely, so the reservation can't
  block CCPR's own claiming machinery).
- **Idempotence:** `add-tag` on an already-present tag, and `remove-tag` on an absent one, are
  **no-ops** — same item returned unchanged, no error. A tag is a set-membership fact; re-asserting or
  re-retracting a fact that already holds isn't an error condition, and treating it as one would force
  every caller (a command that runs `add-tag ... security` unconditionally, say) to first check
  whether the tag already exists just to avoid a spurious failure.
- **`create --tag`:** repeatable, **best-effort on `youtrack`** — same footing as `create`'s existing
  `type`/`owner` handling (ADR-0003 implementation notes): the issue already exists by the time tags
  are applied, so a rejected tag (rare, but tags can in principle be restricted by workflow) must warn
  and continue, never roll back an already-committed create. On `local`, tags always succeed (no
  server-side restriction to reject against).
- **Read-back:** `youtrack`'s `tags[]` is **reserved-filtered** — a `runner:<id>`/`heartbeat:<ts>` tag
  written by the claiming protocol must never leak into the user-facing `tags` field (it isn't a tag a
  human or command added, it's protocol plumbing). `local` has no reserved tags to filter (the
  claiming protocol is a no-op there), so its existing `tags: data.get("tags")` read only needs the
  **`None → []` normalization** this addendum requires everywhere.

#### `list` filters

- **`--tag` (repeatable) is AND:** an item must carry **every** named tag to match — the natural
  reading of "items tagged X and Y", and the one that supports the motivating dedup use case (find
  items already tagged `needs:feedback` **and** `security`) without a second client-side pass.
- **`--type` / `--sprint` / `--priority`:** exact-match client-side filters, both backends — same
  shape as the existing `--status`/`--owner` filters (`item["priority"] != priority` excludes; an
  unset field on the item never matches a given filter value). No partial/prefix matching, no
  filter-value validation against the vocabulary (a typo'd `--priority Crit` simply matches nothing,
  same non-validating behaviour `--status`/`--owner` already have).
- **`--query` is `youtrack`-only, project-scoped:** passed through verbatim to YouTrack's own query
  language (`GET /api/issues?query=project: <PROJ> <user_query>&...`), prefixing `project: <PROJ> `
  so a query can never accidentally (or deliberately) leak results from another project the token
  happens to have read access to. `local` has no server-side query language to pass through to, so it
  raises `WorkItemError` ("the local backend does not support --query — use --tag/--type/--sprint/
  --priority/--status/--owner filters instead") rather than silently ignoring the flag or
  approximating it with a client-side text search, either of which would give a caller a false sense
  that the same query semantics work identically on both backends.

#### Planning custom-fields: `sprint`, `priority`, `estimate`

All three follow `set_type`'s existing shape (validate → Command API by-name write → hard-fail on
rejection), but differ in exactly **what** gets validated and **which** field name is fixed vs.
configurable — worth spelling out because the differences are deliberate, not incidental:

- **`sprint`:** field name is **fixed**, literally `"Sprint"` — a **setup precondition** (the project
  must have this Enum custom field, and the Agile Board configured field-based on it), the same class
  of precondition ADR-0003 already documents for project team membership. **Single-valued**: a second
  `set-sprint` overwrites, it never accumulates — an item is in exactly one sprint at a time, so there
  is no move-choreography to design (no "remove from sprint N, add to sprint N+1" dance). No
  value-mapping is needed: the sprint value the caller passes (e.g. `"4"`) **is** the Enum value name
  the admin configured — there's no CCPR-side vocabulary to translate, unlike `status`. Read is via
  `value(name)`, already covered by the existing `_ISSUE_FIELDS` selector (same shape as `Type`).
  **Hard-fails** on rejection (unknown value / field missing) — same rationale as `set_type`: a
  dedicated call with nothing else to protect via atomicity, and a rejection the caller needs to see.
- **`priority`:** field name is fixed, `"Priority"` (a standard YouTrack field, present by default).
  **Closed CCPR vocabulary**: `{Critical, High, Medium, Low}`, validated on **both** backends — this
  is a deliberate departure from `type`'s local behaviour (freeform there). `type` is freeform on
  `local` because CCPR's own suggested type vocabulary (`feat/fix/refactor/docs/chore`) is explicitly
  **not** meant to constrain a project's own YouTrack `Type` bundle (`Bug`/`Feature`/`Task`, ...), so
  `local` must not be stricter than the actual remote target. `priority` has no such tension: CCPR
  defines the four values itself, there is no legitimate reason for a project to extend the set, and
  `list --priority` needs a **closed, shared** vocabulary on both backends to be meaningfully
  consistent (an arbitrary local priority string would make the filter, and any future `migrate`, silently
  lossy). Validated with a `WorkItemError` on both backends for anything outside the four values.
  `workitems.youtrack.priorityMap` (optional, default: identity/pass-through) maps a canonical value to
  the project's own `Priority` bundle name when it doesn't literally use CCPR's four words — the exact
  same escape hatch `stateMap` already provides for `status`, with the same absent-by-default posture
  (no invented default mapping, since a project's actual bundle values are unknowable in advance).
- **`estimate`:** an **Integer**, non-negative (`>= 0`), rejecting non-integer or negative input on
  both backends with `WorkItemError` — deliberately **not** restricted to a Fibonacci-like subset
  (`1/2/3/5/8`); that sequence is a *usage convention* documented for `/p4-backlog`, not a data-integrity
  constraint the contract should enforce (a project using a different point scale isn't violating
  anything). Unlike `sprint`/`priority`, the custom field's **name is not fixed** and has **no
  default** — `State`/`Type`/`Priority`/`Assignee` are standard YouTrack fields present on every
  instance, but a "story points" field is always a project-specific addition with no universal name
  across installations, so `workitems.youtrack.estimateField` **must** be configured; `set_estimate`
  raises immediately (before any API call) if it is absent, rather than guessing a plausible-sounding
  default name that might not exist on a given instance. Once configured, the write goes through the
  same Command API pattern as the other three (`"<estimateField> <points>"`), so all four field ops
  share one mechanism — only the **read** side differs: `sprint`/`priority`/`type` are Enum fields
  (`value(name)`), `estimate` is the one field whose YouTrack value is a bare **scalar** number, so
  `_ISSUE_FIELDS` and `_item_from_issue` need to handle that shape distinctly from the Enum fields
  (flagged here as an implementation detail to resolve and report against a live instance, in the same
  spirit as ADR-0003's own "Implementation notes" section — the exact field-selection query shape for
  a scalar custom field isn't something this design pass can verify without one).
  `local`: `estimate` is a plain integer frontmatter value, same validation, no field-name concept to
  configure (there is only ever the one `estimate:` key).

### Error semantics (new ops)

- `add-tag`/`remove-tag`/`set-sprint`/`set-priority`/`set-estimate` on a **non-existent id** →
  `WorkItemError`, same as every other dedicated mutation in this contract.
- `add-tag`/`remove-tag` with a tag violating the charset, or carrying a reserved prefix, →
  `WorkItemError` — charset checked first (a structural violation), reserved-prefix checked second.
- `set-priority` with a value outside `{Critical, High, Medium, Low}` → `WorkItemError`, on **both**
  backends (see above).
- `set-estimate` with a non-integer or negative value → `WorkItemError`, on **both** backends. `0` is
  accepted (a legitimately "trivial/no-op" item is not an error condition).
- `set-estimate` when `workitems.youtrack.estimateField` isn't configured → `WorkItemError`, raised
  before any network call.
- `set-sprint`/`set-priority`/`set-estimate` rejected by the YouTrack Command API (unknown value,
  missing field) → `WorkItemError`, surfaced from the same HTTP-400-to-exception path `set_type`
  already uses — atomic reject, issue left unchanged.
- `list --query` on `local` → `WorkItemError` (see above).

### Backend mapping

| Operation | `youtrack` | `local` |
|---|---|---|
| `add-tag` / `remove-tag` | Command API `tag <name>` / `remove tag <name>` — checks the current tag list first (a GET) so a redundant call is skipped rather than relying on the Command API's own idempotence | rewrite the `tags` frontmatter list |
| `create --tag` | best-effort `tag <name>` per tag, after the POST (parity with `type`/`owner`) | always succeeds; seeds `tags` frontmatter |
| `list --tag/--type/--sprint/--priority` | client-side filter over the full project list (same GET `list()` already does) | client-side filter over the frontmatter fields |
| `list --query` | `GET /api/issues?query=project: <PROJ> <user_query>` | raises `WorkItemError` |
| `set-sprint` | Command API `Sprint <n>` (fixed field name; fails hard) | rewrite the `sprint` frontmatter field |
| `set-priority` | Command API `Priority <mapped-name>` (fails hard; `priorityMap` optional) | rewrite the `priority` frontmatter field (validated against the same closed vocabulary) |
| `set-estimate` | Command API `"<estimateField> <points>"` (fails hard; `estimateField` required, no default) | rewrite the `estimate` frontmatter field (integer) |

### Alternatives considered

- **CCPR code against YouTrack's Agile Board API (`/api/agiles`)** for sprint membership: rejected —
  out of scope per ADR-0003 (a work-item store, not a board renderer); the field-based board
  configuration gets the same board functionality without a second write path or a second API client.
- **`type`-style freeform `priority` on `local`**: rejected — unlike `type`, `priority` is a genuinely
  closed CCPR-defined vocabulary with no legitimate project-specific extension, and `list --priority`
  needs both backends to agree on the same finite set to stay meaningful (see above).
- **A default `estimateField` name** (e.g. guessing "Story Points"): rejected — no YouTrack instance
  ships a story-point-like field by default the way it ships `State`/`Priority`/`Type`/`Assignee`;
  inventing a plausible default risks a silent field-name mismatch that only surfaces as a confusing
  400 at write time instead of an immediate, actionable "not configured" error.
- **Single generic `set-field <id> <field> <value>`** instead of three dedicated ops: rejected for the
  same reason ADR-0002's first addendum rejected it for `description`/`title`/`type` — different
  validation rules and different config-key needs (`priorityMap`, `estimateField`) per field would
  either get lost in a generic op or need an internal field-keyed branch, at the same code cost with a
  worse, stringly-typed call site.

### Consequences

- **Contract fixture grows by five new ops × two backends**, plus the `list` filter extensions and the
  `create --tag` extension.
- **`local`'s frontmatter gains three more optional keys** (`sprint`, `priority`, `estimate`) and
  formalizes `tags` as a first-class, writable core-model field (previously present but not part of
  the documented core model) — all absent-key-safe (`None`/`[]` defaults), no migration needed for
  existing item files.
- **Two new provider-config keys** (`workitems.youtrack.priorityMap`, `workitems.youtrack.estimateField`),
  following `stateMap`'s existing precedent for the former and introducing a **required, no-default**
  config key for the latter (a first for this contract — every other backend config key so far has had
  a usable default).
- **Setup precondition**: a project adopting `sprint` must create the `Sprint` Enum field (and,
  separately, configure its Agile Board field-based on it) — documented alongside ADR-0003's existing
  Prerequisites, not new backend code.
