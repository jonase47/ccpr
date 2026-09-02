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

from workitems import WorkItemError

_PROVENANCE_PATTERN = re.compile(r"^Migrated from (.+)\.$", re.MULTILINE)

PHASE_CREATED = "created"
PHASE_STATUS = "status"
PHASE_COMMENTS = "comments"
PHASE_LINKS = "links"

# Two uses that happen to coincide, deliberately: (1) what a phase-less idmap line
# (see module docstring) is assumed to mean -- read_idmap's default for an old-format
# line -- and (2) the phase set migrate() itself writes the moment create()+
# set_status() succeed for an item -- migrate() has only ever written an idmap entry
# strictly after both, on any version of this code. Both facts point at the same
# value, so it is named once rather than duplicated at each use site.
_PHASES_AFTER_CREATE_AND_STATUS = frozenset({PHASE_CREATED, PHASE_STATUS})

# Every phase this run is responsible for completing, for `fully_migrated` (see
# _all_phases_complete). Comments and links, for now (WI-0141) -- results/tags are
# deliberately out of scope; when they're added, they join this set, and NOTHING
# else about the idmap format has to change (see the module docstring).
_REQUIRED_PHASES = frozenset({PHASE_CREATED, PHASE_STATUS, PHASE_COMMENTS, PHASE_LINKS})

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
    (see the module docstring), not on the target rejecting a duplicate. A failed
    POSTCONDITION check (see _verify_comments_migrated) propagates uncaught the
    same way: PHASE_COMMENTS is only ever recorded once the target has actually
    been re-read and shown to carry every source comment, not merely once
    _migrate_comments returned without an exception.

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
            # Hard postcondition, not a trust of _migrate_comments' own return:
            # re-read the target and confirm every source comment actually
            # landed before PHASE_COMMENTS is recorded. Raises uncaught (see
            # migrate()'s own docstring) rather than recording a phase that
            # only LOOKS complete because posting didn't raise.
            _verify_comments_migrated(item, target_backend, entry.target_id)
            entry = IdmapEntry(target_id=entry.target_id, phases=entry.phases | {PHASE_COMMENTS})
            idmap[source_id] = entry
            write_idmap(idmap_path, idmap)

    # Second pass, deliberately separate from the loop above: add_link() needs the
    # PARTNER's target id, which does not exist until the partner item has itself
    # been created -- so a link cannot be migrated inline the way comments can. By
    # the time this pass starts, every item in source_items has an idmap entry (the
    # loop above never returns without one, for every item it processed -- see
    # migrate()'s own docstring on comment failures propagating uncaught, which
    # applies here too), so every link's target is resolvable through the idmap.
    for item in source_items:
        source_id = item["id"]
        entry = idmap[source_id]
        if PHASE_LINKS not in entry.phases:
            _migrate_links(item, target_backend, entry.target_id, idmap)
            # Hard postcondition, same discipline as _verify_comments_migrated:
            # re-read the target and confirm every source link actually landed
            # before PHASE_LINKS is recorded.
            _verify_links_migrated(item, target_backend, entry.target_id, idmap)
            entry = IdmapEntry(target_id=entry.target_id, phases=entry.phases | {PHASE_LINKS})
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
    comment failure OR a failed postcondition verification raises instead, exactly
    like create()/set_status() always have -- see migrate()'s own docstring and
    _verify_comments_migrated) -- so at today's one call site, this formula and
    the old id-presence check agree on every reachable input. This was NOT always
    true: before the postcondition check existed, `_migrate_comments` could return
    without raising while having silently left a source comment un-posted (a
    foreign comment landing on the target between an aborted run and its resume
    could make the old count-based resume logic skip a real, still-unposted
    source comment -- see _migrate_comments' docstring) -- an item PHASE_COMMENTS
    then got recorded for that had not actually completed, exactly the gap
    id-presence-alone could never catch either. The postcondition check closes
    that gap by construction: PHASE_COMMENTS is only ever recorded after the
    target has been re-read and shown to carry every source comment. This formula
    earns its keep independently of that fix the day a phase ever becomes
    best-effort (warn-and-continue instead of raise): id-presence alone would
    then silently accept an item that never finished, and this formula would
    not."""
    return all(
        item["id"] in idmap and _REQUIRED_PHASES <= idmap[item["id"]].phases
        for item in source_items
    )


def _first_unmatched_source_index(source_comments, target_texts):
    """The core "how much of source is already on the target" walk, shared by
    _migrate_comments (to find what to post) and _verify_comments_migrated (to
    confirm nothing is missing): the longest PREFIX of source_comments that is an
    ORDERED SUBSEQUENCE of target_texts. Walks target_texts once, advancing a
    pointer into source_comments only when the current unmatched source text is
    seen -- a text on the target that does not match the pointer's current
    source text is simply skipped (it is either a foreign comment, e.g. left by
    a human, or one that hasn't been reached yet), never counted against the
    match and never removed from consideration.

    Returns the pointer's final position: source_comments[:pointer] is what's
    already present (matched, in order); source_comments[pointer:] is what
    still needs posting. Because the pointer only ever advances forward and
    only checks its OWN current position (never scans ahead into the rest of
    source_comments), the unmatched remainder is always a contiguous TAIL of
    source_comments, never comments scattered out of a prefix -- this is what
    lets both callers below simply slice at `pointer`.

    Deliberately order-aware (subsequence), not membership-aware (set): the real
    140-item work-item corpus contains exactly one pair of byte-identical
    comment texts within a single item's own comment list (WI-0077, a repeated
    "|---|---|---|" table-separator row, measured 02.09.2026). A set-based "is
    this text already present on the target" check would treat the second
    occurrence as already covered by the first and never post it -- silently
    dropping one of two genuinely distinct (if textually identical) comments.
    The subsequence walk above does not have this problem: each target
    occurrence can only ever advance the pointer past ONE corresponding source
    occurrence, so N identical source texts require N distinct target
    occurrences to be considered matched."""
    pointer = 0
    for text in target_texts:
        if pointer < len(source_comments) and text == source_comments[pointer]:
            pointer += 1
    return pointer


def _migrate_comments(source_item, target_backend, target_id):
    """Copies source_item's plain comments to target_id, resuming from wherever a
    prior attempt left off. comment() has no dedup of its own (unlike set_status,
    which plainly overwrites, or add_tag/add_link, which check membership before
    writing), so a mid-item abort must be survivable without risking a duplicate
    post.

    Re-derives progress LIVE from the target's own current comments (rather than
    a persisted per-comment checkpoint in the idmap) via
    _first_unmatched_source_index -- the longest prefix of source_comments that
    is an ordered subsequence of what's already on the target -- and posts only
    the remaining TAIL, in source order.

    This is deliberately NOT "compare against the target's TOTAL comment count"
    (the earlier, defective version of this function): that comparison is only
    correct while nothing but this migration ever writes a comment to the
    target. A human (or any other process) commenting on the target between an
    aborted run and its resume inflates the total count without being one of
    source_comments -- the count-based version would then skip past a real,
    still-unposted source comment as if it had already been copied, LOSING IT
    permanently once the phase was (incorrectly) recorded complete. The
    subsequence walk does not have this problem: a foreign comment is simply a
    target text that never matches the pointer's current source text, so it is
    skipped over rather than mistaken for progress.

    Three known limits of this rule, accepted rather than fixed:

    1. YouTrack's comments endpoint is append-only -- comment() and
       append_result() both POST a new comment; neither this backend nor a real
       YouTrack instance offers a way to insert one BETWEEN two that already
       exist. A newly posted comment (human or this code's own) therefore always
       lands strictly AFTER every comment already on the issue at that moment,
       and FakeYouTrackTransport's `_render_issue` returns `issue["comments"]`
       in that same append order (mirrored by the real backend's
       `_item_from_issue`, which iterates `issue.get("comments", [])` verbatim
       -- see youtrack.py). This is the basis on which the subsequence walk is
       safe: because nothing can be inserted retroactively into the middle of
       the target's comment list, the pointer never needs to "look back" past a
       text it already skipped. If this ever became false (some path could
       reorder or insert a comment out of append order), a foreign comment
       could land BETWEEN two already-transferred source comments and either be
       mismatched against the wrong pointer position or cause the walk to skip
       a real match -- the whole algorithm depends on read-back order being
       exactly write order.
    2. A foreign comment whose text happens to be byte-identical to the NEXT
       unposted source comment will be mistaken for it -- the subsequence walk
       matches on text alone, it has no way to know which process wrote a given
       comment. This is a known, accepted limitation, not something this rule
       tries to fix: closing it would require tagging every comment this code
       posts (e.g. a hidden marker, the way append_result() already does for
       result-links), which is out of scope here.
    3. A comment deleted from the target AFTER this code transferred it makes a
       later resume re-post it: the check only ever sees what is CURRENTLY
       present on the target, it has no memory of what it posted in an earlier
       run beyond what survives on the target itself.

    Read-back soundness: get()'s full comment list was verified against a real
    YouTrack instance at 600 comments (and a 60-comment probe) with no
    pagination truncation on the comments sub-field -- unlike GET /api/issues,
    which page_size_cap simulates truncating without an explicit "$top=-1" (see
    fake_youtrack_transport.py). The largest item in the current 140-item corpus
    has ~131 comments, well under the verified depth. Do not add `$top` handling
    to comment reads on the suspicion that pagination might apply there too --
    it doesn't; this was checked, not assumed."""
    source_comments = source_item.get("comments") or []
    if not source_comments:
        return
    target_texts = target_backend.get(target_id).get("comments") or []
    pointer = _first_unmatched_source_index(source_comments, target_texts)
    for text in source_comments[pointer:]:
        target_backend.comment(target_id, text)


def _verify_comments_migrated(source_item, target_backend, target_id):
    """Hard postcondition for the comments phase: re-reads the target (a FRESH
    read, not the one _migrate_comments already made -- the whole point is not
    to trust that call's own view of what it accomplished) and confirms every
    text in source_item's comments is present as an ordered subsequence, using
    the same walk _migrate_comments uses to decide what to post. If anything is
    still missing, raises -- uncaught, exactly like a comment() failure already
    does (see migrate()'s own docstring) -- rather than letting the caller
    record PHASE_COMMENTS for an item that only APPEARED to finish because
    posting didn't raise."""
    source_comments = source_item.get("comments") or []
    if not source_comments:
        return
    target_texts = target_backend.get(target_id).get("comments") or []
    pointer = _first_unmatched_source_index(source_comments, target_texts)
    if pointer != len(source_comments):
        missing = source_comments[pointer:]
        raise WorkItemError(
            f"comments migration postcondition failed for target {target_id!r}: "
            f"{len(missing)} of {len(source_comments)} source comment(s) not "
            f"found on the target as an ordered subsequence after posting "
            f"(first missing: {missing[0]!r})"
        )


def _resolve_link_target_id(link_target_source_id, idmap):
    """A source link's `target` field is a SOURCE id (e.g. `WI-0029`) -- never a
    target-backend id -- so it must be resolved through the idmap, the only
    trustworthy mapping table (WI-NNNN -> CCP-N numeric alignment is dead: a
    failed create() burns a target-side number, measured in an earlier pilot, so
    the two numberings can drift apart). Raises loud rather than skipping: by the
    time the links pass runs, every item THIS run's own first pass attempted has
    an idmap entry (see migrate()'s docstring on the two-pass split), so a miss
    here can only mean a resume whose idmap lost an entry for an item that pass
    would otherwise have (re-)created -- silently dropping the link would hide
    exactly that kind of data loss."""
    entry = idmap.get(link_target_source_id)
    if entry is None:
        raise WorkItemError(
            f"link target {link_target_source_id!r} is missing from the idmap -- "
            "cannot resolve it to a target-backend id. This should be unreachable "
            "within a single migrate() call (every source item gets an idmap entry "
            "before the links pass starts); it means the idmap on disk lost an "
            "entry for an item that should already have one."
        )
    return entry.target_id


def _migrate_links(source_item, target_backend, target_id, idmap):
    """Recreates source_item's own links on target_id, one add_link() call per
    source link, each resolved through the idmap (see _resolve_link_target_id).
    add_link() is idempotent for the same direction (checks the current, already
    direction-normalized links[] first -- see youtrack.py/local.py), so re-running
    this on a resume never duplicates an edge already present on the target."""
    source_links = source_item.get("links") or []
    for link in source_links:
        resolved_target_id = _resolve_link_target_id(link["target"], idmap)
        target_backend.add_link(target_id, link["type"], resolved_target_id)


def _verify_links_migrated(source_item, target_backend, target_id, idmap):
    """Hard postcondition for the links phase, mirroring
    _verify_comments_migrated: re-reads the target (a FRESH read) and confirms
    every source link is PRESENT on the target -- deliberately not set equality.
    A YouTrack-shaped target reports MORE links than the source: every edge shows
    up on both endpoints, once as `depends-on` and once as the read-only inverse
    `blocks` (verified against a live instance, see the senior-developer's
    briefing for this task) -- so asserting the target's link set equals the
    source's would fail on ordinary, correctly-migrated data. Raises -- uncaught,
    exactly like a comments postcondition failure already does -- rather than
    letting the caller record PHASE_LINKS for an item that only APPEARED to
    finish because add_link() didn't raise."""
    source_links = source_item.get("links") or []
    if not source_links:
        return
    current_links = target_backend.get(target_id).get("links") or []
    missing = []
    for link in source_links:
        resolved_target_id = _resolve_link_target_id(link["target"], idmap)
        expected = {"type": link["type"], "target": resolved_target_id}
        if expected not in current_links:
            missing.append(link)
    if missing:
        raise WorkItemError(
            f"links migration postcondition failed for target {target_id!r}: "
            f"{len(missing)} of {len(source_links)} source link(s) not found on "
            f"the target after migrating (first missing: {missing[0]!r})"
        )


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
