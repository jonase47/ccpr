"""local.py – The `local` work-item backend: structured Markdown at docs/workitems/<id>.md.

Reference implementation of the CCPR work-item contract (ADR-0002) and the contract
test fixture (see scripts/tests/workitems/contract.py). No server, no token: reads and
writes one Markdown file per item.
"""

import datetime
import os
import re
from pathlib import Path

from workitems import (
    STATUS_VALUES, WorkItemError, frontmatter, reject_result_marker, validate_item_id,
    validate_tag,
)

RESULT_HEADING = "## Result"
COMMENTS_HEADING = "## Comments"

_ID_NUMBER_PATTERN = re.compile(r"^WI-(\d+)$")

# Section boundaries (description vs. Acceptance Criteria/Result/Comments) are found by
# scanning the body for lines that look like a heading (`## `). Free user text --
# description, comment -- is embedded in that same body, so a line the user wrote that
# happens to read like a heading (including an EXACT match, e.g. a comment reading
# literally "## Comments") would otherwise be indistinguishable from a real section
# boundary on the next read: the description would truncate early, and/or the real
# section would become unreachable (a heading search matches the first occurrence,
# which would then be the fake one). `_escape_heading_lookalikes` neutralizes every
# such line before it is written; `_unescape_heading_lookalikes` reverses it when the
# text is read back out. The backslash count is round-trip-safe for text that already
# contains an escaped lookalike (of which there should never be any in practice, but
# the transform stays a true inverse either way).
_HEADING_LOOKALIKE_RE = re.compile(r"^(\s*)(\\*)(## .*)$")


def _escape_heading_lookalikes(text):
    return "\n".join(_escape_line(line) for line in text.split("\n"))


def _escape_line(line):
    match = _HEADING_LOOKALIKE_RE.match(line)
    if not match:
        return line
    leading_ws, backslashes, heading_text = match.groups()
    return f"{leading_ws}{backslashes}\\{heading_text}"


def _unescape_heading_lookalikes(text):
    return "\n".join(_unescape_line(line) for line in text.split("\n"))


def _unescape_line(line):
    match = _HEADING_LOOKALIKE_RE.match(line)
    if not match or not match.group(2):
        return line
    leading_ws, backslashes, heading_text = match.groups()
    return f"{leading_ws}{backslashes[1:]}{heading_text}"


def create(config):
    """Factory used by the CLI dispatcher (scripts/workitems.py)."""
    workitems_dir = config.get("workitems_dir", "docs/workitems")
    return LocalBackend(workitems_dir)


class LocalBackend:
    def __init__(self, workitems_dir):
        self.workitems_dir = Path(workitems_dir)

    def create(self, title, item_type=None, owner=None, description=None):
        if not title:
            raise WorkItemError("title is required")

        self.workitems_dir.mkdir(parents=True, exist_ok=True)
        body = _new_item_body(description)

        # Concurrency note: two processes could scan the same directory and compute
        # the same "next" id (a small TOCTOU race). The actual safeguard is the
        # exclusive create below ("x" mode never overwrites an existing file); on a
        # collision we just rescan and retry a bounded number of times. This is
        # "safe-ish", not a real lock — an adversarial flood of simultaneous creates
        # could still exhaust the retry budget. Acceptable for the target usage (a
        # solo dev or small team working one repo), not a distributed-lock guarantee.
        max_attempts = 20
        for _ in range(max_attempts):
            item_id = self._next_id()
            path = self.workitems_dir / f"{item_id}.md"
            data = {"id": item_id, "title": title, "status": "Backlog"}
            if item_type:
                data["type"] = item_type
            if owner:
                data["owner"] = owner
            data["created"] = datetime.date.today().isoformat()
            text = frontmatter.render(data, body)
            try:
                with open(path, "x", encoding="utf-8") as f:
                    f.write(text)
                return self._item_from_data(data, body)
            except FileExistsError:
                continue
        raise WorkItemError("Could not assign a unique work-item id after several attempts")

    def _next_id(self):
        highest = 0
        if self.workitems_dir.is_dir():
            for path in self.workitems_dir.glob("WI-*.md"):
                match = _ID_NUMBER_PATTERN.match(path.stem)
                if match:
                    highest = max(highest, int(match.group(1)))
        return f"WI-{highest + 1:04d}"

    def list(self, status=None, owner=None, tags=None, item_type=None):
        if not self.workitems_dir.is_dir():
            return []

        items = []
        for path in sorted(self.workitems_dir.glob("*.md")):
            item = self._item_from_path(path)
            if status is not None and item["status"] != status:
                continue
            if owner is not None and item["owner"] != owner:
                continue
            if tags and not set(tags).issubset(item["tags"]):
                continue
            if item_type is not None and item["type"] != item_type:
                continue
            items.append(item)
        return items

    def get(self, item_id):
        return self._item_from_path(self._path_for(item_id))

    def claim(self, item_id, owner=None, runner=None):
        """No-op beyond optionally setting owner (local has nothing to lock; ADR-0002
        §6). `runner` is accepted for CLI/signature parity with remote backends but
        genuinely ignored: local has no runner/heartbeat concept (ADR-0005)."""
        path, data, body = self._read(item_id)
        if owner is not None:
            data["owner"] = owner
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def heartbeat(self, item_id, runner=None):
        """No-op (ADR-0005): local has no runner/heartbeat to refresh. Still
        validates the id exists, matching every other operation's behaviour."""
        return self.get(item_id)

    def set_status(self, item_id, status):
        if status not in STATUS_VALUES:
            raise WorkItemError(
                f"Unknown status '{status}'. Valid values: {', '.join(STATUS_VALUES)}"
            )
        path, data, body = self._read(item_id)
        data["status"] = status
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def append_result(self, item_id, ref):
        path, data, body = self._read(item_id)
        new_body = _append_to_section(body, RESULT_HEADING, ref)
        self._write(path, data, new_body)
        return self._item_from_data(data, new_body)

    def comment(self, item_id, text):
        """`local` partitions Result/Comments structurally (separate sections, no
        marker), so it has nothing to protect here on its own -- but the rejection is
        applied uniformly across backends (review follow-up, 09.07.2026) so `comment`'s
        semantics don't depend on which backend a project happens to run."""
        if not text:
            raise WorkItemError("comment text is required")
        reject_result_marker(text)
        path, data, body = self._read(item_id)
        new_body = _append_to_section(body, COMMENTS_HEADING, text)
        self._write(path, data, new_body)
        return self._item_from_data(data, new_body)

    def set_description(self, item_id, text):
        path, data, body = self._read(item_id)
        new_body = _replace_description(body, text)
        self._write(path, data, new_body)
        return self._item_from_data(data, new_body)

    def set_title(self, item_id, text):
        if not text:
            raise WorkItemError("title is required")
        path, data, body = self._read(item_id)
        data["title"] = text
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def set_type(self, item_id, item_type):
        """`local` has no Type bundle to validate against, so any non-empty string
        is accepted -- same freeform behaviour `create` already has for `type`."""
        if not item_type:
            raise WorkItemError("type is required")
        path, data, body = self._read(item_id)
        data["type"] = item_type
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def add_tag(self, item_id, tag):
        """Idempotent (ADR-0002 2nd addendum): re-asserting an already-present tag
        is a no-op, not an error -- a tag is a set-membership fact."""
        validate_tag(tag)
        path, data, body = self._read(item_id)
        tags = list(data.get("tags") or [])
        if tag not in tags:
            tags.append(tag)
            data["tags"] = tags
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def remove_tag(self, item_id, tag):
        """Idempotent: removing an absent tag is a no-op, not an error."""
        validate_tag(tag)
        path, data, body = self._read(item_id)
        tags = list(data.get("tags") or [])
        if tag in tags:
            tags.remove(tag)
            data["tags"] = tags
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def _path_for(self, item_id):
        validate_item_id(item_id)  # primary defense: reject anything but a bare id

        path = self.workitems_dir / f"{item_id}.md"

        # Defense-in-depth: even a validated id must resolve inside workitems_dir.
        # Not relying on Path.is_relative_to (3.9+, uncertain repo-wide baseline) —
        # os.path.commonpath works on any Python 3.
        base = str(self.workitems_dir.resolve())
        resolved = str(path.resolve())
        if os.path.commonpath([base, resolved]) != base:
            raise WorkItemError(f"Invalid work-item id: {item_id!r}")

        if not path.is_file():
            raise WorkItemError(f"Unknown work item: {item_id}")
        return path

    def _read(self, item_id):
        path = self._path_for(item_id)
        data, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        return path, data, body

    def _write(self, path, data, body):
        """Write via a temp file + atomic rename so a failed write never corrupts the item."""
        text = frontmatter.render(data, body)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp_path.write_text(text, encoding="utf-8")
            tmp_path.replace(path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _item_from_path(self, path):
        data, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        return self._item_from_data(data, body)

    def _item_from_data(self, data, body):
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "status": data.get("status"),
            "description": _extract_description(body),
            "result-link": _extract_section_items(body, RESULT_HEADING),
            "comments": _extract_section_items(body, COMMENTS_HEADING),
            "owner": data.get("owner") or None,
            "type": data.get("type"),
            "refs": data.get("refs"),
            # Never None, on either backend (ADR-0002 2nd addendum): an unset field
            # reads as an empty list, not a missing/None value.
            "tags": data.get("tags") or [],
            "created": data.get("created"),
            # Claiming / branch-runner protocol (ADR-0005): local never tracks these
            # (no runner concept, nothing to lock) -- always None, on every item.
            "runner": None,
            "heartbeat": None,
        }


def _new_item_body(description):
    description = _escape_heading_lookalikes((description or "").strip())
    return f"{description}\n\n## Acceptance Criteria\n\n## Result\n\n## Comments\n"


def _extract_description(body):
    desc_lines = []
    for line in body.split("\n"):
        if line.strip().startswith("## "):
            break
        desc_lines.append(line)
    text = "\n".join(desc_lines).strip()
    return _unescape_heading_lookalikes(text)


def _replace_description(body, text):
    """Rewrites the free-text block before the first `## ` heading, leaving every
    section from that heading onward (Acceptance Criteria, Result, Comments)
    untouched. An empty `text` is a valid, deliberate clear (ADR-0002 addendum,
    09.07.2026), not an error -- unlike `set_title`. `text` is escaped before being
    embedded (see `_escape_heading_lookalikes`) so it can never forge a section
    boundary on the next read."""
    lines = body.split("\n")
    heading_idx = _find_first_section_heading(lines)
    rest = lines[heading_idx:] if heading_idx is not None else []
    text = _escape_heading_lookalikes((text or "").strip())
    prefix = f"{text}\n\n" if text else ""
    return prefix + "\n".join(rest)


def _find_first_section_heading(lines):
    for i, line in enumerate(lines):
        if line.strip().startswith("## "):
            return i
    return None


def _extract_section_items(body, heading):
    return [
        _unescape_heading_lookalikes(_strip_bullet(line))
        for line in _section_lines(body.split("\n"), heading)
    ]


def _append_to_section(body, heading, text):
    """Appends `text` as a bullet to the named section (creating it at the end of the
    body if absent). Shared by `append_result` (RESULT_HEADING) and `comment`
    (COMMENTS_HEADING) -- same append-and-rewrite logic, different heading, per
    ADR-0002's addendum: the two channels are structurally separate sections, not a
    marker split (that's youtrack's mechanism, not local's). `text` is escaped before
    being embedded (see `_escape_heading_lookalikes`) so it can never forge a section
    boundary on the next read."""
    lines = body.split("\n")
    new_line = f"- {_escape_heading_lookalikes(text)}"
    heading_idx = _find_heading(lines, heading)

    if heading_idx is None:
        prefix = body.rstrip("\n")
        if prefix:
            prefix += "\n\n"
        return f"{prefix}{heading}\n{new_line}\n"

    end_idx = _section_end(lines, heading_idx)
    existing = [_strip_bullet(line) for line in _section_lines(lines, heading, heading_idx, end_idx)]
    new_section = [heading] + [f"- {item}" for item in existing] + [new_line]
    return "\n".join(lines[:heading_idx] + new_section + lines[end_idx:])


def _find_heading(lines, heading):
    for i, line in enumerate(lines):
        if line.strip() == heading:
            return i
    return None


def _section_end(lines, heading_idx):
    for i in range(heading_idx + 1, len(lines)):
        if lines[i].strip().startswith("## "):
            return i
    return len(lines)


def _section_lines(lines, heading, heading_idx=None, end_idx=None):
    if heading_idx is None:
        heading_idx = _find_heading(lines, heading)
        if heading_idx is None:
            return []
        end_idx = _section_end(lines, heading_idx)
    return [
        line for line in lines[heading_idx + 1:end_idx]
        if line.strip() and not line.strip().startswith("<!--")
    ]


def _strip_bullet(line):
    stripped = line.strip()
    if stripped.startswith("- "):
        return stripped[2:].strip()
    return stripped
