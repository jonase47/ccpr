---
kind: adr
adr_id: ADR-0008
status: proposed
last_updated: 09.07.2026
related:
  - ADR-0002-workitem-backend-contract.md
  - ADR-0003-youtrack-backend.md
  - ../../Manual/WORKITEMS.md
---

# ADR-0008: Typed work-item links

**Status:** Proposed (09.07.2026)
**Decision-makers:** Repo owner (Jonas), early tester (Olli, @OlArtTro)

## Context

ADR-0003 already names typed links (`depends on`, ...) as a **backend-specific optional extension**
the CCPR core never relies on (ADR-0002 §"Model mapping"). Live use surfaced a real need for them —
`/p4-backlog`'s dependency/critical-path tracking currently has no CLI equivalent — but modeling them
properly needs its own decision, structurally distinct from the field-mapping ops in ADR-0002's second
addendum (`sprint`/`priority`/`estimate`, all "validate → Command API by-name write → read via
`value(name)`"):

1. **Direction.** A link is a directed relationship between two items; the same underlying YouTrack
   link record looks different depending on which of the two linked issues you're reading it from
   (`direction: OUTWARD` vs. `INWARD`). The contract needs one explicit rule for normalizing that into
   a single, backend-neutral `{type, target}` shape — this is not a "read via `value(name)`" problem.
2. **`local` has no native nested-object representation.** `frontmatter.py` is a flat key→scalar/list
   store; `links[]` (a list of `{type, target}` pairs) needs an encoding scheme of its own, unlike
   `sprint`/`priority`/`estimate` which are plain scalars.
3. **A new config knob** (`linkTypeMap`) is needed, with a different default posture than `stateMap`/
   `priorityMap` (see below) — worth its own justification rather than folding into the field-ops ADR.

This is why links get their own ADR number rather than a third addendum to ADR-0002.

## Decision

### Vocabulary

Four typed-link verbs, closed set:

| Verb | Meaning |
|---|---|
| `depends-on` | this item cannot complete before the target does |
| `blocks` | **sugar** for the inverse of `depends-on` — never stored as its own edge |
| `relates-to` | a loose, non-blocking association (symmetric) |
| `subtask-of` | this item is a subtask of the target |

Two new operations, on both backends, sharing one contract fixture:

| Operation | CLI | Meaning |
|---|---|---|
| `add-link` | `workitems add-link <id> <type> <target-id>` | create a typed edge from `<id>` to `<target-id>` |
| `remove-link` | `workitems remove-link <id> <type> <target-id>` | remove an exact `{type, target}` edge |

**Core model extension:** `get`/`list` gain `links` — `List[{"type": str, "target": str}]`, default
`[]` (never absent, same discipline as `tags`/`comments`/`result-link`).

### `blocks` is pure client-side sugar, not a stored edge

`add-link <id> blocks <target>` is implemented as `add-link <target> depends-on <id>` — id and target
swapped, delegated entirely to the `depends-on` path. There is **no separate `blocks` command phrase**
resolved against the instance and no `blocks` entry in `linkTypeMap` — the only stored relationship is
`depends-on`; `blocks` is a naming convenience for describing the same edge from the other item's point
of view. `remove-link ... blocks ...` swaps the same way before delegating to the `depends-on` removal.
This keeps the link-type vocabulary the instance needs to know about to exactly three names
(`depends-on`, `relates-to`, `subtask-of`), not four, and avoids needing YouTrack's inward-direction
command phrase at all (only the outward phrase for each of the three real types is ever sent).

### Direction & read-back normalization (the load-bearing rule)

YouTrack reports each link **relative to the issue being read** (`direction: OUTWARD | INWARD | BOTH`,
plus `linkType.name`). `_item_from_issue` normalizes that into the canonical `{type, target}` shape as
follows:

- **`depends-on`-typed link, direction `OUTWARD`** (this item is the dependent) → surfaced as
  `{"type": "depends-on", "target": <linked-id>}`.
- **`depends-on`-typed link, direction `INWARD`** (the linked item depends on *this* one) → surfaced as
  `{"type": "blocks", "target": <linked-id>}` — the read-side counterpart of the write-side sugar
  above: reading a `depends-on` edge from the blocker's side gives you `blocks`, not a second
  `depends-on` entry pointing the "wrong" way.
- **`relates-to`-typed link, any direction** → always surfaced as `{"type": "relates-to", ...}`. This
  type is symmetric by nature (an association, not an ordering), so direction carries no information
  worth encoding — both ends read the same verb.
- **`subtask-of`-typed link, direction `INWARD`** (this item is the child) → surfaced as
  `{"type": "subtask-of", "target": <parent-id>}`.
- **`subtask-of`-typed link, direction `OUTWARD`** (this item is the parent, i.e. it *has* the linked
  item as a subtask) → **not surfaced at all** in `links[]`. There is deliberately no canonical
  "has-subtask" verb in this ADR's vocabulary (unlike `depends-on`/`blocks`, no consumer today needs
  the parent-looking-down view) — adding one would mean inventing a fourth sugar name nothing in the
  current scope asks for. This is a **documented, intentional gap**, not a silent bug: a future ADR (or
  addendum) can add a `has-subtask` sugar verb, mirroring `blocks`, exactly when a real consumer needs
  it (YAGNI, same standard this contract already applies to `comments[]`'s shape in ADR-0002).

`local` has no direction to normalize — the string encoding (below) stores the canonical verb directly
as the caller wrote it, so this normalization logic is `youtrack`-only.

### `linkTypeMap` — configuration, with a default (unlike `stateMap`)

`workitems.youtrack.linkTypeMap` maps a canonical verb to the instance's actual YouTrack link-type
`name` (the same by-name-mapping shape `stateMap` already established for `status`), used both to
build the Command API write (`"<mapped-name> <target>"`) and to match `linkType.name` back to a
canonical verb on read.

Unlike `stateMap`/`priorityMap` (which default to a bare identity pass-through, since a project's own
`State`/`Priority` bundle values are unknowable in advance and have no natural relationship to CCPR's
vocabulary), `linkTypeMap` ships a **mechanical default**: the canonical verb with hyphens replaced by
spaces (`depends-on` → `"depends on"`, `relates-to` → `"relates to"`, `subtask-of` → `"subtask of"`).
This default is not asserted as "the YouTrack out-of-the-box phrase" (link-type naming, like every
other by-name resolution in this backend, is configured per instance and must be verified against a
live one — flagged here the same way ADR-0003 flags its own resolved implementation gaps) — it exists
because, unlike an arbitrary `State` bundle value, a link verb's dehyphenated form is a reasonable,
predictable, testable starting point that a project can override with a single config entry if its
instance names the type differently. `blocks` never appears in `linkTypeMap` (see above — it isn't a
stored type).

### `local` string encoding: flat strings, not nested dicts

`frontmatter.py` only formats scalars and flat string lists (`_format_value`); it has no representation
for a list of objects. `links` is therefore stored as a **string list** with the verb and target joined
by a colon:

```yaml
links: [depends-on:WI-0003, blocks:WI-0005]
```

Parsed by splitting each entry once on `:` — safe because work-item ids match `ID_PATTERN`
(`^[A-Za-z0-9_-]+$`, `workitems/__init__.py`), which **excludes `:`**, so a target id can never contain
the separator and the split is unambiguous in either direction (encode and decode are true inverses).

### `remove-link`: exact match, check-then-act, idempotent

`remove-link <id> <type> <target>` requires an **exact** `{type, target}` match against the item's
current `links[]` (post read-back normalization, so `remove-link <target> blocks <id>` matches the same
underlying edge as `remove-link <id> depends-on <target>` — see the sugar-swap above). Both backends
**read the item first** (the same `get`), check whether the normalized edge is present, and no-op if
it isn't — mirroring `add-tag`/`remove-tag`'s idempotence rule (ADR-0002's second addendum): removing
an edge that already doesn't exist isn't an error, it's a fact already true. Only when the edge is
present does `youtrack` issue the removal command / does `local` rewrite the frontmatter list.

`add-link` is idempotent the same way: adding an edge that's already present is a no-op, not a
duplicate entry.

There is no canonical name to call `remove-link ... has-subtask ...` (see the read-back gap above) —
a caller cannot construct that request in the first place, consistent with it not being surfaced on
read.

### Error semantics

- `add-link`/`remove-link` with a `<type>` outside `{depends-on, blocks, relates-to, subtask-of}` →
  `WorkItemError`, both backends.
- `add-link`/`remove-link` on a non-existent `<id>` → `WorkItemError`, same as every other dedicated
  mutation.
- `add-link` where `<target-id>` does not exist: `local` validates explicitly (the same existence check
  `_path_for` already performs for `<id>`) and raises `WorkItemError`; `youtrack` relies on the Command
  API's existing atomic-reject behaviour (ADR-0003) — an unresolvable target in `"depends on <target>"`
  fails the same way an unresolvable `State`/`for <user>` value does, no special-casing needed.
- No cycle/self-reference validation (e.g. an item depending on itself, or a subtask cycle) — out of
  scope for this addendum; revisit only if a real consumer is harmed by it (YAGNI).

### Backend mapping

| Operation | `youtrack` | `local` |
|---|---|---|
| `add-link <id> depends-on <t>` | Command API `"<linkTypeMap[depends-on]> <t>"` on `<id>` | append `depends-on:<t>` to the `links` frontmatter list on `<id>`'s file |
| `add-link <id> blocks <t>` | delegated to `add-link <t> depends-on <id>` | delegated to `add-link <t> depends-on <id>` |
| `remove-link <id> <type> <t>` | check current `links[]` (a `get`); if present, the Command API removal for the mapped type; else no-op | check current `links[]`; if present, rewrite the frontmatter list without that entry; else no-op |
| `get`/`list` → `links[]` | `_ISSUE_FIELDS` extended with `links(direction,linkType(name),issues(idReadable))`; normalized per the direction rule above | parsed from the `links: [type:target, ...]` frontmatter list |

## Alternatives considered

- **Nested-dict local encoding** (`links: [{type: depends-on, target: WI-0003}]`-shaped YAML): rejected
  — `frontmatter.py` is deliberately a flat, stdlib-only parser (no PyYAML dependency); a flat
  `type:target` string list round-trips cleanly within that existing format, with no new escaping rules
  beyond the ones the id-charset already guarantees.
- **A `has-subtask` sugar verb from day one** (symmetric with `blocks`): rejected — no consumer needs
  the parent-looking-down view today; adding it speculatively would be exactly the kind of
  not-yet-needed richness ADR-0002 already declines for `comments[]`'s shape. The read-back gap is
  documented so it reads as an intentional scope boundary, not an oversight.
- **A default identity `linkTypeMap`** matching `stateMap`'s no-default posture: rejected — a link
  verb's dehyphenated form is a genuinely reasonable, mechanical default a project can start from
  without any configuration (unlike a `State`/`Priority` bundle's values, which have no natural
  relationship to CCPR's vocabulary at all).
- **Hard transactional link validation** (reject creating a link whose target doesn't exist, verified
  against both ends atomically): rejected as unnecessary complexity — `local`'s existence check and
  `youtrack`'s existing atomic-command-reject behaviour already give a hard failure on an invalid
  target without any new machinery.

## Consequences

- **Contract fixture grows by two ops × two backends**, plus the direction-normalization and
  idempotence assertions (a link added from one side must read correctly, with the right verb, from
  the other side too — not just a field-exists check).
- **One new provider-config key** (`workitems.youtrack.linkTypeMap`), with a default unlike its
  siblings (`stateMap`/`priorityMap`) — documented above as a deliberate asymmetry, not an
  inconsistency.
- **`local`'s frontmatter gains one more optional key** (`links`), absent-key-safe (`[]` default), no
  migration needed for existing item files.
- **A documented, intentional gap**: the parent-side view of `subtask-of` is not representable in this
  ADR's vocabulary. Revisit with a `has-subtask` sugar verb if a real consumer needs it.
