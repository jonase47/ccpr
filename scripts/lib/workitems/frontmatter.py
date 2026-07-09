"""frontmatter.py – Minimal YAML-frontmatter reader/writer for work-item files.

Handles exactly the subset used by docs/workitems/<id>.md (ADR-0002 / Manual/WORKITEMS.md):
flat scalar values, inline lists (`refs: [ADR-0011]`), quoted strings, and trailing
`# comment` fragments. This is deliberately not a general YAML parser — the repo has
no PyYAML dependency today (scripts/ is stdlib-only), and the frontmatter schema here
is narrow enough that a full YAML library would be a heavy dependency for what it buys.
"""

import re

FRONTMATTER_KEY_ORDER = (
    "id", "title", "status", "type", "owner", "refs", "tags", "links", "created",
)

# A scalar is an inline list only if the ENTIRE trimmed value is bracketed —
# not merely prefixed with "[" (e.g. `title: [WIP] Rate limiting` is a scalar).
_LIST_PATTERN = re.compile(r"^\[.*\]$")


def parse(text):
    """Split `text` into (frontmatter_dict, body).

    Returns ({}, text) if `text` does not start with a `---` frontmatter block.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text

    data = {}
    for line in lines[1:end_idx]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = _parse_scalar(value.strip())

    body = "\n".join(lines[end_idx + 1:])
    if body.startswith("\n"):
        body = body[1:]
    return data, body


def render(data, body):
    """Serialize `data` (flat dict) + `body` back into a full frontmatter document."""
    lines = ["---"]
    seen = set()
    for key in FRONTMATTER_KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {_format_value(data[key])}")
            seen.add(key)
    for key, value in data.items():
        if key not in seen:
            lines.append(f"{key}: {_format_value(value)}")
    lines.append("---")
    lines.append("")

    text = "\n".join(lines)
    if body:
        text += body if body.startswith("\n") else f"\n{body}"
    return text if text.endswith("\n") else f"{text}\n"


def _parse_scalar(value):
    value = value.strip()
    if _LIST_PATTERN.match(value):
        inner = value[1:-1]
        if not inner.strip():
            return []
        return [_unquote(v.strip()) for v in inner.split(",")]
    value = _strip_inline_comment(value)
    return _unquote(value)


def _strip_inline_comment(value):
    """Strip a trailing `# comment`, but never split on a `#` inside a quoted value.

    Scans char-by-char honoring `\\` as an escape prefix, so an escaped quote
    (`\\"` inside a double-quoted value) never ends the scan early — the previous
    heuristic ("find the next occurrence of the opening quote character") broke on
    any value that itself contained that character unescaped, e.g. the apostrophe
    in `'It's "done"'`.
    """
    value = value.strip()
    if value and value[0] in ("'", '"'):
        quote = value[0]
        i = 1
        closing = None
        while i < len(value):
            if value[i] == "\\" and i + 1 < len(value):
                i += 2
                continue
            if value[i] == quote:
                closing = i
                break
            i += 1
        if closing is None:
            return value  # no closing quote found; treat literally rather than guess
        remainder = value[closing + 1:]
        if "#" in remainder:
            remainder = remainder.split("#", 1)[0]
        return (value[:closing + 1] + remainder).strip()
    if "#" in value:
        value = value.split("#", 1)[0]
    return value.strip()


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        inner = value[1:-1]
        if value[0] == '"':
            # Reverse of _format_value's escaping, in the opposite order: unescape
            # \" before \\, or a literal \\" would be mis-decoded.
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


def _format_value(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]"
    text = str(value)
    if text.startswith("[") or "#" in text:
        # Quote so a later parse doesn't mistake this for an inline list (leading
        # "[") or a comment marker ("#"). Always double-quote and ESCAPE embedded
        # quotes/backslashes rather than heuristically picking single vs. double as
        # the delimiter — a value containing BOTH quote characters (e.g. an
        # apostrophe and a literal double quote) has no safe delimiter to pick.
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text
