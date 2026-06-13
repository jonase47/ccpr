#!/usr/bin/env bash
# quality-scan.sh – Local security and quality scans.
# Usage: ~/.claude/scripts/quality-scan.sh [scope] [projectdirectory]
# Scope: all, deps, sast, config, dsgvo
# Output: docs/.quality-scan-report.json

set -euo pipefail

SCOPE="${1:-all}"
PROJECT_DIR="${2:-$(pwd)}"
cd "${PROJECT_DIR}"

TIMESTAMP=$(date -u "+%Y-%m-%dT%H:%M:%S")
REPORT_FILE="${PROJECT_DIR}/docs/.quality-scan-report.json"

mkdir -p "${PROJECT_DIR}/docs"

# Temporary results
TMPDIR=$(mktemp -d /tmp/quality-scan-XXXXXX)
trap "rm -rf ${TMPDIR}" EXIT

# -- Scan Functions --

scan_deps() {
    local results="${TMPDIR}/deps.json"
    echo '{"scan": "deps", "findings": []}' > "${results}"

    # Node.js
    if [ -f "package-lock.json" ] || [ -f "yarn.lock" ]; then
        if command -v npm &>/dev/null; then
            local audit_raw
            audit_raw=$(npm audit --json 2>/dev/null || echo '{}')
            local vuln_count
            vuln_count=$(echo "${audit_raw}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    meta = d.get('metadata', {}).get('vulnerabilities', {})
    total = sum(meta.values()) if isinstance(meta, dict) else 0
    print(total)
except:
    print(0)
" 2>/dev/null || echo "0")

            python3 -c "
import json
findings = []
if int('${vuln_count}') > 0:
    findings.append({
        'type': 'npm-audit',
        'severity': 'warning',
        'message': '${vuln_count} npm vulnerabilities found',
        'detail': 'Run npm audit --json for details',
    })
print(json.dumps({'scan': 'deps', 'tool': 'npm-audit', 'findings': findings}))
" > "${results}"
        fi
    fi

    # Python
    if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
        if command -v pip-audit &>/dev/null; then
            local pip_raw
            pip_raw=$(pip-audit --format=json 2>/dev/null || echo '[]')
            local pip_count
            pip_count=$(echo "${pip_raw}" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

            if [ "${pip_count}" -gt 0 ]; then
                python3 -c "
import json
findings = [{'type': 'pip-audit', 'severity': 'warning', 'message': '${pip_count} Python vulnerabilities found'}]
print(json.dumps({'scan': 'deps', 'tool': 'pip-audit', 'findings': findings}))
" > "${results}"
            fi
        fi
    fi

    cat "${results}"
}

scan_sast() {
    local results="${TMPDIR}/sast.json"
    local findings="[]"

    # Semgrep if available
    if command -v semgrep &>/dev/null; then
        local semgrep_raw
        semgrep_raw=$(semgrep --config=auto --json -q . 2>/dev/null || echo '{"results":[]}')
        local semgrep_count
        semgrep_count=$(echo "${semgrep_raw}" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('results',[])))" 2>/dev/null || echo "0")

        if [ "${semgrep_count}" -gt 0 ]; then
            findings=$(echo "${semgrep_raw}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
findings = []
for r in data.get('results', [])[:20]:
    findings.append({
        'type': 'semgrep',
        'severity': r.get('extra', {}).get('severity', 'warning'),
        'message': r.get('extra', {}).get('message', '')[:200],
        'file': r.get('path', ''),
        'line': r.get('start', {}).get('line', 0),
        'rule': r.get('check_id', ''),
    })
print(json.dumps(findings))
" 2>/dev/null || echo "[]")
        fi
    fi

    # Grep-based pattern scan (fallback / always runs)
    local grep_findings
    grep_findings=$(python3 << 'PYEOF'
import os, re, json

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
        except:
            pass

print(json.dumps(findings[:50]))
PYEOF
    )

    # Merge findings
    python3 -c "
import json
semgrep = json.loads('${findings}') if '${findings}' != '[]' else []
grep_f = json.loads('''${grep_findings}''')
all_f = semgrep + grep_f
print(json.dumps({'scan': 'sast', 'findings': all_f}))
"
}

scan_config() {
    python3 << 'PYEOF'
import os, json, re

findings = []

# Check .env in .gitignore
gitignore_path = ".gitignore"
env_protected = False
if os.path.isfile(gitignore_path):
    with open(gitignore_path) as f:
        content = f.read()
    env_protected = ".env" in content

if os.path.isfile(".env") and not env_protected:
    findings.append({
        "type": "config",
        "severity": "critical",
        "message": ".env exists but is NOT in .gitignore",
        "file": ".env",
    })

# Check for debug mode in configs
for cfg_file in ["config.json", "config.yaml", "config.yml", "settings.py", "app.config.ts", "app.config.js"]:
    if os.path.isfile(cfg_file):
        with open(cfg_file, errors="ignore") as f:
            content = f.read().lower()
        if "debug" in content and ("true" in content or "= true" in content):
            findings.append({
                "type": "config",
                "severity": "warning",
                "message": f"Debug mode possibly active in {cfg_file}",
                "file": cfg_file,
            })

# CORS wildcard check
for root, dirs, files in os.walk("src"):
    dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__")]
    for fname in files:
        if fname.endswith((".py", ".js", ".ts")):
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(r'cors.*\*|allow_origin.*\*|Access-Control-Allow-Origin.*\*', line, re.IGNORECASE):
                            findings.append({
                                "type": "config",
                                "severity": "warning",
                                "message": "CORS wildcard (*) found",
                                "file": fpath,
                                "line": i,
                            })
            except:
                pass

print(json.dumps({"scan": "config", "findings": findings}))
PYEOF
}

scan_dsgvo() {
    python3 << 'PYEOF'
import os, re, json

PII_PATTERNS = {
    "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    "phone-de": r'(\+49|0)[0-9\s/\-]{8,}',
    "iban": r'[A-Z]{2}\d{2}\s?[\d\s]{12,30}',
    "geburtsdatum": r'\b(geburtsdatum|date_of_birth|dob|birthdate)\b',
}

findings = []

# Check logging for PII
for root, dirs, files in os.walk("src"):
    dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", "venv")]
    for fname in files:
        if not fname.endswith((".py", ".js", ".ts", ".jsx", ".tsx")):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    # Check if PII patterns appear in logging statements
                    is_log = bool(re.search(r'(log\.|logger\.|console\.log|print\(|logging\.)', line, re.IGNORECASE))
                    for name, pattern in PII_PATTERNS.items():
                        if re.search(pattern, line, re.IGNORECASE):
                            sev = "warning" if is_log else "info"
                            msg = f"PII pattern ({name}) in {'log statement' if is_log else 'code'}"
                            if is_log:
                                findings.append({
                                    "type": f"dsgvo-pii-{name}",
                                    "severity": sev,
                                    "message": msg,
                                    "file": fpath,
                                    "line": i,
                                })
        except:
            pass

# Check for consent mechanism
consent_found = False
for root, dirs, files in os.walk("src"):
    dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__")]
    for fname in files:
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, errors="ignore") as f:
                content = f.read().lower()
            if any(term in content for term in ["consent", "cookie-banner", "datenschutz", "privacy-policy"]):
                consent_found = True
                break
        except:
            pass
    if consent_found:
        break

if not consent_found:
    # Only flag if there's actual code
    src_files = sum(1 for r, d, f in os.walk("src") for _ in f)
    if src_files > 2:
        findings.append({
            "type": "dsgvo-consent",
            "severity": "info",
            "message": "No consent mechanism found (cookie banner, privacy policy)",
        })

print(json.dumps({"scan": "dsgvo", "findings": findings}))
PYEOF
}

# -- Main --

echo "Quality scan: scope=${SCOPE}, project=${PROJECT_DIR}" >&2

results=()

case "${SCOPE}" in
    all)
        results+=("$(scan_deps)")
        results+=("$(scan_sast)")
        results+=("$(scan_config)")
        results+=("$(scan_dsgvo)")
        ;;
    deps)   results+=("$(scan_deps)") ;;
    sast)   results+=("$(scan_sast)") ;;
    config) results+=("$(scan_config)") ;;
    dsgvo)  results+=("$(scan_dsgvo)") ;;
    *)
        echo "Unknown scope: ${SCOPE}" >&2
        echo "Allowed: all, deps, sast, config, dsgvo" >&2
        exit 1
        ;;
esac

# Combine results into single JSON
python3 -c "
import json, sys

scans = []
for line in sys.stdin:
    line = line.strip()
    if line:
        try:
            scans.append(json.loads(line))
        except:
            pass

total_findings = sum(len(s.get('findings', [])) for s in scans)
critical = sum(1 for s in scans for f in s.get('findings', []) if f.get('severity') == 'critical')
high = sum(1 for s in scans for f in s.get('findings', []) if f.get('severity') == 'high')
warning = sum(1 for s in scans for f in s.get('findings', []) if f.get('severity') == 'warning')

report = {
    'timestamp': '${TIMESTAMP}',
    'scope': '${SCOPE}',
    'project': '${PROJECT_DIR}',
    'summary': {
        'total_findings': total_findings,
        'critical': critical,
        'high': high,
        'warning': warning,
        'info': total_findings - critical - high - warning,
    },
    'scans': scans,
}

print(json.dumps(report, indent=2, ensure_ascii=False))
" <<< "$(printf '%s\n' "${results[@]}")" > "${REPORT_FILE}"

# Print summary to stderr
echo "Report written: ${REPORT_FILE}" >&2
python3 -c "
import json
with open('${REPORT_FILE}') as f:
    r = json.load(f)
s = r['summary']
print(f\"Findings: {s['total_findings']} (Critical: {s['critical']}, High: {s['high']}, Warning: {s['warning']}, Info: {s['info']})\")
" >&2

# Also output to stdout for piping
cat "${REPORT_FILE}"
