#!/usr/bin/env python3
"""command-check.py – Checks prerequisites before a command call.

Usage: ~/.claude/scripts/command-check.py <command> [projectdirectory]
Output: "ready" or "blocked" with reasons on stdout
"""

import sys
import os
import re

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from next_steps import extract_phase_from_handover
from gate_checklists import (
    GATE_FILE_PATHS,
    GATE_VERDICT_VOCABULARIES,
    GATE_VERDICT_PASSING_VALUES,
    gate_artifact_kind,
)

# Command -> phase mapping (derived from command prefix)
def get_command_phase(command: str) -> str:
    """Extract phase from command name."""
    match = re.match(r"p(\d)", command)
    if match:
        return f"p{match.group(1)}"
    if command.startswith("gate-p"):
        match = re.match(r"gate-p(\d)", command)
        if match:
            return f"p{match.group(1)}"
    return None


# Required artefacts per command (key commands only)
COMMAND_PREREQUISITES = {
    "p5-implement": {
        "files": ["docs/planning/SPRINT.md"],
        "gate": "gate-p4",
    },
    "p5-impl-red": {
        "files": ["docs/planning/SPRINT.md"],
        "gate": "gate-p4",
    },
    "p5-impl-green": {
        "files": ["docs/planning/SPRINT.md"],
        "gate": "gate-p4",
    },
    "p5-impl-refactor": {
        "files": ["docs/planning/SPRINT.md"],
        "gate": "gate-p4",
    },
    "p5-review": {
        "files": ["src/"],
        "gate": "gate-p4",
    },
    "p5-acceptance": {
        "files": ["src/", "tests/"],
        "gate": "gate-p4",
    },
    "p6-functional": {
        "files": ["src/", "tests/"],
        "gate": "gate-p5",
    },
    "p6-audit": {
        "files": ["src/"],
        "gate": "gate-p5",
    },
    "p6-pentest": {
        "files": ["src/"],
        "gate": "gate-p5",
    },
    "p7-prepare": {
        "files": ["src/", "docs/quality/"],
        "gate": "gate-p6",
    },
    "p7-deploy": {
        "files": ["docs/launch/PREPARE.md"],
        "gate": "gate-p6",
    },
    "p4-backlog": {
        "files": [],
        "gate": "gate-p3",
    },
    "p4-sprint": {
        "files": ["docs/planning/BACKLOG.md"],
        "gate": "gate-p3",
    },
    "p3-architecture": {
        "files": [],
        "gate": "gate-p2",
    },
    "p3-data-model": {
        "files": ["docs/architecture/ARCHITECTURE.md"],
        "gate": None,  # Same phase, no gate needed
    },
    "p3-security": {
        "files": ["docs/architecture/ARCHITECTURE.md"],
        "gate": None,
    },
}


def _read_frontmatter_field(path: str, key: str) -> str:
    """Returns the value of a flat top-level `key:` from a document's YAML
    frontmatter block (the `---`-delimited block at the very start of the
    file), or None if the file has no such block or the key is absent
    inside it. First match wins; surrounding quotes are stripped. No list
    support needed here -- `gate:` is never a list.

    Deliberately NOT described as a mirror of scripts/lib/frontmatter.sh's
    `fm_field`: measured 29.08.2026, the two disagree on a CRLF-terminated
    file. Python's text-mode open() translates \r\n before any line is
    inspected, so this function reads `gate: go` correctly; awk's `$0 ==
    "---"` in `fm_has`/`fm_extract` sees "---\r" and reports the whole
    frontmatter block as absent, so phase-docs-lint.sh calls the same file
    "required field missing: gate". Direction matters: the lint is the
    strict one and this parser the lenient one. The root cause is
    pre-existing in frontmatter.sh and affects every check built on it, not
    just this field -- scripts/memory-lint.sh already paid for the same
    lesson once (WI-0086, `sub(/\r$/, "")`, four regression tests in
    test_memory_lint.py). Not fixed here: it is a separate defect with a
    four-lint blast radius, and no CRLF document currently sits inside any
    phase folder in the three reference projects. Recorded so the next
    reader does not have to re-measure it.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if not lines or lines[0].strip() != "---":
        return None
    body = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        body.append(line)
    if not closed:
        return None
    pattern = re.compile(r"^%s:\s*(.*?)\s*$" % re.escape(key))
    for line in body:
        match = pattern.match(line)
        if match:
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value
    return None


def check_gate_passed(gate: str, project_dir: str) -> tuple:
    """Checks whether `gate` has passed. Returns (passed: bool, reason:
    str | None) -- reason is None exactly when passed is True.

    The verdict is read from the gate artifact's own `gate:` YAML
    frontmatter field (templates/PHASE_DOC_SCHEMA.md, "## Gate verdict"),
    never from prose. A prose scan was tried and found wrong three times in
    three consecutive attempts (WI-0129, findings F3/F4): the substring
    "Go" also occurs inside "No-Go" and inside "Go-Live", and every gate
    command instructs authors to *name* "No-Go" in prose when flagging an
    Inviolable breach -- no ordering or regex heuristic over the body text
    can tell a real verdict from a mention of one, and 18 real gate
    documents across three CCPR-using projects were found to use seven
    different prose spellings of their verdict.

    The path probed comes from GATE_FILE_PATHS (scripts/lib/
    gate_checklists.py) -- the artifact each gate-pN.md command itself
    claims to write. `gate-p5` maps to docs/planning/SPRINT.md, the one
    gate with no dedicated GATE_P5.md of its own.

    The accepted vocabulary is selected by the ARTIFACT the path names, not
    by the gate key (gate_artifact_kind(), scripts/lib/gate_checklists.py):
    docs/planning/SPRINT.md accepts pending/done/conditionally_done/
    not_done, every docs/<phase>/GATE_P*.md accepts pending/go/
    conditional_go/no_go/pivot. A value valid on one artifact is rejected
    on the other -- `gate: done` on a GATE_P*.md file, or `gate: go` on
    SPRINT.md, both fail closed.

    Fails closed on purpose, with a reason naming exactly which of four
    shapes the failure is:
      1. the gate's own artifact does not exist yet (falls through to the
         HANDOVER.md fallback below -- see that comment);
      2. the artifact exists but carries no `gate:` field at all;
      3. it carries a `gate:` value outside its artifact's vocabulary;
      4. it carries a valid but non-passing verdict (e.g. `pending`,
         `no_go`, `pivot`, `not_done`).
    There is no lenient fallback for (2) or (3) -- the previous prose
    scanner's `return True` for "no verdict vocabulary found at all" was
    finding F4, and is not carried forward.

    Out of scope, unchanged from before this fix (WI-0129 finding F5, a
    separate open decision): when the gate's own artifact file does not
    exist at all (failure shape 1 above), this falls through to comparing
    the project's current phase (docs/HANDOVER.md) against the gate's phase
    number -- a MAPPED gate whose file has simply not been written yet is
    treated the same as an unmapped one. That branch, and its leniency, are
    untouched here.
    """
    gate_file_rel = GATE_FILE_PATHS.get(gate)
    if gate_file_rel:
        path = os.path.join(project_dir, gate_file_rel)
        if os.path.isfile(path):
            kind = gate_artifact_kind(gate_file_rel)
            vocabulary = GATE_VERDICT_VOCABULARIES[kind]
            passing_values = GATE_VERDICT_PASSING_VALUES[kind]
            verdict = _read_frontmatter_field(path, "gate")
            if verdict is None:
                return False, f"{gate_file_rel} has no 'gate:' field in its frontmatter"
            if verdict not in vocabulary:
                return False, (
                    f"{gate_file_rel} gate='{verdict}' is not a valid verdict "
                    f"(expected one of {sorted(vocabulary)})"
                )
            if verdict not in passing_values:
                return False, f"{gate_file_rel} gate='{verdict}' does not unblock the next phase"
            return True, None

    # Also check HANDOVER.md for phase completion hints (finding F5,
    # deliberately unchanged -- see docstring above)
    if os.path.isfile(os.path.join(project_dir, "docs", "HANDOVER.md")):
        # Check if current phase is beyond the gate's phase
        info = extract_phase_from_handover(project_dir)
        if info["phase"]:
            current_num = int(info["phase"][1])
            gate_num = int(gate.replace("gate-p", ""))
            if current_num > gate_num:
                return True, None

    return False, f"{gate} not passed (no gate artifact found, and HANDOVER.md does not show the phase beyond {gate})"


def check_command(command: str, project_dir: str) -> tuple:
    """Check if command prerequisites are met.

    Returns (ready: bool, reasons: list[str])
    """
    command = command.lstrip("/")
    reasons = []

    # Check specific prerequisites
    prereqs = COMMAND_PREREQUISITES.get(command)

    if prereqs:
        # Check required files
        for f in prereqs.get("files", []):
            full_path = os.path.join(project_dir, f)
            if f.endswith("/"):
                if not os.path.isdir(full_path):
                    reasons.append(f"{f} missing (directory not present)")
                elif not os.listdir(full_path):
                    reasons.append(f"{f} is empty")
            else:
                if not os.path.isfile(full_path):
                    reasons.append(f"{f} missing (prerequisite for /{command})")

        # Check gate
        gate = prereqs.get("gate")
        if gate:
            passed, reason = check_gate_passed(gate, project_dir)
            if not passed:
                reasons.append(reason)

    else:
        # Generic phase-based check
        phase = get_command_phase(command)
        if phase:
            phase_num = int(phase[1])
            if phase_num > 0:
                prev_gate = f"gate-p{phase_num - 1}"
                passed, reason = check_gate_passed(prev_gate, project_dir)
                if not passed:
                    reasons.append(reason)

    return len(reasons) == 0, reasons


def main():
    if len(sys.argv) < 2:
        print("Usage: command-check.py <command> [projectdirectory]")
        print("  command: p5-implement, p6-audit, gate-p3, etc.")
        sys.exit(1)

    command = sys.argv[1].lstrip("/")
    project_dir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    ready, reasons = check_command(command, project_dir)

    if ready:
        print("ready")
    else:
        print("blocked")
        for reason in reasons:
            print(f"- {reason}")

    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()
