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
# `\Z` (not a bare `$`): `$` matches just before a trailing "\n" too, not only at the
# true end of string -- an id ending in a newline would otherwise pass this check and
# reach a writer that embeds it verbatim, corrupting a frontmatter file across two
# physical lines on the next parse (review follow-up, 09.07.2026).
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\Z")

# Status vocabulary (Manual/WORKITEMS.md §2 / ADR-0002): backends map their own states
# onto this set. `set-status` rejects anything outside it.
STATUS_VALUES = (
    "Backlog",
    "Ready",
    "In Progress",
    "In Review",
    "Parked",
    "Waiting for Approval",
    "Done",
    "Blocked",
    "Cancelled",
)


# The machine marker that disambiguates a `append-result` reference from a plain
# human `comment` on the SAME underlying comment stream (ADR-0003, ADR-0002 addendum
# 09.07.2026). Shared at package level (not just youtrack's own concern) because
# `comment()` on every backend rejects text starting with this marker -- a human
# calling `comment` must never be able to forge a `result-link` entry, regardless of
# which backend is in play (see the contract test in contract.py).
RESULT_MARKER = "<!-- ccpr:result -->"


# Tags reserved for the claiming / branch-runner protocol (ADR-0005, ADR-0003):
# `runner:<id>` and `heartbeat:<compact-utc-timestamp>`. Lifted up from youtrack.py
# (the only backend that models claiming as tags) into this shared module -- both
# the claiming protocol's internal writes (which bypass add_tag/remove_tag entirely,
# calling _run_command directly) and add_tag/remove_tag (which must refuse them, so a
# caller can never collide with claiming plumbing via the public API) need the same
# list. Single source of truth (ADR-0002 2nd addendum, 09.07.2026).
RESERVED_TAG_PREFIXES = ("runner:", "heartbeat:")

# No spaces: the YouTrack Command API tokenizes a `tag <name>` command on whitespace,
# and a space-containing tag would either need quoting (an extra parsing mode this
# contract doesn't otherwise have) or silently split into two tokens.
# `\Z` (not a bare `$`) for the same reason as ID_PATTERN above -- a trailing "\n"
# must not slip past this check either.
_TAG_PATTERN = re.compile(r"^[A-Za-z0-9_:.-]+\Z")


def is_reserved_tag(tag):
    """True if `tag` starts with a prefix reserved for the claiming protocol."""
    return any(tag.startswith(prefix) for prefix in RESERVED_TAG_PREFIXES)


def validate_tag(tag):
    """Reject anything that is not a bare tag name (charset), or that collides with
    the claiming protocol's reserved namespace. Charset is checked first (a
    structural violation), the reserved-prefix check second -- both per ADR-0002's
    2nd addendum error semantics."""
    if not tag or not _TAG_PATTERN.match(tag):
        raise WorkItemError(f"Invalid tag: {tag!r}")
    if is_reserved_tag(tag):
        raise WorkItemError(
            f"Tag {tag!r} uses a namespace reserved for the claiming protocol "
            f"({', '.join(RESERVED_TAG_PREFIXES)}); add-tag/remove-tag cannot be "
            "used on it."
        )


class WorkItemError(Exception):
    """Raised for invalid work-item operations (unknown id, invalid status, ...)."""


def validate_item_id(item_id):
    """Reject anything that is not a bare identifier (primary defense against path
    traversal / injection via a work-item id). Backends additionally apply their own
    containment checks as defense-in-depth (e.g. `local`'s resolved-path check)."""
    if not item_id or not ID_PATTERN.match(item_id):
        raise WorkItemError(f"Invalid work-item id: {item_id!r}")


def reject_result_marker(text):
    """Shared guard for every backend's `comment`: a human comment must never be able
    to forge a `result-link` entry by typing the marker `append-result` uses itself
    (review follow-up, 09.07.2026). Applied uniformly across backends -- even `local`,
    which partitions Result/Comments structurally and has nothing of its own to
    protect here -- so `comment`'s semantics don't depend on which backend is in play."""
    if text.startswith(RESULT_MARKER):
        raise WorkItemError(
            f"comment text cannot start with the reserved result marker {RESULT_MARKER!r} "
            "-- use append-result to attach a result reference."
        )


# Claiming / branch-runner protocol (ADR-0005): default if workitems.claiming.staleAfter
# isn't configured. 1 hour is a reasonable default for a heartbeat-based liveness check
# without forcing every project to configure it before claiming works at all.
DEFAULT_STALE_AFTER_SECONDS = 3600.0


def safe_parse_datetime(value, parser):
    """Best-effort datetime parse: returns None (never raises) if `value` is falsy or
    `parser(value)` fails.

    Heartbeat timestamps can be hand-edited in a tracker's UI (a YouTrack tag, e.g.)
    into something malformed — a bad timestamp must mean "no valid heartbeat" (the
    item is then simply not considered live / not swept), never a crash that escapes
    past the CLI's `except WorkItemError` boundary as a raw traceback.

    `parser` is injected so this one helper covers every timestamp shape in this
    codebase that needs the same "never raise" treatment: youtrack.py's compact tag
    format (via `functools.partial(datetime.datetime.strptime, format=...)` or a
    lambda) and the ISO-8601 string every item dict's `heartbeat` field carries
    (via `datetime.datetime.fromisoformat`), used by both youtrack.py's own
    liveness check and sweep.py.
    """
    if not value:
        return None
    try:
        return parser(value)
    except (ValueError, TypeError):
        return None

# Closed CCPR-defined priority vocabulary (ADR-0002 2nd addendum) -- validated on
# BOTH backends, unlike `type`'s freeform-on-local behaviour: CCPR defines these four
# values itself, so there is no legitimate reason for a project to extend the set, and
# `list --priority` needs a closed, shared vocabulary to stay meaningfully consistent.
PRIORITY_VALUES = ("Critical", "High", "Medium", "Low")


def validate_priority(priority):
    if priority not in PRIORITY_VALUES:
        raise WorkItemError(
            f"Unknown priority {priority!r}. Valid values: {', '.join(PRIORITY_VALUES)}"
        )


def validate_estimate(points):
    """`estimate` (story points) is a non-negative integer, on both backends
    (ADR-0002 2nd addendum) -- deliberately not restricted to a Fibonacci-like
    subset, that is a usage convention (p4-backlog), not a data-integrity
    constraint. `bool` is excluded explicitly: it is a Python `int` subclass, so
    `isinstance(True, int)` is True and would otherwise silently pass."""
    if isinstance(points, bool) or not isinstance(points, int) or points < 0:
        raise WorkItemError(
            f"Invalid estimate {points!r}: must be a non-negative integer"
        )


# Typed work-item links (ADR-0008). `blocks` is pure client-side sugar for the
# inverse of `depends-on` -- never stored as its own edge (see add_link/remove_link
# in local.py/youtrack.py, which swap id/target and delegate to "depends-on" for it).
# It is still part of the vocabulary a caller may pass to add-link/remove-link.
LINK_TYPES = ("depends-on", "blocks", "relates-to", "subtask-of")


def validate_link_type(link_type):
    """Reject anything outside the closed link-verb vocabulary (ADR-0008), on both
    backends -- same shape as validate_tag's charset guard, but a closed set rather
    than a pattern."""
    if link_type not in LINK_TYPES:
        raise WorkItemError(
            f"Unknown link type {link_type!r}. Valid values: {', '.join(LINK_TYPES)}"
        )


# `\Z` for consistency with ID_PATTERN/_TAG_PATTERN above (same `$`-vs-trailing-"\n"
# trap) -- not independently exploitable here today, since parse_duration_seconds
# already calls value.strip() before matching, but this pattern must not silently
# rely on that caller-side strip to stay safe.
_DURATION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(s|m|h|d)?\Z")
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
