#!/usr/bin/env python3
"""quality_scan_sast_patterns.py -- grep-based SAST pattern scan used by
scripts/quality-scan.sh's scan_sast() (WI-0055).

Moved out of an inline `python3 << 'PYEOF'` heredoc that was nested inside a
`$(...)` command substitution: bash tracks quote parity while it scans for
the substitution's closing `)`, and the SQL-string pattern below carries an
apostrophe (`f\\'`) that broke that parity, making the whole shipped script
unparseable (`bash -n` failed, and running it silently exited 0 having
written nothing). A real file sidesteps the nesting entirely rather than
escaping the apostrophe -- escaping is what left scripts/memory-lint.sh
fragile for eight rounds (WI-0037, WI-0044): the fix would be correct only
until the next quote is added to a pattern, and the failure it produces is
either a hard parse error (an odd escape count) or, worse, a script that
still parses and runs but silently drops findings (an even one). A file has
no such parity constraint to defend, and it is trivially unit-testable and
`python3 -m py_compile`-able on its own.

Behaviour is unchanged from the heredoc body it replaces: walks `src`
(relative to the caller's current working directory -- scan_sast() invokes
this after cd'ing into the target project directory) and reports up to 50
pattern matches as JSON on stdout. WI-0126 wave 1a, defect 3 (28.08.2026):
when there are more than 50, one extra finding (type "scan-truncated",
severity "info") is appended naming the real total -- the cap used to be
silent, making "50 matches" and "50-plus-unknown-many matches"
byte-identical output.
"""

import os
import re
import json

PATTERNS = {
    "eval/exec": {
        "pattern": r"\b(eval|exec)\s*\(",
        "extensions": [".py", ".js", ".ts"],
        "severity": "high",
        "message": "eval/exec found - potential code injection risk",
    },
    "innerHTML": {
        "pattern": r"\.innerHTML\s*=",
        "extensions": [".js", ".ts", ".jsx", ".tsx"],
        "severity": "high",
        "message": "innerHTML assignment - XSS risk",
    },
    "SQL-String": {
        "pattern": r'(f"|f\').*?(SELECT|INSERT|UPDATE|DELETE)',
        "extensions": [".py"],
        "severity": "high",
        "message": "SQL in f-string - SQL injection risk",
    },
    "hardcoded-secret": {
        "pattern": r'(password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}',
        "extensions": [".py", ".js", ".ts", ".env", ".yml", ".yaml", ".json"],
        "severity": "critical",
        "message": "Possible hardcoded secret",
    },
    "console-log": {
        "pattern": r"console\.(log|debug|warn)\(",
        "extensions": [".js", ".ts", ".jsx", ".tsx"],
        "severity": "info",
        "message": "console.log in production code",
    },
}


def main():
    findings = []
    for root, dirs, files in os.walk("src"):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", "venv", ".venv")]
        for fname in files:
            ext = os.path.splitext(fname)[1]
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        for name, rule in PATTERNS.items():
                            if ext in rule["extensions"] and re.search(rule["pattern"], line, re.IGNORECASE):
                                findings.append({
                                    "type": f"pattern-{name}",
                                    "severity": rule["severity"],
                                    "message": rule["message"],
                                    "file": fpath,
                                    "line": i,
                                })
            except Exception:
                pass

    # A silent cap makes "50 matches" and "50-plus-unknown-many matches"
    # byte-identical output (WI-0126 wave 1a, defect 3). One extra finding,
    # appended only when the cap actually trims something, names the real
    # total instead.
    cap = 50
    total = len(findings)
    capped = findings[:cap]
    if total > cap:
        capped.append({
            "type": "scan-truncated",
            "severity": "info",
            "message": "pattern scan found %d matches; only the first %d are included" % (total, cap),
        })
    print(json.dumps(capped))


if __name__ == "__main__":
    main()
