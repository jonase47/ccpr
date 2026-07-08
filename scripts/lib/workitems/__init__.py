"""workitems – CCPR work-item backend package (ADR-0002).

Each module in this package (`local.py`, and future remote backends) implements the
five-operation contract: list / get / claim / set-status / append-result. The CLI
dispatcher (scripts/workitems.py) reads `workitems.provider` from settings.json and
imports the matching module by name.
"""

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
