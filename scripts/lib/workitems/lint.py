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


def _referenced_ids(item):
    text = " ".join(part for part in (item.get("title"), item.get("description")) if part)
    return set(ID_REFERENCE_PATTERN.findall(text))


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
    referenced = {item["id"]: _referenced_ids(item) for item in items}

    findings = []
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

        # Parenthesised, not left to precedence: `&` binds looser than `-`, so the
        # unbracketed form reads as one thing and groups as another (it happens to
        # be equivalent for sets, which is exactly why it would survive review).
        # `- {item_id}`: an item naming its own id is not a missing edge.
        unlinked = ((referenced[item_id] & known_ids)
                    - {item_id}
                    - adjacency.get(item_id, set()))
        for target in sorted(unlinked):
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
        },
        "findings": findings,
    }
