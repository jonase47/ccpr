---
kind: adr
adr_id: ADR-0003
adr_status: proposed
status: draft
last_updated: 02.09.2026
related:
  - ADR-0002-workitem-backend-contract.md
  - ../../Manual/WORKITEMS.md
  - ADR-0005-claiming-runner-protocol.md
---

# ADR-0003: YouTrack backend (first remote work-item backend)

**Status:** Proposed (08.07.2026)
**Decision-makers:** Repo owner (Jonas), early tester (Olli, @OlArtTro)

## Context

ADR-0002 defines the backend-neutral contract and the provider model; `local` is the default. This
ADR specifies the **first remote backend** — a self-hosted **YouTrack** — which proves the remote path
and lets a team share work state between parallel CCPR instances.

YouTrack was chosen as the first remote target because it self-hosts, exposes a plain **REST + Command
API** (no MCP dependency — a deliberate choice after an MCP-based tracker candidate proved unreliable),
and has a real workflow model (assignee, a state bundle, typed links). It is **one backend
implementation, never the core** — the contract stays tool-neutral (ADR-0002).

The design constraint that matters most: the backend must be **generic across YouTrack instances**. A
naive integration hardcodes the instance's numeric field and bundle IDs (`State` field `157-…`,
`Assignee` `157-…`, bundle values `162-…`); that binds the code to one server. The generic backend
**resolves fields and states by name at runtime**, and prefers the **Command API** (which is
name-based) over raw field writes.

## Decision

### Access

- Base: `<baseUrl>/api` for issues/fields/commands; **auth is a permanent token** as
  `Authorization: Bearer <token>`. The token itself never enters the repo (ADR-0002 / `WORKITEMS.md`):
  it comes either from the environment variable named by `tokenEnv`, or — added 10.07.2026, so a
  session doesn't need to export an env var by hand — from a file path named by `tokenFile` (a
  600-permission file outside the repo). `tokenEnv` wins when both are configured and resolve.
- **Direct REST, no MCP.**
- Note the **YouTrack ↔ Hub split**: issues, custom fields, commands, and boards live under `/api`;
  users, groups, roles, and passwords live under `/hub/api/rest`. The work-item backend only needs
  `/api`. Identity/team administration is **out of band** (see Prerequisites) — the backend does not
  provision users.

### Model mapping

| Core field (ADR-0002) | YouTrack |
|---|---|
| `id` | `idReadable` (e.g. `PROJ-42`) |
| `title` | `summary` |
| `status` | the `State` custom field (a `StateBundle`), mapped **by name** |
| `description` | `description` |
| `result-link` | appended as a comment (or into the description's Result section) |
| `owner` | the `Assignee` custom field (the responsible human) |

Backend-specific fields (typed links / `depends on`, tags, priority, board membership) may be exposed
as **optional extensions**, but the CCPR core never relies on them (ADR-0002). Board and swimlane
rendering is **out of scope** for the backend — it is a work-item store, not a board renderer.

### Operation mapping

| Contract op | YouTrack call |
|---|---|
| `list` | `GET /api/issues?query=project:<PROJ>&fields=idReadable,summary,description,customFields(name,value(name))` |
| `get` | `GET /api/issues/{id}?fields=…` |
| `set-status` | **Command API**: `POST /api/commands {"query":"State {name}","issues":[{"idReadable":id}]}` |
| `claim` | Command API `for {user}` (sets Assignee) + the runner protocol (ADR-0005) |
| `append-result` | add a comment with the PR/commit link |

The **Command API** (`POST /api/commands`, e.g. `State In Progress for alice`, `for bob`,
`Type Task Priority Major tag chore`, `depends on PROJ-3`) is preferred for writes: it is name-based
and robust, so the backend needs no instance-specific numeric field IDs.

### State vocabulary

The backend maps CCPR's status vocabulary (`Backlog → Ready → In Progress → In Review → Waiting for
Approval → Done`, plus `Parked`/`Blocked`/`Cancelled`) onto the project's `State` bundle **by name**. A project
either names its `State` values to match, or supplies a name→name mapping in
`workitems.youtrack.stateMap`. Resolving by name (not numeric bundle IDs) is what keeps the backend
instance-independent.

### Claiming

`Assignee` is the **responsible human (owner)** — `claim` sets it. Runners (human or AI) are dispatched
separately; their liveness is a separate signal (a `runner:<id>` tag / heartbeat), and work happens on
a `ticket/<id>` branch, with `Parked` marking a branch that has commits but no live runner. The full
protocol is **ADR-0005**; this backend exposes the hooks it needs (set Assignee, set State, read/write
a runner tag).

### Prerequisites (setup, not runtime)

A real gotcha with self-hosted YouTrack: **API-created projects have no Hub project**, so project team
membership (which grants assignee capability) and project-scoped roles **cannot be set over REST** —
they are configured **once in the UI** (Project → Settings → Team). The backend therefore assumes the
project, its `State` bundle, and team membership already exist. Provisioning is a documented setup
step, not a backend responsibility.

## Consequences

- The **team write-loop backend exists**: a project with `workitems.provider: youtrack` reads and
  writes its work state in YouTrack via the contract, and CCPR commands drive the transitions
  (ADR-0002 write-loop).
- **Generic across instances:** by resolving fields/states by name and using the Command API, the
  backend carries no instance-specific IDs; only `baseUrl`/`project`/`tokenEnv` differ per project.
- **Identity stays out of band:** the Hub split means user/team admin is UI/Hub work, which suits the
  backend's scope (work items, not identity).
- Contributed remote backends (Forgejo/GitHub issues, …) follow this shape and are validated against
  the same contract fixture (ADR-0002).

## Alternatives considered

- **MCP-based integration:** rejected — reliability; direct REST is simpler and fully controllable.
- **Hardcoded numeric field/bundle IDs** (fastest to write): rejected — binds the backend to one
  instance; resolve by name instead.
- **Raw custom-field writes** for state/assignee: dispreferred vs the Command API, which is name-based
  and avoids resolving numeric field IDs at all.

## Implementation notes (validated against a live instance)

Points the first implementation had to resolve, verified read-only against a real self-hosted YouTrack:

- **Project id resolution.** `POST /api/issues` needs the project's internal id, not its short name.
  Resolve `project` (short name in config) → id by lookup — the same "resolve by name" principle,
  extended to the project axis. The lookup endpoint is admin-scoped, so a minimally-scoped token may
  lack permission; the backend raises a clear error distinguishing "not permitted" from "not found".
- **`append-result` uses a machine marker, not a human phrase.** Result comments are tagged with
  `<!-- ccpr:result -->` so `get`/`list` can distinguish them from ordinary human comments; an English
  prefix like "Result:" would collide with comments a person might actually type.
- **Listing disables pagination explicitly** (`$top=-1`) rather than trusting the tracker's default
  page size — otherwise a large project silently returns a truncated list, which would corrupt any
  bulk operation (`lift`/`migrate`).
- **Out-of-vocabulary read states pass through with a warning.** A project may carry `State` values
  outside CCPR's vocabulary and without a `stateMap` entry; on read the raw name is surfaced with a
  one-line warning rather than dropped or silently coerced. `set-status` still validates on write.
- **Invalid commands are rejected atomically.** An unresolvable `State`/`for <user>` command returns
  HTTP 400 and leaves the issue unchanged (no partial apply) — it surfaces as an error, never a silent
  "applied". This is why the write-loop can trust a successful command.

## Notes

The concrete API behaviours above are abstracted from a real self-hosted YouTrack integration; the
instance-specific reference notes (host, keys, numeric field IDs) are kept in a private repo and are
**not** ported here — this backend is written generically.

## Addendum (02.09.2026): The setup preconditions are demonstrably incomplete

### Context

The "Prerequisites (setup, not runtime)" section above lists the project, its `State` bundle, and team
membership. A real migration pilot against a live, self-hosted instance (01.09.2026,
`docs/.handover-archive/2026-09-01-youtrack-pilot-report.md`,
`docs/.handover-archive/2026-08-28-open-findings.md` findings #46–#48) measured that this list is
incomplete in three ways — one that blocks every create outright, one that silently fabricates data,
and one naming a configuration key this ADR predates.

### Decision

**1. `State` needs a default value, not just a populated bundle.** `create()`'s own `POST /api/issues`
call (`youtrack.py:321`) sends no `customFields` at all — the initial state is set by a separate
Command API call immediately afterward, `self.set_status(item_id, "Backlog")` (`youtrack.py:337-340`).
On the pilot instance, with `State` required (`canBeEmpty=False`) and no default configured, the
`POST /api/issues` call itself was rejected with `State is required`
(`@jetbrains/required-custom-fields-feature` —
`docs/.handover-archive/2026-09-01-youtrack-pilot-report.md:111` and
`docs/.handover-archive/2026-08-28-open-findings.md:1395-1397`) — YouTrack's own
project-level workflow rule refuses to create an issue at all when a required field has no resolvable
value, before this backend's own follow-up `State` command ever runs. Measured consequence: **every**
create fails, and no orphan issue is left behind — the pilot's `CT-1` id was consumed by exactly such a
failure, with the instance reporting 0 issues afterward
(`docs/.handover-archive/2026-09-01-youtrack-pilot-report.md:13-16`).

This means `_rollback_failed_create` (`youtrack.py:447-466`) — which deletes an issue that WAS created
but whose subsequent, explicit `State` command was then rejected — is **not** the code path this
precondition exercises: there is no issue to roll back, because the `POST /api/issues` call itself
raised, before `item_id = created["idReadable"]` is ever reached. `_rollback_failed_create` covers a
narrower, different window: an issue that YouTrack accepted with no explicit state (a project where
`State` is not strictly required at creation time), whose immediately-following `State <name>` command
is then rejected for some other reason (e.g. an unmapped state name). Fixed on the pilot instance by
giving `State` a default value (`Backlog`), matching the one working reference project measured
alongside it.

**2. `Type` and `Priority` need `canBeEmpty: true` AND their default cleared — not `canBeEmpty` alone.**
Neither backend's `create()` sets a priority (ADR-0004's addendum); `type` is set best-effort only when
the source item carries one. On a project where `Priority` is required with a default (e.g. `Normal`),
every item that arrives with no source priority silently acquires the default instead of staying unset
— measured on 130 of 137 real corpus items, all reading `Medium` after un-mapping through
`priorityMap`, despite carrying no local priority (`docs/.handover-archive/2026-08-28-open-findings.md`
finding #47). **Making the field optional alone (`canBeEmpty: true`) is not enough and was measured not
enough**: with only `canBeEmpty` toggled and the default left in place, a fresh item still came out
`Normal` — "the default applies regardless of whether the field may be empty"
(`docs/.handover-archive/2026-08-28-open-findings.md:1325-1327`). Only clearing **both**
(`canBeEmpty: true` **and** `defaultValues: []`) was measured to leave an item with no source value
arriving as `Priority: None`, verified by an independent read-back rather than trusted from the write's
own response (`docs/.handover-archive/2026-08-28-open-findings.md:1331-1367`). The same two-part change
applies to `Type` — mechanically the same enum field shape as `Priority`
(`docs/.handover-archive/2026-08-28-open-findings.md:1372-1378`) — for a project that wants `migrate`
to carry a genuinely absent type rather than fabricate the bundle default.

**3. A new configuration key, `workitems.youtrack.tagVisibilityGroup`, is not covered by this ADR's
original "Access"/"Model mapping" sections.** It names a tag-visibility group **by name**
(`workitems.youtrack.tagVisibilityGroup`, resolved via `GET /api/groups`,
`_resolve_tag_visibility_group_id`, `youtrack.py:762-797`) — never a group id in config, the same
"resolve by name, never a numeric id" principle this ADR already applies to fields, states, and the
project reference. Consumed by `_ensure_tag_visibility` (`youtrack.py:799-888`), called before a fresh
tag is first applied (both from `create(..., tags=[...])` and from `add_tag`): a tag that already
exists on the instance is left untouched, including one that is already private
(`youtrack.py:810-818`). For a genuinely new tag:
- **Unset** — the tag is created and applied with YouTrack's own default (private) visibility, and a
  stderr warning names the missing key (`TAG_VISIBILITY_NOT_CONFIGURED`, `youtrack.py:843-852`).
- **Set, but the name resolves to no group** — same private-and-warn outcome
  (`TAG_VISIBILITY_GROUP_NOT_FOUND`, `youtrack.py:780-787`).
- **Set, but the name matches more than one group** — same private-and-warn outcome
  (`TAG_VISIBILITY_GROUP_AMBIGUOUS`, `youtrack.py:788-797`) — this backend never guesses which group
  was meant.

In every one of these three cases the tag is still created and applied; only its visibility is left at
the default. A fourth, heavier outcome — the instance itself rejecting the visibility write, or a
read-back that does not match what was requested — raises `WorkItemError` rather than returning one of
the three reasons above (`TAG_VISIBILITY_WRITE_REJECTED`, `youtrack.py:127`, added 02.09.2026); see
ADR-0004's addendum for how `migrate()` reports all four.

No other claim in the original "Prerequisites" section was found contradicted by the code — the
project/State-bundle/team-membership list is incomplete, per the above, not wrong.
