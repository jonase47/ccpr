#!/usr/bin/env python3
"""logs-summary.py – Evaluates session logs and creates summaries.

Usage: ~/.claude/scripts/logs-summary.py [focus] [period] [--project <path>]
  focus: errors, performance, agents, loops, all (default: all)
  period: today, week, session:<id>, all (default: today)
  --project: Only evaluate sessions for this project directory
Output: Markdown on stdout
"""

import sys
import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict

LOGS_DIR = os.path.expanduser("~/.claude/logs")
SESSIONS_DIR = os.path.expanduser("~/.claude/sessions")


def get_project_session_ids(project_path: str) -> set:
    """Get session IDs that belong to a specific project directory."""
    project_path = os.path.realpath(os.path.expanduser(project_path))
    session_ids = set()

    if not os.path.isdir(SESSIONS_DIR):
        return session_ids

    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            cwd = os.path.realpath(data.get("cwd", ""))
            if cwd == project_path or cwd.startswith(project_path + os.sep):
                session_ids.add(data.get("sessionId", ""))
        except (json.JSONDecodeError, OSError):
            continue

    return session_ids


def find_log_files(period: str = "today", project_session_ids: set = None) -> list:
    """Find relevant .jsonl log files based on time period and optional project filter."""
    log_files = []

    for root, dirs, files in os.walk(LOGS_DIR):
        for fname in files:
            if fname.endswith(".jsonl"):
                fpath = os.path.join(root, fname)

                # Project filter: only include session dirs matching project
                if project_session_ids is not None:
                    # Check if this file is in a session directory that matches
                    parts = fpath.split(os.sep)
                    if "sessions" in parts:
                        sess_idx = parts.index("sessions")
                        if sess_idx + 1 < len(parts):
                            session_dir = parts[sess_idx + 1]
                            if session_dir not in project_session_ids:
                                continue
                    else:
                        # Aggregated logs – skip when filtering by project
                        continue

                mtime = os.path.getmtime(fpath)
                mdate = datetime.fromtimestamp(mtime)

                if period == "today":
                    if mdate.date() == datetime.now().date():
                        log_files.append((fpath, mdate))
                elif period == "week":
                    if mdate >= datetime.now() - timedelta(days=7):
                        log_files.append((fpath, mdate))
                elif period.startswith("session:"):
                    session_id = period.split(":", 1)[1]
                    if session_id in fname:
                        log_files.append((fpath, mdate))
                elif period == "all":
                    log_files.append((fpath, mdate))

    return sorted(log_files, key=lambda x: x[1], reverse=True)


def parse_log_entries(log_files: list) -> list:
    """Parse JSONL log files into entries."""
    entries = []

    for fpath, _ in log_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entry["_file"] = fpath
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    return entries


def analyze_errors(entries: list) -> dict:
    """Analyze error patterns in log entries."""
    errors = Counter()
    error_details = defaultdict(list)

    for entry in entries:
        # Check for error indicators
        content = json.dumps(entry, ensure_ascii=False)

        if "error" in content.lower() or "Error" in content:
            # Extract error type
            for pattern, name in [
                (r"LoopWarning", "LoopWarning"),
                (r"EISDIR", "EISDIR"),
                (r"ENOENT", "ENOENT"),
                (r"ToolFailure", "ToolFailure"),
                (r"timeout", "Timeout"),
                (r"EACCES", "Permission Error"),
                (r"ModuleNotFoundError", "ModuleNotFound"),
                (r"SyntaxError", "SyntaxError"),
                (r"TypeError", "TypeError"),
            ]:
                if re.search(pattern, content, re.IGNORECASE):
                    errors[name] += 1
                    if len(error_details[name]) < 3:
                        # Try to extract context
                        msg = re.search(rf"{pattern}[^\"]*", content)
                        if msg:
                            error_details[name].append(msg.group()[:100])

    return {"counts": dict(errors.most_common(10)), "details": dict(error_details)}


def analyze_performance(entries: list) -> dict:
    """Analyze session performance metrics."""
    sessions = defaultdict(lambda: {"tool_calls": 0, "duration_entries": 0})

    current_session = None
    tool_call_count = 0

    for entry in entries:
        session = entry.get("_file", "unknown")
        if session != current_session:
            current_session = session
            tool_call_count = 0

        # Count tool calls
        if entry.get("type") in ("tool_use", "tool_result") or "tool" in str(entry.get("type", "")):
            sessions[session]["tool_calls"] += 1
        sessions[session]["duration_entries"] += 1

    session_count = len(sessions)
    avg_tools = sum(s["tool_calls"] for s in sessions.values()) / max(session_count, 1)

    # Count compact reminders and stagnation warnings
    all_content = json.dumps(entries, ensure_ascii=False)
    compact_reminders = len(re.findall(r"compact", all_content, re.IGNORECASE))
    stagnation_warnings = len(re.findall(r"stagnation|loop.?warning", all_content, re.IGNORECASE))

    return {
        "session_count": session_count,
        "avg_tool_calls": round(avg_tools),
        "compact_reminders": compact_reminders,
        "stagnation_warnings": stagnation_warnings,
    }


def analyze_agents(entries: list) -> dict:
    """Analyze agent usage patterns."""
    agent_calls = Counter()
    agent_names = [
        "senior-developer", "qa-tester", "wingman", "konzeptor",
        "system-architekt", "project-planner", "ux-designer",
        "code-reviewer", "debugger", "devops", "security-master",
        "pentester", "tech-writer", "business-analyst",
    ]

    all_content = json.dumps(entries, ensure_ascii=False)

    for agent in agent_names:
        count = len(re.findall(agent, all_content, re.IGNORECASE))
        if count > 0:
            agent_calls[agent] = count

    return {"agent_usage": dict(agent_calls.most_common())}


def analyze_loops(entries: list) -> dict:
    """Detect potential loops (repeated operations on same files)."""
    read_ops = Counter()
    write_ops = Counter()

    for entry in entries:
        content = json.dumps(entry, ensure_ascii=False)

        # Detect file reads
        file_match = re.findall(r'"file_path"\s*:\s*"([^"]+)"', content)
        for f in file_match:
            if "Read" in content:
                read_ops[f] += 1
            elif "Write" in content or "Edit" in content:
                write_ops[f] += 1

    # Flag files read more than 5 times
    repeated_reads = {f: c for f, c in read_ops.items() if c > 5}

    return {
        "repeated_reads": dict(Counter(repeated_reads).most_common(5)),
        "most_edited": dict(Counter(write_ops).most_common(5)),
    }


def format_report(focus: str, period: str, errors: dict, perf: dict, agents: dict, loops: dict) -> str:
    """Format analysis results as Markdown."""
    now = datetime.now().strftime("%d.%m.%Y")
    lines = []

    period_label = {
        "today": "today",
        "week": "last 7 days",
        "all": "all available",
    }.get(period, period)

    lines.append(f"# Log Analysis ({now}, {period_label})")
    lines.append("")

    if focus in ("all", "performance"):
        lines.append(f"## Sessions: {perf['session_count']}")
        lines.append(f"- Average tool calls per session: {perf['avg_tool_calls']}")
        lines.append(f"- Compact reminders triggered: {perf['compact_reminders']}x")
        lines.append(f"- Stagnation warnings: {perf['stagnation_warnings']}x")
        lines.append("")

    if focus in ("all", "errors"):
        lines.append("## Top Errors")
        if errors["counts"]:
            for i, (name, count) in enumerate(errors["counts"].items(), 1):
                detail = ""
                if name in errors["details"] and errors["details"][name]:
                    detail = f" – {errors['details'][name][0]}"
                lines.append(f"{i}. {name} ({count}x){detail}")
        else:
            lines.append("No errors found.")
        lines.append("")

    if focus in ("all", "agents"):
        lines.append("## Agent Usage")
        if agents["agent_usage"]:
            lines.append("| Agent | References |")
            lines.append("|-------|------------|")
            for agent, count in agents["agent_usage"].items():
                lines.append(f"| {agent} | {count} |")
        else:
            lines.append("No agent usage found.")
        lines.append("")

    if focus in ("all", "loops"):
        lines.append("## Loop Analysis")
        if loops["repeated_reads"]:
            lines.append("**Files read multiple times (>5x):**")
            for f, c in loops["repeated_reads"].items():
                lines.append(f"- {f}: read {c}x")
        if loops["most_edited"]:
            lines.append("**Most edited files:**")
            for f, c in loops["most_edited"].items():
                lines.append(f"- {f}: edited {c}x")
        if not loops["repeated_reads"] and not loops["most_edited"]:
            lines.append("No conspicuous patterns.")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    recommendations = []

    if loops.get("repeated_reads"):
        recommendations.append("- Read loops indicate missing codebase knowledge -> update Agent Memory")
    if perf.get("compact_reminders", 0) > 2:
        recommendations.append("- Frequent compact reminders -> cut tasks smaller or use /compact more proactively")
    if perf.get("stagnation_warnings", 0) > 0:
        recommendations.append("- Stagnation warnings -> reconsider approach instead of getting stuck in loops")
    if errors.get("counts", {}).get("LoopWarning", 0) > 2:
        recommendations.append("- LoopWarnings -> do not read files repeatedly, cache results")

    if recommendations:
        lines.extend(recommendations)
    else:
        lines.append("- No conspicuous issues found.")

    lines.append("")
    return "\n".join(lines)


def main():
    # Parse --project flag from argv
    project_path = None
    args = sys.argv[1:]
    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            project_path = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("Error: --project requires a path")
            sys.exit(1)

    focus = args[0] if len(args) > 0 else "all"
    period = args[1] if len(args) > 1 else "today"

    if focus not in ("errors", "performance", "agents", "loops", "all"):
        print(f"Unknown focus: {focus}")
        print("Allowed: errors, performance, agents, loops, all")
        sys.exit(1)

    project_session_ids = None
    if project_path:
        project_session_ids = get_project_session_ids(project_path)
        if not project_session_ids:
            print(f"No sessions found for project: {project_path}")
            sys.exit(0)

    log_files = find_log_files(period, project_session_ids)

    if not log_files:
        print(f"No log files found for period: {period}")
        sys.exit(0)

    entries = parse_log_entries(log_files)

    errors = analyze_errors(entries) if focus in ("all", "errors") else {"counts": {}, "details": {}}
    perf = analyze_performance(entries) if focus in ("all", "performance") else {}
    agents = analyze_agents(entries) if focus in ("all", "agents") else {"agent_usage": {}}
    loops = analyze_loops(entries) if focus in ("all", "loops") else {"repeated_reads": {}, "most_edited": {}}

    report = format_report(focus, period, errors, perf, agents, loops)
    print(report)


if __name__ == "__main__":
    main()
