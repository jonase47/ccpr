"""lint.py – `workitems.py lint`: resolves each work item's OWN TEXT against its
typed links (CCP-1171, ADR-0008).

A typed link is the machine-readable form of "this relates to that". Nothing else in
this repository resolves those edges against what an item's own prose claims, so an
item could name another in its description and carry no edge to it -- reasoning
recoverable only by reading prose, which is exactly what the link graph exists to
avoid.

Backend-agnostic by construction, the same way sweep()/migrate()/lift() are: it
consumes `backend.list()` and nothing else, so it runs identically against the
offline `local` backend and a remote one. Two consequences worth stating:

- **The link graph is read UNDIRECTED.** `local` stores an edge on ONE side only
  (`add_link(A, relates-to, B)` writes on A's file and nothing on B's), while
  `youtrack` derives both sides from a single shared link record. Treating the edge
  as directed would therefore report a real, existing relation as missing on
  `local` -- a provider-dependent verdict for an identical graph.
- **The id pattern is resolved AGAINST the listed ids**, never trusted on its own.
  `\\b[A-Z][A-Z0-9]*-\\d+\\b` matches `ADR-0008` and `G-107` as readily as `CCP-1171`;
  only tokens that name an item the backend actually listed become a comparison. The
  remainder is counted and reported as scope, not silently dropped.
- **The recorded dedup-evidence line is excused from `named-without-link`** (CCP-1177).
  `create --checked-against` writes the ids a filer SEARCHED into the description; an
  id the search REJECTED is not a relation, and reporting it would make this lint go
  redder with every correctly filed item. The exemption is per REFERENCE, not per
  item, and the references it withholds are counted under
  `scope.dedup_evidence_line.excused` -- withheld from one comparison, not dropped
  from what this module admits to having read. See the block above _referenced_ids.
"""

import re

from workitems import WorkItemError

# The reference classes this lint's id pattern cannot reach, stated in its own
# output rather than only in the work item that commissioned it: a comparison
# whose extent is not stated is not a result.
NOT_REACHED = (
    "a reference whose id names no item this backend listed -- it is counted under "
    "unresolved_references and compared against nothing. Legacy WI-NNNN ids from "
    "before a migration fall here, resolvable only through docs/workitems-idmap.yml, "
    "as do ids from another project and ids of deleted items",
    "prose that names an item without using its id -- there is nothing to match",
    "a reference living only in a comment or a result-link: only title and "
    "description are read",
)

# Deliberately broad, then intersected with the backend's own ids (see the module
# docstring): a pattern narrow enough to be "correct" for one provider's id shape
# would be wrong for the next one, and this module never learns a provider's name.
ID_REFERENCE_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")


def _adjacency(items):
    """Undirected view of the typed-link graph: id -> set of ids it is linked to,
    from EITHER side of the edge."""
    adjacency = {}
    for item in items:
        for link in item.get("links") or []:
            target = link.get("target")
            if not target:
                continue
            adjacency.setdefault(item["id"], set()).add(target)
            adjacency.setdefault(target, set()).add(item["id"])
    return adjacency


def _id_prefix(item_id):
    """`CCP-1171` -> `CCP`. An id with no separator is its own prefix."""
    return item_id.rsplit("-", 1)[0]


def _count_by_prefix(item_ids):
    """`{"ADR": 30, "WI": 148}` -- how many DISTINCT unresolved references each id
    namespace contributed. A flat sample would be sorted alphabetically and so would
    show one namespace and hide the others, which is the opposite of naming a scope.
    """
    counts = {}
    for item_id in item_ids:
        prefix = _id_prefix(item_id)
        counts[prefix] = counts.get(prefix, 0) + 1
    return dict(sorted(counts.items()))


# --------------------------------------------------------------------------
# The dedup-evidence line (CCP-1172), and why its SHAPE is defined here
# --------------------------------------------------------------------------
# `create --checked-against` records the ids a filer SEARCHED into the stored
# description. CCP-1171's scan above reads any id in a description as a claimed
# relation -- so the two features, merged hours apart, defeat each other: every
# correctly filed item makes this lint redder, with findings nobody is supposed
# to fix. An id that was searched and found NOT to apply is precisely not a
# `relates-to`; linking it would fill the graph with non-relations and devalue
# what this module measures.
#
# The exemption below is anchored to the line as it is ACTUALLY WRITTEN, not to
# a pattern re-typed from reading the writer (CCP-1177 AC 4, the rule CCP-1170
# followed for `.gitignore`, G-091): `compose_evidence_description()` is the
# ONE register of the shape, and scripts/workitems.py's
# `_compose_create_description()` calls it instead of composing the line itself.
# Writer and reader therefore cannot drift -- there is no second copy to drift
# from.
#
# WHERE it lives, stated accurately because the obvious reading is wrong. The
# writer cannot host it: `scripts/workitems.py` is a script whose own name is
# shadowed by this package on `sys.path`, so nothing in the package can import
# it. That rules out the writer -- it does NOT rule out the package's own
# `__init__.py`, which every module here (this one included, for
# WorkItemError) already imports from. `__init__.py` is in fact the better
# home, and there is direct precedent: RESULT_MARKER sits there rather than in
# the backend that writes it, for exactly this reason -- a marker shared
# between a writer and the readers that must recognise it belongs to neither.
#
# It is here instead because `__init__.py` was outside the write boundary of
# the ticket that introduced this (CCP-1177). That is a boundary artifact, not
# a design choice, and it is recorded as placement debt rather than dressed up:
# a follow-up should move EVIDENCE_PREFIX / EVIDENCE_SEPARATOR /
# compose_evidence_description / split_evidence to `__init__.py`. The move is
# functionally inert -- both sides already agree, because workitems.py calls
# through this module -- so it is a relocation, not a fix.
#
# What the placement does get right, and what a move must preserve: of the two
# sides, the READER's correctness is the fragile one. A recogniser that
# silently stops recognising leaves no trace, while a writer that stops calling
# this composer is visible in the artifact it writes (and is pinned end-to-end
# from the CLI in test_workitems_cli.py).
EVIDENCE_PREFIX = "Checked against: "

# A blank line, i.e. the evidence occupies the FIRST PARAGRAPH and the item's
# own prose starts after it. Named rather than inlined so the round-trip guard
# below and the writer both bind to the same constant.
EVIDENCE_SEPARATOR = "\n\n"


def compose_evidence_description(description, checked_against):
    """The single register of the dedup-evidence line's shape: the recorded
    value on the first line behind `Checked against: `, a blank line, then the
    item's own description. Called by scripts/workitems.py's
    `_compose_create_description()` (which owns the VALIDATION of the value --
    non-empty after trimming -- and nothing about the layout)."""
    header = f"{EVIDENCE_PREFIX}{checked_against}"
    if description:
        return f"{header}{EVIDENCE_SEPARATOR}{description}"
    return header


def split_evidence(description):
    """Inverse of `compose_evidence_description`: `(evidence, remainder)`.

    A description that does not OPEN with the prefix carries no evidence line
    and is returned whole as the remainder -- the exemption is anchored to the
    composed line, never to "the first paragraph" of any item.
    """
    text = description or ""
    if not text.startswith(EVIDENCE_PREFIX):
        return "", text
    evidence, _, remainder = text.partition(EVIDENCE_SEPARATOR)
    return evidence, remainder


# Sentinels for the round-trip guard. The body deliberately contains a blank
# line of its own: a splitter that took the LAST separator instead of the first
# would round-trip a single-paragraph body unnoticed.
_PROBE_VALUE = "PROBE-1, PROBE-2 via a search"
_PROBE_BODY = "probe body paragraph one\n\nprobe body paragraph two"


def _verify_splitter_against_composer():
    """AC 4's loud half. The composer above and the splitter beside it are two
    halves of one contract that a later edit could move independently; if they
    ever disagree, this module must say so rather than quietly stop exempting
    (and go red with findings nobody should fix) or quietly start exempting too
    much (and drop the check). Raises WorkItemError, which `lint()` turns into
    the `could-not-run` verdict this module already reserves for "nothing was
    reliably compared" -- not a `pass` with a short findings list.

    Both shapes are probed, because `create` writes both: with a description
    and without one."""
    for body, expected_remainder in ((_PROBE_BODY, _PROBE_BODY), (None, "")):
        composed = compose_evidence_description(body, _PROBE_VALUE)
        evidence, remainder = split_evidence(composed)
        if evidence != f"{EVIDENCE_PREFIX}{_PROBE_VALUE}" or remainder != expected_remainder:
            raise WorkItemError(
                "the dedup-evidence line's composer and this module's splitter "
                f"disagree: compose_evidence_description() produced {composed!r}, "
                f"from which split_evidence() recovered {(evidence, remainder)!r} "
                f"instead of {(EVIDENCE_PREFIX + _PROBE_VALUE, expected_remainder)!r}. "
                "The CCP-1177 exemption cannot be applied without silently "
                "changing what is scanned, so nothing was compared"
            )


def _referenced_ids(item):
    """`(every id named, every id named OUTSIDE the dedup-evidence line)`.

    Both are returned because the report needs both: the findings are computed
    from the second, while `scope.unresolved_references` stays computed from
    the first -- the exemption removes a reference from one COMPARISON, it does
    not narrow what this lint admits to having read.
    """
    title = item.get("title") or ""
    description = item.get("description") or ""
    _, outside_evidence = split_evidence(description)
    return (
        set(ID_REFERENCE_PATTERN.findall(f"{title} {description}")),
        set(ID_REFERENCE_PATTERN.findall(f"{title} {outside_evidence}")),
    )


def _unlinked_among(candidates, item_id, *, known_ids, edges):
    """The `named-without-link` test itself, factored out because it is applied
    TWICE per item: once to the references that count as findings and once to the
    ones the CCP-1177 exemption withholds. Sharing the expression is what lets the
    excused count be read as "the findings the exemption suppressed" rather than as
    a second, independently drifting definition of the same thing.

    Keyword-only for the two graph reads: they are both collections of ids and
    a transposed pair would produce a plausible wrong answer rather than an
    error. Named at the call site, a typo is a TypeError there, not a silent
    misread here.

    Parenthesised, not left to precedence: `&` binds looser than `-`, so the
    unbracketed form reads as one thing and groups as another (it happens to be
    equivalent for sets, which is exactly why it would survive review).
    `- {item_id}`: an item naming its own id is not a missing edge.
    """
    return sorted((candidates & known_ids)
                  - {item_id}
                  - edges.get(item_id, set()))


def refusal(reason, provider=None):
    """The one report shape for "nothing was compared". Public because the CLI
    reaches it on a path this module never sees: a backend that cannot even be
    CONSTRUCTED (a remote provider with no resolvable token) fails before
    `backend.list()` is ever called, and that is the same refusal, not a
    different one."""
    return {
        "verdict": "could-not-run",
        "provider": provider,
        "reason": reason,
        # Same three-part wording install.sh's verify_cannot_run() established: a
        # check that could not look is not a check that looked and found nothing,
        # and an exit code alone cannot tell the two apart.
        "message": (
            f"COULD NOT RUN -- {reason}. Nothing was compared. This is NOT the "
            "same as 'no findings'. the work-item link lint DID NOT RUN"
        ),
        "items_scanned": None,
        "findings": [],
    }


def lint(backend, provider=None):
    """One pass over every item the backend lists. Returns a report dict.

    Three verdicts, kept apart on purpose: `pass` (the backend was read and nothing
    was found), `findings` (read, something found) and `could-not-run` (the backend
    could not be reached, so NOTHING was compared). The third is not a pass with an
    empty list -- an exit code alone cannot tell those two apart, which is why the
    verdict is carried in the report itself.

    `provider` is a LABEL, not a switch: this module never behaves differently per
    provider, but a reader of the report has to be able to tell whether the run just
    read Markdown files offline or reached a remote tracker.
    """
    try:
        # Before the read, not after: an instrument that cannot be trusted to
        # classify what it finds should not go looking. Same refusal channel as
        # an unreachable backend -- in both cases nothing was compared.
        _verify_splitter_against_composer()
        items = backend.list()
    except WorkItemError as exc:
        return refusal(str(exc), provider=provider)

    known_ids = {item["id"] for item in items}
    # The project's OWN id namespace, derived from the data rather than from a
    # provider name: a target outside it is unresolvable by construction (a
    # backend only ever lists its own project), so it must not be reported as a
    # dangling edge.
    #
    # CAVEAT, stated because everything else here states its extent: this namespace
    # has no oracle independent of the very `list()` that produced the findings. If
    # a backend ever returned a PARTIAL item list without raising, an in-namespace
    # dangling link could reclassify as the milder `link-outside-project` rather
    # than the read itself looking wrong. Not a live risk today -- youtrack.list()
    # disables pagination explicitly ($top=-1) and local reads the whole directory
    # -- but a backend that degrades silently would degrade this split silently too.
    known_prefixes = {_id_prefix(item_id) for item_id in known_ids}
    adjacency = _adjacency(items)
    referenced = {}
    referenced_outside_evidence = {}
    for item in items:
        named, named_outside_evidence = _referenced_ids(item)
        referenced[item["id"]] = named
        referenced_outside_evidence[item["id"]] = named_outside_evidence

    findings = []
    excused_by_item = {}
    for item in items:
        item_id = item["id"]
        for link in item.get("links") or []:
            target = link.get("target")
            # A link entry with no target names nothing, so there is nothing to
            # resolve and it is skipped rather than counted. Structurally
            # unreachable through either shipped backend (local._parse_links and
            # youtrack._item_from_issue both drop an entry before it gets here),
            # which is why it is a skip and not a finding kind of its own.
            if not target or target in known_ids:
                continue
            # `or "?"` rather than bare .get(): the detail line is read by a human,
            # and an absent type interpolated raw reads as a link whose type IS the
            # string "None".
            link_type = link.get("type") or "?"
            if _id_prefix(target) in known_prefixes:
                findings.append({
                    "kind": "dangling-link",
                    "item": item_id,
                    "target": target,
                    "detail": f"{item_id} carries a {link_type} link to {target}, "
                              "an id in this project's own namespace that no listed "
                              "item carries",
                })
            else:
                findings.append({
                    "kind": "link-outside-project",
                    "item": item_id,
                    "target": target,
                    "detail": f"{item_id} carries a {link_type} link to {target}, "
                              "outside the id namespace of every listed item -- this "
                              "lint cannot resolve it and did not try",
                })

        # Read from `referenced_outside_evidence`, not `referenced`: a reference
        # whose ONLY mention is the dedup-evidence line records a search, not a
        # relation (CCP-1177). Per REFERENCE, never per item -- an id the
        # evidence line mentions AND the item's own prose names is still a
        # finding, which is the difference between correcting this check and
        # removing it.
        unlinked = _unlinked_among(
            referenced_outside_evidence[item_id], item_id,
            known_ids=known_ids, edges=adjacency,
        )
        # Exactly the findings the exemption suppressed -- the SAME test, applied
        # to the withheld references, so it cannot count one that would not have
        # been reported anyway (an already-linked reference, or the item itself).
        # Reported under `scope` because this module's standing rule is that a
        # remainder is counted and named, not silently dropped; and because a
        # count that falls to zero while findings reappear is how a broken
        # exemption announces itself to a reader.
        excused = _unlinked_among(
            referenced[item_id] - referenced_outside_evidence[item_id],
            item_id, known_ids=known_ids, edges=adjacency,
        )
        if excused:
            excused_by_item[item_id] = excused
        for target in unlinked:
            findings.append({
                "kind": "named-without-link",
                "item": item_id,
                "target": target,
                "detail": f"{item_id} names {target} in its title/description "
                          "but carries no typed link to it",
            })

    findings.sort(key=lambda f: (f["kind"], f["item"], f["target"]))

    unresolved = sorted(
        {token for tokens in referenced.values() for token in tokens} - known_ids
    )
    return {
        "verdict": "findings" if findings else "pass",
        "provider": provider,
        "items_scanned": len(items),
        "scope": {
            "fields_scanned": ["title", "description"],
            "id_pattern": ID_REFERENCE_PATTERN.pattern,
            "resolved_against": f"the {len(known_ids)} id(s) this backend listed",
            "unresolved_references": {
                "count": len(unresolved),
                "by_namespace": _count_by_prefix(unresolved),
            },
            "not_reached": list(NOT_REACHED),
            "dedup_evidence_line": {
                "prefix": EVIDENCE_PREFIX,
                "rule": (
                    "an id whose ONLY mention in an item is inside the "
                    f"`{EVIDENCE_PREFIX.strip()}` line `create --checked-against` "
                    "writes (CCP-1172) records a search that REJECTED it, not a "
                    "relation, and is excused from named-without-link (CCP-1177). "
                    "An id the item names anywhere else as well is NOT excused"
                ),
                "not_reached": (
                    "the exemption is anchored to the line's SHAPE, not to its "
                    "provenance: any description opening with this prefix is "
                    "treated as a recorded dedup check, including one written by "
                    "`set-description` rather than by `create --checked-against`. "
                    "A real unlinked relation can therefore be excused by writing "
                    "it into that position. It is still LISTED below rather than "
                    "dropped, which is the check a reader has"
                ),
                "excused": {
                    "count": sum(len(ids) for ids in excused_by_item.values()),
                    "by_item": dict(sorted(excused_by_item.items())),
                },
            },
        },
        "findings": findings,
    }
