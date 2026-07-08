"""frontmatter.py – Minimal YAML-frontmatter reader/writer for work-item files.

Handles exactly the subset used by docs/workitems/<id>.md (ADR-0002 / Manual/WORKITEMS.md):
flat scalar values, inline lists (`refs: [ADR-0011]`), quoted strings, and trailing
`# comment` fragments. This is deliberately not a general YAML parser — the repo has
no PyYAML dependency today (scripts/ is stdlib-only), and the frontmatter schema here
is narrow enough that a full YAML library would be a heavy dependency for what it buys.
"""

FRONTMATTER_KEY_ORDER = (
    "id", "title", "status", "type", "owner", "refs", "tags", "created",
)


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
    if value.startswith("[") and "]" in value:
        inner = value[1:value.index("]")]
        if not inner.strip():
            return []
        return [_unquote(v.strip()) for v in inner.split(",")]
    value = _strip_inline_comment(value)
    return _unquote(value)


def _strip_inline_comment(value):
    """Strip a trailing `# comment`, but never split on a `#` inside a quoted value."""
    value = value.strip()
    if value and value[0] in ("'", '"'):
        quote = value[0]
        closing = value.find(quote, 1)
        if closing != -1:
            remainder = value[closing + 1:]
            if "#" in remainder:
                remainder = remainder.split("#", 1)[0]
            return (value[:closing + 1] + remainder).strip()
        return value  # no closing quote found; treat literally rather than guess
    if "#" in value:
        value = value.split("#", 1)[0]
    return value.strip()


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _format_value(value):
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]"
    text = str(value)
    if "#" in text:
        # Quote so a later parse doesn't mistake the `#` for a comment marker.
        quote = "'" if '"' in text else '"'
        return f"{quote}{text}{quote}"
    return text
