#!/usr/bin/env bash
# run-tests.sh – Runs tests and returns structured JSON output.
# Usage: ~/.claude/scripts/run-tests.sh [testpath] [projectdirectory]
# Output: JSON on stdout

set -euo pipefail

TEST_PATH="${1:-}"
PROJECT_DIR="${2:-$(pwd)}"
cd "${PROJECT_DIR}"

# -- Framework Detection --

detect_framework() {
    if [ -f "package.json" ]; then
        if grep -q '"vitest"' package.json 2>/dev/null; then
            echo "vitest"
        elif grep -q '"jest"' package.json 2>/dev/null; then
            echo "jest"
        elif grep -q '"mocha"' package.json 2>/dev/null; then
            echo "mocha"
        else
            # Check for test script
            local test_cmd
            test_cmd=$(python3 -c "import json; d=json.load(open('package.json')); print(d.get('scripts',{}).get('test',''))" 2>/dev/null || true)
            if echo "${test_cmd}" | grep -q "vitest"; then echo "vitest"
            elif echo "${test_cmd}" | grep -q "jest"; then echo "jest"
            else echo "npm-test"
            fi
        fi
    elif [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "setup.cfg" ]; then
        echo "pytest"
    elif [ -f "Cargo.toml" ]; then
        echo "cargo"
    elif [ -f "go.mod" ]; then
        echo "go"
    else
        echo "unknown"
    fi
}

FRAMEWORK=$(detect_framework)
TIMESTAMP=$(date -u "+%Y-%m-%dT%H:%M:%S")

# -- Runners --

run_pytest() {
    local test_arg="${TEST_PATH:-.}"
    local tmpfile
    tmpfile=$(mktemp /tmp/pytest-report-XXXXXX.json)

    # Run pytest with JSON report if plugin available
    if python3 -c "import pytest_json_report" 2>/dev/null; then
        python3 -m pytest "${test_arg}" --tb=short -q \
            --json-report --json-report-file="${tmpfile}" \
            $( [ -n "$(pip show pytest-cov 2>/dev/null)" ] && echo "--cov --cov-report=json:/tmp/pytest-cov.json" || true ) \
            2>&1 || true

        python3 << PYEOF
import json, sys

try:
    with open("${tmpfile}") as f:
        report = json.load(f)
except:
    print(json.dumps({"framework": "pytest", "error": "JSON report not readable"}))
    sys.exit(0)

summary = report.get("summary", {})
failures = []
for test in report.get("tests", []):
    if test.get("outcome") == "failed":
        call = test.get("call", {})
        failures.append({
            "test": test.get("nodeid", "unknown"),
            "file": test.get("nodeid", "").split("::")[0],
            "error": call.get("longrepr", "")[:300],
            "short": call.get("crash", {}).get("message", "")[:150],
        })

result = {
    "framework": "pytest",
    "timestamp": "${TIMESTAMP}",
    "summary": {
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("deselected", 0) + summary.get("xfailed", 0),
        "duration_s": round(summary.get("duration", 0), 2),
    },
    "failures": failures,
    "coverage": None,
}

# Try to read coverage
try:
    with open("/tmp/pytest-cov.json") as f:
        cov = json.load(f)
    result["coverage"] = {
        "total_pct": cov.get("totals", {}).get("percent_covered", 0),
        "uncovered_files": [
            name for name, data in cov.get("files", {}).items()
            if data.get("summary", {}).get("percent_covered", 100) < 50
        ][:10],
    }
except:
    pass

print(json.dumps(result, indent=2, ensure_ascii=False))
PYEOF
    else
        # Fallback: parse raw pytest output
        local raw
        raw=$(python3 -m pytest "${test_arg}" --tb=short -q 2>&1 || true)

        python3 << PYEOF
import re, json

raw = '''${raw}'''

# Parse summary line like "5 passed, 2 failed in 1.23s"
summary_match = re.search(r'(\d+) passed', raw)
failed_match = re.search(r'(\d+) failed', raw)
duration_match = re.search(r'in ([\d.]+)s', raw)

passed = int(summary_match.group(1)) if summary_match else 0
failed = int(failed_match.group(1)) if failed_match else 0

# Parse failure blocks
failures = []
for m in re.finditer(r'FAILED (.+?) - (.+?)(?:\n|$)', raw):
    failures.append({
        "test": m.group(1),
        "file": m.group(1).split("::")[0],
        "error": m.group(2)[:300],
        "short": m.group(2)[:150],
    })

result = {
    "framework": "pytest",
    "timestamp": "${TIMESTAMP}",
    "summary": {
        "total": passed + failed,
        "passed": passed,
        "failed": failed,
        "skipped": 0,
        "duration_s": float(duration_match.group(1)) if duration_match else 0,
    },
    "failures": failures,
    "coverage": None,
}

print(json.dumps(result, indent=2, ensure_ascii=False))
PYEOF
    fi

    rm -f "${tmpfile}" /tmp/pytest-cov.json
}

run_jest_or_vitest() {
    local runner="$1"
    local test_arg="${TEST_PATH:-}"
    local tmpfile
    tmpfile=$(mktemp /tmp/jest-report-XXXXXX.json)

    if [ "${runner}" = "vitest" ]; then
        npx vitest run ${test_arg} --reporter=json 2>/dev/null > "${tmpfile}" || true
    else
        npx jest ${test_arg} --json --outputFile="${tmpfile}" 2>/dev/null || true
    fi

    python3 << PYEOF
import json, sys

try:
    with open("${tmpfile}") as f:
        report = json.load(f)
except:
    print(json.dumps({"framework": "${runner}", "error": "JSON report not readable"}))
    sys.exit(0)

failures = []
for suite in report.get("testResults", []):
    for test in suite.get("assertionResults", []):
        if test.get("status") == "failed":
            failures.append({
                "test": test.get("fullName", test.get("title", "unknown")),
                "file": suite.get("name", "unknown"),
                "error": "\n".join(test.get("failureMessages", []))[:300],
                "short": test.get("failureMessages", [""])[0][:150] if test.get("failureMessages") else "",
            })

result = {
    "framework": "${runner}",
    "timestamp": "${TIMESTAMP}",
    "summary": {
        "total": report.get("numTotalTests", 0),
        "passed": report.get("numPassedTests", 0),
        "failed": report.get("numFailedTests", 0),
        "skipped": report.get("numPendingTests", 0),
        "duration_s": round((report.get("testResults", [{}])[0].get("endTime", 0) -
                            report.get("startTime", 0)) / 1000, 2) if report.get("testResults") else 0,
    },
    "failures": failures,
    "coverage": None,
}

print(json.dumps(result, indent=2, ensure_ascii=False))
PYEOF

    rm -f "${tmpfile}"
}

run_cargo() {
    local test_arg="${TEST_PATH:-}"
    local raw
    raw=$(cargo test ${test_arg} 2>&1 || true)

    python3 << PYEOF
import re, json

raw = '''${raw}'''

# Parse "test result: ok. X passed; Y failed; Z ignored"
result_match = re.search(r'test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored', raw)
passed = int(result_match.group(1)) if result_match else 0
failed = int(result_match.group(2)) if result_match else 0
ignored = int(result_match.group(3)) if result_match else 0

failures = []
for m in re.finditer(r"---- (.+?) stdout ----\n(.*?)(?=\n---- |\nfailures:)", raw, re.DOTALL):
    failures.append({
        "test": m.group(1),
        "file": "",
        "error": m.group(2).strip()[:300],
        "short": m.group(2).strip().split("\n")[0][:150],
    })

result = {
    "framework": "cargo",
    "timestamp": "${TIMESTAMP}",
    "summary": {
        "total": passed + failed + ignored,
        "passed": passed,
        "failed": failed,
        "skipped": ignored,
        "duration_s": 0,
    },
    "failures": failures,
    "coverage": None,
}

print(json.dumps(result, indent=2, ensure_ascii=False))
PYEOF
}

run_go() {
    local test_arg="${TEST_PATH:-./...}"
    local raw
    raw=$(go test -v -count=1 ${test_arg} 2>&1 || true)

    python3 << PYEOF
import re, json

raw = '''${raw}'''

passed = len(re.findall(r'--- PASS:', raw))
failed = len(re.findall(r'--- FAIL:', raw))
skipped = len(re.findall(r'--- SKIP:', raw))

failures = []
for m in re.finditer(r'--- FAIL: (\S+) .+?\n(.*?)(?=--- |\nFAIL\t|\nok\t)', raw, re.DOTALL):
    failures.append({
        "test": m.group(1),
        "file": "",
        "error": m.group(2).strip()[:300],
        "short": m.group(2).strip().split("\n")[0][:150],
    })

duration_match = re.search(r'ok\s+.+?\s+([\d.]+)s', raw)

result = {
    "framework": "go",
    "timestamp": "${TIMESTAMP}",
    "summary": {
        "total": passed + failed + skipped,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration_s": float(duration_match.group(1)) if duration_match else 0,
    },
    "failures": failures,
    "coverage": None,
}

print(json.dumps(result, indent=2, ensure_ascii=False))
PYEOF
}

run_npm_test() {
    local raw
    raw=$(npm test 2>&1 || true)
    echo "{\"framework\": \"npm-test\", \"timestamp\": \"${TIMESTAMP}\", \"raw_output\": $(echo "${raw}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()[:2000]))')}"
}

# -- Main --

case "${FRAMEWORK}" in
    pytest)   run_pytest ;;
    jest)     run_jest_or_vitest "jest" ;;
    vitest)   run_jest_or_vitest "vitest" ;;
    cargo)    run_cargo ;;
    go)       run_go ;;
    npm-test) run_npm_test ;;
    *)
        echo "{\"framework\": \"unknown\", \"error\": \"No test framework detected in ${PROJECT_DIR}\"}"
        exit 1
        ;;
esac
