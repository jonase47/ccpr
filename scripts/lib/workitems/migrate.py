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

## Idmap format

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
import sys

from workitems import WorkItemError, normalize_result_ref

_PROVENANCE_PATTERN = re.compile(r"^Migrated from (.+)\.$", re.MULTILINE)

PHASE_CREATED = "created"
PHASE_STATUS = "status"
PHASE_COMMENTS = "comments"
# Deliberately a SEPARATE, NEW phase from PHASE_COMMENTS -- not a widened
# meaning of it. An earlier version of this code folded classified `## Result`
# PROSE into PHASE_COMMENTS's own source list (see _comment_source_texts'
# history) without renaming the phase; an idmap written by a build that
# predates that change already carries `comments` (correctly, by ITS
# meaning -- only item["comments"] had been copied), so a resumed run against
# such an idmap silently skipped the now-wider phase and the prose was lost
# for good, with the run still reporting success. Splitting it into its own
# phase means an old idmap's `comments` marker stays true to what it always
# meant, and the new phase's absence from that idmap is exactly what makes a
# resume pick the prose up -- no marker rewriting needed. See
# _migrate_result_prose / _verify_result_prose_migrated.
PHASE_RESULT_PROSE = "result-prose"
PHASE_LINKS = "links"
PHASE_RESULT_REFS = "result-refs"

# `## Result` entry classifier (rule C, PO decision): an entry is a REF only if
# EVERY whitespace-separated token is a bare sha (7-40 lowercase hex chars, with
# an optional "user@"-style prefix) or a bare URL -- anything else (including a
# sha embedded in prose, e.g. "Commit: `15ca8cf` (...)") is prose and travels as
# a comment instead. Deliberately narrow: widening it to catch embedded shas is
# an explicit non-goal (measured 02.09.2026: 18 such entries in the real corpus,
# left as comments on purpose). Matched against the real 141-item corpus: 142 of
# 811 `## Result` entries classify as refs, carrying 153 tokens (some entries
# hold two shas -- both must match, not just the first).
_RESULT_REF_TOKEN_PATTERN = re.compile(
    r"^(?:(?:[A-Za-z0-9._/-]+@)?[0-9a-f]{7,40}|https?://\S+)$"
)

# Two uses that happen to coincide, deliberately: (1) what a phase-less idmap line
# (see module docstring) is assumed to mean -- read_idmap's default for an old-format
# line -- and (2) the phase set migrate() itself writes the moment create()+
# set_status() succeed for an item -- migrate() has only ever written an idmap entry
# strictly after both, on any version of this code. Both facts point at the same
# value, so it is named once rather than duplicated at each use site.
_PHASES_AFTER_CREATE_AND_STATUS = frozenset({PHASE_CREATED, PHASE_STATUS})

# Every phase this run is responsible for completing, for `fully_migrated` (see
# _all_phases_complete). Comments, result-prose, links and result-refs -- tags
# and priority are DELIBERATELY excluded (see migrate()'s own docstring for
# why): tags are best-effort on every path that applies them -- create()'s
# own contract (see _apply_optional_create_field) and, for an adopted item,
# add_tag() wrapped the same way (see _apply_tags_to_adopted_item) -- and
# reported instead of gated; priority is a
# plain idempotent overwrite with nothing to resume. When another phase joins
# this set, NOTHING else about the idmap format has to change (see the module
# docstring).
_REQUIRED_PHASES = frozenset({
    PHASE_CREATED, PHASE_STATUS, PHASE_COMMENTS, PHASE_RESULT_PROSE,
    PHASE_LINKS, PHASE_RESULT_REFS,
})


def _is_result_ref(entry):
    """Rule C (PO decision, see _RESULT_REF_TOKEN_PATTERN): True only if every
    whitespace-separated token in `entry` matches the ref pattern. An entry with
    no non-whitespace tokens at all is never a ref (there is nothing to migrate
    as one)."""
    tokens = entry.split()
    if not tokens:
        return False
    return all(_RESULT_REF_TOKEN_PATTERN.match(token) for token in tokens)


def _classify_result_entries(entries):
    """Splits a source item's `result-link` entries into (refs, prose) by rule C,
    preserving each sublist's own relative order from `entries`."""
    refs = []
    prose = []
    for entry in entries:
        (refs if _is_result_ref(entry) else prose).append(entry)
    return refs, prose


def _ref_result_entries(item):
    """The result-refs phase's source list, normalized through the SAME edge-
    whitespace rule `append_result()` applies on write
    (`workitems.normalize_result_ref`) -- review follow-up, 02.09.2026. Before
    this normalization existed, `append_result()` wrote a ref's raw text
    byte-faithfully, so comparing this list against a target's read-back
    values (also raw, at the time) was comparing like with like. Once
    `append_result()` started trimming edge whitespace on write (see
    `normalize_result_ref`'s own docstring), a PRE-EXISTING source entry that
    still carries edge whitespace (measured 02.09.2026: 34 of the live
    corpus's result-link entries) would post through `append_result()`
    correctly trimmed, but the postcondition compared THIS function's raw,
    untrimmed text against the target's now-trimmed value -- an item that
    migrated correctly would fail its own postcondition on every subsequent
    run. Normalizing HERE, the single place both `_migrate_result_refs` and
    `_verify_result_refs_migrated` read their source list from, means there is
    exactly one rule for "the same ref" -- neither caller needs (or is
    permitted) its own second definition. Never raises for an already-
    classified ref: `_is_result_ref`/rule C only accepts an entry with at
    least one non-whitespace token, and `normalize_result_ref` only strips
    edges, so a ref's content survives the strip unconditionally.

    The prose sibling, `_prose_result_entries`, deliberately does NOT do this
    -- classified prose travels through `comment()`, which was never given a
    `normalize_result_ref()` call (a comment is prose, byte-faithful by
    design; see `normalize_result_ref`'s own docstring and
    ResultRefEdgeWhitespaceMigrationTest's comments-phase counter-proof in
    test_migrate.py)."""
    refs, _ = _classify_result_entries(item.get("result-link") or [])
    return [normalize_result_ref(ref) for ref in refs]


def _prose_result_entries(item):
    _, prose = _classify_result_entries(item.get("result-link") or [])
    return prose

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
    skipped_already_migrated ([source_id, ...]), archived (bool), archive_path
    (only present if archived), tags (per-item + total requested/applied/missing,
    see _record_tag_diff), sprint_dropped ([{"source_id", "value"}, ...] for every
    source item that carried a sprint -- see below), and fully_migrated (bool).

    `owner` and `type` go through the SAME create()-time best-effort path as tags
    (see youtrack.py's create()/_apply_optional_create_field) but are deliberately
    NOT given their own report entry: measured against the real corpus, `owner` is
    empty on every one of the 141 items (nothing it could ever swallow today) and
    `type` is set on every item with zero measured loss. Tags, by contrast, has a
    demonstrated, reachable swallow path (test_create_with_an_unmappable_tag_
    succeeds_and_leaves_no_orphan in test_youtrack.py) and a real corpus with 259
    assignments across 35 distinct tags -- real risk earns a report, zero-measured
    risk does not (YAGNI). If a future corpus or a project's own workflow ever
    starts rejecting an owner/type value, the mechanism to report it is the exact
    same shape as _record_tag_diff (create()'s return value already carries
    "owner"/"type" for comparison) -- extend by adding a call, not by inventing a
    new pattern.

    Sprint is never migrated at all (a separate PO decision, not a best-effort
    gap): the one sprint-carrying item's value has no home in the target's shared
    Sprints bundle, and a dedicated bundle for a single item costs more than the
    loss. `report["sprint_dropped"]` names every source item that carried one, so
    the omission reads as a decision on the record, not a silently missing field.
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
    report = {
        "migrated": [], "skipped_already_migrated": [],
        # Tags are best-effort, both at create() time (see
        # _apply_optional_create_field in youtrack.py) and on the adopted-item
        # path (see _apply_tags_to_adopted_item, which wraps add_tag() with
        # the same discipline) -- a rejected tag simply vanishes, by design,
        # with no exception propagating out of migrate(). This report is the
        # ONLY place that vanishing becomes visible. Per item AND in total,
        # always present (even all-zero: an absent field is not the same
        # statement as a zero) -- see _record_tag_diff.
        #
        # total_visibility_not_set / each item's own "visibility_not_set" list
        # (PO decision, verbatim in substance): a tag counts as `applied` the
        # moment it's on the item, regardless of whether its VISIBILITY was
        # ever set -- an unconfigured/unresolvable/ambiguous
        # tagVisibilityGroup still creates and applies the tag, just with its
        # default (private) visibility, and the only prior trace was a
        # stderr warning this report never collected (see youtrack.py's
        # TAG_VISIBILITY_NOT_CONFIGURED/_GROUP_NOT_FOUND/_GROUP_AMBIGUOUS).
        # A fourth reason, TAG_VISIBILITY_WRITE_REJECTED (PO decision,
        # 02.09.2026, added after the original three-reason enumeration --
        # see that constant's own module-level comment in youtrack.py), is a
        # genuine instance failure rather than a missing setting; its entry
        # additionally carries the instance's own message. NEVER gated into
        # fully_migrated (see _all_phases_complete / _REQUIRED_PHASES, which
        # excludes tags entirely): a missing configuration is a state of the
        # environment, not a failure of the migration, and visibility is
        # repairable afterwards while a lost comment is not -- the same
        # holds for a write that was rejected once but would succeed on
        # retry.
        "tags": {
            "items": [], "total_requested": 0, "total_applied": 0, "total_missing": 0,
            "total_visibility_not_set": 0,
        },
    }

    for item in source_items:
        source_id = item["id"]
        entry = idmap.get(source_id)

        if entry is None:
            if source_id in existing_markers:
                target_id = existing_markers[source_id]
                # Same reasoning as status/priority just below: a crash could
                # have happened before tags ran in the prior attempt, so an
                # adopted item might still be sitting with none of its source
                # tags applied. Unlike status/priority, create(tags=...) is
                # not available here -- the target item already exists -- so
                # this goes through add_tag() instead (see
                # _apply_tags_to_adopted_item for why that also needs its own
                # best-effort wrapping, unlike create()'s own tag loop, which
                # already gets that for free).
                requested_tags = item.get("tags") or []
                _apply_tags_to_adopted_item(
                    report, target_backend, source_id, target_id, requested_tags,
                )
            else:
                description = item.get("description") or ""
                provenance = f"Migrated from {source_id}."
                description = f"{description}\n\n{provenance}" if description else provenance

                requested_tags = item.get("tags") or []
                created = target_backend.create(
                    title=item["title"], item_type=item.get("type"),
                    owner=item.get("owner"), description=description,
                    tags=requested_tags,
                )
                target_id = created["id"]
                _record_tag_diff(
                    report, source_id, target_id, requested_tags, created.get("tags") or [],
                    _tag_visibility_outcomes(target_backend),
                )

            # Re-applied unconditionally, even for an adopted item: a crash could
            # have happened before set_status() ran in the prior attempt, so the
            # adopted item might still be sitting at its create-time default
            # (Backlog).
            status = item.get("status")
            if status and status != "Backlog":
                target_backend.set_status(target_id, status)

            # Same reasoning as status: reapplied unconditionally on every
            # entry-is-None pass (fresh create OR crash-recovered adoption),
            # never resumed/tracked as an idmap phase (see migrate()'s own
            # docstring). Unlike status, there is no "skip because create()
            # already set a default" case -- neither backend's create() takes
            # a priority= param, so the target genuinely starts with NO
            # priority regardless of the source. An item with no source
            # priority is therefore simply never touched here, which is what
            # keeps the target's priority absent too -- an earlier pilot
            # measured a missing priority being INVENTED (None -> "Medium")
            # before this design, which is worse than a lost field because it
            # looks like real data.
            priority = item.get("priority")
            if priority:
                target_backend.set_priority(target_id, priority)

            entry = IdmapEntry(target_id=target_id, phases=_PHASES_AFTER_CREATE_AND_STATUS)
            idmap[source_id] = entry
            write_idmap(idmap_path, idmap)  # incremental: survives a mid-run crash
            report["migrated"].append((source_id, target_id))
        else:
            report["skipped_already_migrated"].append(source_id)

        # Resume never re-attempts create()/set_status() above for an item already
        # in the idmap -- but its OWN remaining phase(s) still run every call, until
        # they're recorded done. Comments, result-prose and result-refs are the
        # phases beyond created/status today; a future phase slots in the same way.
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

        # Deliberately AFTER the comments block above, not merged into it (see
        # PHASE_RESULT_PROSE's own docstring for why the two are separate
        # phases): running comments first keeps an uninterrupted run's posting
        # order identical to what it was before this phase split (plain
        # comments, then prose), and on a resume it means the prose phase
        # always sees whatever plain comments already landed as part of the
        # target's current comments list, exactly like a foreign comment.
        if PHASE_RESULT_PROSE not in entry.phases:
            _migrate_result_prose(item, target_backend, entry.target_id)
            # Hard postcondition, same discipline as _verify_comments_migrated:
            # re-read the target's comments channel and confirm every
            # classified prose entry actually landed before PHASE_RESULT_PROSE
            # is recorded.
            _verify_result_prose_migrated(item, target_backend, entry.target_id)
            entry = IdmapEntry(target_id=entry.target_id, phases=entry.phases | {PHASE_RESULT_PROSE})
            idmap[source_id] = entry
            write_idmap(idmap_path, idmap)

        if PHASE_RESULT_REFS not in entry.phases:
            _migrate_result_refs(item, target_backend, entry.target_id)
            # Hard postcondition, same discipline as _verify_comments_migrated:
            # re-read the target's OWN result-link channel and confirm every
            # source ref actually landed before PHASE_RESULT_REFS is recorded.
            _verify_result_refs_migrated(item, target_backend, entry.target_id)
            entry = IdmapEntry(target_id=entry.target_id, phases=entry.phases | {PHASE_RESULT_REFS})
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

    # Sprint is deliberately never migrated (ADR-0004 follow-up, PO decision):
    # the real corpus's one sprint-carrying item's value does not exist in the
    # target's shared Sprints bundle, and a dedicated bundle for a single item
    # costs more than the loss. Computed over ALL source_items regardless of
    # skip/migrate status this run (a static fact about the corpus, not a
    # per-run event) so a silent omission and this deliberate one never look
    # alike -- named here, not just left absent from the report.
    report["sprint_dropped"] = [
        {"source_id": item["id"], "value": item["sprint"]}
        for item in source_items if item.get("sprint")
    ]

    return report


def _all_phases_complete(idmap, source_items):
    """The definition `fully_migrated` needs once idmap entries track PER-PHASE
    completion: bare id-presence ("item id in idmap") stopped being an
    accurate description the moment an item could sit in the idmap with its
    comments phase still pending. Gates archiving the source directory and (in
    scripts/workitems.py) flipping the active provider.

    Defense in depth, not the sole guard: migrate()'s loop never returns a report
    at all while an item it attempted this run is left incomplete -- an uncaught
    comment failure, an uncaught link failure, or a failed postcondition
    verification for either phase raises instead, exactly like create()/set_status()
    always have -- see migrate()'s own docstring, _verify_comments_migrated, and
    _verify_links_migrated -- so at today's one call site, this formula and the old
    id-presence check agree on every reachable input. This was NOT always
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


def _comment_source_texts(item):
    """The comments phase's source list: `item["comments"]` verbatim, nothing
    else. An earlier version of this function also appended classified
    `## Result` PROSE (see _prose_result_entries), riding PHASE_COMMENTS's own
    resume marker -- see PHASE_RESULT_PROSE's docstring for why that was a
    bug (a widened source list under an unrenamed phase name), and
    _migrate_result_prose / _verify_result_prose_migrated for where the prose
    now lives, as its own phase against the SAME comments channel. Shared by
    _migrate_comments and _verify_comments_migrated so the two can never see
    a different source list for the same item."""
    return item.get("comments") or []


def _comments_and_prose_progress(source_item, target_backend, target_id):
    """ONE PASS over the target's CURRENT comments channel, tracking TWO
    INDEPENDENT pointers -- `comment_pointer` into source_comments,
    `prose_pointer` into source_prose -- so EACH phase's own progress can be
    read off without either phase's progress depending on the OTHER ever
    reaching ITS OWN end. Shared by _migrate_comments/
    _verify_comments_migrated (which only ever look at `comment_pointer`)
    and _migrate_result_prose/_verify_result_prose_migrated (which only ever
    look at `prose_pointer`).

    For each target text, in order: try to match it against
    `source_comments[comment_pointer]` first; if it matches, advance
    `comment_pointer`. Otherwise try `source_prose[prose_pointer]`; if THAT
    matches, advance `prose_pointer`. A text matching neither current
    pointer is foreign (human, or not yet reached) and is simply skipped --
    the same "skip, never remove from consideration" discipline
    _first_unmatched_source_index already uses for a single list.

    WHY two independent pointers in one pass, not a single shared pointer
    over the combined list (an earlier version of this function, itself a
    fix for a code-review finding -- see git history): a single shared
    pointer makes prose's own completion depend on WALKING CONTIGUOUSLY
    THROUGH THE ENTIRE comments segment first. If a plain comment is later
    deleted from the target (an accepted, documented limitation for the
    comments phase alone -- see _migrate_comments' own "known limit 3") AND
    PHASE_COMMENTS was already recorded from an earlier run (so
    migrate()'s loop never re-invokes the comments phase to notice), the
    shared pointer would get PERMANENTLY stuck at the gap the deleted
    comment left -- and since the prose phase's own progress was computed
    as an OFFSET from that same stuck pointer, it could never advance past
    it either, even though the comments phase's own completeness is no
    longer relevant (it isn't re-checked) and the target's actual prose
    entries are genuinely still there. Two independent pointers do not have
    this coupling: `comment_pointer` can get stuck at a gap in the comments
    segment without ever blocking `prose_pointer`'s own, separate progress
    through whatever prose text the walk encounters.

    WHY two pointers in ONE pass (not two fully independent
    _first_unmatched_source_index calls, the ORIGINAL, pre-code-review
    design): running comments' and prose's matching as two SEPARATE walks,
    each starting fresh at its own pointer=0 against the SAME target list,
    can mis-attribute a text that is byte-identical between the two phases'
    own source lists -- e.g. a plain comment "Done." and a classified
    `## Result` PROSE entry "Done." on the same item. The comments phase
    posts its "Done." first; an independent prose walk starting its own
    pointer fresh at 0 then matches that ALREADY-POSTED "Done." against ITS
    OWN "Done." entry, so the real prose entry never gets posted, and the
    (also independent) prose postcondition passes anyway, for the identical
    reason. A SINGLE pass with comments given priority at each step does not
    have this ambiguity in the NO-GAP case: each target occurrence can
    advance AT MOST ONE of the two pointers, and since comments always post
    before prose within a given run (migrate()'s own per-item ordering),
    trying comments first at each step matches write order. This preserves
    the SAME guarantee _first_unmatched_source_index already gives within
    one list (N identical texts need N distinct target occurrences -- see
    test_duplicate_comment_texts_within_one_items_list_both_survive_a_resume)
    across the phase boundary too, without coupling either phase's progress
    to the OTHER'S ever reaching completion.

    REMAINING GAP, not fully closed (a third code-review round; see git
    history): if comment_pointer ever gets stuck below len(source_comments)
    -- the deleted-interior-comment case above -- a LATER text that is
    byte-identical to comment_pointer's CURRENT (unreachable) expectation is
    genuinely ambiguous: it could be the comments-list entry that would have
    matched had the gap not existed, or a coincidentally identical prose
    entry. Pure text-value matching cannot tell these apart (the deleted
    text is, by definition, no longer visible to distinguish them) -- a
    sound fix needs the two phases' postings to carry a hidden identity
    marker of their own (the way append_result() already tags result-refs
    via RESULT_MARKER), which is a bigger design change (it touches what a
    human sees in the comments channel) than a bugfix round should decide
    unilaterally. The AMBIGUITY GUARD below closes the DANGEROUS half of
    this gap without resolving it structurally: a text that could still
    belong to a not-yet-matched comments entry is never silently donated to
    prose (so `fully_migrated: True` never gets reported while data is
    genuinely missing) -- but it also never resolves the ambiguity in
    prose's favour either, so such an item stays stuck (raising on every
    retry, safely, rather than silently succeeding) until a human
    intervenes. Safer than the alternative, not a full close."""
    source_comments = _comment_source_texts(source_item)
    source_prose = _prose_result_entries(source_item)
    target_texts = target_backend.get(target_id).get("comments") or []
    comment_pointer = 0
    prose_pointer = 0
    for text in target_texts:
        if comment_pointer < len(source_comments) and text == source_comments[comment_pointer]:
            comment_pointer += 1
            continue
        # AMBIGUITY GUARD (see "REMAINING GAP" above): a text that could
        # still satisfy a LATER, not-yet-matched comments entry is never
        # let through to the prose check -- it stays unattributed to
        # either pointer rather than being silently claimed by prose.
        if text in source_comments[comment_pointer:]:
            continue
        if prose_pointer < len(source_prose) and text == source_prose[prose_pointer]:
            prose_pointer += 1
    return comment_pointer, prose_pointer, source_comments, source_prose


def _migrate_comments(source_item, target_backend, target_id):
    """Copies source_item's plain comments (`item["comments"]` only -- see
    _comment_source_texts; classified `## Result` prose is a separate phase,
    _migrate_result_prose, sharing this function's target read via
    _comments_and_prose_progress but never its OWN progress) to target_id,
    resuming from wherever a prior attempt left off. comment() has no dedup
    of its own (unlike set_status, which plainly overwrites, or
    add_tag/add_link, which check membership before writing), so a mid-item
    abort must be survivable without risking a duplicate post.

    Re-derives progress LIVE from the target's own current comments (rather
    than a persisted per-comment checkpoint in the idmap) via
    _comments_and_prose_progress's `comment_pointer` -- the longest prefix
    of source_comments matched, in order, against the target -- and posts
    only the remaining TAIL, in source order. This phase's own progress
    never depends on whether ANY prose has been posted or matched (see
    _comments_and_prose_progress's own docstring for why that independence
    matters).

    This is deliberately NOT "compare against the target's TOTAL comment
    count" (an earlier, defective version of this function): that
    comparison is only correct while nothing but this migration ever writes
    a comment to the target. A human (or any other process) commenting on
    the target between an aborted run and its resume inflates the total
    count without being one of source_comments -- the count-based version
    would then skip past a real, still-unposted source comment as if it had
    already been copied, LOSING IT permanently once the phase was
    (incorrectly) recorded complete. The subsequence walk does not have
    this problem: a foreign comment is simply a target text that never
    matches the pointer's current source text, so it is skipped over
    rather than mistaken for progress.

    Four known limits of this rule, accepted rather than fixed:

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
       result-links), which is out of scope here. This is distinct from the
       comments/prose collision _comments_and_prose_progress's own docstring
       describes -- that one is closed for the NO-GAP case (both are this
       migration's own known source texts, and the two-pointer design keeps
       them from colliding); it is NOT fully closed once combined with limit
       #3/#4 below (a comments-list gap plus a byte-identical prose entry is
       genuinely ambiguous from text alone -- see _comments_and_prose_
       progress's own "REMAINING GAP" section for the accepted, bounded
       mitigation). This limit #2 is a genuinely foreign (human, or another
       process') comment, which this code has no way to distinguish from its
       own regardless of any gap.
    3. A comment deleted from the target AFTER this code transferred it makes
       a later resume re-post it -- but ONLY if the comments phase itself
       gets a chance to run again, which it does not once PHASE_COMMENTS is
       recorded (migrate()'s loop skips a completed phase outright). In that
       case a deletion is simply invisible to this phase from then on: no
       re-post, no error, no further action. The two-pointer design in
       _comments_and_prose_progress exists specifically so this SAME
       deletion does not also block the (separately resumable)
       result-prose phase's own, independent progress.
    4. A comment deleted from the target BEFORE PHASE_COMMENTS is ever
       recorded (i.e. still mid-resume, this phase's own postcondition has
       not yet passed) makes `comment_pointer` permanently unable to reach
       `len(source_comments)` for as long as the gap remains -- every
       subsequent call re-posts source_comments[comment_pointer:], which
       includes texts already on the target elsewhere (past the gap),
       producing duplicates on each retry. This is the SAME accepted
       shape limit #3 already describes for a POST-completion deletion,
       just reachable a step earlier; not otherwise different in kind.

    Read-back soundness: get()'s full comment list was verified against a real
    YouTrack instance at 600 comments (and a 60-comment probe) with no
    pagination truncation on the comments sub-field -- unlike GET /api/issues,
    which page_size_cap simulates truncating without an explicit "$top=-1" (see
    fake_youtrack_transport.py). The largest item in the current 140-item corpus
    has ~131 comments, well under the verified depth. Do not add `$top` handling
    to comment reads on the suspicion that pagination might apply there too --
    it doesn't; this was checked, not assumed."""
    source_comments = _comment_source_texts(source_item)
    if not source_comments:
        return
    comment_pointer, _prose_pointer, source_comments, _source_prose = _comments_and_prose_progress(
        source_item, target_backend, target_id,
    )
    for text in source_comments[comment_pointer:]:
        target_backend.comment(target_id, text)


def _verify_comments_migrated(source_item, target_backend, target_id):
    """Hard postcondition for the comments phase: re-reads the target (a FRESH
    read, not the one _migrate_comments already made -- the whole point is not
    to trust that call's own view of what it accomplished) and confirms every
    text in source_item's comment source (see _comment_source_texts) is
    present as an ordered subsequence, using the SAME two-pointer walk
    _migrate_comments uses to decide what to post
    (_comments_and_prose_progress, reading only `comment_pointer`). If
    anything is still missing, raises -- uncaught, exactly like a comment()
    failure already does (see migrate()'s own docstring) -- rather than
    letting the caller record PHASE_COMMENTS for an item that only APPEARED
    to finish because posting didn't raise."""
    source_comments = _comment_source_texts(source_item)
    if not source_comments:
        return
    comment_pointer, _prose_pointer, source_comments, _source_prose = _comments_and_prose_progress(
        source_item, target_backend, target_id,
    )
    if comment_pointer < len(source_comments):
        missing = source_comments[comment_pointer:]
        raise WorkItemError(
            f"comments migration postcondition failed for target {target_id!r}: "
            f"{len(missing)} of {len(source_comments)} source comment(s) not "
            f"found on the target as an ordered subsequence after posting "
            f"(first missing: {missing[0]!r})"
        )


def _migrate_result_prose(source_item, target_backend, target_id):
    """Copies source_item's classified `## Result` PROSE (see
    _prose_result_entries / rule C) to target_id via comment() -- the SAME
    channel _migrate_comments writes to, not a new one (a prose entry has no
    dedicated channel of its own on the target, unlike a ref -- see
    _migrate_result_refs). Own phase (PHASE_RESULT_PROSE), own resume
    bookkeeping, reading only `prose_pointer` from the SAME two-pointer walk
    _migrate_comments uses (_comments_and_prose_progress) -- deliberately
    NOT a walk that requires the comments segment to match contiguously
    first (see _comments_and_prose_progress's own docstring for why that
    coupling was itself a bug), and NOT an independent from-scratch walk of
    prose alone either (see the same docstring for the collision that
    creates).

    Ordering: migrate()'s per-item loop runs the comments phase before this
    one, so on an uninterrupted run source_item's plain comments always
    precede its prose in the target's comments list -- matching the order the
    two classes were combined in before this phase split existed, and
    matching the priority _comments_and_prose_progress gives comments at
    each step of its single pass."""
    source_prose = _prose_result_entries(source_item)
    if not source_prose:
        return
    _comment_pointer, prose_pointer, _source_comments, source_prose = _comments_and_prose_progress(
        source_item, target_backend, target_id,
    )
    for text in source_prose[prose_pointer:]:
        target_backend.comment(target_id, text)


def _verify_result_prose_migrated(source_item, target_backend, target_id):
    """Hard postcondition for the result-prose phase, mirroring
    _verify_comments_migrated exactly, against the SAME two-pointer walk
    (_comments_and_prose_progress, reading only `prose_pointer`): re-reads
    the target (a FRESH read) and confirms every classified prose entry is
    present as an ordered subsequence. Raises -- uncaught, same discipline
    as every other phase's postcondition -- rather than letting the caller
    record PHASE_RESULT_PROSE for an item that only APPEARED to finish
    because comment() didn't raise."""
    source_prose = _prose_result_entries(source_item)
    if not source_prose:
        return
    _comment_pointer, prose_pointer, _source_comments, source_prose = _comments_and_prose_progress(
        source_item, target_backend, target_id,
    )
    if prose_pointer < len(source_prose):
        missing = source_prose[prose_pointer:]
        raise WorkItemError(
            f"result-prose migration postcondition failed for target {target_id!r}: "
            f"{len(missing)} of {len(source_prose)} classified result-prose "
            f"entry(ies) not found on the target as an ordered subsequence "
            f"after posting (first missing: {missing[0]!r})"
        )


def _migrate_result_refs(source_item, target_backend, target_id):
    """Copies source_item's classified result REFS (see _classify_result_entries
    / rule C) to target_id via append_result(), resuming from wherever a prior
    attempt left off. Identical resume discipline to _migrate_comments:
    append_result() posts to the SAME comments endpoint as comment() does (just
    marker-prefixed -- see fail_comment_at's own docstring in
    fake_youtrack_transport.py) and has no dedup of its own either, so the same
    ordered-subsequence walk (_first_unmatched_source_index) applies -- but
    against the target's OWN result-link channel, never its comments channel:
    the two are already partitioned by RESULT_MARKER on read (see youtrack.py's
    _item_from_issue), so a foreign result-link entry can never be mistaken for
    a foreign comment or vice versa."""
    source_refs = _ref_result_entries(source_item)
    if not source_refs:
        return
    target_refs = target_backend.get(target_id).get("result-link") or []
    pointer = _first_unmatched_source_index(source_refs, target_refs)
    for ref in source_refs[pointer:]:
        target_backend.append_result(target_id, ref)


def _verify_result_refs_migrated(source_item, target_backend, target_id):
    """Hard postcondition for the result-refs phase, mirroring
    _verify_comments_migrated exactly, against the target's result-link
    channel: re-reads the target (a FRESH read) and confirms every ref in
    source_item's classified refs is present as an ordered subsequence. Raises
    -- uncaught, same discipline as every other phase's postcondition -- rather
    than letting the caller record PHASE_RESULT_REFS for an item that only
    APPEARED to finish because append_result() didn't raise."""
    source_refs = _ref_result_entries(source_item)
    if not source_refs:
        return
    target_refs = target_backend.get(target_id).get("result-link") or []
    pointer = _first_unmatched_source_index(source_refs, target_refs)
    if pointer != len(source_refs):
        missing = source_refs[pointer:]
        raise WorkItemError(
            f"result-ref migration postcondition failed for target {target_id!r}: "
            f"{len(missing)} of {len(source_refs)} source result ref(s) not "
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
    here means one of two things -- either a resume whose idmap lost an entry for
    an item that pass would otherwise have (re-)created, or the link's target
    was never part of THIS run's source set at all because its own source file
    is gone (`local.py`'s add_link validates both ids at write time, but has no
    target-existence check on read and no delete operation of its own, so a
    dangling link survives if the target item's file is removed by hand) --
    silently dropping the link would hide either kind of data loss."""
    entry = idmap.get(link_target_source_id)
    if entry is None:
        raise WorkItemError(
            f"link target {link_target_source_id!r} is missing from the idmap -- "
            "cannot resolve it to a target-backend id. This should be unreachable "
            "within a single migrate() call (every source item gets an idmap entry "
            "before the links pass starts); it means either the idmap on disk "
            "lost an entry for an item that should already have one, or the "
            "link's target no longer exists in the source store (a dangling "
            "link left behind by a source file removed by hand) -- restore the "
            "missing source item, or hand-edit the link-holding item's own "
            "frontmatter to drop the dangling link entry (the `remove-link` "
            "command validates both ids the same way `add_link` does, so it "
            "cannot remove a link to a target that is already gone)."
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


def _tag_visibility_outcomes(target_backend):
    """Reads the tag-visibility outcomes from the create() call just made
    (see youtrack.py's last_create_tag_visibility_outcomes), if the target
    backend tracks them at all. A backend with no tag-visibility concept
    (e.g. `local`) has no such method -- treated as "nothing to report",
    not an error, since migrate() itself is not YouTrack-specific (see
    _verify_links_migrated's own docstring for the same "a YouTrack-shaped
    target" carve-out elsewhere in this module)."""
    accessor = getattr(target_backend, "last_create_tag_visibility_outcomes", None)
    if accessor is None:
        return []
    return accessor()


def _adopted_tag_visibility_outcome(target_backend):
    """Reads the tag-visibility outcome of the add_tag() call just made (see
    youtrack.py's last_add_tag_visibility_outcome), if the target backend
    tracks it at all. Same "no such concept, nothing to report" carve-out as
    _tag_visibility_outcomes -- a backend with no tag-visibility concept
    (e.g. `local`) has no such method."""
    accessor = getattr(target_backend, "last_add_tag_visibility_outcome", None)
    if accessor is None:
        return None
    return accessor()


def _apply_tags_to_adopted_item(report, target_backend, source_id, target_id, requested_tags):
    """Applies an adopted (crash-recovered) item's source tags one at a time
    via add_tag() -- create(tags=...) is not available here, the target item
    already exists. Same reasoning as status/priority's own unconditional
    re-application on this path (see migrate()'s loop): a crash could have
    happened before tags ran in the prior attempt, so an adopted item might
    still carry none of its source tags.

    Unlike create()'s own tag loop (_apply_tag_with_visibility in
    youtrack.py), add_tag() is NOT best-effort by design -- it raises
    uncaught on a rejected tag (see add_tag's own docstring: "nothing else to
    protect via atomicity, unlike create()"). That reasoning does not carry
    over here: from migrate()'s side, an adopted item's target ALSO already
    exists, exactly like a freshly created one does by the time its tags are
    applied -- so a tag rejected by the target project's own workflow must
    not abort an item that already exists, and, at this call site
    specifically, must not abort a whole migration run (potentially 100+
    items) over one item's one tag. This function supplies that best-effort
    wrapping itself, matching create()'s outcome exactly: a rejected tag is
    warned about on stderr and left out of `applied`, never raised.

    Does not thread through _tag_visibility_outcomes: that accessor reads
    create()'s own last_create_tag_visibility_outcomes side channel, which
    create() never touches on this path. Instead reads
    _adopted_tag_visibility_outcome (youtrack.py's own add_tag()-shaped
    channel, see last_add_tag_visibility_outcome's docstring) right after
    EVERY add_tag() attempt, success or failure -- both matter: a warn-and-
    continue reason (TAG_VISIBILITY_NOT_CONFIGURED and siblings) is recorded
    even though the tag command below still ran and the tag IS applied
    (mirrors create()'s own tag loop, which records the same outcome
    regardless of whether the LATER, unrelated tag-command step then also
    fails); a TAG_VISIBILITY_WRITE_REJECTED reason is recorded even though
    add_tag() then raises and the tag ends up in `missing` instead of
    `applied` -- unlike create()'s path (which still applies the tag despite
    a write-rejected visibility), add_tag()'s own contract (see its
    docstring) does not attempt the tag command after a visibility failure,
    so `visibility_not_set` and `applied`/`missing` are not mutually
    exclusive here the way _record_tag_diff's own docstring describes for
    the create() path -- a write-rejected tag can appear in BOTH
    `visibility_not_set` and `missing` on this path specifically. The
    accessor is duck-typed (add_tag()'s own workflow-rejection raise, from
    _run_command, is a SEPARATE failure with nothing to do with visibility
    -- see last_add_tag_visibility_outcome's own docstring on why that
    failure never reaches this channel; the "not-permitted" tag test below
    proves this stays empty for that case).

    add_tag() is idempotent (reads the item and returns early if the tag is
    already present) and does its own read per tag -- at the real corpus's
    scale this is one extra GET per tag on a narrow crash-recovery path, not
    the common case tags travel through; negligible today, worth
    reconsidering only if adoption ever stopped being the exception."""
    applied = []
    visibility_not_set = []
    for tag in requested_tags:
        try:
            target_backend.add_tag(target_id, tag)
        except WorkItemError as exc:
            print(
                f"Warning: could not apply tag {tag!r} to adopted item {target_id} "
                f"(source {source_id}): {exc}. Continuing without it.",
                file=sys.stderr,
            )
        else:
            applied.append(tag)
        outcome = _adopted_tag_visibility_outcome(target_backend)
        if outcome is not None:
            visibility_not_set.append(outcome)
    _record_tag_diff(report, source_id, target_id, requested_tags, applied, visibility_not_set)


def _record_tag_diff(report, source_id, target_id, requested, applied, visibility_not_set):
    """Appends one entry to report["tags"]["items"] for an item that just had
    tags applied this run -- either through target_backend.create(tags=
    requested) (a fresh item) or through _apply_tags_to_adopted_item (an
    adopted, crash-recovered item; see that function's own docstring for why
    it needs its own best-effort wrapping around add_tag()). `applied` is
    what the target backend's own return value/state actually shows, NEVER
    an assumption that `requested` landed unchanged. `missing` is
    requested-not-in-applied, computed here rather than left for a report
    consumer to derive, so "zero missing" and "no entry at all" can never be
    confused by a caller that forgets to check for absence. Only an
    already-idmapped (genuinely resumed) item gets no entry this run (see
    migrate()'s own docstring on why tags are not re-diffed on resume).

    `visibility_not_set` (see _tag_visibility_outcomes) is a DIFFERENT axis
    from `missing`: a tag can be `applied` (present on the item) and still
    have its visibility never set (created private, PO decision -- see
    migrate()'s own docstring on report["tags"] for why this is reported,
    never gated). On the adopted-item path specifically (see
    _apply_tags_to_adopted_item's own docstring), a TAG_VISIBILITY_
    WRITE_REJECTED entry is the ONE case where the two axes are not
    independent: add_tag() never attempts the tag command after its own
    visibility write fails, so that tag lands in BOTH `visibility_not_set`
    AND `missing` -- unlike every other entry in either list, which only
    ever appears in one."""
    missing = [tag for tag in requested if tag not in applied]
    report["tags"]["items"].append({
        "source_id": source_id, "target_id": target_id,
        "requested": requested, "applied": applied, "missing": missing,
        "visibility_not_set": visibility_not_set,
    })
    report["tags"]["total_requested"] += len(requested)
    report["tags"]["total_applied"] += len(applied)
    report["tags"]["total_missing"] += len(missing)
    report["tags"]["total_visibility_not_set"] += len(visibility_not_set)


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
