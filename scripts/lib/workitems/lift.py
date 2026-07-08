"""lift.py – `ccpr workitems lift`: proposes structured local work items from
heterogeneous prose sources (ADR-0004). A SCAFFOLD, not magic: dry-run by default,
semi-automated, and explicit about what needs a human.

Scope for this increment: ONE concrete input format — Markdown checklists
(`- [ ]` open / `- [x]` done) and simple bulleted lists (a bullet with no checkbox,
whose done/open status cannot be determined from the text alone). Any other line
shape (prose paragraphs, tables, code blocks, other markup) is reported under
`skipped_unsupported`, never silently dropped — other formats are explicitly future
work, not attempted here.

CRITICAL — read before trusting this tool's output. ADR-0004 requires that a lifted
item's status be VERIFIED AGAINST THE CODE / VCS, because prose status drifts from
reality in both directions (long-done work still marked "open"; hidden-done work
never marked at all). That verification needs human judgment a script does not have.
This module does NOT perform it and does NOT claim to. Its job is narrower and
honest: parse the source text, and SURFACE what a human must verify — cross-source
contradictions (the same behaviour described with conflicting open/done markers) and
items whose status the text simply doesn't state (confidence: low, defaulted to
Backlog, flagged for review). Every proposed item — especially every low-confidence
or contradictory one — is unverified until a human confirms it against the actual
code. DISCLAIMER below is embedded in every report this module returns, and (for
low-confidence items) in the written item's description too.
"""

import hashlib
import re

from workitems import WorkItemError

DISCLAIMER = (
    "lift does NOT verify status against the code or VCS (ADR-0004 requires that, "
    "but it needs human judgment a script doesn't have). It only parses source text "
    "and surfaces what needs human verification: cross-source contradictions, and "
    "items whose status could not be determined from the text (confidence: low, "
    "defaulted to Backlog). Treat every proposed item as unverified until a human "
    "confirms it against the actual code."
)

LIFT_KEY_PREFIX = "Lift-Key: "

_CHECKLIST_PATTERN = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.+?)\s*$")
_BULLET_PATTERN = re.compile(r"^\s*-\s+(.+?)\s*$")
_HEADING_PATTERN = re.compile(r"^\s*#{1,6}\s+.+$")


def parse_exclude_rule(raw):
    """Parse a `PATTERN=REASON` CLI argument into {"pattern": ..., "reason": ...}."""
    pattern, _, reason = raw.partition("=")
    return {"pattern": pattern, "reason": reason or "excluded"}


def lift(source_paths, local_backend, exclude_rules=None, apply=False):
    """Scan source_paths for checklist/bulleted-list items and propose local items.

    Dry-run (apply=False, the default): returns the report, writes nothing.
    apply=True: creates each proposed item via local_backend.create() (so ids are
    assigned the same way any other local item gets one), re-reads it to confirm it
    parses (fails loudly if not — "parse its own output"), and records the assigned
    id in the report. A single item's failure (whatever the cause) is caught,
    recorded in report["failed"], and does not abort the rest of the batch.
    """
    compiled_rules = [
        {"compiled": re.compile(rule["pattern"], re.IGNORECASE), "reason": rule["reason"]}
        for rule in (exclude_rules or [])
    ]

    report = {
        "proposed": [], "already_lifted": [], "excluded": [],
        "skipped_unsupported": [], "contradictions": [], "duplicate_within_batch": [],
        "failed": [], "applied": bool(apply), "disclaimer": DISCLAIMER,
    }

    candidates = []
    for source_path in source_paths:
        with open(source_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line_number, raw_line in enumerate(lines, start=1):
            _classify_line(source_path, line_number, raw_line, compiled_rules, candidates, report)

    existing_keys = _existing_lift_keys(local_backend)
    _resolve_candidates(candidates, existing_keys, report)

    if apply:
        _apply(report, local_backend)

    return report


def _classify_line(source_path, line_number, raw_line, compiled_rules, candidates, report):
    line = raw_line.rstrip("\n")
    if not line.strip() or _HEADING_PATTERN.match(line):
        return  # structural noise (blank line / heading) — not a candidate, not reported

    checklist_match = _CHECKLIST_PATTERN.match(line)
    if checklist_match:
        marker, text = checklist_match.groups()
        status = "Done" if marker.lower() == "x" else "Backlog"
        confidence = "normal"
    else:
        bullet_match = _BULLET_PATTERN.match(line)
        if bullet_match:
            text = bullet_match.group(1)
            status = "Backlog"
            confidence = "low"  # no checkbox — text alone can't settle done/open
        else:
            report["skipped_unsupported"].append({
                "file": source_path, "line": line_number, "text": line.strip(),
                "reason": "not a supported format (checklist or simple bulleted list "
                          "only in this increment); other formats are future work",
            })
            return

    for rule in compiled_rules:
        if rule["compiled"].search(text):
            report["excluded"].append({
                "file": source_path, "line": line_number, "text": text,
                "reason": rule["reason"],
            })
            return

    normalized_text = _normalize(text)
    candidates.append({
        "file": source_path, "line": line_number, "text": text,
        "status": status, "confidence": confidence,
        "normalized_text": normalized_text,
        "dedup_key": _dedup_key(source_path, normalized_text),
    })


def _normalize(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def _dedup_key(source_path, normalized_text):
    return hashlib.sha256(f"{source_path}::{normalized_text}".encode("utf-8")).hexdigest()[:16]


def _resolve_candidates(candidates, existing_keys, report):
    """Group by behaviour described (normalized text), not by source (ADR-0004:
    dedup by behaviour, not id) — the same line repeated across files becomes ONE
    proposed item, unless the sources disagree on its status (a contradiction)."""
    groups = {}
    for candidate in candidates:
        groups.setdefault(candidate["normalized_text"], []).append(candidate)

    for normalized_text, occurrences in groups.items():
        statuses = {occ["status"] for occ in occurrences}
        if len(statuses) > 1:
            report["contradictions"].append({
                "text": normalized_text,
                "occurrences": [
                    {"file": occ["file"], "line": occ["line"], "status": occ["status"]}
                    for occ in occurrences
                ],
            })
            continue

        new_occurrences = [occ for occ in occurrences if occ["dedup_key"] not in existing_keys]
        for occ in occurrences:
            if occ["dedup_key"] in existing_keys:
                report["already_lifted"].append(
                    {"file": occ["file"], "line": occ["line"], "text": occ["text"]}
                )
        if not new_occurrences:
            continue

        primary = min(new_occurrences, key=lambda occ: (occ["file"], occ["line"]))
        for occ in new_occurrences:
            if occ is not primary:
                report["duplicate_within_batch"].append({
                    "file": occ["file"], "line": occ["line"], "text": occ["text"],
                    "merged_into": primary["text"],
                })

        report["proposed"].append({
            "title": primary["text"],
            "status": primary["status"],
            "confidence": primary["confidence"],
            "sources": [{"file": occ["file"], "line": occ["line"]} for occ in new_occurrences],
            "dedup_keys": [occ["dedup_key"] for occ in new_occurrences],
            "id": None,
        })


def _existing_lift_keys(local_backend):
    keys = set()
    for item in local_backend.list():
        description = item.get("description") or ""
        for line in description.split("\n"):
            if line.startswith(LIFT_KEY_PREFIX):
                keys.update(k.strip() for k in line[len(LIFT_KEY_PREFIX):].split(",") if k.strip())
    return keys


def _apply(report, local_backend):
    for entry in report["proposed"]:
        try:
            _apply_one(entry, local_backend)
        except Exception as exc:
            # One bad item (an edge case the frontmatter writer/parser doesn't
            # handle, a backend-level failure, anything) must not abort the whole
            # batch -- record it and continue with the rest.
            report["failed"].append({"title": entry["title"], "error": str(exc)})


def _apply_one(entry, local_backend):
    description_lines = [
        "Lifted via `ccpr workitems lift` (ADR-0004) — status NOT verified against code.",
    ]
    description_lines.extend(
        f"Source: {source['file']}:{source['line']}" for source in entry["sources"]
    )
    if entry["confidence"] == "low":
        description_lines.append(
            "Confidence: low — status could not be determined from the source "
            "text; defaulted to Backlog. Please review against the actual code."
        )
    description_lines.append(f"{LIFT_KEY_PREFIX}{','.join(entry['dedup_keys'])}")
    description = "\n".join(description_lines)

    created = local_backend.create(title=entry["title"], description=description)
    item_id = created["id"]
    if entry["status"] != "Backlog":
        local_backend.set_status(item_id, entry["status"])

    # Parse its own output (ADR-0004): re-read from disk and fail loudly if it
    # doesn't come back the way it was just written, rather than silently
    # shipping a serialization that turns out to be unparseable.
    reread = local_backend.get(item_id)
    if reread["title"] != entry["title"] or reread["status"] != entry["status"]:
        raise WorkItemError(
            f"lift: failed to parse its own output for item {item_id!r} "
            f"(expected title={entry['title']!r} status={entry['status']!r}, "
            f"got title={reread['title']!r} status={reread['status']!r})"
        )

    entry["id"] = item_id
