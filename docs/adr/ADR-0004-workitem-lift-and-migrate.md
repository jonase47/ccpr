---
kind: adr
adr_id: ADR-0004
adr_status: proposed
status: draft
last_updated: 02.09.2026
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

## Addendum (02.09.2026): Field scope, the id-map's phase-tracking format, and unrepresentable values

### Context

The original decision above describes the id-map as `local-id ↔ remote-id` and does not enumerate
which fields `migrate` actually transfers. Both are now out of date: `migrate`
(`scripts/lib/workitems/migrate.py`) has grown per-item phase tracking, and a real pilot against a live
YouTrack instance
(01.09.2026, `docs/.handover-archive/2026-09-01-youtrack-pilot-report.md`,
`docs/.handover-archive/2026-08-28-open-findings.md` findings #46–#48) measured two different
unrepresentable-value cases that needed two different answers, and one setup gap this ADR's sibling
(ADR-0003) did not name.

### Decision

**Field scope.** `create()` carries `title`, `description` (with a `Migrated from <source-id>.`
provenance line appended — `migrate.py:300-302`), and, best-effort (warn on rejection, continue —
`youtrack.py`'s `_apply_optional_create_field`/`_apply_tag_with_visibility`), `type`, `owner`, and
`tags`. `status` is applied right after create, but only when it is not the target's own create-time
default (`"Backlog"` — `migrate.py:320-322`). `priority` is reapplied unconditionally on every pass
that just created or adopted an item, but only when the source actually carries one
(`migrate.py:336-338`) — see "unrepresentable values" below for why. Four further phases each carry
their own resumable, read-back-verified transfer: comments, classified `## Result` prose, classified
`## Result` refs, and links (`PHASE_COMMENTS`/`PHASE_RESULT_PROSE`/`PHASE_RESULT_REFS`/`PHASE_LINKS`,
`migrate.py:53-70`). `owner` and `type` get no dedicated report entry: measured against the real
141-item corpus, `owner` is empty on every item (nothing it could swallow) and `type` is set on every
item with zero measured loss (`migrate.py:228-240`). `sprint` is never migrated at all (see below).

**What happens to a value the target cannot represent — two cases, decided differently.**

- *Priority* — an item with no source priority arrives with **none**. `migrate.py` never calls
  `set_priority()` when `item.get("priority")` is falsy (`migrate.py:336-338`), and neither backend's
  `create()` takes a `priority=` parameter, so a freshly created target item genuinely starts with no
  priority set at all. This corrects a defect the 01.09.2026 pilot measured against the live instance
  before this rule existed: WI-0077 carries no local priority, but arrived in YouTrack reading
  `Medium` — the project's `Priority` field was required (`canBeEmpty=False`) with default `Normal`,
  which `priorityMap` un-maps to `Medium` (`docs/.handover-archive/2026-09-01-youtrack-pilot-report.md`
  lines 60–72; the same mechanism measured across 130 of 137 corpus items in
  `docs/.handover-archive/2026-08-28-open-findings.md` finding #47). "An earlier pilot measured a
  missing priority being INVENTED (`None` -> `Medium`) before this design, which is worse than a lost
  field because it looks like real data" (`migrate.py:330-335`). Making this safe on the target side
  also required a target-instance field change — see ADR-0003's own addendum.
- *Sprint* — never migrated, a deliberate PO decision, not a best-effort gap. The one corpus item
  carrying a sprint value (`0`) has no home in the target's shared `Sprints` bundle, and a dedicated
  bundle for a single item costs more than the loss (`migrate.py:242-246`). Every source item that
  carried a sprint is named in `report["sprint_dropped"]`, computed over the full source set regardless
  of skip/migrate status this run — a static fact about the corpus, not a per-run event
  (`migrate.py:434-444`) — so the omission "reads as a decision on the record, not a silently missing
  field."

**The id-map format — no longer flat.** One line per item:
`source-id: target-id phase1,phase2,...` (phases sorted alphabetically, comma-separated, no spaces —
`migrate.py:26-40`, `write_idmap` at `migrate.py:168-194`). The six phase names, copied verbatim from
`migrate.py:53-70`: `created`, `status`, `comments`, `result-prose`, `links`, `result-refs`. A line
with no trailing phase list (`source-id: target-id`, nothing after the target id) is left over from a
version of this code before phase-tracking existed: `read_idmap` treats it as `{created, status}`
(`migrate.py:160-163`, the `_PHASES_AFTER_CREATE_AND_STATUS` constant at `migrate.py:91`) — the only
two phases a pre-phase-tracking build could ever have completed before writing an entry at all, since
that code never wrote an idmap entry before both `create()` and `set_status()` had already succeeded
(module docstring, `migrate.py:36-40`). Each phase is written to the map only after a hard
postcondition re-reads the target and confirms the corresponding data actually landed — e.g.
`_verify_comments_migrated` (`migrate.py:736-761`) — never merely because the posting call returned
without raising.

**`fully_migrated` and its two gates.** `_all_phases_complete` (`migrate.py:449-479`) requires every
item in `_REQUIRED_PHASES` — `created`, `status`, `comments`, `result-prose`, `links`, `result-refs`
(tags and priority deliberately excluded, see below) — before it reports `fully_migrated: True`.
`report["fully_migrated"]` gates two actions: **archiving** the source's on-disk directory
(`migrate.py:414`, reached only `if fully_migrated`) and **flipping** `workitems.provider` to the
target (`scripts/workitems.py:427-428`, `_update_provider_in_settings` called only
`if report.get("fully_migrated")`). The gate matters because both actions are effectively one-way in
practice: archiving moves (not deletes) the source directory, and once the provider is flipped, a
second `migrate` invocation against the same target is refused outright — it would treat the
now-active target as the source, find none of its ids in the idmap (whose keys are the old source
ids), and recreate every item (`scripts/workitems.py:396-407`). A partially migrated run that had
archived and flipped anyway would leave a project with an incomplete target store and no clean way
back — hence gating both on every item's every required phase being verified complete.

**Tags are reported, not gated.** Tags are excluded from `_REQUIRED_PHASES` (`migrate.py:93-104`) and
never block `fully_migrated`. `report["tags"]` carries per-item and total requested/applied/missing/
visibility-not-set counts (`_record_tag_diff`, `migrate.py:952-979`). A tag that could not be made
visible carries one of four reason strings, copied verbatim from `youtrack.py`:
`TAG_VISIBILITY_NOT_CONFIGURED = "not_configured"` (`youtrack.py:109`),
`TAG_VISIBILITY_GROUP_NOT_FOUND = "group_not_found"` (`youtrack.py:110`),
`TAG_VISIBILITY_GROUP_AMBIGUOUS = "group_ambiguous"` (`youtrack.py:111`), and
`TAG_VISIBILITY_WRITE_REJECTED = "write_rejected"` (`youtrack.py:127`, added 02.09.2026 — "the
throwing one was not excluded, it was overlooked", per that constant's own module comment). The first
three name a missing configuration; the fourth is a genuine instance-level failure and additionally
carries the instance's own error message (`youtrack.py:118-127`). None of the four ever gates
`fully_migrated`: "a missing configuration is a state of the environment, not a failure of the
migration, and visibility is repairable afterwards while a lost comment is not"
(`migrate.py:280-285`).
