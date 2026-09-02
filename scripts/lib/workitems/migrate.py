"""migrate.py – `ccpr workitems migrate`: moves items from the current backend to a
target backend, once, reversibly (ADR-0004).

Mechanical only: uses the six-operation contract (list/get/create/set-status) — no
judgment calls, unlike `lift` (which needs a human for anything ambiguous). Per
ADR-0004:

- Writes docs/workitems-idmap.yml (source-id -> target-id, plus which migration
  phases have completed for that item) so references in HANDOVER/learnings stay
  resolvable, and puts the source id in each target item's description (reverse
  lookup / provenance).
- Archives the source store (never deletes) — the rollback path (set `provider` back
  to the source and keep working). Only applies when the source is filesystem-based
  (`local`); a remote source has nothing to archive.
- Is safe to re-run: resumes from the existing id-map instead of recreating items
  already migrated, and a full second run (nothing left to migrate) is a no-op. An
  item present in the idmap is never recreated, even if some of its OWN phases
  (e.g. comments) are still incomplete — only the remaining phase(s) run.
- Leaves exactly one active backend afterward (ADR-0002) — the CLI dispatcher flips
  settings.json's `workitems.provider` to the target once migration completes.

The archive timestamp comes from an injected `clock` (a zero-arg callable returning a
datetime), never a bare `datetime.now()` call buried in the archiving logic, so tests
get a deterministic archive directory name.

## Idmap format (WI-0141)

One line per item: `source-id: target-id phase1,phase2,...` — phases sorted
alphabetically, comma-separated, no spaces. `created`/`status` are recorded as soon
as an item has been created in the target and had its status applied (mirroring the
single write the pre-phase-tracking code used to do at that same point); further
phases (`comments`, and later others) are recorded once THEIR work completes, each
with its own idmap write — so an abort mid-migration leaves the idmap accurately
reflecting how far a given item got, not just whether it exists in the target.

A line with no phase list (`source-id: target-id`, no trailing space+phases) is a
file left over from before phase-tracking existed — this code never wrote an idmap
entry before both create() and set_status() had already succeeded for that item (the
one-time write always happened strictly after both), so a phase-less line can only
ever mean `created` and `status` are done; nothing else is known.
"""

import collections
import datetime
import os
import re
import shutil

_PROVENANCE_PATTERN = re.compile(r"^Migrated from (.+)\.$", re.MULTILINE)

PHASE_CREATED = "created"
PHASE_STATUS = "status"
PHASE_COMMENTS = "comments"

# Two uses that happen to coincide, deliberately: (1) what a phase-less idmap line
# (see module docstring) is assumed to mean -- read_idmap's default for an old-format
# line -- and (2) the phase set migrate() itself writes the moment create()+
# set_status() succeed for an item -- migrate() has only ever written an idmap entry
# strictly after both, on any version of this code. Both facts point at the same
# value, so it is named once rather than duplicated at each use site.
_PHASES_AFTER_CREATE_AND_STATUS = frozenset({PHASE_CREATED, PHASE_STATUS})

# Every phase this run is responsible for completing, for `fully_migrated` (see
# _all_phases_complete). Comments only, for now (WI-0141) -- results/tags/links are
# deliberately out of scope; when they're added, they join this set, and NOTHING
# else about the idmap format has to change (see the module docstring).
_REQUIRED_PHASES = frozenset({PHASE_CREATED, PHASE_STATUS, PHASE_COMMENTS})

IdmapEntry = collections.namedtuple("IdmapEntry", ["target_id", "phases"])


def default_clock():
    return datetime.datetime.now()


def read_idmap(path):
    """Parse the idmap file into {source_id: IdmapEntry(target_id, phases)}. Returns
    {} if absent. See the module docstring for the on-disk format and what a
    phase-less line means."""
    if not os.path.isfile(path):
        return {}
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            source_id = key.strip()
            target_id, _, phase_str = value.strip().partition(" ")
            phase_str = phase_str.strip()
            phases = (
                frozenset(p.strip() for p in phase_str.split(","))
                if phase_str else _PHASES_AFTER_CREATE_AND_STATUS
            )
            mapping[source_id] = IdmapEntry(target_id=target_id, phases=phases)
    return mapping


def write_idmap(path, mapping):
    """Write the mapping atomically (temp file + rename), sorted for stable diffs.
    Every value must be an IdmapEntry with a non-empty `phases` set -- an entry is
    only ever written once at least one phase (created+status, at minimum) has
    actually completed, so an empty set would be lossy: it round-trips back through
    read_idmap indistinguishable from a legacy phase-less line (see module
    docstring), silently turning "nothing done yet" into "created+status done"."""
    lines = [
        "# Auto-generated by `ccpr workitems migrate` (ADR-0004): "
        "source-id: target-id [comma-separated completed phases]"
    ]
    for source_id in sorted(mapping):
        entry = mapping[source_id]
        if not entry.phases:
            raise ValueError(
                f"write_idmap: entry for {source_id!r} has no completed phases -- "
                "an idmap entry is only ever written once at least one phase has "
                "completed (see write_idmap's docstring)"
            )
        phase_str = ",".join(sorted(entry.phases))
        lines.append(f"{source_id}: {entry.target_id} {phase_str}")
    text = "\n".join(lines) + "\n"

    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp_path, path)


def migrate(source_backend, target_backend, idmap_path, source_workitems_dir=None,
            archive_root=None, clock=None):
    """Run one migration pass. Safe to call repeatedly (resumes from idmap_path).

    Args:
        source_backend: instance implementing the six-op contract to migrate FROM.
        target_backend: instance implementing the six-op contract to migrate TO.
        idmap_path: where to read/write the source-id -> target-id mapping.
        source_workitems_dir: the source's on-disk directory to archive once fully
            migrated, if the source is filesystem-based (None for a remote source —
            nothing to archive).
        archive_root: directory the archive is created alongside (defaults to the
            parent of source_workitems_dir).
        clock: zero-arg callable returning a datetime (defaults to datetime.now) —
            injected so tests get a deterministic archive directory name.

    Comment failures propagate uncaught, exactly like create()/set_status() always
    have (matching a real process crash) -- comment() has no dedup of its own, so a
    caller resuming after such a crash relies on the idmap's per-item phase record
    (see the module docstring), not on the target rejecting a duplicate.

    Returns a report dict: migrated ([(source_id, target_id), ...]),
    skipped_already_migrated ([source_id, ...]), archived (bool), and archive_path
    (only present if archived).
    """
    clock = clock or default_clock
    idmap = read_idmap(idmap_path)
    # Crash recovery for the window between create()/set_status() succeeding in the
    # target and the idmap write that records the pairing: if a prior run created an
    # item and then died before that write, the idmap alone won't show it as
    # migrated. Scan the target for its own provenance marker first, so such an item
    # is ADOPTED (its id recorded in the idmap) instead of recreated.
    existing_markers = _existing_migration_markers(target_backend)

    source_items = source_backend.list()
    report = {"migrated": [], "skipped_already_migrated": []}

    for item in source_items:
        source_id = item["id"]
        entry = idmap.get(source_id)

        if entry is None:
            if source_id in existing_markers:
                target_id = existing_markers[source_id]
            else:
                description = item.get("description") or ""
                provenance = f"Migrated from {source_id}."
                description = f"{description}\n\n{provenance}" if description else provenance

                created = target_backend.create(
                    title=item["title"], item_type=item.get("type"),
                    owner=item.get("owner"), description=description,
                )
                target_id = created["id"]

            # Re-applied unconditionally, even for an adopted item: a crash could
            # have happened before set_status() ran in the prior attempt, so the
            # adopted item might still be sitting at its create-time default
            # (Backlog).
            status = item.get("status")
            if status and status != "Backlog":
                target_backend.set_status(target_id, status)

            entry = IdmapEntry(target_id=target_id, phases=_PHASES_AFTER_CREATE_AND_STATUS)
            idmap[source_id] = entry
            write_idmap(idmap_path, idmap)  # incremental: survives a mid-run crash
            report["migrated"].append((source_id, target_id))
        else:
            report["skipped_already_migrated"].append(source_id)

        # Resume never re-attempts create()/set_status() above for an item already
        # in the idmap -- but its OWN remaining phase(s) still run every call, until
        # they're recorded done. Comments is the only phase beyond created/status
        # today (WI-0141); a future phase slots in the same way.
        if PHASE_COMMENTS not in entry.phases:
            _migrate_comments(item, target_backend, entry.target_id)
            entry = IdmapEntry(target_id=entry.target_id, phases=entry.phases | {PHASE_COMMENTS})
            idmap[source_id] = entry
            write_idmap(idmap_path, idmap)

    report["archived"] = False
    fully_migrated = _all_phases_complete(idmap, source_items)
    report["fully_migrated"] = fully_migrated
    if fully_migrated and source_workitems_dir is not None and os.path.isdir(source_workitems_dir):
        # Re-check immediately before archiving: an item created in the source
        # between the initial list() snapshot (above) and this point would
        # otherwise be swept into the archive unmigrated and silently lost.
        original_ids = {item["id"] for item in source_items}
        current_ids = {item["id"] for item in source_backend.list()}
        new_ids = sorted(current_ids - original_ids)
        if new_ids:
            report["archive_skipped_new_items_appeared"] = new_ids
        else:
            archive_path = _archive(source_workitems_dir, archive_root, clock)
            report["archived"] = True
            report["archive_path"] = archive_path
            # The rollback path (ADR-0004): archiving moves the directory, it never
            # deletes it, but nothing moves it back automatically. Spell out the
            # exact command rather than leaving that to memory -- move it back,
            # then set workitems.provider back to the source (the CLI adds that
            # second half, which needs the provider NAME, not just instances).
            report["restore_command"] = f"mv {archive_path} {source_workitems_dir}"

    return report


def _all_phases_complete(idmap, source_items):
    """The definition `fully_migrated` needs once idmap entries track PER-PHASE
    completion (WI-0141): bare id-presence ("item id in idmap") stopped being an
    accurate description the moment an item could sit in the idmap with its
    comments phase still pending. Gates archiving the source directory and (in
    scripts/workitems.py) flipping the active provider.

    Defense in depth, not the sole guard: migrate()'s loop never returns a report
    at all while an item it attempted this run is left incomplete (an uncaught
    comment failure raises instead, exactly like create()/set_status() always
    have -- see migrate()'s own docstring) -- so at today's one call site, this
    formula and the old id-presence check agree on every reachable input. It earns
    its keep the day a phase ever becomes best-effort (warn-and-continue instead of
    raise): id-presence alone would then silently accept an item that never
    finished, and this formula would not."""
    return all(
        item["id"] in idmap and _REQUIRED_PHASES <= idmap[item["id"]].phases
        for item in source_items
    )


def _migrate_comments(source_item, target_backend, target_id):
    """Copies source_item's plain comments to target_id, resuming from wherever a
    prior attempt left off. comment() has no dedup of its own (unlike set_status,
    which plainly overwrites, or add_tag/add_link, which check membership before
    writing), so a mid-item abort must be survivable without risking a duplicate
    post.

    Re-derives progress LIVE from the target's own comment count (rather than a
    persisted per-comment checkpoint in the idmap): comments are appended in order
    and never edited or removed by this code, so "how many are already there" is
    exactly "how many of the source's list still need posting" -- no separate
    counter to keep in sync. Posts only the not-yet-posted TAIL, in source order, so
    a caller's assertion on ordering (not just count) holds after a resume."""
    source_comments = source_item.get("comments") or []
    if not source_comments:
        return
    already_posted = len(target_backend.get(target_id).get("comments") or [])
    for text in source_comments[already_posted:]:
        target_backend.comment(target_id, text)


def _existing_migration_markers(target_backend):
    """Map source_id -> target_id for every target item already carrying a
    "Migrated from <source_id>." provenance line (mirrors lift.py's own
    Lift-Key:/_existing_lift_keys pattern for the same crash-recovery purpose)."""
    markers = {}
    for item in target_backend.list():
        description = item.get("description") or ""
        for match in _PROVENANCE_PATTERN.finditer(description):
            markers[match.group(1)] = item["id"]
    return markers


def _archive(source_dir, archive_root, clock):
    stamp = clock().strftime("%Y%m%d%H%M%S")
    root = archive_root or os.path.dirname(os.path.abspath(source_dir))
    archive_path = os.path.join(root, f".workitems-archive-{stamp}")
    shutil.move(source_dir, archive_path)
    return archive_path
