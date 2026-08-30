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
            test_cmd=$(python3 -c "import json; d=json.load(open('package.json')); print(d.get('scripts',{}).get('test',''))" 2>/dev/null || true)  # exit-status: exempt downstream-checks-result
            # Here-strings, not pipes -- see scripts/manual-lint.sh's
            # `idx_content` site for why a producer piped into `grep -q`
            # can report a real hit as a miss under `set -o pipefail`.
            if grep -q "vitest" <<< "${test_cmd}"; then echo "vitest"
            elif grep -q "jest" <<< "${test_cmd}"; then echo "jest"
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
    local tmpfile cov_tmpfile
    # No suffix after the XXXXXX run in either template -- BSD mktemp (the
    # macOS floor platform) only substitutes a TRAILING run of X's; a
    # literal suffix after it is returned unsubstituted on the first call
    # and collides (`mkstemp failed: File exists`) on any call that follows
    # while that same literal path still exists (WI-0129). The extension is
    # not load-bearing: `--json-report-file=`/`--cov-report=json:` and the
    # Python heredoc below all open these paths explicitly, none infer a
    # format from the file suffix.
    tmpfile=$(mktemp /tmp/pytest-report-XXXXXX)
    cov_tmpfile=$(mktemp /tmp/pytest-cov-XXXXXX)

    # Run pytest with JSON report if plugin available
    if python3 -c "import pytest_json_report" 2>/dev/null; then
        python3 -m pytest "${test_arg}" --tb=short -q \
            --json-report --json-report-file="${tmpfile}" \
            $( [ -n "$(pip show pytest-cov 2>/dev/null)" ] && echo "--cov --cov-report=json:${cov_tmpfile}" || true ) \
            2>&1 || true  # exit-status: exempt test-runner-output-capture

        RUN_TESTS_TMPFILE="${tmpfile}" RUN_TESTS_COV_FILE="${cov_tmpfile}" RUN_TESTS_TIMESTAMP="${TIMESTAMP}" python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import json, os, sys

try:
    with open(os.environ["RUN_TESTS_TMPFILE"]) as f:
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
    "timestamp": os.environ["RUN_TESTS_TIMESTAMP"],
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
    with open(os.environ["RUN_TESTS_COV_FILE"]) as f:
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
        local raw_tmpfile
        raw_tmpfile=$(mktemp /tmp/pytest-raw-XXXXXX)
        # EXIT trap, not a manual `rm -f` after the heredoc below: the
        # heredoc is `# exit-status: exempt set-e-sufficient` (an uncaught
        # Python exception there aborts the whole script under `set -e`
        # BEFORE a manual cleanup line placed after it would ever run),
        # and this file now holds untrusted test-runner output on disk,
        # however briefly -- an EXIT trap fires on that abort path too.
        # DOUBLE-quoted so `${raw_tmpfile}` expands NOW, into the trap's own
        # command string -- `raw_tmpfile` is `local` to this function and is
        # gone by the time the trap actually fires (script end); a
        # single-quoted trap defers the expansion to firing time, when
        # `set -u` sees an unbound variable and the cleanup itself fails.
        trap "rm -f '${raw_tmpfile}'" EXIT
        python3 -m pytest "${test_arg}" --tb=short -q > "${raw_tmpfile}" 2>&1 || true  # exit-status: exempt test-runner-output-capture

        RUN_TESTS_RAW_FILE="${raw_tmpfile}" RUN_TESTS_TIMESTAMP="${TIMESTAMP}" python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import os, re, json

# `raw` is untrusted test-runner output -- it reaches Python through a file
# read via an ENVIRONMENT-provided path, never through interpolation into
# this heredoc's own source text (WI-0129 F7: an unquoted delimiter here
# used to let a literal ``'''`` in `raw` close this string early and run
# whatever followed as Python source).
with open(os.environ["RUN_TESTS_RAW_FILE"], errors="replace") as f:
    raw = f.read()

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
    "timestamp": os.environ["RUN_TESTS_TIMESTAMP"],
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

    rm -f "${tmpfile}" "${cov_tmpfile}"
}

run_jest_or_vitest() {
    local runner="$1"
    local test_arg="${TEST_PATH:-}"
    local tmpfile
    # Same reasoning as run_pytest()'s tmpfile above: no suffix after
    # XXXXXX, so BSD mktemp actually randomizes it.
    tmpfile=$(mktemp /tmp/jest-report-XXXXXX)

    # `test_arg` may be empty (no TEST_PATH given) -- an unconditional
    # `"${test_arg}"` would then pass a literal empty-string argument to
    # the runner, which is NOT the same as passing none. `runner_args` is
    # built conditionally so a non-empty path reaches the runner as
    # exactly one argument (space/glob-safe) and an empty path contributes
    # none at all. `${runner_args[@]+"${runner_args[@]}"}` guards against
    # `set -u` under bash 3.2, where `"${arr[@]}"` on an EMPTY array is an
    # unbound-variable error (see scripts/phase-docs-lint.sh's FILES[@]
    # guard for the same pattern).
    local runner_args=()
    if [ -n "${test_arg}" ]; then
        runner_args=("${test_arg}")
    fi

    if [ "${runner}" = "vitest" ]; then
        npx vitest run ${runner_args[@]+"${runner_args[@]}"} --reporter=json 2>/dev/null > "${tmpfile}" || true
    else
        npx jest ${runner_args[@]+"${runner_args[@]}"} --json --outputFile="${tmpfile}" 2>/dev/null || true
    fi

    RUN_TESTS_TMPFILE="${tmpfile}" RUN_TESTS_RUNNER="${runner}" RUN_TESTS_TIMESTAMP="${TIMESTAMP}" python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import json, os, sys

runner = os.environ["RUN_TESTS_RUNNER"]

try:
    with open(os.environ["RUN_TESTS_TMPFILE"]) as f:
        report = json.load(f)
except:
    print(json.dumps({"framework": runner, "error": "JSON report not readable"}))
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
    "framework": runner,
    "timestamp": os.environ["RUN_TESTS_TIMESTAMP"],
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
    local raw_tmpfile
    raw_tmpfile=$(mktemp /tmp/cargo-raw-XXXXXX)
    # See run_pytest's fallback branch for why this is an EXIT trap, not a
    # manual `rm -f` placed after the heredoc.
    trap "rm -f '${raw_tmpfile}'" EXIT
    # See run_jest_or_vitest for why `test_arg` is passed via a
    # conditionally-populated array rather than a bare `"${test_arg}"`:
    # `test_arg` defaults to empty here, and `cargo test ""` is not the
    # same as `cargo test` (a literal empty filter argument vs. none).
    local runner_args=()
    if [ -n "${test_arg}" ]; then
        runner_args=("${test_arg}")
    fi
    cargo test ${runner_args[@]+"${runner_args[@]}"} > "${raw_tmpfile}" 2>&1 || true

    RUN_TESTS_RAW_FILE="${raw_tmpfile}" RUN_TESTS_TIMESTAMP="${TIMESTAMP}" python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import os, re, json

# See run_pytest's fallback branch for why `raw` reaches Python through a
# file read via an environment-provided path (WI-0129 F7).
with open(os.environ["RUN_TESTS_RAW_FILE"], errors="replace") as f:
    raw = f.read()

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
    "timestamp": os.environ["RUN_TESTS_TIMESTAMP"],
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
    local raw_tmpfile
    raw_tmpfile=$(mktemp /tmp/go-raw-XXXXXX)
    # See run_pytest's fallback branch for why this is an EXIT trap, not a
    # manual `rm -f` placed after the heredoc.
    trap "rm -f '${raw_tmpfile}'" EXIT
    # `test_arg` defaults to `./...` here, never empty, so a plain quote is
    # sufficient and correct -- same shape as the pytest sites above. No
    # conditional-array dance needed (contrast run_jest_or_vitest/
    # run_cargo, whose default IS empty).
    go test -v -count=1 "${test_arg}" > "${raw_tmpfile}" 2>&1 || true

    RUN_TESTS_RAW_FILE="${raw_tmpfile}" RUN_TESTS_TIMESTAMP="${TIMESTAMP}" python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import os, re, json

# See run_pytest's fallback branch for why `raw` reaches Python through a
# file read via an environment-provided path (WI-0129 F7).
with open(os.environ["RUN_TESTS_RAW_FILE"], errors="replace") as f:
    raw = f.read()

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
    "timestamp": os.environ["RUN_TESTS_TIMESTAMP"],
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
    local raw json_raw
    raw=$(npm test 2>&1 || true)
    # The python3 encode used to be embedded inline inside the outer echo's
    # string literal ($(... ) glued between literal JSON text on both
    # sides) -- on bash 3.2, set -e only checks a $(...)'s exit status when
    # it is the entire bare right-hand side of a var="$(cmd)" assignment
    # (the LAST one, if several are concatenated in the same word) or
    # stands alone as the whole simple command; never when it is one
    # argument, or part of one argument, to some OTHER command -- which is
    # exactly what this substitution was, glued into echo's own string
    # literal (WI-0105). Hoisted to its own assignment with a real ||
    # fallback: a best-effort JSON-report generator degrading to a fixed
    # placeholder string on encode failure fits this file's own tone better
    # than aborting the whole run (run_pytest/run_jest_or_vitest already
    # tolerate their own runner's failure via `|| true` for the same reason).
    json_raw=$(echo "${raw}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()[:2000]))') || json_raw='"<json-encode-failed>"'
    echo "{\"framework\": \"npm-test\", \"timestamp\": \"${TIMESTAMP}\", \"raw_output\": ${json_raw}}"
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
