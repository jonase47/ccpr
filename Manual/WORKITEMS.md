# Work Items — the backend-neutral work-state contract

**Status:** Proposed (draft) — see [`docs/adr/ADR-0002-workitem-backend-contract.md`](../docs/adr/ADR-0002-workitem-backend-contract.md)
**Date:** 08.07.2026

> CCPR works **with or without a ticket system.** The default is local Markdown files in the repo —
> no server, no token, no setup. A team can point the same commands at a remote tracker by changing
> one setting. Neither mode is special-cased in the commands: they speak to one narrow contract, and
> the configured **backend** decides where the items live.

---

## 1. The contract

CCPR commands never read work-state files directly. They call a helper that exposes six operations:

| Operation | CLI | Meaning |
|---|---|---|
| create | `workitems create --title T [--type X] [--owner O] [--description D]` | create a new item; the backend assigns a stable `id` (JSON) |
| list | `workitems list [--status S] [--owner O]` | enumerate items (JSON array) |
| get | `workitems get <id>` | fetch one item (JSON) |
| claim | `workitems claim <id> [--owner O] [--runner R]` | take ownership / mark active |
| set-status | `workitems set-status <id> <status>` | move an item through its lifecycle |
| append-result | `workitems append-result <id> <ref>` | attach a result reference (PR/commit link) |

`create` assigns the `id` — callers never supply one (the `local` backend hands out the next
monotonic `WI-NNNN`; a remote backend returns the tracker's id). `lift` (ADR-0004) is bulk creation;
`create` is the single-item path a planning command uses.

The helper (`scripts/workitems.py`) reads `workitems.provider` from `settings.json` and dispatches to
the provider implementation under `scripts/lib/workitems/<provider>.py`. `list` and `get` print JSON so
commands can consume them without parsing prose.

## 2. Core model

Every backend maps exactly these fields — the CCPR core relies on **nothing** beyond them (a backend
may expose more, e.g. milestones or cycles, but a command must never depend on backend-specific
fields, or the public framework acquires a silent tool-lock-in):

| Field | Notes |
|---|---|
| `id` | stable, referenceable (e.g. `WI-0007`); survives in HANDOVER/commits/learnings |
| `title` | one line |
| `status` | one of the vocabulary below |
| `description` | free text (Markdown) |
| `result-link` | optional; where the delivered work lives — **accumulates** (`append-result` adds refs; an item may hold several PR/commit links) |
| `owner` | the responsible human; optional while unclaimed |

### Status vocabulary

```
Backlog → Ready → In Progress → In Review → Waiting for Approval → Done
```
plus **`Parked`**, **`Blocked`**, and **`Cancelled`** crosscutting (the two gates are distinct states:
`In Review` = code review pending, `Waiting for Approval` = acceptance pending). Backends map their own states onto this set;
`Parked` and the claiming semantics are specified in ADR-0005.

## 3. Provider configuration

`settings.json`:

```json
"workitems": {
  "provider": "local",
  "youtrack": {
    "baseUrl": "https://tracker.example.org",
    "project": "PROJ",
    "tokenEnv": "YOUTRACK_TOKEN"
  },
  "claiming": {
    "staleAfter": "2h",
    "heartbeatInterval": "5m"
  }
}
```

- `provider` defaults to `local`. Set it per project.
- Remote-backend **credentials come only from environment variables** (`tokenEnv` names the variable).
  Never place a secret in `settings.json` or any tracked file.
- `claiming` (remote backends only): `staleAfter` is how long without a heartbeat before `sweep`
  moves a claimed item to `Parked`; `heartbeatInterval` is advisory for whatever refreshes a runner's
  heartbeat. Durations accept `45s` / `5m` / `2h` / `1d` or a bare number of seconds. See §6 and ADR-0005.

## 4. The `local` backend

The default. A **structured store**, not prose: one file per item.

```
docs/workitems/WI-0007.md
```

```markdown
---
id: WI-0007
title: Rate-limit the authentication endpoints
status: In Progress
type: feat            # feat | fix | refactor | docs | chore (optional)
owner: alice          # optional until claimed
refs: [ADR-0011]      # optional cross-references
tags: [security]      # optional
created: 2026-07-08   # optional, ISO date
---

The login / refresh / API-key endpoints have no rate limiting. Add a limiter …

## Acceptance Criteria
- Login is limited to N attempts / window per identifier.
- Exceeding the limit returns 429 with `Retry-After`.

## Result
<!-- append-result writes PR/commit links here -->
```

- **IDs** are stable and monotonic (`WI-0001`, `WI-0002`, …), assigned on creation. They are what
  HANDOVER, commit messages, and learnings reference — never renumber.
- The local backend implements the contract by reading/writing these files. No server, no token.
- `claim` on `local` is a **no-op** that may set `owner` (a solo developer with local files has nothing
  to lock — see §6).
- `BACKLOG.md` / `SPRINT.md` become **human-facing planning views** (roadmap narrative) over the items;
  `HANDOVER.md` shrinks to narrative + item references. Existing projects convert their prose to this
  format with `ccpr workitems lift` (ADR-0004) — one run; the workflow stays all-local.

## 5. Remote backends

A remote backend maps the contract onto a tracker's API (the first, a self-hosted issue tracker, is
specified in ADR-0003). The item `id` is the tracker's own (e.g. `PROJ-42`); a project keeps a local
**id-map** (`docs/workitems-idmap.yml`, written by `migrate`) so references in HANDOVER and learnings
stay resolvable across the switch.

**One active backend per project — no bidirectional sync.** Moving solo→team is the one-time
`ccpr workitems migrate` (ADR-0004), not a continuous sync (which would create merge conflicts in a
new dimension). The old local files are archived, not deleted — that is the rollback path (set
`provider` back to `local`).

## 6. Claiming

Claiming answers "who is working this item right now?" It is **mandatory for remote backends** (a team
and its runners must not collide) and a **no-op for `local`** (solo with local files has nothing to
lock). The full protocol — `Parked` state for a branch with commits but no live runner, `ticket/<id>`
branches, a runner heartbeat — is ADR-0005.

Two supporting commands (remote-only; no-ops on `local`):

| Command | Meaning |
|---|---|
| `workitems heartbeat <id> --runner R` | refresh the runner's liveness timestamp |
| `workitems sweep` | move any `In Progress` item whose heartbeat is older than `staleAfter` **and** whose `ticket/<id>` branch has commits to `Parked` (resumable) |

`claim` refuses to take over an item held by a **live** runner, and refuses a terminal (`Done` /
`Cancelled`) item; it resumes a `Parked` item or takes over one whose heartbeat has gone stale.

## 7. The write-loop (how status stays accurate)

Status is kept current **structurally, not by discipline** — the drift failure mode this whole design
exists to prevent (a register that reads "open" while the code is done, or vice-versa).

- **Workflow-driven (primary):** the CCPR commands invoke the contract at defined transitions —
  `claim` + `set-status In Progress` when implementation starts, `set-status In Review` +
  `append-result <PR>` when submitted for review, `set-status Waiting for Approval` on review-approval,
  `set-status Done` on acceptance/merge. The update happens because the command runs it, not because an
  agent remembers.
- **Hook safety-net:** a git hook catches out-of-band events — a commit on a `ticket/<id>` branch
  records the commit against the item; a session-end hook consolidates. This closes the gap when work
  happens outside an orchestrated command. (The runner heartbeat is the extreme case — ADR-0005.)

## 8. How commands adopt the contract

The commands that read `BACKLOG.md` / `SPRINT.md` today migrate to the contract **incrementally** —
old and new models coexist during the transition. A command stops reading/writing those files for item
state and instead calls `workitems …`. Priority order: the commands that *write* work state first (so
the source of truth is single), then the read-only consumers. (`HANDOVER.md` is a session snapshot, not
item state — it stays prose; see §10.)

### The adoption guard (feature-detect — every wired command opens with this)

A project may not have adopted the structured store yet (no `docs/workitems/`, still prose
`BACKLOG.md`). A wired command must degrade gracefully — **never fork the store, never hard-fail**:

> Run `python3 ~/.claude/scripts/workitems.py list` **and** check whether the `docs/workitems/`
> directory exists (e.g. `ls docs/workitems/`). Both signals are needed — see the note below.
> - **Non-empty list** → the project uses the structured store. Use the CLI for **all** item state below.
> - **Empty list, but `docs/workitems/` exists** → the store is adopted, just empty for this query (an
>   empty store, or a `--status`-filtered query with no matches). **Use the CLI — the empty result is
>   real.** For a gate that means a genuine finding (e.g. "no Ready story" = Not Met), NOT a reason to
>   fall back to prose.
> - **Empty list and no `docs/workitems/` directory** → not adopted, still on prose. Fall back to the
>   existing `SPRINT.md`/`BACKLOG.md` behaviour, and emit one line: *"Tip: run `lift` to adopt the
>   structured work-item store."*
>
> **Why the directory check is essential:** `list` returns the identical `[]` for an adopted-but-empty
> store and a never-adopted project — only the directory's existence tells them apart. Treating an
> adopted-empty store as never-adopted would **false-pass a gate** (skip a real Not-Met via the prose
> exemption).

Rationale: **dual-write** re-creates two writable registers (the §7 drift). **Requiring `lift`** breaks
every project on upgrade. Feature-detect honours "old and new coexist" and the empty-list case is
already safe.

### Status-verb mapping (the prose loop → the vocabulary)

| Prose phrase today | CLI call |
|---|---|
| start work on a story | `claim <id> --owner <who>` then `set-status <id> "In Progress"` |
| implementation done → submit for code review | `set-status <id> "In Review"` |
| code review **approved** (→ awaits acceptance) | `set-status <id> "Waiting for Approval"` |
| acceptance **accepted** / merged | `set-status <id> "Done"` |
| review or acceptance **rejected** ("back to Dev") | `set-status <id> "In Progress"` |
| "add new item to BACKLOG" | `create --title … --type … --description …` (the backend assigns the id) |
| record the delivered PR/commit | `append-result <id> <link>` |

The two gates are **distinct states**, so `p5-review` (resolves `list --status "In Review"`) and
`p5-acceptance` (resolves `list --status "Waiting for Approval"`) never contend for the same item.

**Once wired, item status is NEVER hand-edited in `SPRINT.md`/`BACKLOG.md`** — those become planning
**views** over the items (a `render` command to regenerate them is future work; during the transition
the CLI `list` is the live view).

## 9. Testing

`local` is both the **reference implementation** and the **contract test fixture**: a shared test
suite runs every backend (including contributed ones) against the same contract, so a backend cannot
silently diverge. A new backend passes iff it satisfies the fixture.

## 10. What this replaces

| Today | With the contract |
|---|---|
| `BACKLOG.md` (prose hierarchy) | planning **view** over the items |
| `SPRINT.md` (prose sprint plan) | planning **view** (the items in the current iteration) |
| `HANDOVER.md` (session snapshot with the work list) | **narrative** + item references |
| commands parsing those files | commands calling `workitems …` |

---

*Design decisions and rationale: ADR-0002. Remote backend: ADR-0003. `lift`/`migrate`: ADR-0004.
Claiming/runner protocol: ADR-0005.*
