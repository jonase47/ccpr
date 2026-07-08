"""workitems – CCPR work-item backend package (ADR-0002).

Each module in this package (`local.py`, and future remote backends) implements the
five-operation contract: list / get / claim / set-status / append-result. The CLI
dispatcher (scripts/workitems.py) reads `workitems.provider` from settings.json and
imports the matching module by name.
"""

import re

# Ids are bare identifiers: no path separators, no `.`, no leading `/`. Validated
# here (not only in the `local` backend) because an id can end up in a filesystem
# path today (local) and in a `ticket/<id>` branch name tomorrow (ADR-0005) — both
# are injection surfaces if an id is accepted unchecked.
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# Status vocabulary (Manual/WORKITEMS.md §2 / ADR-0002): backends map their own states
# onto this set. `set-status` rejects anything outside it.
STATUS_VALUES = (
    "Backlog",
    "Ready",
    "In Progress",
    "Parked",
    "Waiting for Approval",
    "Done",
    "Blocked",
    "Cancelled",
)


class WorkItemError(Exception):
    """Raised for invalid work-item operations (unknown id, invalid status, ...)."""


def validate_item_id(item_id):
    """Reject anything that is not a bare identifier (primary defense against path
    traversal / injection via a work-item id). Backends additionally apply their own
    containment checks as defense-in-depth (e.g. `local`'s resolved-path check)."""
    if not item_id or not ID_PATTERN.match(item_id):
        raise WorkItemError(f"Invalid work-item id: {item_id!r}")
