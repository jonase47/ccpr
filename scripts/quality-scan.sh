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
# SUMMARY_TMP is declared empty here (not yet a path) so the trap below can
# reference it unconditionally even on an exit that happens before the
# combiner step ever runs, without tripping `set -u`. It is assigned its
# real path once the combiner step creates its own scratch file directly
# under docs/ -- see the comment there for why it no longer lives here
# under ${TMPDIR}. Whichever exit path fires -- success (SUMMARY_TMP was
# already renamed away by `mv`, so `rm -f` on it is a harmless no-op) or
# either of the two `exit 1` branches below the combiner (the file still
# sits there unrenamed) -- this single trap is the one place that cleans it
# up; the file's OWN error handling never gets a chance to run its own
# cleanup once `exit 1` fires.
SUMMARY_TMP=""
# MARKER_TMP is write_failure_marker()'s own scratch file -- same reason,
# same declare-empty-before-the-trap treatment as SUMMARY_TMP above (see
# its comment for the full rationale); this one is assigned inside that
# function instead of by the combiner step further down.
MARKER_TMP=""
trap 'rm -rf "${TMPDIR}"; rm -f "${SUMMARY_TMP}"; rm -f "${MARKER_TMP}"' EXIT
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
    cap = 20
    total = len(results)
    out = []
    for r in results[:cap]:
        extra = r.get("extra", {})
        out.append({
            "type": "semgrep",
            "severity": extra.get("severity", "warning"),
            "message": (extra.get("message") or "")[:200],
            "file": r.get("path", ""),
            "line": r.get("start", {}).get("line", 0),
            "rule": r.get("check_id", ""),
        })
    # A silent cap makes "20 results" and "20-plus-unknown-many results"
    # byte-identical output -- the same gap as the pattern-scan's 50-cap,
    # but undocumented anywhere (WI-0128 wave 1a, defect 3). One extra
    # finding, appended only when the cap actually trims something, names
    # the real total instead.
    if total > cap:
        out.append({
            "type": "scan-truncated",
            "severity": "info",
            "message": "semgrep reported %d findings; only the first %d are included" % (total, cap),
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
        write_failure_marker "${1##*/} exited non-zero"
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
# on this superset, "venv" and ".venv" included, everywhere it is used --
# walking a virtualenv looking for either signal yields third-party noise,
# never a real finding about THIS project's own code. ".venv" (tranche 3b,
# 28.08.2026) was not part of the original three-way comparison the PO
# decision above was based on -- it surfaced from a FOURTH, previously
# unnoticed skip list in scripts/lib/quality_scan_sast_patterns.py, which
# already carried both spellings. The true superset across all four lists
# is five entries, not four.
#
# There are FOUR os.walk("src") call sites in this file, not three: the CORS
# walk below, the PII walk and the consent walk in scan_dsgvo(), and a fourth,
# counting walk in scan_dsgvo() ("src_files = ..." below) that gates whether
# the consent finding fires at all. WI-0128 wave 1a unified only the first
# three on this superset and deliberately left the fourth unfiltered --
# filtering it would have changed WHEN the consent finding fires, a second,
# unapproved behaviour change at the time (see CHANGELOG.md for that
# "report, not fixed" record). PO decision (WI-0128 wave 1b, 28.08.2026):
# filter the fourth walk too, on the same superset as its three siblings.
# Before this fix, files under node_modules/venv/.git counted toward "is
# there actual code" (`src_files > 2` below), so a project whose only files
# live in a virtualenv could trip the consent finding on venv noise alone --
# see SrcFilesCountWalkVenvBehaviourChangeTest in test_quality_scan.py for
# the measured before/after.
#
# TWO separate definitions of this SKIP_DIRS tuple exist in this file -- this
# one and scan_dsgvo()'s below -- because each lives inside its own
# independently quoted `python3 << 'PYEOF'` heredoc (see the TOOL_REPORT_PY
# heredoc's own comment above for the same constraint): nothing can be shared
# between two quoted heredocs without unquoting the delimiter, which would
# let the shell expand "$"-prefixed tokens inside the Python body it is meant
# to protect. A third option -- one `export`ed shell variable read via
# `os.environ` in both heredocs, sidestepping heredoc quoting entirely -- was
# considered and declined: duplicating a five-tuple is simpler and more
# YAGNI-compliant than introducing an env-var passing convention for one pair
# of literals.
SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv", ".venv")

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

# Extension filter (WI-0128 wave 1b, ARGUED, not unified with the PII/consent
# walks below): a CORS header is set from server-side or config code -- a
# Python backend, a Node/Express middleware, a TypeScript API route handler.
# .jsx/.tsx are UI-component files (the extension itself signals the file
# contains JSX markup); setting an HTTP response header is not something
# that shape of file does. See ExtensionFilterAsymmetryTest in
# test_quality_scan.py for the full three-way comparison and the reasoning
# for each of the three walks' differing breadth.
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
SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv", ".venv")

findings = []

# Check logging for PII
#
# Extension filter (WI-0128 wave 1b, ARGUED, wider than the CORS walk on
# purpose): a hardcoded email, phone number or IBAN can appear anywhere a
# developer types a literal string -- including inline in a React/Vue
# component's JSX markup, or a console.log left in one. This walk claims
# "any code", not a specific header-setting statement, so its extension set
# is the wider one. See ExtensionFilterAsymmetryTest in test_quality_scan.py.
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

# Extension filter (WI-0128 wave 1b, ARGUED): none, deliberately -- reads
# every file under src/. A cookie banner, privacy-policy link or
# "datenschutz" mention is at least as likely to live in an .html template,
# a .md legal page or a JSON i18n string table under src/ as in a
# .py/.js/.ts file. Narrowing this walk to source-code extensions would make
# it blind to the exact places a consent notice usually lives. See
# ExtensionFilterAsymmetryTest in test_quality_scan.py.
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
    src_files = 0
    for r, d, f in os.walk("src"):
        d[:] = [x for x in d if x not in SKIP_DIRS]
        src_files += len(f)
    if src_files > 2:
        findings.append({
            "type": "dsgvo-consent",
            "severity": "info",
            "message": "No consent mechanism found (cookie banner, privacy policy)",
        })

print(json.dumps({"scan": "dsgvo", "findings": findings}))
PYEOF
}

# Builds the failure-marker JSON written in REPORT_FILE's place when a scan
# run fails (WI-0128 wave 1b, PO decision 28.08.2026 -- see the comment on
# the SUMMARY_TMP block further down for the decision itself; wave 2,
# 28.08.2026, added the two call sites below run_py() and the empty-entry
# guard use). Defined here, before "-- Main --", because run_py() (above)
# and the case/for-loop (below) both need it available by the time they
# actually RUN -- a function's BODY may reference a name defined later in
# the file (bash does not resolve it until the function is called), but the
# name must exist by the time that call happens, and every real call
# happens from inside "-- Main --". A separate heredoc-to-file for the same
# reason TOOL_REPORT_PY/SUMMARY_PY are: nested inside a `$(...)` command
# substitution it would break bash's quote tracking; redirected to a file
# it parses fine.
FAILURE_MARKER_PY="${TMPDIR}/quality_scan_failure_marker.py"
cat > "${FAILURE_MARKER_PY}" <<'MARKEREOF'
"""Builds the failure-marker JSON written in place of a report when report
generation fails. Takes over an existing report -- if any -- to track a
streak of consecutive failures: if the existing file already IS a failure
marker, the streak continues (its own first-failure timestamp is kept, the
counter increments); otherwise (a real report, no file at all, or
something unreadable/corrupt) the streak restarts at 1. An unreadable
existing report must never block writing this marker -- it is read
best-effort only, never required.

    quality_scan_failure_marker.py <report-file> <timestamp> <reason>

Prints the marker JSON to stdout. Exit status is always 0 -- a failure to
read the OLD report is absorbed into "streak restarts at 1", never
propagated as this script's own failure (the caller's own scan failure is
what matters here, not this best-effort bookkeeping).
"""
import json
import sys

report_file, timestamp, reason = sys.argv[1], sys.argv[2], sys.argv[3]

consecutive_failures = 1
first_failure_at = timestamp

try:
    with open(report_file, encoding="utf-8") as f:
        existing = json.load(f)
except Exception:
    existing = None

if isinstance(existing, dict) and existing.get("status") == "failed":
    try:
        consecutive_failures = int(existing.get("consecutive_failures", 0)) + 1
    except (TypeError, ValueError):
        consecutive_failures = 1
    first_failure_at = existing.get("first_failure_at") or timestamp

marker = {
    "status": "failed",
    "timestamp": timestamp,
    "reason": reason,
    "consecutive_failures": consecutive_failures,
    "first_failure_at": first_failure_at,
}
print(json.dumps(marker, indent=2, ensure_ascii=False))
MARKEREOF

# Writes the failure marker into REPORT_FILE, in place of whatever was
# there before (a stale report, an earlier marker, or nothing). Same
# scratch-then-mv discipline as the report itself below -- never move a
# 0-byte or partial marker into place. A failure inside THIS function
# (e.g. python3 itself dying) is swallowed on purpose: the caller's own
# `exit 1` for the underlying scan failure must still fire either way, and
# a best-effort marker is strictly better than crashing the error-reporting
# path over a failure to report the error.
#
# Four call sites as of wave 2 (:332 run_py(), :767 the empty-entry guard,
# and :892/:897 the two report-generation branches inside the SUMMARY_TMP
# combiner below), and they never fire twice for the same failure in one
# run (measured 28.08.2026, so no de-duplication guard is needed here).
# The two report-generation call sites are mutually exclusive with EACH
# OTHER by construction: :892 fires when python3 exits non-zero, :897 only
# when it exits 0 but writes nothing -- two sequential `if` blocks on the
# same SUMMARY_TMP, each ending in its own `exit 1`, so whichever fires
# first exits the script before the second `if` is ever evaluated. A
# genuine scan_X() crash never reaches the empty-entry loop below, but not
# because a crash is bash's sole/last command in general -- bash 3.2 does
# not honour errexit for a failure that happens mid-subshell (see
# run_py()'s own comment above for that measurement). The real,
# script-specific reason is spelled out at the empty-entry guard below:
# every scan_X() ends in a command whose failure becomes the `$(scan_X)`
# substitution's own exit status, and scan_deps()/scan_sast() additionally
# rely on run_py()'s own explicit `exit 1`, which fires regardless of
# position inside the function. The loop's own call site fires only for
# the OPPOSITE shape: a scan that exits 0 while printing nothing at all.
write_failure_marker() {
    local reason="$1"
    # Re-declares the SAME top-level EXIT trap here, verbatim -- measured:
    # when this function runs from inside run_py() called by scan_deps()/
    # scan_sast() (both executed as `$(scan_X)` command substitutions, i.e.
    # their own forked subshell), an EXTERNAL signal killing that subshell
    # does NOT run the trap it merely INHERITED from the top-level shell --
    # only a trap the subshell itself explicitly (re-)registers fires on a
    # signal-caused exit; an inherited-only one only fires on that
    # subshell's own NORMAL exit (falling off the end, or its own `exit N`,
    # both already covered before this fix). At the top level (the other
    # three call sites: the empty-entry guard and both report-generation
    # branches, none of them inside a subshell) this is a harmless no-op --
    # the exact same trap is already active there.
    trap 'rm -rf "${TMPDIR}"; rm -f "${SUMMARY_TMP}"; rm -f "${MARKER_TMP}"' EXIT
    MARKER_TMP=$(mktemp "${PROJECT_DIR}/docs/.quality-scan-report.json.tmp.XXXXXX")
    if python3 "${FAILURE_MARKER_PY}" "${REPORT_FILE}" "${TIMESTAMP}" "${reason}" \
            > "${MARKER_TMP}" 2>/dev/null && [ -s "${MARKER_TMP}" ]; then
        mv "${MARKER_TMP}" "${REPORT_FILE}"
    else
        rm -f "${MARKER_TMP}"
    fi
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
        # No marker here, deliberately (WI-0128 wave 2, ARGUED): this is a
        # usage error, raised before any scan has run at all -- unlike
        # run_py()'s and the empty-entry guard's failures above, nothing was
        # attempted here, so there is nothing this run "broke". Overwriting
        # a valid earlier report with a failure marker over a typo'd scope
        # argument would be pure data loss (destroying a real, working
        # report for zero benefit) -- a genuinely broken scan is still
        # caught by the two guards above regardless of how the run was
        # invoked. Same ARGUED-exception treatment as the extension filter
        # above scan_dsgvo()'s consent walk: an explicit, reasoned no-op
        # documented in place, not a silent gap.
        echo "Unknown scope: ${SCOPE}" >&2
        echo "Allowed: all, deps, sast, config, dsgvo" >&2
        exit 1
        ;;
esac

# A scan that produced NOTHING is not a clean scan. Corrected 28.08.2026
# (WI-0128 wave 2, corrected again same day): this guard is NOT reached by
# a scan_X() CRASH, but for a script-specific reason, not a general bash
# rule. Measured on /bin/bash 3.2.57 with this exact
# `results+=("$(scan_X)")` call shape: a crash that is NOT the function's
# last command, followed by anything output-less, does NOT abort the
# script -- it leaves an empty entry and the script exits 0, i.e. it WOULD
# reach this guard. What actually holds every scan_X() crash back today is
# that each one ends in a command whose failure becomes the substitution's
# own exit status: scan_deps()/scan_sast() end in run_py() --merge, and
# run_py() itself calls `exit 1` on failure, which terminates the
# `$(scan_X)` subshell outright regardless of where inside the function it
# fires (see run_py()'s own comment above for why bash 3.2 needs that
# explicit exit rather than relying on inherited errexit); scan_config()/
# scan_dsgvo() end in their own heredoc with no such explicit exit, so
# their crash protection depends entirely on being the function's literal
# last command -- append one more output-less line after either and a
# crash there would reach this guard instead of aborting the script. What
# DOES reach here today is the opposite shape: a scan that exits 0
# (nothing "failed" from bash's point of view) while silently printing
# nothing at all -- and the combiner below skips empty lines, which would
# drop the whole scan from the report while still reporting exit 0 and a
# plausible summary.
for entry in "${results[@]}"; do
    if [ -z "${entry}" ]; then
        echo "quality-scan.sh: FAILED -- a scan produced no record (scope=${SCOPE})" >&2
        write_failure_marker "a scan produced no record (scope=${SCOPE})"
        exit 1
    fi
done

# Combine results into single JSON.
#
# TIMESTAMP/SCOPE/PROJECT_DIR reach this step through argv, never through
# "${var}" inside the Python source -- the same rule the TOOL_REPORT_PY
# heredoc's own header states (:58-65, rule 2). Measured 28.08.2026: a
# project directory containing an apostrophe used to break the OLD
# `python3 -c "... '${PROJECT_DIR}' ..."` form with a SyntaxError (WI-0126
# wave 1a, defect 1) -- the same defect class WI-0055 already fixed twice
# elsewhere in this file. The body lives in a real file, written via a
# quoted heredoc, for the same reason TOOL_REPORT_PY does (a heredoc nested
# inside a `$(...)` command substitution breaks bash's quote tracking).
SUMMARY_PY="${TMPDIR}/quality_scan_summary.py"
cat > "${SUMMARY_PY}" <<'SUMMARYEOF'
import json, sys

scans = []
for line in sys.stdin:
    line = line.strip()
    if line:
        try:
            scans.append(json.loads(line))
        except:
            pass

# Normalise every finding's severity at this ONE boundary -- the only place
# all four scans' findings converge (merge() upstream covers only two of
# them). PO decision (WI-0128 wave 1a, defect 2): a closed vocabulary,
# folded case-insensitively. Measured 28.08.2026: semgrep reports
# 'ERROR'/'WARNING' (real semgrep 1.174.0, see test_quality_scan.py's
# SEMGREP_TWO_RESULTS fixture), and the OLD bucketing below compared
# case-SENSITIVELY against lowercase literals -- every semgrep finding,
# including an ERROR, fell through to 'info' by subtraction. A value
# outside this vocabulary (e.g. the npm-side SEVERITIES tuple's own 'low'/
# 'moderate', which this combiner has never had a bucket for) is not
# silently re-bucketed either: the original finding's severity is left
# untouched, and one companion finding makes the gap visible instead of
# indistinguishable from a clean bill.
SEVERITY_ALIASES = {
    'critical': 'critical',
    'high': 'high',
    'warning': 'warning',
    'info': 'info',
    'error': 'high',
}

unrecognised = []
for scan in scans:
    for finding in scan.get('findings', []):
        raw = finding.get('severity')
        key = raw.strip().lower() if isinstance(raw, str) else None
        canonical = SEVERITY_ALIASES.get(key)
        if canonical is not None:
            finding['severity'] = canonical
        else:
            unrecognised.append({
                'type': 'severity-unrecognised',
                'severity': 'high',
                'message': "a %r finding carries unrecognised severity %r -- not counted in any bucket" % (
                    finding.get('type', '?'), raw,
                ),
                'detail': 'scan=%s' % scan.get('scan', '?'),
            })
if unrecognised:
    scans.append({'scan': 'severity-normalization', 'findings': unrecognised})

total_findings = sum(len(s.get('findings', [])) for s in scans)
critical = sum(1 for s in scans for f in s.get('findings', []) if f.get('severity') == 'critical')
high = sum(1 for s in scans for f in s.get('findings', []) if f.get('severity') == 'high')
warning = sum(1 for s in scans for f in s.get('findings', []) if f.get('severity') == 'warning')
info = sum(1 for s in scans for f in s.get('findings', []) if f.get('severity') == 'info')

report = {
    'timestamp': sys.argv[1],
    'scope': sys.argv[2],
    'project': sys.argv[3],
    'summary': {
        'total_findings': total_findings,
        'critical': critical,
        'high': high,
        'warning': warning,
        'info': info,
    },
    'scans': scans,
}

print(json.dumps(report, indent=2, ensure_ascii=False))
SUMMARYEOF

# Written to a scratch file first and only moved into place once python3
# has both exited 0 AND produced non-empty output. Independent of the
# apostrophe class above (WI-0128 wave 1a's zusatzauflage): an aborted or
# empty report build must never leave a 0-byte docs/.quality-scan-report.json
# behind -- CLAUDE.md tells /p6-audit and /p6-pentest to use that file "if
# it exists", and a 0-byte file measurably exists.
#
# PO decision (WI-0128 wave 1b, 28.08.2026 -- wave 1a round 2, defect B left
# this as an open, undecided question): on failure, overwrite the report
# with an explicit failure marker (write_failure_marker() above) rather than
# leaving a stale report from an earlier successful run untouched, or
# writing nothing at all. The marker must be recognisable as a non-result
# without a consumer knowing the run's exit code, since /p6-audit and
# /p6-pentest only check the file's EXISTENCE (CLAUDE.md) -- the same reason
# it must never carry a `summary.total_findings: 0` shape, which would read
# exactly like a clean report.
#
# The scratch file is created directly under the same directory as
# REPORT_FILE (docs/), not under ${TMPDIR} (mktemp -d /tmp/...) -- `mv` is
# only atomic within one filesystem, and /tmp and a mounted project volume
# are routinely separate mounts in the documented Docker deployment target
# (CLAUDE.md), where a kill mid-copy would leave exactly the partial report
# this scratch-then-move scheme exists to prevent. Do not move this back
# under ${TMPDIR}: that reintroduces the cross-filesystem gap. Cleanup on
# every exit path (success and both `exit 1` branches below) is handled by
# the SUMMARY_TMP trap set near TMPDIR's own declaration, not by a trap
# here -- ${TMPDIR}'s trap alone never reached this file even before this
# fix, since this file never lived under ${TMPDIR}.
SUMMARY_TMP=$(mktemp "${PROJECT_DIR}/docs/.quality-scan-report.json.tmp.XXXXXX")
if ! python3 "${SUMMARY_PY}" "${TIMESTAMP}" "${SCOPE}" "${PROJECT_DIR}" \
        <<< "$(printf '%s\n' "${results[@]}")" > "${SUMMARY_TMP}"; then
    echo "quality-scan.sh: FAILED -- report generation exited non-zero" >&2
    write_failure_marker "report generation exited non-zero"
    exit 1
fi
if [ ! -s "${SUMMARY_TMP}" ]; then
    echo "quality-scan.sh: FAILED -- report generation produced no output" >&2
    write_failure_marker "report generation produced no output"
    exit 1
fi
mv "${SUMMARY_TMP}" "${REPORT_FILE}"

# Print summary to stderr. REPORT_FILE reaches Python through argv, not
# through "${var}" inside the source -- found while fixing the combiner
# step above (same defect class, same file, one function further down: an
# apostrophe in PROJECT_DIR reaches this interpolation too).
echo "Report written: ${REPORT_FILE}" >&2
python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    r = json.load(f)
s = r['summary']
print(f\"Findings: {s['total_findings']} (Critical: {s['critical']}, High: {s['high']}, Warning: {s['warning']}, Info: {s['info']})\")
" "${REPORT_FILE}" >&2  # exit-status: exempt set-e-sufficient

# Also output to stdout for piping
cat "${REPORT_FILE}"
