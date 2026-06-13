#!/usr/bin/env python3
"""Phase-to-Commands mapping for the Claude Code agent system.

Parses HANDOVER.md to determine current phase and returns allowed next commands
based on NEXT_STEPS_REFERENCE.md rules.
"""

import re
import os
from pathlib import Path

# Phase sequence with their commands
PHASE_SEQUENCES = {
    "p0": ["p0-problem", "p0-market", "p0-regulatory", "gate-p0"],
    "p1": ["p1-journeys", "p1-features", "p1-business-model", "p1-financial-plan", "p1-privacy", "gate-p1"],
    "p2": ["p2-assumptions", "p2-market-validation", "p2-regulatory-check", "p2-poc", "gate-p2"],
    "p3": ["p3-architecture", "p3-data-model", "p3-security", "p3-ux", "p3-infra", "p3-cost", "gate-p3"],
    "p4": ["p4-backlog", "p4-setup", "p4-docs", "p4-sprint", "gate-p4"],
    "p5": ["p5-implement", "p5-review", "p5-acceptance", "p5-bugfix", "p5-docs", "gate-p5"],
    "p6": ["p6-functional", "p6-exploratory", "p6-a11y", "p6-audit", "p6-pentest", "p6-bugfix", "gate-p6"],
    "p7": ["p7-prepare", "p7-deploy", "p7-monitoring", "p7-release-docs", "p7-gtm", "gate-p7"],
    "p8": ["p8-ops", "p8-business", "p8-security", "p8-iteration"],
}

# Gate transitions: gate -> first command of next phase
GATE_TRANSITIONS = {
    "gate-p0": "p1-journeys",
    "gate-p1": "p2-assumptions",
    "gate-p2": "p3-architecture",
    "gate-p3": "p4-backlog",
    "gate-p4": "p5-implement",
    "gate-p5": "p6-functional",
    "gate-p6": "p7-prepare",
    "gate-p7": "p8-ops",
}

# Utility commands (phase-independent)
UTILITY_COMMANDS = ["konzept", "konzept-update", "epic", "user-stories", "roadmap", "roadmap-update", "decision", "project-init"]


def extract_phase_from_handover(project_dir: str) -> dict:
    """Extract current phase info from HANDOVER.md.

    Returns dict with keys: phase, status, last_command, next_step, open_items
    """
    handover_path = os.path.join(project_dir, "docs", "HANDOVER.md")
    result = {
        "phase": None,
        "status": None,
        "last_command": None,
        "next_step": None,
        "open_items": [],
    }

    if not os.path.exists(handover_path):
        return result

    with open(handover_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract phase – handles "**Phase:** P2 Validation (...)" and plain "Phase: P5"
    phase_match = re.search(r"\*{0,2}Phase\*{0,2}:?\*{0,2}\s*P(\d)", content)
    if phase_match:
        result["phase"] = f"p{phase_match.group(1)}"

    # Extract status – dedicated field at line start (not inside tables)
    status_match = re.search(r"^[* ]*Status[* ]*:?\*{0,2}\s*(.+)", content, re.MULTILINE)
    if status_match and not status_match.group(0).strip().startswith("|"):
        result["status"] = re.sub(r"\*", "", status_match.group(1)).strip()
    else:
        # Fall back: extract from phase line parenthetical, e.g. "(completed, Gate GO)"
        paren_match = re.search(r"\*{0,2}Phase\*{0,2}:?\*{0,2}\s*P\d[^(]*\(([^)]+)\)", content)
        if paren_match:
            result["status"] = paren_match.group(1).strip()

    # Extract last command/agent – handles **Last Active:** /gate-p2
    last_match = re.search(r"\*{0,2}Last Active\*{0,2}:?\*{0,2}\s*(.+)", content)
    if last_match:
        result["last_command"] = re.sub(r"\*", "", last_match.group(1)).strip()

    # Extract next steps – try inline field first, then ## section
    # Inline: "**Next Steps:** Fulfill requirements, then /p3-architecture"
    inline_next = re.search(r"\*{0,2}Next Steps?\*{0,2}:?\*{0,2}\s*(.+)", content)
    if inline_next:
        line = re.sub(r"\*", "", inline_next.group(1)).strip()
        cmd_match = re.search(r"/([a-z0-9-]+)", line)
        if cmd_match:
            result["next_step"] = cmd_match.group(1)

    # Also check ## section with numbered or bulleted items
    if not result["next_step"]:
        next_section = re.search(r"##\s*Next Steps?\s*\n((?:[\d]+\..*\n?|[-*].*\n?|/.*\n?)+)", content)
        if next_section:
            first_line = next_section.group(1).strip().split("\n")[0]
            cmd_match = re.search(r"/([a-z0-9-]+)", first_line)
            if cmd_match:
                result["next_step"] = cmd_match.group(1)

    # Extract open items
    open_section = re.search(r"##\s*Open Decisions\s*\n\|.+\n\|.+\n((?:\|.+\n)*)", content)
    if open_section:
        for line in open_section.group(1).strip().split("\n"):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells and cells[0] != "---":
                result["open_items"].append(cells[0])

    return result


def get_allowed_commands(phase: str, last_command: str = None, next_step: str = None) -> list:
    """Return allowed next commands for the given phase.

    Args:
        phase: Current phase like "p5"
        last_command: Last executed command (optional)
        next_step: Explicitly stated next step from HANDOVER.md (optional)
    """
    if not phase:
        return ["project-init", "p0-problem"]

    commands = PHASE_SEQUENCES.get(phase, [])
    if not commands:
        return []

    # If next step is explicitly stated, prioritize it
    if next_step and next_step in commands:
        result = [next_step]
        # Add gate if not already the next step
        gate = f"gate-{phase}"
        if gate in commands and gate != next_step:
            result.append(gate)
        return result[:3]

    # If last command is known, find position in sequence
    if last_command:
        # Strip leading / if present
        cmd = last_command.lstrip("/")

        # Check if it's a gate that was passed
        if cmd in GATE_TRANSITIONS:
            return [GATE_TRANSITIONS[cmd]]

        # Find in current phase sequence
        if cmd in commands:
            idx = commands.index(cmd)
            # Return next commands in sequence
            return commands[idx + 1 : idx + 4]

    # Default: return first few commands of the phase
    return commands[:3]


def check_gate_required(phase: str) -> str:
    """Check which gate must be passed before entering this phase.

    Returns the required gate name or None.
    """
    phase_num = int(phase[1]) if phase and len(phase) == 2 else None
    if phase_num and phase_num > 0:
        return f"gate-p{phase_num - 1}"
    return None


def main():
    """CLI interface for next_steps module."""
    import sys
    import json

    project_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    info = extract_phase_from_handover(project_dir)
    allowed = get_allowed_commands(info["phase"], info["last_command"], info["next_step"])
    required_gate = check_gate_required(info["phase"]) if info["phase"] else None

    output = {
        "phase": info["phase"],
        "status": info["status"],
        "last_command": info["last_command"],
        "allowed_commands": allowed,
        "required_gate": required_gate,
        "open_items": info["open_items"],
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
