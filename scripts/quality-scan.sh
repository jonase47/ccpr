#!/usr/bin/env bash
# quality-scan.sh – Local security and quality scans.
# Usage: ~/.claude/scripts/quality-scan.sh [scope] [projectdirectory]
# Scope: all, deps, sast, config, dsgvo
# Output: docs/.quality-scan-report.json

set -euo pipefail

# Captured before the cd below -- resolves the script's own directory
# regardless of the project directory it is asked to scan.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCOPE="${1:-all}"
PROJECT_DIR="${2:-$(pwd)}"
cd "${PROJECT_DIR}"

TIMESTAMP=$(date -u "+%Y-%m-%dT%H:%M:%S")
REPORT_FILE="${PROJECT_DIR}/docs/.quality-scan-report.json"

mkdir -p "${PROJECT_DIR}/docs"

# Temporary results
TMPDIR=$(mktemp -d /tmp/quality-scan-XXXXXX)
trap "rm -rf ${TMPDIR}" EXIT
# Note on WI-0055's measured "exit 0 having done nothing": a bash-level fatal
# abort (the parse error this item fixes; the same applies to a `set -u`
# unbound-variable hit) never sets $? to anything reflecting the abort, so no
# trap wording -- not even `trap 'ec=$?; ...; exit "${ec}"' EXIT` -- can
# recover it (measured: capturing $? first still reports exit 0 for both
# failure shapes, because $? already held the PRECEDING command's status
# before the abort happened; only ordinary command failures under `set -e`
# and explicit `exit N` calls survive a trap intact, which this script's own
# report-integrity check below relies on). The actual fix for "cannot ship
# unparseable" is scripts/tests/test_shell_script_syntax.py's `bash -n` gate,
# not this trap.

# -- External-tool report reader (WI-0102) --
#
# Every external scanner here shares one shape: it PRINTS its full JSON
# report and STILL exits non-zero when it finds something. Measured
# 24.08.2026 against a throwaway project pinning minimist 0.0.8 --
# `npm audit --json` answered {critical: 1, total: 1} with exit 1, and the
# `|| echo '{}'` arm this file used to carry appended a SECOND JSON document
# to a complete one. json.load then died on "Extra data", a bare `except:`
# printed 0, and the deps scan reported "clean" in precisely the case it
# exists to catch. pip-audit was measured to behave identically (6
# vulnerabilities, exit 1, chain reported 0); semgrep exits 0 on findings
# today, but the same run with `--error` prints the same report and exits 1,
# so the shape is one flag away from breaking there too.
#
# Two rules follow, and both are load-bearing:
#
#   1. NO SILENT FALLBACK. "the tool could not be evaluated" and "the tool
#      found nothing" must never produce the same number. An unusable report
#      becomes a `scan-error` finding; a tool that is missing where there IS
#      something to scan becomes a `scan-skipped` finding. Only a tool that
#      ran and genuinely found nothing yields an empty findings list.
#   2. NO SHELL VALUE IS EVER INTERPOLATED INTO PYTHON SOURCE. Tool output
#      reaches Python through a FILE PATH in argv, never through "${var}"
#      inside a `python3 -c "..."` string. Measured 24.08.2026 against real
#      semgrep 1.174.0: the first rule it hits on `subprocess(shell=True)`
#      carries apostrophes in its message, the old merge step interpolated
#      that text straight into Python source, and the whole sast scan died
#      with a SyntaxError and wrote no report at all. Same apostrophe class
#      as WI-0055, one function further down.
#
# The body lives in a temp file rather than inline for the WI-0055 reason
# (a heredoc nested inside a `$(...)` command substitution breaks bash's
# quote tracking). A quoted heredoc REDIRECTED TO A FILE, as below, is a
# different construct and parses fine -- `bash -n` covers this file on every
# run via scripts/tests/test_shell_script_syntax.py.
TOOL_REPORT_PY="${TMPDIR}/quality_scan_tool_report.py"
cat > "${TOOL_REPORT_PY}" <<'TOOLREPORTEOF'
"""Turns one external scanner's JSON report into a findings list.

    quality_scan_tool_report.py <kind> <report-file> <status> [<stderr-file>]
    quality_scan_tool_report.py --skipped <kind>
    quality_scan_tool_report.py --merge <scan-name> <parts-file>

The first form prints a JSON array of findings for one producer, the second
the finding that stands for "this producer is not installed", and the third
merges the accumulated arrays (one JSON array per line) into the scan record
the caller writes out. Exit status is 0 in every ordinary case, INCLUDING a
producer that failed -- that failure is reported as a finding, never
swallowed and never turned into a zero. A non-zero exit here means the
reader itself broke, and the caller stops the run.
"""
import json
import sys

SEVERITIES = ("info", "low", "moderate", "high", "critical")

# Statuses each producer documents as "ran to completion". For the three
# external scanners 0 = nothing found and 1 = something found; the local
# pattern pass has no "found something" status and any non-zero is a crash.
# Anything outside this set means the producer did not finish, and a report
# that happens to parse must not then be read as "0 vulnerabilities".
COMPLETED = {
    "npm-audit": ("0", "1"),
    "pip-audit": ("0", "1"),
    "semgrep": ("0", "1"),
    "pattern-scan": ("0",),
}


class ReportError(Exception):
    """The tool's output parsed as JSON but is not the report we expect."""


def findings_npm(doc):
    meta = doc.get("metadata", {}).get("vulnerabilities")
    if not isinstance(meta, dict):
        raise ReportError("no metadata.vulnerabilities object in the report")
    buckets = [k for k in SEVERITIES if k in meta]
    if not buckets:
        raise ReportError("metadata.vulnerabilities names no severity bucket")
    # Sum the severity buckets ONLY. npm also ships a 'total' key holding
    # their sum, so the old sum(meta.values()) counted every vulnerability
    # twice -- one critical advisory came out as 2 (WI-0102).
    count = sum(int(meta[k]) for k in buckets)
    if count == 0:
        return []
    return [{
        "type": "npm-audit",
        "severity": "warning",
        "message": "%d npm vulnerabilities found" % count,
        "detail": "Run npm audit --json for details",
    }]


def findings_pip(doc):
    # pip-audit >= 2.x: {"dependencies": [...], "fixes": [...]}
    # pip-audit 1.x:    a bare list of dependency objects.
    if isinstance(doc, dict):
        deps = doc.get("dependencies")
        if not isinstance(deps, list):
            raise ReportError("no dependencies array in the report")
    elif isinstance(doc, list):
        deps = doc
    else:
        raise ReportError("unexpected top-level JSON %s" % type(doc).__name__)
    # The old len(json.load(...)) counted DEPENDENCIES on the 1.x shape and
    # the two TOP-LEVEL KEYS on the 2.x one -- measured: a clean project was
    # reported as "2 Python vulnerabilities found" (WI-0102).
    count = 0
    for dep in deps:
        if not isinstance(dep, dict):
            raise ReportError("dependency entry is not an object")
        vulns = dep.get("vulns", [])
        if not isinstance(vulns, list):
            raise ReportError("vulns is not an array")
        count += len(vulns)
    if count == 0:
        return []
    return [{
        "type": "pip-audit",
        "severity": "warning",
        "message": "%d Python vulnerabilities found" % count,
        "detail": "Run pip-audit --format=json for details",
    }]


def findings_semgrep(doc):
    results = doc.get("results")
    if not isinstance(results, list):
        raise ReportError("no results array in the report")
    out = []
    for r in results[:20]:
        extra = r.get("extra", {})
        out.append({
            "type": "semgrep",
            "severity": extra.get("severity", "warning"),
            "message": (extra.get("message") or "")[:200],
            "file": r.get("path", ""),
            "line": r.get("start", {}).get("line", 0),
            "rule": r.get("check_id", ""),
        })
    return out


def findings_pattern_scan(doc):
    # The local grep-based pass (lib/quality_scan_sast_patterns.py) already
    # speaks the findings format. It goes through the same reader as the
    # external tools on purpose: bash 3.2 does not honour `set -e` inside a
    # `$(...)` command substitution, so a crash here used to leave nothing
    # behind and read as "no patterns matched" (WI-0102).
    if not isinstance(doc, list):
        raise ReportError("pattern scan did not print a JSON array")
    for item in doc:
        if not isinstance(item, dict):
            raise ReportError("pattern scan entry is not an object")
    return doc


HANDLERS = {
    "npm-audit": findings_npm,
    "pip-audit": findings_pip,
    "semgrep": findings_semgrep,
    "pattern-scan": findings_pattern_scan,
}


def scan_error(kind, status, reason, detail=""):
    suffix = (" -- %s" % detail) if detail else ""
    return [{
        "type": "scan-error",
        "severity": "high",
        "tool": kind,
        "message": "%s could not be evaluated: %s" % (kind, reason),
        "detail": "exit status %s -- this is NOT a clean result%s" % (status, suffix),
    }]


def scan_skipped(kind):
    return [{
        "type": "scan-skipped",
        "severity": "info",
        "tool": kind,
        "message": "%s is not installed, so these dependencies were not scanned" % kind,
        "detail": "absence of findings here means absence of measurement",
    }]


def last_stderr_line(path):
    """The producer's own last word, so a scan-error finding says WHY.

    Kept to one line, and truncated from the FRONT rather than the back:
    measured 24.08.2026, a Python "can't open file" message spent its first
    200 characters on the interpreter's own homebrew path and never reached
    the filename. The specific part of a tool error sits at its end.
    Missing or empty stderr is normal, not an error of its own."""
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = [l.strip() for l in handle if l.strip()]
    except OSError:
        return ""
    if not lines:
        return ""
    line = lines[-1]
    return line if len(line) <= 200 else "..." + line[-197:]


def read_tool(kind, path, status, err_path=""):
    if kind not in HANDLERS:
        raise SystemExit("quality_scan_tool_report.py: unknown producer %r" % kind)
    detail = last_stderr_line(err_path)
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError as exc:
        return scan_error(kind, status, "report file unreadable (%s)" % exc, detail)
    if status not in COMPLETED[kind]:
        return scan_error(kind, status, "did not run to completion", detail)
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        return scan_error(kind, status, "report is not valid JSON (%s)" % exc, detail)
    try:
        return HANDLERS[kind](doc)
    except (ReportError, TypeError, ValueError) as exc:
        return scan_error(kind, status, str(exc), detail)


def merge(scan_name, parts_path):
    findings = []
    with open(parts_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            findings.extend(json.loads(line))
    return {"scan": scan_name, "findings": findings}


def main(argv):
    if len(argv) == 4 and argv[1] == "--merge":
        print(json.dumps(merge(argv[2], argv[3])))
        return 0
    if len(argv) == 3 and argv[1] == "--skipped":
        print(json.dumps(scan_skipped(argv[2])))
        return 0
    if len(argv) in (4, 5):
        print(json.dumps(read_tool(*argv[1:])))
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
TOOLREPORTEOF

# Runs the report reader and refuses to continue if IT fails.
#
# Not marked `set-e-sufficient` like the rest of this file's python3 calls,
# because that justification does not hold here: every scan function below
# is invoked as `results+=("$(scan_X)")`, and bash 3.2 -- the /bin/bash this
# project pins -- does NOT honour `set -e` inside a `$(...)` command
# substitution. Measured 24.08.2026: a failing command inside such a
# substitution aborts neither the function nor the script; execution simply
# continues and the outer script exits 0. Relying on `set -e` in here would
# reproduce the very defect WI-0102 is about, one level up.
run_py() {
    if ! python3 "$@"; then
        echo "quality-scan.sh: FAILED -- ${1##*/} exited non-zero" >&2
        exit 1
    fi
}

# Runs one producer and prints its findings array.
#   run_tool_report <kind> <report-file> <command...>
# The exit status is captured from the producer's OWN simple command --
# never read back through `$?` after a pipe or a command substitution, where
# it would belong to the last process rather than to the producer. Its
# stderr is kept (not sent to /dev/null) so a scan-error finding can say why.
run_tool_report() {
    local kind="$1"
    local out="$2"
    shift 2
    local err="${out}.stderr"
    local status=0
    "$@" > "${out}" 2> "${err}" || status=$?
    run_py "${TOOL_REPORT_PY}" "${kind}" "${out}" "${status}" "${err}"
}

# -- Scan Functions --

scan_deps() {
    # One line of JSON findings per tool, merged at the end. The old code
    # had each tool write the WHOLE scan record to the same file, so a
    # project with both a lockfile and a requirements.txt lost its npm
    # findings whenever pip-audit had anything to say (WI-0102).
    local parts="${TMPDIR}/deps-parts.jsonl"
    : > "${parts}"

    # Node.js
    if [ -f "package-lock.json" ] || [ -f "yarn.lock" ]; then
        if command -v npm &>/dev/null; then
            run_tool_report npm-audit "${TMPDIR}/npm-audit.json" npm audit --json >> "${parts}"
        else
            # There is something to scan and no scanner. Unlike sast, this
            # scan has no fallback of its own, so staying silent here would
            # print the same empty findings list a genuinely clean project
            # gets -- the very confusion this item is about.
            run_py "${TOOL_REPORT_PY}" --skipped npm-audit >> "${parts}"
        fi
    fi

    # Python
    if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
        if command -v pip-audit &>/dev/null; then
            run_tool_report pip-audit "${TMPDIR}/pip-audit.json" pip-audit --format=json >> "${parts}"
        else
            run_py "${TOOL_REPORT_PY}" --skipped pip-audit >> "${parts}"
        fi
    fi

    run_py "${TOOL_REPORT_PY}" --merge deps "${parts}"
}

scan_sast() {
    local parts="${TMPDIR}/sast-parts.jsonl"
    : > "${parts}"

    # Semgrep if available. No scan-skipped finding when it is absent: this
    # scan keeps its own grep-based pattern pass below, so "semgrep missing"
    # still leaves a measurement behind -- which is exactly what the deps
    # scan does not have.
    if command -v semgrep &>/dev/null; then
        run_tool_report semgrep "${TMPDIR}/semgrep.json" semgrep --config=auto --json -q . >> "${parts}"
    fi

    # Grep-based pattern scan (fallback / always runs). Body lives in a real
    # file (lib/quality_scan_sast_patterns.py) rather than an inline heredoc
    # -- WI-0055: a heredoc nested inside this command substitution broke
    # bash's quote tracking on an apostrophe in the body's SQL-string
    # pattern and made the whole script unparseable.
    run_tool_report pattern-scan "${TMPDIR}/pattern-scan.json" \
        python3 "${SCRIPT_DIR}/lib/quality_scan_sast_patterns.py" >> "${parts}"

    run_py "${TOOL_REPORT_PY}" --merge sast "${parts}"
}

scan_config() {
    python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import os, json, re

# Directories that add noise, not signal, when scanning application source
# for CORS wildcards or a DSGVO consent mechanism (see scan_dsgvo() below for
# the second use). PO decision (WI-0126, 28.08.2026): unify this skip *list*
# on this superset, "venv" included, everywhere it is used -- walking a
# virtualenv looking for either signal yields third-party noise, never a
# real finding about THIS project's own code.
#
# There are FOUR os.walk("src") call sites in this file, not three: the CORS
# walk below, the PII walk and the consent walk in scan_dsgvo(), and a fourth,
# unfiltered counting walk in scan_dsgvo() ("src_files = sum(...)") that gates
# whether the consent finding fires at all. Only the first three carry a
# SKIP_DIRS filter and are unified here; the fourth has no directory filter
# and is deliberately left alone -- filtering it would change WHEN the
# consent finding fires, a second, unapproved behaviour change. Consequence
# (report, not fixed; see CHANGELOG.md and docs/workitems/WI-0126.md):
# files under node_modules/venv/.git count toward "is there actual code"
# (`src_files > 2` below), so a project whose only files live in a
# virtualenv can trip the consent finding on venv noise alone.
#
# TWO separate definitions of this SKIP_DIRS tuple exist in this file -- this
# one and scan_dsgvo()'s below -- because each lives inside its own
# independently quoted `python3 << 'PYEOF'` heredoc (see the TOOL_REPORT_PY
# heredoc's own comment above for the same constraint): nothing can be shared
# between two quoted heredocs without unquoting the delimiter, which would
# let the shell expand "$"-prefixed tokens inside the Python body it is meant
# to protect. A third option -- one `export`ed shell variable read via
# `os.environ` in both heredocs, sidestepping heredoc quoting entirely -- was
# considered and declined: duplicating a four-tuple is simpler and more
# YAGNI-compliant than introducing an env-var passing convention for one pair
# of literals.
SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv")

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
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
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
    python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import os, re, json

PII_PATTERNS = {
    "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    "phone-de": r'(\+49|0)[0-9\s/\-]{8,}',
    "iban": r'[A-Z]{2}\d{2}\s?[\d\s]{12,30}',
    "geburtsdatum": r'\b(geburtsdatum|date_of_birth|dob|birthdate)\b',
}

# See scan_config()'s SKIP_DIRS comment above for why this heredoc needs its
# own separate definition of the same superset (WI-0126, 28.08.2026).
SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv")

findings = []

# Check logging for PII
for root, dirs, files in os.walk("src"):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
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
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
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

# A scan that produced NOTHING is not a clean scan. Same bash 3.2 fact as
# above: a crash inside `$(scan_X)` neither aborts the function nor the
# script, so a broken scan arrives here as an empty string -- and the
# combiner below skips empty lines, which would silently drop the whole scan
# from the report while still reporting exit 0 and a plausible summary.
for entry in "${results[@]}"; do
    if [ -z "${entry}" ]; then
        echo "quality-scan.sh: FAILED -- a scan produced no record (scope=${SCOPE})" >&2
        exit 1
    fi
done

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
" <<< "$(printf '%s\n' "${results[@]}")" > "${REPORT_FILE}"  # exit-status: exempt set-e-sufficient

# Make "the scan ran" and "the scan failed" distinguishable explicitly,
# instead of relying only on the implicit chain of set -e propagating a
# python3 failure this far (WI-0055: exit 0 used to be reported even when
# no report was ever written -- see the trap comment above for why that
# specific case cannot be recovered after the fact, and
# scripts/tests/test_shell_script_syntax.py for what actually prevents it).
if [ ! -s "${REPORT_FILE}" ]; then
    echo "quality-scan.sh: FAILED -- no report was written to ${REPORT_FILE}" >&2
    exit 1
fi

# Print summary to stderr
echo "Report written: ${REPORT_FILE}" >&2
python3 -c "
import json
with open('${REPORT_FILE}') as f:
    r = json.load(f)
s = r['summary']
print(f\"Findings: {s['total_findings']} (Critical: {s['critical']}, High: {s['high']}, Warning: {s['warning']}, Info: {s['info']})\")
" >&2  # exit-status: exempt set-e-sufficient

# Also output to stdout for piping
cat "${REPORT_FILE}"
