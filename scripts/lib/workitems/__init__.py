"""workitems – CCPR work-item backend package (ADR-0002).

Each module in this package (`local.py`, and future remote backends) implements the
five-operation contract: list / get / claim / set-status / append-result. The CLI
dispatcher (scripts/workitems.py) reads `workitems.provider` from settings.json and
imports the matching module by name.
"""


class WorkItemError(Exception):
    """Raised for invalid work-item operations (unknown id, invalid status, ...)."""
