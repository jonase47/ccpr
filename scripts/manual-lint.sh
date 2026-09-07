#!/usr/bin/env bash
# manual-lint.sh — Read-only validator for a documentation index/detail-file
# contract (WI-0112a). Schema: templates/PHASE_DOC_SCHEMA.md, `## kind`
# section (vocabulary) and the `parent_index` row (resolution rule).
#
# Checks:
#   (a) parent_index resolves to an existing file — document-relative
#       first, root-fallback second. Same cascade phase-docs-lint.sh's
#       checks (f)/(g) already implement (scripts/phase-docs-lint.sh:274-
#       297), reused rather than reinvented: the fallback base there is
#       the project-directory argument (PROJECT_DIR); here, since this
#       script is generic over ANY root rather than hardwired to a
#       project layout, the fallback base is this script's own ROOT
#       argument — the same role, translated to a generic root.
#   (b) the REVERSE direction: an index named as `parent_index` by a
#       detail file must itself link that detail file back (a markdown
#       link whose destination is the document-relative path from the
#       index's own directory to the detail file). PHASE_DOC_SCHEMA.md
#       has named this direction as a documented-but-unvalidated
#       convention since it shipped ("Index-↔-detail consistency" —
#       "Nothing checks them"); this is the first check that does.
#   (c) `kind:` — when set, checked against the vocabulary documented in
#       templates/PHASE_DOC_SCHEMA.md's `## kind` section. That vocabulary is
#       the KNOWN set, not the ALLOWED set: CCPR cannot enumerate every
#       document genre a downstream project will legitimately invent, so an
#       unrecognised value is a WARNING (surface it for deliberate curation),
#       not an error (same open-enum precedent as memory-lint.sh check (c)'s
#       Tier-2 `type:` field — see that script's comment).
#   (f) derived-count markers — a number in prose, guarded by an inline HTML
#       comment on the SAME line, is compared against a value derived from the
#       repository. See the "Check (f)" block below for the full grammar and
#       the reasoning behind each of its rules. Every finding is an ERROR;
#       check (f) raises no warnings.
#   (g) forbidden-prose terms — OPT-IN, CCP-1151 stage 4 cut 4. A project may
#       configure a term that must not appear as ordinary prose, plus three
#       lists of contexts that excuse a real occurrence (the frozen field key
#       it collides with, a vendor filename, a protocol document). See the
#       "Check (g)" block below for the configuration shape and the reasoning
#       behind each list. Every finding is an ERROR; check (g) raises no
#       warnings. With NOTHING configured, check (g) checks nothing — the
#       generic script never hardcodes any project's retired vocabulary.
#
# WHY THE LETTERS JUMP FROM (c) TO (f) — this gap is deliberate, not a
# numbering accident. (d) and (e) are RESERVED by documentation standard v0.7
# for the frontmatter reliability fields, which are not built yet. Do not
# "repair" the sequence by renaming (f) to (d): the letter is referenced from
# the report's `**Checks:**` line, from templates/PHASE_DOC_SCHEMA.md, from
# scripts/tests/test_manual_lint.py and from CHANGELOG.md, and renaming it
# breaks all of them at once for no gain. (g) is simply the next letter after
# (f), no gap involved.
#
# Usage:
#   bash scripts/manual-lint.sh [<root-dir> ...]
#
# Generic over ANY documentation root — NOT hardwired to handbook/.
# install.sh does not copy handbook/ into ~/.claude (see handbook/README.md:2-5),
# so a script that defaulted to it would find nothing on every installed
# CCPR — the exact defect 0e76919 fixed for phase-docs-lint.sh's
# PHASE_FOLDERS default. Point it at whichever tree carries the
# kind/parent_index contract, e.g. `bash scripts/manual-lint.sh handbook`.
#
# More than one root may be given (CCP-1151 stage 4 cut 4): every root is
# scanned and the findings are combined into ONE report, with file counts
# summed and each finding's path shown relative to the root that produced
# it. A single root, or none at all (defaulting to the current working
# directory), behaves exactly as before this capability existed.
#
# Exit-Codes: 0 clean, 1 warnings, 2 errors.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

# ROOTS — one or more root directories, in the order given. Empty means
# "no positional argument at all", not "one empty-string root": the
# default-to-cwd behaviour below must fire for zero args, not for an
# array holding one blank element.
ROOTS=("$@")
if [[ ${#ROOTS[@]} -eq 0 ]]; then
    ROOTS=("$(pwd)")
fi

# The kind: KNOWN set — measured across this repository 26.08.2026 (WI-0112a):
# every distinct value any shipped file, template, or command prescribes.
# Mirrored verbatim in templates/PHASE_DOC_SCHEMA.md's `## kind` section —
# keep both in sync when a new kind is introduced. This is not a closed
# allow-list: a project may legitimately carry its own document genres this
# repository never saw (measured 26.08.2026 against two real CCPR-using
# projects — consumer-b, Org-X — 16 distinct unrecognised-but-legitimate
# values between them). is_valid_kind() below therefore only decides whether
# a value is RECOGNISED; check (c) reports an unrecognised one as a warning,
# not an error (measured 26.08.2026, follow-up to WI-0112a — no separate WI filed).
# Near-miss values seen in that measurement but deliberately NOT added, because
# each already has a canonical equivalent below that the source project deviated
# from rather than a genuinely new genre: `sprint-review` → use `review`;
# `story-index` → use `sub-index`. Don't re-add them without checking this note.
VALID_KINDS="adr api-resource-detail commands-doc-detail component-detail constitution detail entity-detail epic-detail frame learnings promotion-brief review risk-detail setup-detail sprint-detail sub-index system-doc-detail track-decision wireframe-detail"

is_valid_kind() {
    local k="$1"
    for v in $VALID_KINDS; do
        [[ "$k" == "$v" ]] && return 0
    done
    return 1
}

# rel_path <from_dir_abs> <to_file_abs> — the relative path FROM a
# directory TO a file, both given as absolute, already-normalized paths
# (produced via `cd ... && pwd`, so neither carries a ".." segment).
# Purely string-based: bash 3.2 (macOS default) ships no `realpath`, and
# the system `realpath` binary is not guaranteed present either. Splits
# both paths on "/", walks the shared prefix, then emits one "../" per
# remaining `from` segment followed by the remaining `to` segments —
# the canonical document-relative form this repository's own handbook/
# links already use (`[…](system/agents.md)`, no leading "./", no
# fragment): check (b) below does a literal substring match against
# that exact shape, not a general link-destination parser.
rel_path() {
    local from="$1" to="$2"
    local IFS=/
    local -a from_parts to_parts
    read -r -a from_parts <<< "$from"
    read -r -a to_parts <<< "$to"
    local i=0
    while [[ $i -lt ${#from_parts[@]} && $i -lt ${#to_parts[@]} \
        && "${from_parts[$i]}" == "${to_parts[$i]}" ]]; do
        i=$((i + 1))
    done
    local up=$(( ${#from_parts[@]} - i ))
    local result="" j=0
    while [[ $j -lt $up ]]; do
        result="../$result"
        j=$((j + 1))
    done
    local k=$i
    while [[ $k -lt ${#to_parts[@]} ]]; do
        result="${result}${to_parts[$k]}"
        k=$((k + 1))
        [[ $k -lt ${#to_parts[@]} ]] && result="${result}/"
    done
    printf '%s' "$result"
}

# ---------------------------------------------------------------------------
# Check (f) — derived-count markers
# ---------------------------------------------------------------------------
#
# GRAMMAR. An inline HTML comment on the SAME LINE as the number it guards:
#
#     CCPR ships 116 commands. <!-- ${MARKER_WORD} count ../commands/*.md -->
#
# Two verbs, and no others:
#   count <glob>  the derived value must EQUAL the number on the line.
#   floor <glob>  the derived value must be >= the number on the line. A floor
#                 stays silent while its subject GROWS and fires only when the
#                 derived value falls BELOW the claim. The verb exists because
#                 the already-settled README.md test-count decision
#                 ("2,600+ tests") needs >= semantics, and a contract that
#                 cannot express it would push that claim back to a hand-typed
#                 number — the thing this check is here to remove.
#
# RULES. All three are ERRORS (exit 2). Check (f) raises no warnings.
#
#   1. EXACTLY ONE number on the marked line, the marker comment itself
#      excluded. More than one, or none, is an error. The alternative —
#      set-membership semantics, "the derived value must appear among the
#      numbers on the line" — has a hole: `115 commands plus 1 = 116 total`
#      would pass on the presence of 116 while 115 is wrong. The one-number
#      rule closes it, at the price of forcing simple, pinnable sentences.
#      That price is the point: a sentence too tangled to pin is a sentence
#      whose numbers nobody can check either.
#   2. A glob that matches ZERO files is an ERROR, not a warning. A guard that
#      silently checks nothing is worse than no guard, because it also looks
#      like coverage (KA-G-017: "a check run that reports no scope is not a
#      pass"). The milder reading — warn, since a downstream project that
#      inherits this tree may not have the path — was considered and rejected:
#      if the path does not exist there, the claim in front of the marker is
#      unsupported for that project too, and the error points squarely at the
#      line that should have been adapted or deleted at project init.
#   3. Derived value vs. the number on the line: mismatch (`count`) or
#      shortfall (`floor`) is an error.
#
# NUMBER PARSING. A number is its VALUE, not its literal. A thousands
# separator binds into one number (`2,600` → 2600) but only in full
# three-digit groups, so `1,2` reads as two numbers and fails rule 1 rather
# than silently becoming 12. A trailing `+` (`2,600+ tests`, README.md's floor
# form) is prose ornament: it neither creates a number nor alters one. Leading
# zeros are read base-10, never octal.
#
# WHAT CHECK (f) IS NOT. It is OPT-IN BY MARKER and therefore a FALLBACK
# GUARD, NOT A DETECTOR: it can never find an UNMARKED wrong number. It is
# also deliberately limited to SIMPLE SINGLE-NUMBER claims. Multi-number
# anchor sentences — e.g. the command breakdown `3/5/4/23/4/12/22/5/4 = 82` —
# are explicitly NOT check (f) terrain and stay with
# scripts/tests/test_doc_counts_agree.py and its dedicated extractors, which
# can parse a shape this generic shell guard has no business modelling.
#
# VOCABULARY SEPARATION. This markdown marker vocabulary and the Python
# `<hash> pin: <group> <id>` vocabulary in scripts/tests/ are disjoint BY
# CORPUS, verified 05.09.2026 by reading the code rather than by assumption:
# pin_registry.corpus_files() (scripts/tests/pin_registry.py:906-913)
# enumerates scripts/tests/*.py + scripts/tests/workitems/*.py only and never
# sees a markdown file, and its MARKER_RE (pin_registry.py:87) requires a
# leading `#`, which an HTML comment does not have. In particular the Python
# `floor` group's admissibility rule ("a floor is admissible only where the
# same subject also carries a `set` pin", scripts/tests/test_pin_inventory.py)
# does NOT transfer to the markdown `floor` verb here — there is no
# cross-vocabulary rule, and none should be invented.
#
# A marker inside a FENCED CODE BLOCK is documentation OF the marker, not a
# live one, and is skipped. This repository has been bitten by that class
# before: memory-lint.sh's check (n) once reported bracketed text inside a
# code block as a dead link, and freeze-phase-docs.sh hoisted a fenced example
# header as a real `reviewed_head` value (see CHANGELOG.md). The fence rules
# mirror memory-lint.sh's own state machine: an opener is ``` or ~~~ (three or
# more, indented at most 3 spaces) and closes only on its OWN delimiter
# character, at a length at least the opener's.
#
# KNOWN LIMITATION, stated narrowly on purpose: that protection covers FENCED
# blocks only. A marker written inside an INLINE code span (single backticks)
# is still read as live. Closing it would mean parsing inline spans — backtick
# runs of arbitrary length, escapes — which is a markdown parser, not a guard
# clause; and the failure is fail-LOUD (an error nobody can miss), never a
# silent pass. Measured 05.09.2026: no line inside handbook/ — the only tree
# check-all.sh points this linter at — writes the marker syntax inline. Pinned
# by CheckFInlineCodeSpanLimitationTest so the limitation is a decision on
# record rather than something a later reader rediscovers.

# The literal word a marker comment opens with. Held in a variable, never
# written out next to `<!--` anywhere in this file, so that this script's own
# header examples above cannot be mistaken for live markers by any future
# scanner reading this file as documentation.
MARKER_WORD="pin:"

# Both marker regexes match against ONE COMMENT SPAN's content (the text
# between a `<!--` and its own `-->`), never against the raw line. Searching
# the raw line for a marker while counting numbers on the STRIPPED line is two
# different readings of the same text, and they disagree exactly where an
# outer comment encloses the marker: `<!-- TODO … <!-- pin: … -->` is ONE html
# comment (a comment ends at the FIRST `-->`), so the marker is commented out
# and must be inert — the raw-line search saw a live marker anyway and then
# reported the enclosing comment's now-empty prose as "0 numbers". Deriving
# both from the same walk makes that class unrepresentable rather than fixed.
F_MARKER_PRESENT_RE="^[[:space:]]*${MARKER_WORD}"
F_MARKER_RE="^[[:space:]]*${MARKER_WORD}[[:space:]]*([^[:space:]]+)[[:space:]]+([^[:space:]]+)[[:space:]]*$"
F_FENCE_OPEN_RE='^ {0,3}(`{3,}|~{3,})'
F_NUMBER_RE='[0-9]+(,[0-9][0-9][0-9])*'

# f_strip_markup <line> — the line with every complete `<!-- ... -->` span
# replaced by a single space, so rule 1 counts the numbers of the PROSE and
# never the digits of a glob (`assets2/*.txt`, `p3-*.md`). Every HTML comment
# is stripped, not just the marker: a line carrying both an unrelated comment
# and a marker would otherwise count the unrelated one's digits too. Result in
# F_STRIPPED (a global, not a command substitution: a subshell per marked line
# would buy nothing and bash 3.2 does not honour `set -e` inside one anyway).
#
# The two ends MUST be paired through `rest`, never taken independently off
# `$s`. Searching for the closer with `${s#*-->}` looks equivalent and is not:
# on a line carrying a literal `-->` EARLIER than the opener (`Flow A --> B, so
# there are 3 assets. <!-- ... -->`, an arrow in ordinary prose) it advances to
# the STRAY arrow, so the span between arrow and opener is emitted twice and a
# single-number line is rejected as carrying two. Found by an adversarial probe
# after the first implementation shipped green; see CheckFStrayArrowTest.
# An opener with no closer after it ends the loop with the remainder intact —
# an unterminated comment is prose here, not a licence to swallow the rest.
# It also collects each stripped span's CONTENT into F_SPANS, because that is
# where markers are looked for: one walk produces both the prose to count and
# the comments to interpret, so the two can never disagree about where a
# comment begins and ends.
F_STRIPPED=""
F_SPANS=()
f_strip_markup() {
    local s="$1" out="" head="" rest=""
    F_SPANS=()
    while [[ "$s" == *"<!--"* ]]; do
        head="${s%%<!--*}"
        rest="${s#*<!--}"
        [[ "$rest" == *"-->"* ]] || break
        out="$out$head "
        F_SPANS+=("${rest%%-->*}")
        s="${rest#*-->}"
    done
    F_STRIPPED="$out$s"
}

# f_extract_numbers <text> — every number in <text>, normalised to its base-10
# VALUE, into F_NUMBERS. Pure bash: `[[ =~ ]]` is a builtin, so this adds no
# external-tool invocation to the inventory scripts/tests/
# test_external_tool_exit_status.py pins.
F_NUMBERS=()
f_extract_numbers() {
    local text="$1" tok=""
    F_NUMBERS=()
    while [[ "$text" =~ $F_NUMBER_RE ]]; do
        tok="${BASH_REMATCH[0]}"
        F_NUMBERS+=("$((10#${tok//,/}))")
        text="${text#*"$tok"}"
    done
}

# f_count_glob <dir> <pattern> — how many paths <pattern> matches when
# expanded relative to <dir>, into F_GLOB_COUNT. The `cd` happens in a
# subshell so the caller's working directory is untouched and <dir>'s own
# characters never enter the glob word. With `nullglob` off (the default) an
# unmatched pattern expands to itself, which the `-e` test then rejects — so a
# pattern with no wildcard at all is simply a count of one named path.
F_GLOB_COUNT=0
f_count_glob() {
    local dir="$1" pattern="$2" out=""
    F_GLOB_COUNT=0
    [[ -d "$dir" ]] || return 0
    out="$(cd "$dir" && {
        c=0
        for m in $pattern; do
            if [ -e "$m" ]; then c=$((c + 1)); fi
        done
        printf '%s' "$c"
    })" || out=0
    [[ -n "$out" ]] || out=0
    F_GLOB_COUNT="$out"
}

# ---------------------------------------------------------------------------
# Check (g) — forbidden-prose terms (CCP-1151 stage 4 cut 4)
# ---------------------------------------------------------------------------
#
# CONFIGURATION. Opt-in, same precedent as artifact-gate.sh's gate.denyNames
# (scripts/lib/discipline_gate.sh): a personal, non-distributed
# ~/.claude/memory-sync.json (key `lint.forbiddenProse`), or an env override,
# CCPR_LINT_FORBIDDEN_PROSE. The env value is a JSON ARRAY, not the flat
# comma/newline-separated shape gate.denyNames uses — a denyNames entry is one
# bare string, but a forbiddenProse entry is a
# {term, tokenContexts, lineContains, pathContains} object, and there is no
# natural flat encoding for a list of objects. When the env var is set (even
# to "[]"), it REPLACES the file — same precedent as
# lib/discipline_gate.sh:gate_load_config's GATE_DENY_SOURCE handling.
#
# Absent python3, check (g) reads as "not configured" rather than refusing to
# run (the Constitution's "installable and runnable on a clean machine"
# Inviolable) — but once python3 IS present, a config the operator actually
# wrote wrong (a missing `term`, an unknown key, invalid JSON) is REFUSED
# (exit 2), never silently narrowed — the same "refuse rather than guess"
# discipline conformance-run.sh's own config reader applies to a structurally
# similar list-of-objects config.
#
# THREE INDEPENDENT EXCUSE LISTS per term, checked in this order but none
# depending on another:
#   tokenContexts — the text immediately preceding the match (case-
#     insensitively, no character skipped) ends with one of these strings.
#     A PREFIX check, not enclosing-token equality: CCPR's own measured
#     corpus needed to excuse "subskill", "1-subskill", "per-subskill" and
#     the hyphenated "sub-skill"/"Sub-Skill" alike, and a naive "the
#     surrounding alnum-only token equals subskill" rule catches only the
#     first of those four real spellings. `["sub", "sub-"]` catches all four
#     with two entries instead of enumerating every possible prefix before a
#     hyphen (scripts/tests/test_manual_lint_check_g.py documents the
#     measurement).
#   lineContains — literal, CASE-SENSITIVE substrings of the RAW line
#     (markup included — a marker inside an HTML comment must still be
#     read, unlike check (f)'s markup-stripped prose count).
#   pathContains — literal, case-sensitive substrings of the file's path
#     relative to the scanned root's OWN directory name (that root's
#     basename, prefixed onto its path — NOT the file's full absolute
#     path: an ancestor directory above the scanned root, e.g. a checkout
#     path or a username, must never silently widen what a configured
#     substring excuses). A match excuses the WHOLE FILE for that term (a
#     protocol document, a fixture that pins a pre-sweep literal on
#     purpose), not just one line.
#
# An occurrence excused by none of the three is an ERROR. Check (g) raises
# no warnings.
#
# FILE SCOPE. Check (g) scans *.md, *.py and *.sh under each root — wider
# than checks (a)/(b)/(c)/(f), which are markdown-only because kind:/
# parent_index: is a markdown-frontmatter contract. A prose-word guard has
# no such restriction, and CCPR's own real corpus needs it: the frozen field
# key's marker comments live inside scripts/project-init.sh (a heredoc that
# generates markdown) and a vendor integration lives in hooks/agent-
# monitor.py, neither of which any *.md-only scan would ever reach.
LINT_TERMS=()
LINT_TOKENS=()   # newline-joined blob per term index
LINT_LINES=()
LINT_PATHS=()

_lint_config_path() {
    printf '%s' "${MEMORY_SYNC_CONFIG:-$HOME/.claude/memory-sync.json}"
}

# _lint_read_config — one "KEY\tVALUE" record per line on stdout:
#   TERM\t<term>     starts a new forbiddenProse entry
#   TOKEN\t<value>   one tokenContexts entry of the CURRENT term
#   LINE\t<value>    one lineContains entry of the CURRENT term
#   PATHC\t<value>   one pathContains entry of the CURRENT term
#   ERROR\t<message> the config is malformed; nothing else is emitted
# Exit 0 on success (zero or more TERM entries), exit 1 with exactly one
# ERROR record on a malformed config. This function's own exit status IS the
# caller's signal — checked via `if OUT=$(...); then rc=0; else rc=$?; fi`,
# never `2>/dev/null || true`, because a malformed config must be refused,
# not silently read as "not configured" (contrast with lib/discipline_gate.sh
# _gate_read_config, which IS best-effort, for a deny-list where "not
# configured" is itself an accepted, common state).
_lint_read_config() {
    python3 - "$(_lint_config_path)" <<'PY'  # exit-status: exempt propagates-as-function-return
import json, os, sys

def emit_error(msg):
    print("ERROR\t" + str(msg).replace("\n", " ").replace("\t", " "))
    sys.exit(1)

def validate_and_emit(entries):
    if not isinstance(entries, list):
        emit_error("'lint.forbiddenProse' is not a list")
    for i, e in enumerate(entries, start=1):
        if not isinstance(e, dict):
            emit_error("forbiddenProse[%d] is not an object" % i)
        known = {"term", "tokenContexts", "lineContains", "pathContains", "_comment"}
        unknown = sorted(k for k in e if k not in known)
        if unknown:
            emit_error("forbiddenProse[%d] has unknown key(s): %s" % (i, ", ".join(unknown)))
        term = e.get("term")
        if not isinstance(term, str) or not term:
            emit_error("forbiddenProse[%d] is missing a non-empty string 'term'" % i)
        if "\n" in term or "\t" in term:
            emit_error("forbiddenProse[%d].term contains a newline or tab" % i)
        print("TERM\t" + term)
        for field, rec in (("tokenContexts", "TOKEN"), ("lineContains", "LINE"), ("pathContains", "PATHC")):
            vals = e.get(field, [])
            if not isinstance(vals, list):
                emit_error("forbiddenProse[%d].%s is not a list" % (i, field))
            for v in vals:
                if not isinstance(v, str) or not v:
                    emit_error("forbiddenProse[%d].%s contains a non-string or empty entry" % (i, field))
                if "\n" in v or "\t" in v:
                    emit_error("forbiddenProse[%d].%s entry contains a newline or tab" % (i, field))
                print(rec + "\t" + v)
    sys.exit(0)

env_val = os.environ.get("CCPR_LINT_FORBIDDEN_PROSE", "")
if env_val.strip():
    try:
        entries = json.loads(env_val)
    except Exception as e:
        emit_error("CCPR_LINT_FORBIDDEN_PROSE is not valid JSON: %s" % e)
    validate_and_emit(entries)

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
except FileNotFoundError:
    sys.exit(0)
except Exception as e:
    emit_error("%s is not valid JSON: %s" % (path, e))

lint = cfg.get("lint")
if lint is None:
    sys.exit(0)
if not isinstance(lint, dict):
    emit_error("'lint' is not an object")
unknown = sorted(k for k in lint if k not in {"forbiddenProse", "_comment"})
if unknown:
    emit_error("unknown key(s) in 'lint': %s" % ", ".join(unknown))
validate_and_emit(lint.get("forbiddenProse", []))
PY
}

# lint_load_forbidden_prose — fills LINT_TERMS/LINT_TOKENS/LINT_LINES/
# LINT_PATHS. Absent python3, or absent config entirely, leaves all four
# empty (check (g) then checks nothing — see the module header). A config
# the operator actually wrote wrong is refused: printed to stderr, exit 2.
lint_load_forbidden_prose() {
    LINT_TERMS=(); LINT_TOKENS=(); LINT_LINES=(); LINT_PATHS=()
    command -v python3 >/dev/null 2>&1 || return 0

    local rc=0 out cur
    if out="$(_lint_read_config)"; then rc=0; else rc=$?; fi
    if [[ "$rc" -ge 1 ]]; then
        echo "manual-lint: $(printf '%s\n' "$out" | awk -F'\t' '$1 == "ERROR" { print $2; exit }')" >&2  # exit-status: exempt internal-record-parsing
        exit 2
    fi

    cur=-1
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        key="${line%%$'\t'*}"
        val="${line#*$'\t'}"
        case "$key" in
            TERM)
                LINT_TERMS+=("$val")
                LINT_TOKENS+=("")
                LINT_LINES+=("")
                LINT_PATHS+=("")
                cur=$((${#LINT_TERMS[@]} - 1))
                ;;
            TOKEN) LINT_TOKENS[$cur]="${LINT_TOKENS[$cur]}${LINT_TOKENS[$cur]:+$'\n'}$val" ;;
            LINE)  LINT_LINES[$cur]="${LINT_LINES[$cur]}${LINT_LINES[$cur]:+$'\n'}$val" ;;
            PATHC) LINT_PATHS[$cur]="${LINT_PATHS[$cur]}${LINT_PATHS[$cur]:+$'\n'}$val" ;;
        esac
    done <<< "$out"
}

# g_line_has_any <text> <blob> — true if <text> contains (case-sensitive
# substring) ANY of the newline-separated entries in <blob>. An empty blob
# never matches (an unconfigured list excuses nothing).
g_line_has_any() {
    local text="$1" blob="$2" needle
    [[ -n "$blob" ]] || return 1
    while IFS= read -r needle; do
        [[ -n "$needle" ]] || continue
        [[ "$text" == *"$needle"* ]] && return 0
    done <<< "$blob"
    return 1
}

# g_excused_by_token <line_lower> <offset> <blob> — true if the text of
# <line_lower> immediately before character position <offset> ends with any
# of <blob>'s newline-separated prefixes (case-insensitively — <blob>'s own
# entries are lowered here, <line_lower> is already lowered by the caller).
g_excused_by_token() {
    local line_lower="$1" offset="$2" blob="$3" before needle needle_lower
    [[ -n "$blob" ]] || return 1
    before="${line_lower:0:offset}"
    while IFS= read -r needle; do
        [[ -n "$needle" ]] || continue
        needle_lower="$(printf '%s' "$needle" | LC_ALL=C tr '[:upper:]' '[:lower:]')"
        [[ "$before" == *"$needle_lower" ]] && return 0
    done <<< "$blob"
    return 1
}

# g_find_offsets <line_lower> <term_lower> — every 0-based character offset
# at which <term_lower> occurs in <line_lower>, into G_OFFSETS. Pure bash,
# mirroring f_extract_numbers's own prefix-strip loop above: G-153 requires
# every OCCURRENCE, not just whether the line matched at all, since a line
# can carry the forbidden term more than once.
G_OFFSETS=()
g_find_offsets() {
    local remaining="$1" term_lower="$2" prefix offset=0
    G_OFFSETS=()
    [[ -n "$term_lower" ]] || return 0
    while [[ "$remaining" == *"$term_lower"* ]]; do
        prefix="${remaining%%"$term_lower"*}"
        offset=$((offset + ${#prefix}))
        G_OFFSETS+=("$offset")
        offset=$((offset + ${#term_lower}))
        remaining="${remaining#*"$term_lower"}"
    done
}

errors=()
warnings=()
infos=()
err()  { errors+=("$1"); }
warn() { warnings+=("$1"); }
info() { infos+=("$1"); }

# PARENT_LINKS — "idx_abs_path|child_abs_path" entries, one per file whose
# parent_index resolved (via check (a)'s cascade) to an existing index.
# Consumed by check (b) below, once every root's per-file pass has finished
# — bash 3.2 has no associative arrays, so this is a flat pair list rather
# than an idx -> [children] map, grouped back out by a sort -u over the idx
# column. Declared once, OUTSIDE the per-root loop below, so it accumulates
# across every root rather than being reset by the second one.
PARENT_LINKS=()

# ROOTS_ABS — every given root resolved to an absolute path, in the same
# order as ROOTS, skipping any that do not exist. Consumed by display_rel()
# below (check (b)'s human-readable path in a warning) so a warning about a
# file under the SECOND root is not stripped against the first root's own
# absolute path — the single-ROOT_ABS scalar this replaced would have
# produced exactly that misattribution the moment a second root was given.
ROOTS_ABS=()

# display_rel <abs_path> — <abs_path> relative to whichever configured root
# it lives under, tried in the order the roots were given; the absolute
# path itself if none match (should not happen for a path this script
# itself produced, but a silent wrong answer is worse than an unstripped
# one here).
display_rel() {
    local abs="$1" r
    for r in ${ROOTS_ABS[@]+"${ROOTS_ABS[@]}"}; do
        case "$abs" in
            "$r"/*) printf '%s' "${abs#$r/}"; return 0 ;;
        esac
    done
    printf '%s' "$abs"
}

FILES_TOTAL=0

# lint_load_forbidden_prose() populates LINT_TERMS/LINT_TOKENS/LINT_LINES/
# LINT_PATHS once, ROOT-independent — check (g)'s configuration is not a
# per-root concept. "Not configured" is reported here, once, rather than
# once per root: it is a fact about the RUN, not about any one tree.
lint_load_forbidden_prose
if [[ ${#LINT_TERMS[@]} -eq 0 ]]; then
    info "check (g) NOT CONFIGURED — no forbidden-prose terms were checked. Set lint.forbiddenProse in $(_lint_config_path), or pass CCPR_LINT_FORBIDDEN_PROSE."
fi

for ROOT in "${ROOTS[@]}"; do

# Collect files. CCP-1163: ROOT may now be a single FILE, not only a
# directory — manual-lint.sh describes itself as "generic over ANY
# documentation root", and a lone top-level document (CLAUDE.md,
# instincts.md, a script) is a legitimate root of exactly one file, not a
# degenerate directory. A FILE root contributes itself when it matches
# *.md (the shape checks (a)/(b)/(c)/(f) understand); a file root that does
# NOT match *.md — a shell script, say — correctly contributes nothing to
# THIS array (check (g) below has its own, wider match), the same "empty
# scope" state a directory with no markdown files already produces, not a
# new state.
#
# A missing ROOT is not distinguished from an existing-but-empty one in
# FILES_TOTAL — both end up scanning zero files — but the stderr notice
# below names which of the two it was, since "0 files scanned, 0 errors"
# would otherwise read as a clean pass either way (WI-0090/WI-0121
# convention: an empty scan says so on stderr, not silence). The existence
# test for that notice is `-e` (any kind of directory entry), never the
# old `! -d` — that test misreported an EXISTING file as "does not exist"
# solely because a file fails `-d`, the exact defect that made
# `bash scripts/manual-lint.sh instincts.md` read as a missing root before
# this fix.
FILES=()
if [[ -f "$ROOT" ]]; then
    case "$ROOT" in
        *.md) FILES=("$ROOT") ;;
    esac
elif [[ -d "$ROOT" ]]; then
    while IFS= read -r line; do
        FILES+=("$line")
    done < <(find "$ROOT" -type f -name "*.md")
fi
ROOT_FILES_TOTAL=${#FILES[@]}
FILES_TOTAL=$((FILES_TOTAL + ROOT_FILES_TOTAL))

if [[ "$ROOT_FILES_TOTAL" -eq 0 ]]; then
    if [[ ! -e "$ROOT" ]]; then
        echo "manual-lint: root '$ROOT' does not exist" >&2
    else
        echo "manual-lint: no markdown files found under $ROOT" >&2
    fi
fi

# ROOT_ABS — ROOT resolved to an absolute path once per iteration, so every
# later "make this path human-readable relative to ROOT" strip (in the
# per-file loop below) works against the SAME base regardless of whether
# ROOT itself was given relative or absolute on the command line. Only
# computed when ROOT exists — find() above already left FILES empty for a
# missing ROOT, so this is unreachable in that case. For a FILE root,
# ROOT_ABS is the file's PARENT directory (not the file itself, which `cd`
# would reject) — display_rel()'s "strip the `$r/` prefix" contract below
# needs a directory on the left of that slash either way, directory root
# or file root.
ROOT_ABS=""
if [[ -f "$ROOT" ]]; then
    ROOT_ABS="$(cd "$(dirname "$ROOT")" && pwd)"
    ROOTS_ABS+=("$ROOT_ABS")
elif [[ -d "$ROOT" ]]; then
    ROOT_ABS="$(cd "$ROOT" && pwd)"
    ROOTS_ABS+=("$ROOT_ABS")
fi

for file in ${FILES[@]+"${FILES[@]}"}; do
    # code-reviewer finding (CCP-1163, second cut): for a FILE root, $file
    # equals $ROOT exactly (no trailing path component) — the
    # `${file#$ROOT/}` strip pattern never matches (it requires a literal
    # "/" right after $ROOT), so $rel silently stayed the full, unstripped
    # $ROOT string. Harmless when $ROOT is given relative on the command
    # line, but check-all.sh resolves its own PROJECT_DIR to an ABSOLUTE
    # path (`pwd -P`) before building every root argument — so every real
    # invocation of a newly wired file root (CLAUDE.md, instincts.md, ...)
    # leaked the full local filesystem path into every report line, the
    # exact thing the directory case's own `rel`/`gfile_display` comments
    # elsewhere in this file commit to never doing. A file root has no
    # "inside" to report a path relative TO — its own basename IS its full
    # identity, the same answer check (g)'s `gfile_display` already reaches
    # for the identical case.
    if [[ -f "$ROOT" ]]; then
        rel="$(basename "$ROOT")"
    else
        rel="${file#$ROOT/}"
    fi
    base_dir="$(dirname "$file")"

    # (c) kind: vocabulary — opt-in, only fires when kind: is actually set.
    kind_val="$(fm_field "$file" kind || true)"
    if [[ -n "$kind_val" ]] && ! is_valid_kind "$kind_val"; then
        warn "$rel — kind='$kind_val' is not in the known vocabulary (see templates/PHASE_DOC_SCHEMA.md) — add it there deliberately if this project uses it on purpose"
    fi

    # (a) parent_index — document-relative first, ROOT-fallback second,
    # same two-step cascade as phase-docs-lint.sh checks (f)/(g)
    # (scripts/phase-docs-lint.sh:274-297): a document-relative hit stays
    # silent (the documented, preferred form), a ROOT-relative hit is
    # reported as `info` so the fallback usage stays visible rather than
    # unnoticed drift, and neither resolving is an `err`.
    parent_idx="$(fm_field "$file" parent_index || true)"
    idx_resolved=""
    if [[ -n "$parent_idx" ]]; then
        if [[ -f "$base_dir/$parent_idx" ]]; then
            idx_resolved="$base_dir/$parent_idx"
        elif [[ -f "$ROOT/$parent_idx" ]]; then
            idx_resolved="$ROOT/$parent_idx"
            info "$rel — parent_index='$parent_idx' resolved via root fallback ($ROOT/$parent_idx), not found relative to $base_dir"
        else
            err "$rel — parent_index='$parent_idx' points to non-existent file"
        fi
    fi

    if [[ -n "$idx_resolved" ]]; then
        idx_abs="$(cd "$(dirname "$idx_resolved")" && pwd)/$(basename "$idx_resolved")"
        file_abs="$(cd "$base_dir" && pwd)/$(basename "$file")"
        PARENT_LINKS+=("$idx_abs|$file_abs")
    fi

    # (f) derived-count markers — grammar, rules and rationale in the
    # "Check (f)" block above. File-local, so it lives here in the per-file
    # loop rather than in the second pass check (b) needs.
    #
    # `|| [[ -n "$line" ]]` keeps the last line of a file that ends without a
    # newline: `read` returns non-zero there but has still filled $line.
    fence_char=""
    fence_close_re=""
    line_no=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line_no=$((line_no + 1))

        if [[ -n "$fence_char" ]]; then
            if [[ "$line" =~ $fence_close_re ]]; then
                fence_char=""
                fence_close_re=""
            fi
            continue
        fi
        if [[ "$line" =~ $F_FENCE_OPEN_RE ]]; then
            fence_opener="${BASH_REMATCH[1]}"
            fence_char="${fence_opener:0:1}"
            # A fence closes only on its OWN character, at least as long as
            # the opener — so a ``` inside an open ~~~ fence stays content.
            fence_close_re="^ {0,3}[${fence_char}]{${#fence_opener},}[[:space:]]*$"
            continue
        fi

        # One walk, two products: the prose to count numbers in, and the
        # comment spans to look for markers in (see f_strip_markup).
        f_strip_markup "$line"
        [[ ${#F_SPANS[@]} -gt 0 ]] || continue

        # Pass 1 — marker SHAPE. Every marker span on the line is parsed,
        # not just the first: a marker that is recognised and then silently
        # dropped is exactly the failure this check exists to remove.
        line_markers=()
        for span in ${F_SPANS[@]+"${F_SPANS[@]}"}; do
            [[ "$span" =~ $F_MARKER_PRESENT_RE ]] || continue
            if [[ ! "$span" =~ $F_MARKER_RE ]]; then
                err "$rel:$line_no — malformed derived-count marker (expected '<!-- $MARKER_WORD <count|floor> <glob> -->')"
                continue
            fi
            marker_verb="${BASH_REMATCH[1]}"
            marker_glob="${BASH_REMATCH[2]}"
            case "$marker_verb" in
                count|floor) line_markers+=("$marker_verb $marker_glob") ;;
                *) err "$rel:$line_no — unknown marker verb '$marker_verb' (the vocabulary is: count, floor)" ;;
            esac
        done
        [[ ${#line_markers[@]} -gt 0 ]] || continue

        # Pass 2 — the one-number rule, once per LINE rather than once per
        # marker: the numbers belong to the line, so two markers on it must
        # not produce the same complaint twice.
        f_extract_numbers "$F_STRIPPED"
        if [[ ${#F_NUMBERS[@]} -ne 1 ]]; then
            err "$rel:$line_no — a derived-count marker guards a line carrying ${#F_NUMBERS[@]} numbers; exactly one is required (rewrite the sentence so it states a single number, marker comment excluded)"
            continue
        fi
        declared_value="${F_NUMBERS[0]}"

        # Pass 3 — resolve and compare, per marker.
        for entry in "${line_markers[@]}"; do
            marker_verb="${entry%% *}"
            marker_glob="${entry#* }"

            # Glob resolution — document-relative first, ROOT-fallback
            # second: the same cascade check (a) above already implements for
            # parent_index, reused rather than reinvented, with a fallback hit
            # reported as `info` for the same reason (keep the fallback usage
            # visible instead of letting it become unnoticed drift).
            f_count_glob "$base_dir" "$marker_glob"
            derived_value="$F_GLOB_COUNT"
            if [[ "$derived_value" -eq 0 ]]; then
                f_count_glob "$ROOT" "$marker_glob"
                derived_value="$F_GLOB_COUNT"
                if [[ "$derived_value" -gt 0 ]]; then
                    info "$rel:$line_no — $marker_verb marker '$marker_glob' resolved via root fallback ($ROOT), not relative to $base_dir"
                else
                    err "$rel:$line_no — $marker_verb marker '$marker_glob' matches no files (neither relative to $base_dir nor to $ROOT) — a guard with no scope checks nothing"
                    continue
                fi
            fi

            if [[ "$marker_verb" == "count" ]]; then
                if [[ "$derived_value" -ne "$declared_value" ]]; then
                    err "$rel:$line_no — count marker '$marker_glob' derives $derived_value, but the line states $declared_value"
                fi
            else
                if [[ "$derived_value" -lt "$declared_value" ]]; then
                    err "$rel:$line_no — floor marker '$marker_glob' derives $derived_value, below the $declared_value the line states"
                fi
            fi
        done
    done < "$file"
done

# (g) forbidden-prose terms — scanned over *.md/*.py/*.sh under THIS root,
# only when at least one term is configured (LINT_TERMS empty means "not
# configured", see lint_load_forbidden_prose above — no find() cost paid
# for a check nobody turned on). CCP-1163: a FILE root contributes itself
# when it matches one of the three extensions — same shape as the
# checks-(a)/(b)/(c)/(f) FILES array above, just against check (g)'s wider
# extension set.
if [[ ${#LINT_TERMS[@]} -gt 0 ]] && { [[ -d "$ROOT" ]] || [[ -f "$ROOT" ]]; }; then
    G_FILES=()
    if [[ -f "$ROOT" ]]; then
        case "$ROOT" in
            *.md|*.py|*.sh) G_FILES=("$ROOT") ;;
        esac
    else
        while IFS= read -r gline; do
            G_FILES+=("$gline")
        done < <(find "$ROOT" -type f \( -name "*.md" -o -name "*.py" -o -name "*.sh" \))
    fi

    for gfile in ${G_FILES[@]+"${G_FILES[@]}"}; do
        grel="${gfile#$ROOT/}"
        # gfile_display — grel, prefixed with the SCANNED ROOT's own
        # directory name (never its full ancestor chain). pathContains
        # entries are written as repository-relative substrings ("docs/
        # adr/", "instincts/external.md"), which only ever appear in
        # $grel when ROOT happens to be the repository root itself — a
        # measured defect (CCP-1151 stage 4 cut 4 authoring): pointing this
        # script at ROOT=instincts strips "instincts/" off the very path
        # the exemption is written against, so "instincts/external.md"
        # never matches "external.md" alone. The first fix tried here
        # matched against the file's FULL absolute path instead, which
        # does resolve that case but widens the blast radius to every
        # ANCESTOR directory above the scanned root — a checkout path, a
        # username, a CI workspace name that happens to contain a
        # configured substring would silently (and wrongly) excuse a file
        # nobody meant to exempt (code-reviewer finding, CCP-1151 stage 4
        # cut 4). Prefixing only the root's OWN basename — resolved via
        # ROOT_ABS, never the raw $ROOT string, since `basename .` returns
        # "." literally rather than the real directory name — reproduces
        # the repository-relative shape pathContains entries are written
        # against without exposing anything above the root the operator
        # actually pointed this script at.
        #
        # CCP-1163: a FILE root has no "inside" to strip $ROOT/ off of —
        # $grel above stayed the full, unstripped $gfile (identical to
        # $ROOT, the single file this root names). The directory case's
        # own safety property — never expose anything ABOVE the level the
        # operator pointed this script at — is reproduced here the same
        # way: just the file's OWN basename, never $ROOT_ABS (that would be
        # the file's PARENT directory per the ROOT_ABS computation above,
        # a level this script was never asked to scan).
        if [[ -f "$ROOT" ]]; then
            gfile_display="$(basename "$ROOT")"
        else
            gfile_display="$(basename "$ROOT_ABS")/$grel"
        fi
        for ((ti = 0; ti < ${#LINT_TERMS[@]}; ti++)); do
            term="${LINT_TERMS[$ti]}"

            # pathContains excuses the WHOLE FILE for this term — skip
            # before ever opening it.
            if g_line_has_any "$gfile_display" "${LINT_PATHS[$ti]}"; then
                continue
            fi

            # File-level pre-filter (WI-style performance note, CCP-1151
            # stage 4 cut 4): the vast majority of files in a real tree do
            # not contain the term at all, and forking `tr` twice per LINE
            # regardless — the first version of this loop did exactly that
            # — made a full-repo run take minutes. One `grep -qi` decides
            # whether this (file, term) pair needs any further work; a miss
            # here costs one process, not one per line.
            grep -qiF -- "$term" "$gfile" 2>/dev/null || continue

            term_lower="$(printf '%s' "$term" | LC_ALL=C tr '[:upper:]' '[:lower:]')"

            # ORIG_LINES/LOWER_LINES — the file's lines, and the SAME lines
            # lowercased, read as two parallel arrays built from ONE `tr`
            # invocation over the whole file rather than one per line. bash
            # 3.2 (this repo's floor, ADR-0011) has no built-in one-shot
            # "read every line into an array" command (that arrived in a
            # later bash major version), hence the two explicit read loops.
            # The `|| [[ -n "$l" ]]` keeps a final line that has no trailing
            # newline, matching the read idiom used throughout this script's
            # other per-file loops.
            ORIG_LINES=()
            while IFS= read -r l || [[ -n "$l" ]]; do ORIG_LINES+=("$l"); done < "$gfile"
            LOWER_LINES=()
            while IFS= read -r l || [[ -n "$l" ]]; do LOWER_LINES+=("$l"); done \
                < <(LC_ALL=C tr '[:upper:]' '[:lower:]' < "$gfile")

            for ((li = 0; li < ${#ORIG_LINES[@]}; li++)); do
                gline="${ORIG_LINES[$li]}"
                line_lower="${LOWER_LINES[$li]}"
                g_line_no=$((li + 1))
                [[ "$line_lower" == *"$term_lower"* ]] || continue

                g_find_offsets "$line_lower" "$term_lower"
                for off in ${G_OFFSETS[@]+"${G_OFFSETS[@]}"}; do
                    if g_excused_by_token "$line_lower" "$off" "${LINT_TOKENS[$ti]}"; then
                        continue
                    fi
                    if g_line_has_any "$gline" "${LINT_LINES[$ti]}"; then
                        continue
                    fi
                    # CCP-1163 (second cut, code-reviewer finding): the
                    # reported path was always $grel here, which — for a
                    # FILE root — is the unstripped, potentially-absolute
                    # $ROOT itself (see the comment on $grel above), never
                    # fixed even after $gfile_display already computed the
                    # correct basename-only display for the pathContains
                    # test just above. $gfile_display for the DIRECTORY
                    # case is deliberately NOT substituted here too — it
                    # carries an extra root-basename prefix ($grel does
                    # not) that would change every existing directory-root
                    # report's path shape, a wider behaviour change than
                    # this fix is scoped to.
                    if [[ -f "$ROOT" ]]; then
                        err "$gfile_display:$g_line_no:$((off + 1)) — forbidden prose term '$term' found outside its configured allowed contexts (lint.forbiddenProse) — excuse it via tokenContexts/lineContains/pathContains, or fix the wording"
                    else
                        err "$grel:$g_line_no:$((off + 1)) — forbidden prose term '$term' found outside its configured allowed contexts (lint.forbiddenProse) — excuse it via tokenContexts/lineContains/pathContains, or fix the wording"
                    fi
                done
            done
        done
    done
fi

done

# (b) Reverse direction — the index an existing parent_index resolved to
# must itself link the claiming file back. Grouped by unique index path so
# each index's content is read once, not once per child.
if [[ ${#PARENT_LINKS[@]} -gt 0 ]]; then
    while IFS= read -r idx_path; do
        [[ -z "$idx_path" ]] && continue
        idx_dir="$(dirname "$idx_path")"
        idx_content="$(cat "$idx_path")"
        idx_rel="$(display_rel "$idx_path")"
        for pair in "${PARENT_LINKS[@]}"; do
            this_idx="${pair%%|*}"
            [[ "$this_idx" == "$idx_path" ]] || continue
            child="${pair#*|}"
            child_rel="$(display_rel "$child")"
            target="$(rel_path "$idx_dir" "$child")"
            # A here-string, not a pipe: under `set -o pipefail` a
            # `printf | grep -qF` can report the whole pipeline as failed
            # via SIGPIPE precisely when grep exits early on a match while
            # printf is still writing the rest of a large index — turning a
            # real hit into a reported miss (measured 16% false-negative
            # rate at ~37 KB of content). A here-string keeps grep as the
            # only command in the statement, so there is no producer left
            # to receive SIGPIPE. Not switched to `grep -qF ... "$idx_path"`
            # instead, because idx_content is deliberately read ONCE per
            # index above and reused across every child in this inner loop
            # (see the comment on the outer `while` below) — grepping the
            # file directly here would re-read it once per child again. On
            # bash 3.2 (this repo's minimum target) a here-string larger
            # than the pipe buffer is written through a temp file rather
            # than an in-memory fd, which is a performance cost, not a
            # correctness one — real handbook/-sized index files are nowhere
            # near where that would matter.
            if ! grep -qF "]($target)" <<< "$idx_content"; then
                warn "$idx_rel — does not link back to $child_rel, which names it as parent_index (expected a link to '$target')"
            fi
        done
    done < <(printf '%s\n' "${PARENT_LINKS[@]}" | cut -d'|' -f1 | sort -u)
fi

# Report output
NOW="$(date '+%d.%m.%Y %H:%M')"
echo "# Manual Lint Report"
echo
ROOTS_JOINED="$(IFS=','; echo "${ROOTS[*]}")"
echo "**Roots:** $ROOTS_JOINED"
echo "**Checks:** (a) parent_index resolves (document-relative first, root-fallback second) · (b) the resolved index links the claiming file back · (c) kind: is in the known vocabulary (warning if not) · (f) a marked number agrees with the value derived from its glob · (g) a configured forbidden-prose term is not used outside its allowed contexts (opt-in — not configured means not checked)"
echo "**Run:** $NOW"
echo "**Files scanned:** $FILES_TOTAL"
echo

echo "## Errors (${#errors[@]})"
echo
if [[ ${#errors[@]} -eq 0 ]]; then echo "_none_"; fi
for e in "${errors[@]:-}"; do [[ -n "$e" ]] && echo "- $e"; done
echo

echo "## Warnings (${#warnings[@]})"
echo
if [[ ${#warnings[@]} -eq 0 ]]; then echo "_none_"; fi
for w in "${warnings[@]:-}"; do [[ -n "$w" ]] && echo "- $w"; done
echo

echo "## Info (${#infos[@]})"
echo
if [[ ${#infos[@]} -eq 0 ]]; then echo "_none_"; fi
for i in "${infos[@]:-}"; do [[ -n "$i" ]] && echo "- $i"; done
echo

echo "---"
echo
echo "**Summary:** ${#errors[@]} errors, ${#warnings[@]} warnings, ${#infos[@]} info."

if (( ${#errors[@]} > 0 )); then
    echo "**Exit:** 2"
    exit 2
elif (( ${#warnings[@]} > 0 )); then
    echo "**Exit:** 1"
    exit 1
fi
echo "**Exit:** 0"
exit 0
