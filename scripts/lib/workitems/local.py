"""local.py – The `local` work-item backend: structured Markdown at docs/workitems/<id>.md.

Reference implementation of the CCPR work-item contract (ADR-0002) and the contract
test fixture (see scripts/tests/workitems/contract.py). No server, no token: reads and
writes one Markdown file per item.
"""

import datetime
import os
import re
from pathlib import Path

from workitems import STATUS_VALUES, WorkItemError, frontmatter, validate_item_id

RESULT_HEADING = "## Result"

_ID_NUMBER_PATTERN = re.compile(r"^WI-(\d+)$")


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

    def list(self, status=None, owner=None):
        if not self.workitems_dir.is_dir():
            return []

        items = []
        for path in sorted(self.workitems_dir.glob("*.md")):
            item = self._item_from_path(path)
            if status is not None and item["status"] != status:
                continue
            if owner is not None and item["owner"] != owner:
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
        new_body = _append_to_result_section(body, ref)
        self._write(path, data, new_body)
        return self._item_from_data(data, new_body)

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
            "result-link": _extract_result_links(body),
            "owner": data.get("owner") or None,
            "type": data.get("type"),
            "refs": data.get("refs"),
            "tags": data.get("tags"),
            "created": data.get("created"),
            # Claiming / branch-runner protocol (ADR-0005): local never tracks these
            # (no runner concept, nothing to lock) -- always None, on every item.
            "runner": None,
            "heartbeat": None,
        }


def _new_item_body(description):
    description = (description or "").strip()
    return f"{description}\n\n## Acceptance Criteria\n\n## Result\n"


def _extract_description(body):
    desc_lines = []
    for line in body.split("\n"):
        if line.strip().startswith("## "):
            break
        desc_lines.append(line)
    return "\n".join(desc_lines).strip()


def _extract_result_links(body):
    return [_strip_bullet(line) for line in _result_section_lines(body.split("\n"))]


def _append_to_result_section(body, ref):
    lines = body.split("\n")
    new_line = f"- {ref}"
    heading_idx = _find_heading(lines, RESULT_HEADING)

    if heading_idx is None:
        prefix = body.rstrip("\n")
        if prefix:
            prefix += "\n\n"
        return f"{prefix}{RESULT_HEADING}\n{new_line}\n"

    end_idx = _section_end(lines, heading_idx)
    existing = [_strip_bullet(line) for line in _result_section_lines(lines, heading_idx, end_idx)]
    new_section = [RESULT_HEADING] + [f"- {link}" for link in existing] + [new_line]
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


def _result_section_lines(lines, heading_idx=None, end_idx=None):
    if heading_idx is None:
        heading_idx = _find_heading(lines, RESULT_HEADING)
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
