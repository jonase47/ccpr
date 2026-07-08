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


# Claiming / branch-runner protocol (ADR-0005): default if workitems.claiming.staleAfter
# isn't configured. 1 hour is a reasonable default for a heartbeat-based liveness check
# without forcing every project to configure it before claiming works at all.
DEFAULT_STALE_AFTER_SECONDS = 3600.0

_DURATION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(s|m|h|d)?$")
_DURATION_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration_seconds(value):
    """Parse a `workitems.claiming` duration (staleAfter / heartbeatInterval) into
    seconds. Accepts a bare number (seconds) or a string with a single-letter unit
    suffix: s(econds)/m(inutes)/h(ours)/d(ays) — e.g. "30m", "2h", "1d", or a plain
    "3600". Deliberately not ISO 8601 durations: a feature this narrow (two config
    keys) doesn't need a heavier parser, and this format is easier for a human to
    read and write directly in settings.json.
    """
    if isinstance(value, bool):
        raise WorkItemError(f"Invalid duration: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        raise WorkItemError(f"Invalid duration: {value!r}")

    match = _DURATION_PATTERN.match(value.strip())
    if not match:
        raise WorkItemError(
            f"Invalid duration {value!r}: expected a number of seconds, or a number "
            "followed by s/m/h/d (e.g. '30m', '2h', '1d')."
        )
    number, unit = match.groups()
    return float(number) * _DURATION_UNIT_SECONDS.get(unit, 1)
