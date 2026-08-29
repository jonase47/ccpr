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
from gate_checklists import GATE_FILE_PATHS

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


def check_gate_passed(gate: str, project_dir: str) -> bool:
    """Check if a gate has been passed (its own GATE_PX.md exists with 'Go').

    The path probed comes from GATE_FILE_PATHS (scripts/lib/
    gate_checklists.py) -- the phase-folder path each gate-pN.md command
    itself claims to write (e.g. docs/planning/GATE_P4.md), not the three
    flat legacy paths (docs/GATE_P4.md, docs/GATE-P4.md, docs/gate-p4.md)
    probed before this fix. No command, script, template or doc in this
    repo ever wrote to any of those three shapes -- dropped outright
    (WI-0129, finding F1).

    "gate-p5" has no entry in GATE_FILE_PATHS: /gate-p5 never writes a
    dedicated gate file at all (its sprint verdict lives in
    docs/planning/SPRINT.md, a differently-shaped document; parsing it is
    out of scope here). For any gate absent from GATE_FILE_PATHS, this
    function skips the file probe entirely and falls straight through to
    the HANDOVER.md phase-comparison check below.

    That fallback is not gate-p5-only, though: a MAPPED gate (one with an
    entry in GATE_FILE_PATHS -- all seven of gate-p0/1/2/3/4/6/7) whose
    phase-folder file simply does not yet exist on disk falls through to
    the exact same HANDOVER.md comparison -- the `if os.path.isfile(path):`
    check below has no `else`, so a missing file is not itself a "blocked"
    verdict. This is pre-existing behaviour, unchanged by this fix.

    WI-0129's F5 ("HANDOVER phase claim overrides any gate, verdict never
    read", docs/workitems/WI-0129.md) named this same symptom under the
    pre-fix probe, where it was unconditional: none of the three flat
    candidate paths was ever a real write target (finding F1), so no gate
    file could ever be found and this fallback ran for every gate, every
    time, regardless of what verdict a project had actually written.
    Post-fix, an existing gate file at its claimed path IS found and IS
    read -- the fallback now only runs while that file has not yet been
    written, a narrower window than what F5 described. Whether staying
    lenient even for that narrower window is still the right call for all
    seven mapped gates is a separate, currently untracked open question --
    NOT the same thing as finding 20 in docs/.handover-archive/2026-08-28-
    open-findings.md, which is about gate-p5 specifically (a gate with no
    file at all, by design, so it can ONLY ever pass through this fallback
    -- a different mechanism from a mapped gate's file being merely not
    yet written). Not decided or scoped here either way.
    """
    gate_file_rel = GATE_FILE_PATHS.get(gate)
    if gate_file_rel:
        path = os.path.join(project_dir, gate_file_rel)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
            # No gate command prescribes a verdict-line syntax -- all of
            # them only say to append the verdict under "Gate Notes". Since
            # it is appended, the LAST Go/No-Go token in the document is the
            # actual conclusion, not an earlier one: several gate commands
            # instruct writers to name "No-Go" in prose when flagging an
            # Inviolable breach, and that prose mention must not override a
            # later "Verdict: Go" (WI-0128, finding #5 follow-up).
            verdict_matches = list(re.finditer(r"\b(no.go)\b|\b(go)\b", content))
            if verdict_matches:
                # group(1) set -> the match was "no-go"; group(2) set -> "go"
                return verdict_matches[-1].group(1) is None
            # Lenient fallback: the file exists but uses no Go/No-Go
            # vocabulary at all (some projects may not use that format).
            # Absence of any verdict language is not itself a rejection.
            return True

    # Also check HANDOVER.md for phase completion hints
    if os.path.isfile(os.path.join(project_dir, "docs", "HANDOVER.md")):
        # Check if current phase is beyond the gate's phase
        info = extract_phase_from_handover(project_dir)
        if info["phase"]:
            current_num = int(info["phase"][1])
            gate_num = int(gate.replace("gate-p", ""))
            if current_num > gate_num:
                return True

    return False


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
        if gate and not check_gate_passed(gate, project_dir):
            reasons.append(f"{gate} not passed (gate file missing or no 'Go')")

    else:
        # Generic phase-based check
        phase = get_command_phase(command)
        if phase:
            phase_num = int(phase[1])
            if phase_num > 0:
                prev_gate = f"gate-p{phase_num - 1}"
                if not check_gate_passed(prev_gate, project_dir):
                    reasons.append(f"{prev_gate} not passed")

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
