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

set -euo pipefail

# fm_has — Checks whether the file starts with a `---` block.
fm_has() {
    local file="$1"
    [[ -f "$file" ]] || return 1
    [[ "$(head -n1 "$file")" == "---" ]] || return 1
    # Search for the closing marker within the first 50 lines
    awk 'NR==1 && $0=="---" {found_open=1; next}
         found_open && $0=="---" {found_close=1; exit}
         NR>50 {exit}
         END {exit !found_close}' "$file"
}

# fm_extract — Outputs the frontmatter lines (without `---` markers).
fm_extract() {
    local file="$1"
    awk 'NR==1 && $0=="---" {in_fm=1; next}
         in_fm && $0=="---" {exit}
         in_fm {print}' "$file"
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
        }'
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
        }'
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
