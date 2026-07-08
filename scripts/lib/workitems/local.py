"""local.py – The `local` work-item backend: structured Markdown at docs/workitems/<id>.md.

Reference implementation of the CCPR work-item contract (ADR-0002) and the contract
test fixture (see scripts/tests/workitems/contract.py). No server, no token: reads and
writes one Markdown file per item.
"""

from pathlib import Path

from workitems import STATUS_VALUES, WorkItemError, frontmatter


def create(config):
    """Factory used by the CLI dispatcher (scripts/workitems.py)."""
    workitems_dir = config.get("workitems_dir", "docs/workitems")
    return LocalBackend(workitems_dir)


class LocalBackend:
    def __init__(self, workitems_dir):
        self.workitems_dir = Path(workitems_dir)

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

    def claim(self, item_id, owner=None):
        """No-op beyond optionally setting owner (local has nothing to lock; ADR-0002 §6)."""
        path = self._path_for(item_id)
        data, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        if owner is not None:
            data["owner"] = owner
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def set_status(self, item_id, status):
        if status not in STATUS_VALUES:
            raise WorkItemError(
                f"Unknown status '{status}'. Valid values: {', '.join(STATUS_VALUES)}"
            )
        path = self._path_for(item_id)
        data, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        data["status"] = status
        self._write(path, data, body)
        return self._item_from_data(data, body)

    def _path_for(self, item_id):
        path = self.workitems_dir / f"{item_id}.md"
        if not path.is_file():
            raise WorkItemError(f"Unknown work item: {item_id}")
        return path

    def _write(self, path, data, body):
        """Write via a temp file + atomic rename so a failed write never corrupts the item."""
        text = frontmatter.render(data, body)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)

    def _item_from_path(self, path):
        data, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        return self._item_from_data(data, body)

    def _item_from_data(self, data, body):
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "status": data.get("status"),
            "description": _extract_description(body),
            "result-link": [],
            "owner": data.get("owner") or None,
            "type": data.get("type"),
            "refs": data.get("refs"),
            "tags": data.get("tags"),
            "created": data.get("created"),
        }


def _extract_description(body):
    desc_lines = []
    for line in body.split("\n"):
        if line.strip().startswith("## "):
            break
        desc_lines.append(line)
    return "\n".join(desc_lines).strip()
