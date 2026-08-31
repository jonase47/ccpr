#!/usr/bin/env bash
# frontmatter.sh — YAML Frontmatter helper for lint scripts
# Read-only, idempotent. Used by memory-lint.sh and phase-docs-lint.sh.
#
# Source: bash ~/.claude/scripts/lib/frontmatter.sh   (for function calls from other scripts)
#
# Functions:
#   fm_has <file>                          → 0 if a `---` block exists at the start of the file
#   fm_extract <file>                      → echo the frontmatter lines (without markers)
#   fm_field <file> <key>                  → echo the value (first line matching `key:`)
#   fm_list <file> <key>                   → echo list entries (inline [a, b] OR YAML block)
#   fm_validate_required <file> <k1,k2,…>  → echo missing fields (one per line), exit 0 if all present
#   fm_date_shape_ok <value>               → 0 if <value> is DD.MM.YYYY, optionally + " (note)"
#   fm_date_to_epoch <value>               → echo epoch of <value>'s UTC midnight, or "0" if unparseable
#   fm_set <file> <key> <value>            → write/replace a flat top-level key, body untouched
#   fm_set_many <file> <k1=v1> [<k2=v2> …] → write/replace MULTIPLE flat top-level keys as ONE atomic group

set -euo pipefail

# CRLF (WI-0131). Every marker comparison in this library asks for the
# string `---` exactly, and `awk` splits records on `\n` alone — so on a
# file with Windows line endings the markers arrive as `---\r` and NOTHING
# here matched them. The block did not read as malformed, it read as
# ABSENT, which is the dangerous direction on both sides: the lints raise
# `required field missing` about a field the document plainly carries,
# while the writer (`freeze-phase-docs.sh`) silently freezes nothing. The
# repo-root `.gitattributes` (bc87c9f) normalises endings HERE; it has no
# reach into the adopter project trees these scripts actually run against.
#
# Two mechanisms, two treatments, because one does not reach the other:
#
#   * The READERS below strip the carriage return off `$0` itself, as the
#     FIRST statement of the record block — the same position, and for the
#     same "reach" reason, as `memory-lint.sh`'s own strip (WI-0086): every
#     later branch reads `$0` or a substring of it. This is also why
#     `fm_field`, `fm_list` and `fm_validate_required` need no strip of
#     their own: all three read `fm_extract`'s output, never the file.
#   * The WRITERS (`fm_set`, `fm_set_many`) must NOT do that — they print
#     `$0` verbatim for every line they pass through, and a strip on `$0`
#     would quietly rewrite the whole document to LF, breaking their
#     body-untouched contract. They compare against a stripped COPY and
#     carry the record's own terminator onto the line they write.
#   * `fm_has`'s first-line test is a SHELL string comparison that runs
#     before any `awk` does, so no `awk`-level strip can reach it. It gets
#     its own `${first%$'\r'}` below.
#
# A bare `\r` INSIDE a line (a pre-OS-X Mac line ending) is deliberately
# not handled anywhere here: `awk` has already split on `\n`, so such a
# document arrives as a single record and no per-record strip can recover
# a line structure it never had.

# fm_has — Checks whether the file starts with a `---` block.
fm_has() {
    local file="$1"
    local first
    [[ -f "$file" ]] || return 1
    first="$(head -n1 "$file")"
    # Trims the TERMINATOR, not the content: `----\r` stays a non-match.
    first="${first%$'\r'}"
    [[ "$first" == "---" ]] || return 1
    # Search for the closing marker within the first 50 lines
    awk '{ sub(/\r$/, "") }
         NR==1 && $0=="---" {found_open=1; next}
         found_open && $0=="---" {found_close=1; exit}
         NR>50 {exit}
         END {exit !found_close}' "$file"  # exit-status: exempt propagates-as-function-return
}

# fm_extract — Outputs the frontmatter lines (without `---` markers).
# Emits the lines WITHOUT their carriage returns, so every reader built on
# top of it (fm_field, fm_list, fm_validate_required) sees clean values —
# `fm_list`'s inline branch in particular anchors on `^\[.*\]$`, which a
# trailing `\r` defeats even where a plain value would survive on a
# trailing-whitespace trim alone.
fm_extract() {
    local file="$1"
    awk '{ sub(/\r$/, "") }
         NR==1 && $0=="---" {in_fm=1; next}
         in_fm && $0=="---" {exit}
         in_fm {print}' "$file"  # exit-status: exempt propagates-as-function-return
}

# fm_field — Returns the value for `key:` (trims whitespace, strips surrounding quotes).
# For lists or multi-line values: first line only.
fm_field() {
    local file="$1"
    local key="$2"
    fm_extract "$file" | awk -v k="$key" '
        $0 ~ "^"k":" {
            sub("^"k":[[:space:]]*", "")
            # Trim trailing whitespace
            sub(/[[:space:]]+$/, "")
            # Strip surrounding quotes (single or double)
            if (match($0, /^"(.*)"$/)) { $0 = substr($0, 2, length($0)-2) }
            else if (match($0, /^'\''(.*)'\''$/)) { $0 = substr($0, 2, length($0)-2) }
            print
            exit
        }'  # exit-status: exempt propagates-as-function-return
}

# fm_list — Outputs list entries.
# Supports inline: `related: [a.md, b.md]`
# Supports YAML block:
#   related:
#     - a.md
#     - b.md
fm_list() {
    local file="$1"
    local key="$2"
    fm_extract "$file" | awk -v k="$key" '
        BEGIN { in_block=0 }
        $0 ~ "^"k":" {
            line = $0
            sub("^"k":[[:space:]]*", "", line)
            # Inline variant: [a, b, c]
            if (match(line, /^\[.*\]$/)) {
                inner = substr(line, 2, length(line)-2)
                n = split(inner, arr, ",")
                for (i = 1; i <= n; i++) {
                    item = arr[i]
                    gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
                    gsub(/^["'\'']|["'\'']$/, "", item)
                    if (length(item) > 0) print item
                }
                exit
            }
            # Block start: empty or whitespace-only after key:
            if (length(line) == 0 || line ~ /^[[:space:]]*$/) {
                in_block = 1
                next
            }
        }
        in_block && /^[[:space:]]*-[[:space:]]+/ {
            item = $0
            sub(/^[[:space:]]*-[[:space:]]+/, "", item)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
            gsub(/^["'\'']|["'\'']$/, "", item)
            print item
            next
        }
        in_block && !/^[[:space:]]/ {
            in_block = 0
        }'  # exit-status: exempt propagates-as-function-return
}

# fm_validate_required — Checks required fields. Prints missing fields to stdout.
# Exit 0 if all present, else 1.
# Portable between bash and zsh (no `read -a`).
fm_validate_required() {
    local file="$1"
    local required_csv="$2"
    local missing=0
    local field val
    # tr-based splitting works identically in bash and zsh
    while IFS= read -r field; do
        field="${field// /}"
        [[ -z "$field" ]] && continue
        val="$(fm_field "$file" "$field" || true)"
        if [[ -z "$val" ]]; then
            echo "$field"
            missing=1
        fi
    done < <(printf '%s\n' "$required_csv" | tr ',' '\n')
    return $missing
}

# fm_date_shape_ok — Checks the LEXICAL shape of a `last_updated`-style
# value: `DD.MM.YYYY`, optionally followed by whitespace and a
# parenthesised note (WI-0106/WI-0107). Says nothing about whether the
# digits name a real calendar day — pair with fm_date_to_epoch for that.
#
# The pattern is shared, byte-for-byte, by phase-docs-lint.sh's check (e)
# and memory-lint.sh's check (e) — both PHASE_DOC_SCHEMA.md and
# MEMORY_SCHEMA.md specify the same optional " (note)" suffix, which
# carries WHY the date moved (which round, which item) and is load-bearing:
# it must survive here unchanged, not be simplified away.
fm_date_shape_ok() {
    local value="$1"
    [[ "$value" =~ ^[0-9]{2}\.[0-9]{2}\.[0-9]{4}([[:space:]]+\(.*\))?$ ]]
}

# fm_date_to_epoch — DD.MM.YYYY (optionally + " (note)", see
# fm_date_shape_ok) → epoch of that day's UTC midnight (BSD and GNU date
# compatible). Echoes "0" if the value cannot be parsed as a real calendar
# day — a value can pass fm_date_shape_ok and still fail here (`32.13.2026`,
# `99.99.9999`: right shape, no such day).
#
# Moved verbatim from memory-lint.sh's date_to_epoch (WI-0107) — only the
# name changed, to match this library's fm_ prefix convention. Do not
# "improve" this while reading it; the platform handling below is
# deliberate, not incidental.
#
# Both the time zone and the time of day are pinned deliberately, and any
# age-difference check built on top only works because BOTH sides of its
# subtraction go through this one function. Two separate defects sit here
# (WI-0087):
#
# 1. Time of day. The BSD branch used to parse with "%d.%m.%Y", a format with no
#    time component — and BSD date fills unnamed fields from the RUNNING WALL
#    CLOCK, not from midnight. A reference epoch captured once at script start
#    then carried a different time of day than a value computed later, and
#    their difference was short by the script's own elapsed runtime. After
#    integer truncation that lands one day low: a genuinely 91-day-old file
#    reported 90 and, at a 90-day threshold, did not warn at all. The reported
#    age was a property of WHEN IN THE RUN a file was reached, so on a large
#    store the same date could report two different ages in one run, and the
#    same store two different ages in two runs. Measured on the live stores
#    before the fix: six consecutive runs over the same unchanged inventory
#    reported 93/93/91 four times and 94/94/92 once.
#
# 2. Time zone. The GNU branch never had defect 1 — it builds an ISO date, which
#    date -d anchors on midnight — but anchoring on LOCAL midnight is wrong for a
#    difference in days: across a spring-forward the two local midnights are only
#    23 h apart, and the same truncation lands one day low again for every window
#    spanning that transition. -u puts both ends on UTC midnight, where every day
#    is exactly 86400 s long and the subtraction is exact by construction.
#
# The two branches also disagreed with each other, which is why this never showed
# on Linux: the same file could warn there and stay silent on macOS. They now
# return the same number for the same input — verified for both branches, see
# scripts/tests/test_memory_lint.py.
fm_date_to_epoch() {
    local d="$1"
    # BSD date (macOS), in two steps rather than one. The obvious single call —
    # -f "%d.%m.%Y %H:%M:%S" against "$d 00:00:00" — also fixes the anchor, but it
    # tightens what counts as a DATE at the same time, and that is a different
    # decision than this one. BSD date accepts trailing text after the value it
    # matched ("16.05.2026 (Note: ...)" parses, with a warning on stderr) and so
    # does GNU date on the rewritten form; ten files across the live stores lean
    # on that, and appending a time turns every one of them into a hard parse
    # error. So: step one reduces the value to the calendar day BSD date reads
    # out of it, accepting exactly what it accepted before; step two anchors that
    # day, and only that day, at UTC midnight. Whether the loose form should stay
    # legal is a schema question, and it is filed as one (WI-0106).
    local ymd
    if ymd="$(date -j -f "%d.%m.%Y" "$d" "+%Y-%m-%d" 2>/dev/null)"; then
        date -j -u -f "%Y-%m-%d %H:%M:%S" "$ymd 00:00:00" "+%s" 2>/dev/null && return 0
    fi
    # GNU date: -u -d with the value rewritten to ISO. -d already anchors on
    # midnight, so only the time zone changes here.
    local iso
    iso="$(printf '%s' "$d" | awk -F. '{print $3"-"$2"-"$1}')"  # exit-status: exempt downstream-checks-result
    date -u -d "$iso" "+%s" 2>/dev/null || echo "0"
}

# _fm_preserve_mode <original-file> <temp-file> — copies the original's
# permission bits onto the temp file before the atomic `mv` replaces it
# (WI-0021 review, Important 2): `mktemp` creates its temp file with mode
# 0600, and `mv` on the SAME filesystem is a `rename()` — the renamed
# inode carries the SOURCE's permissions forward, not the destination's.
# Left alone, every fm_set/fm_set_many write silently narrows a 644 or
# 755 file to 600. `chmod --reference` is GNU-only; this repo's target
# platform is BSD/macOS, so the mode is read portably via BSD `stat -f
# '%Lp'` first, falling back to GNU `stat -c '%a'`. Best-effort: if
# neither `stat` flavour is available, the file is still written
# correctly, just without its original mode restored.
_fm_preserve_mode() {
    local original="$1" tmp="$2" mode
    mode="$(stat -f '%Lp' "$original" 2>/dev/null)" \
        || mode="$(stat -c '%a' "$original" 2>/dev/null)" \
        || return 0
    chmod "$mode" "$tmp" 2>/dev/null || true
}

# _fm_strip_trailing_newline_if_source_had_none <original-file> <temp-file>
# — awk's `print` unconditionally appends ORS (a newline) to every record
# it emits, including the LAST one, even when the record it read had no
# trailing newline in the source file — reproduced directly: a body
# ending "...no trailing newline." (no final \n byte) comes back from a
# plain awk pass with one added. Detected via the ORIGINAL file's last
# byte (`tail -c1` is non-empty iff the file does NOT end in a newline,
# since a command substitution strips a trailing newline but nothing
# else); the temp file awk just produced always carries at least one
# trailing newline at this point, so removing exactly one restores parity
# with the input — never more, so a body that legitimately ends in
# several blank lines keeps all but the single byte awk added.
_fm_strip_trailing_newline_if_source_had_none() {
    local original="$1" tmp="$2" content
    [[ -n "$(tail -c1 "$original" 2>/dev/null)" ]] || return 0
    content="$(cat "$tmp"; printf 'X')"
    content="${content%X}"
    content="${content%$'\n'}"
    printf '%s' "$content" > "$tmp"
}

# fm_set — Writes a flat top-level frontmatter key (WI-0021/WI-0076,
# ADR-0009 Addendum 1 A8: the shipped writer must be portable, no `sed -i`
# BSD/GNU split). Replaces an existing occurrence of `key:` in place, or
# inserts one just before the closing `---` when the key is absent.
# NEVER touches the body — scanning stops the instant the closing `---`
# marker is seen, so a body line that reads exactly like "key: value" is
# left byte-for-byte alone. Portable: writes a temp file in the SAME
# directory as <file> (same filesystem, atomic `mv`), never edits in
# place. `mv` replacing a symlinked target with a regular file is the
# same, already-accepted behaviour the `sed -i` this replaced had too —
# worth naming once here since this is a shared library function, not a
# regression from the switch. Requires an existing frontmatter block
# (fm_has) — a file without one is an error, not a silent create.
# Idempotent: setting the same key/value twice yields a byte-identical
# file.
fm_set() {
    local file="$1"
    local key="$2"
    local value="$3"

    fm_has "$file" || { echo "fm_set: no frontmatter block in $file" >&2; return 1; }

    # Defensive: a value with an embedded newline BYTE would split one
    # frontmatter line into several, corrupting the block's structure —
    # none of this repo's callers ever pass one, but folding to a space
    # keeps a stray one from silently breaking the file instead of erroring.
    value="${value//$'\n'/ }"

    local tmp
    tmp="$(mktemp "${file}.XXXXXX")" || return 1

    # Passed via ENVIRON, NOT `awk -v key=... -v value=...` (WI-0021
    # review, Important 1): a `-v` assignment goes through the SAME
    # backslash-escape processing as an awk string literal, so a value
    # that merely CONTAINS a literal backslash-n (a --note argument like
    # "siehe docs\notes.md", or any Windows-style path fragment) silently
    # turns into a REAL newline byte inside awk — reproduced directly
    # with `awk -v v='a\nb' 'BEGIN{print length(v)}'` returning 3, not 4.
    # ENVIRON values are copied verbatim, with no escape processing at
    # all, so this avoids the bug at its root instead of adding a second
    # escaping layer on top.
    #
    # `if ! awk ...; then` — checked explicitly rather than left bare: an
    # awk failure must not fall through to `mv`, which would otherwise
    # silently overwrite the original with an empty/partial temp file.
    if ! FM_SET_KEY="$key" FM_SET_VALUE="$value" awk '
        BEGIN {
            key = ENVIRON["FM_SET_KEY"]
            value = ENVIRON["FM_SET_VALUE"]
            state = 0
            replaced = 0
        }
        # CRLF: compare against a stripped COPY, never against `$0` — see
        # the library header. `eol` carries the terminator of the current
        # record onto any line this program GENERATES, so a rewritten or
        # inserted key matches the endings of the document it lands in,
        # while every passed-through line is still printed byte-for-byte.
        {
            line = $0
            eol = ""
            if (sub(/\r$/, "", line)) eol = "\r"
        }
        NR == 1 && line == "---" { print; state = 1; next }
        state == 1 && line == "---" {
            if (!replaced) print key ": " value eol
            print
            state = 2
            next
        }
        state == 1 && index(line, key ":") == 1 {
            # Literal match, NOT `$0 ~ "^" key ":"` (WI-0021 review, small
            # fix #1) — interpolating the key unchecked into a regex
            # turns any regex metacharacter in it ("." in particular)
            # into a wildcard, so e.g. key "a.b" would ALSO match an
            # unrelated "axb:" line. Unreachable today (every caller
            # passes a literal identifier key), but fm_set is documented
            # as a general write path.
            print key ": " value eol
            replaced = 1
            next
        }
        { print }
    ' "$file" > "$tmp"; then
        rm -f "$tmp"
        echo "fm_set: failed to rewrite $file" >&2
        return 1
    fi

    _fm_strip_trailing_newline_if_source_had_none "$file" "$tmp"
    _fm_preserve_mode "$file" "$tmp"
    if ! mv "$tmp" "$file"; then
        echo "fm_set: failed to move $tmp into place for $file — left behind for inspection" >&2
        return 1
    fi
}

# fm_set_many <file> <key1=value1> [<key2=value2> …] — writes MULTIPLE
# flat top-level frontmatter keys in a SINGLE awk pass and a SINGLE
# temp-file-plus-`mv` (WI-0021 review, Critical fix). ADR-0009 §6 names
# acknowledgement's five-key write as "the single highest-risk detail in
# the whole design": five SEPARATE fm_set calls are each individually
# atomic, but the GROUP of five is NOT — an abort between the first and
# the second call (signal, full disk, write error) leaves a document
# carrying the NEW anchor_commit but NONE of the anchor_ack fields, and
# `status` then reads "no anchor_ack recorded" as "anchor up to date":
# the drift the acknowledgement exists to record vanishes without ever
# having been written. fm_set_many closes this structurally — there is
# no intermediate state where some of the given keys are on disk and
# others are not.
#
# Same guarantees as fm_set: body untouched, a file without a
# frontmatter block is an error (never a silent create), idempotent,
# permission bits preserved, keys matched literally rather than
# interpolated into a regex, and a source file with no trailing newline
# is not silently given one.
fm_set_many() {
    local file="$1"
    shift
    [[ $# -gt 0 ]] || { echo "fm_set_many: no key=value pairs given" >&2; return 1; }

    fm_has "$file" || { echo "fm_set_many: no frontmatter block in $file" >&2; return 1; }

    local i=0 pair key value
    local -a export_names=()
    for pair in "$@"; do
        key="${pair%%=*}"
        value="${pair#*=}"
        # Same embedded-newline-BYTE defense as fm_set.
        value="${value//$'\n'/ }"
        i=$((i + 1))
        export "FM_SET_MANY_KEY_$i=$key"
        export "FM_SET_MANY_VAL_$i=$value"
        export_names+=("FM_SET_MANY_KEY_$i" "FM_SET_MANY_VAL_$i")
    done
    export FM_SET_MANY_COUNT="$i"
    export_names+=("FM_SET_MANY_COUNT")

    local tmp
    if ! tmp="$(mktemp "${file}.XXXXXX")"; then
        unset "${export_names[@]}"
        return 1
    fi

    # One awk pass, one temp file, one `mv` — the whole point of this
    # function. Keys/values reach awk via enumerated ENVIRON entries
    # (FM_SET_MANY_KEY_<n>/FM_SET_MANY_VAL_<n>), not `-v`: same
    # escape-processing bug fm_set's own switch fixes (see there), and
    # `-v` has no array form to pass an arbitrary-length list through in
    # the first place.
    if ! awk '
        BEGIN {
            n = ENVIRON["FM_SET_MANY_COUNT"] + 0
            for (idx = 1; idx <= n; idx++) {
                k = ENVIRON["FM_SET_MANY_KEY_" idx]
                keys[idx] = k
                vals[k] = ENVIRON["FM_SET_MANY_VAL_" idx]
                replaced[k] = 0
            }
            state = 0
        }
        # CRLF: stripped COPY for comparison, `eol` for generated lines —
        # same treatment and same reasoning as fm_set above.
        {
            line = $0
            eol = ""
            if (sub(/\r$/, "", line)) eol = "\r"
        }
        NR == 1 && line == "---" { print; state = 1; next }
        state == 1 && line == "---" {
            for (idx = 1; idx <= n; idx++) {
                k = keys[idx]
                if (!replaced[k]) print k ": " vals[k] eol
            }
            print
            state = 2
            next
        }
        state == 1 {
            matched = ""
            for (idx = 1; idx <= n; idx++) {
                k = keys[idx]
                # Literal match, same reasoning as the fm_set fix above.
                if (index(line, k ":") == 1) { matched = k; break }
            }
            if (matched != "") {
                print matched ": " vals[matched] eol
                replaced[matched] = 1
                next
            }
            print
            next
        }
        { print }
    ' "$file" > "$tmp"; then
        rm -f "$tmp"
        unset "${export_names[@]}"
        echo "fm_set_many: failed to rewrite $file" >&2
        return 1
    fi

    unset "${export_names[@]}"
    _fm_strip_trailing_newline_if_source_had_none "$file" "$tmp"
    _fm_preserve_mode "$file" "$tmp"
    if ! mv "$tmp" "$file"; then
        echo "fm_set_many: failed to move $tmp into place for $file — left behind for inspection" >&2
        return 1
    fi
}
