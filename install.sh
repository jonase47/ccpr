#!/usr/bin/env bash
#
# CCPR installer.
#
# Copies the framework artifacts into ~/.claude with a timestamped backup and a
# loud overwrite confirmation. Pre-1.0 there is no merge or migration: this
# script makes the shallow file copy *safe* (back up first, show what gets
# overwritten, require an explicit "yes"). It does NOT preserve in-place
# customizations of shipped files — that customization-preserving installer is
# the v1.0 roadmap item (see docs/CONSTITUTION.md, Aspirational).
#
# Your own data is never touched: ~/.claude/memory/ and ~/.claude/scripts/local-llm/
# are out of scope (not in the artifact allowlist below), and anything already in
# ~/.claude is captured by the backup before the first file is written.
#
# Usage:
#   ./install.sh                 # fresh install: back up, preview, confirm, copy everything
#   ./install.sh --update        # update: copy framework only, keep your personal files + instincts
#   ./install.sh --update --with-instincts  # update, but also refresh instincts
#   ./install.sh --dry-run       # show what would happen, change nothing
#   ./install.sh --yes           # skip the confirmation prompt (still backs up)
#   CCPR_DEST=/path ./install.sh # install to a custom target dir
#
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CCPR_DEST:-$HOME/.claude}"

# Artifacts are grouped so --update can leave the files you personalise (or that
# mature on your machine) alone. Repo-meta files (README, CHANGELOG, LICENSE,
# AUTHORS, CONTRIBUTING, SECURITY, BETA, install.sh, .git, .gitignore) are never
# copied into your config.
#
# FRAMEWORK : pure framework — always (re)installed.
# INSTINCTS : ship a starter set, but mature on your machine via /postmortem —
#             installed fresh, skipped on --update unless --with-instincts.
# PERSONAL  : you edit these after install — installed fresh, never touched by --update.
FRAMEWORK=( agents commands docs hooks scripts templates )
INSTINCTS=( instincts instincts-archive instincts.md )
PERSONAL=( settings.json CLAUDE.md )

# PROTECTED : user-owned sub-paths that live INSIDE a framework directory. A
# framework dir is replaced wholesale, which would otherwise delete these. If
# they already exist in the target they are stashed and restored verbatim (your
# copy wins over anything shipped). On a fresh target where they don't exist,
# the shipped starter version (if any) is installed normally.
#   - scripts/local-llm  : your Ollama wrappers carry hardware-specific model choices.
#   - scripts/lib/scan_rules, scripts/lib/test_parsers : harness-managed local data.
PROTECTED=( scripts/local-llm scripts/lib/scan_rules scripts/lib/test_parsers )

ASSUME_YES=0
DRY_RUN=0
UPDATE=0
WITH_INSTINCTS=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    -n|--dry-run) DRY_RUN=1 ;;
    -u|--update) UPDATE=1 ;;
    --with-instincts) WITH_INSTINCTS=1 ;;
    -h|--help)
      cat <<'EOF'
CCPR installer — copy the framework into ~/.claude, safely.

Backs up an existing target (timestamped), shows which artifacts would be
overwritten, and requires confirmation before writing. Pre-1.0 there is no
merge/migration: shipped files are replaced wholesale. Your own data is kept:
~/.claude/memory/ is out of scope, and user-owned sub-paths inside framework
dirs (scripts/local-llm/, scripts/lib/scan_rules/, scripts/lib/test_parsers/)
are preserved across the replace.

Modes:
  (default)          Fresh install — copies framework + instincts + your
                     personalisable files (CLAUDE.md, settings.json).
  --update           Update — copies framework only. Keeps CLAUDE.md and
                     settings.json (your edits) and instincts (matured via
                     /postmortem) as they are. The safe re-run for upgrades.
  --with-instincts   With --update, also refresh the shipped instincts
                     (overwrites your matured ones — back up / re-merge after).

Options:
  --dry-run          Show what would happen, change nothing.
  --yes              Skip the confirmation prompt (still backs up).
  CCPR_DEST=/path    Install to a custom target directory.
EOF
      exit 0
      ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

# Build the effective artifact list from the mode.
ARTIFACTS=( "${FRAMEWORK[@]}" )
SKIPPED=()
if [[ "$UPDATE" -eq 1 ]]; then
  if [[ "$WITH_INSTINCTS" -eq 1 ]]; then
    ARTIFACTS+=( "${INSTINCTS[@]}" )
  else
    SKIPPED+=( "${INSTINCTS[@]}" )
  fi
  SKIPPED+=( "${PERSONAL[@]}" )
else
  ARTIFACTS+=( "${INSTINCTS[@]}" "${PERSONAL[@]}" )
fi

# Sanity check: are we actually inside a CCPR checkout?
if [[ ! -d "$SRC/agents" || ! -d "$SRC/commands" ]]; then
  echo "ERROR: $SRC does not look like a CCPR checkout (no agents/ or commands/)." >&2
  echo "Run this script from the root of the cloned repository." >&2
  exit 1
fi

echo "CCPR installer"
echo "  source: $SRC"
echo "  target: $DEST"
if [[ "$UPDATE" -eq 1 ]]; then
  echo "  mode:   update (framework only$([[ "$WITH_INSTINCTS" -eq 1 ]] && echo " + instincts"))"
else
  echo "  mode:   fresh install (everything)"
fi
echo

# In update mode, reassure which files are deliberately left as-is.
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  echo "Keeping your local files (NOT touched):"
  for item in "${SKIPPED[@]}"; do
    echo "     - $item"
  done
  echo "   (Use --with-instincts to also refresh instincts.)"
  echo
fi

# Show which artifacts already exist at the target (would be overwritten).
overwrites=()
for item in "${ARTIFACTS[@]}"; do
  [[ -e "$DEST/$item" ]] && overwrites+=("$item")
done

if [[ ${#overwrites[@]} -gt 0 ]]; then
  echo "!! WARNING: the following already exist in $DEST and WILL be overwritten:"
  for item in "${overwrites[@]}"; do
    echo "     - $item"
  done
  echo "   (A full timestamped backup of $DEST is taken first — nothing is lost.)"
  echo "   Note: shipped files are replaced wholesale. If you edited any of the above"
  echo "   in place, re-apply your changes from the backup afterwards."
  echo "   User-owned sub-paths are preserved across the replace:"
  for p in "${PROTECTED[@]}"; do
    [[ -e "$DEST/$p" ]] && echo "     ~ $p (kept)"
  done
  echo
else
  echo "No existing CCPR artifacts found in $DEST — this looks like a fresh install."
  echo
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] Would back up $DEST (if it exists) and copy:"
  for item in "${ARTIFACTS[@]}"; do
    echo "  $SRC/$item -> $DEST/$item"
  done
  echo "[dry-run] No changes made."
  exit 0
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
  printf "Proceed with backup + install? [y/N] "
  read -r reply
  case "$reply" in
    y|Y|yes|YES) ;;
    *) echo "Aborted. Nothing changed."; exit 0 ;;
  esac
fi

# Back up an existing target before writing anything.
if [[ -e "$DEST" ]]; then
  backup="${DEST%/}.backup-$(date +%Y%m%d-%H%M%S)"
  echo "Backing up $DEST -> $backup"
  cp -r "$DEST" "$backup"
fi

mkdir -p "$DEST"

# Copy each artifact. Directory artifacts are replaced wholesale, but any
# user-owned PROTECTED sub-paths under them are stashed first and restored after,
# so a wholesale replace never deletes your local data.
for item in "${ARTIFACTS[@]}"; do
  if [[ ! -e "$SRC/$item" ]]; then
    echo "  (skip: $item not present in source)"
    continue
  fi
  echo "  installing $item"
  if [[ -d "$SRC/$item" ]]; then
    # Stash protected sub-paths that live under this artifact and already exist.
    stash=""
    for p in "${PROTECTED[@]}"; do
      if [[ "$p" == "$item/"* && -e "$DEST/$p" ]]; then
        [[ -n "$stash" ]] || stash="$(mktemp -d "${TMPDIR:-/tmp}/ccpr-stash-XXXXXX")"
        mkdir -p "$stash/$(dirname "$p")"
        cp -R "$DEST/$p" "$stash/$p"
        echo "    preserving $p"
      fi
    done
    rm -rf "${DEST:?}/$item"
    cp -R "$SRC/$item" "$DEST/$item"
    # Restore the stashed sub-paths (your copy wins over anything shipped).
    if [[ -n "$stash" ]]; then
      for p in "${PROTECTED[@]}"; do
        if [[ "$p" == "$item/"* && -e "$stash/$p" ]]; then
          rm -rf "$DEST/$p"
          mkdir -p "$(dirname "$DEST/$p")"
          cp -R "$stash/$p" "$DEST/$p"
        fi
      done
      rm -rf "$stash"
    fi
  else
    cp "$SRC/$item" "$DEST/$item"
  fi
done

echo
if [[ "$UPDATE" -eq 1 ]]; then
  echo "Done. CCPR framework updated in $DEST."
  echo "Your CLAUDE.md, settings.json$([[ "$WITH_INSTINCTS" -eq 1 ]] || echo " and instincts") were left untouched."
  echo
  echo "Next:"
  echo "  - Read CHANGELOG.md for what changed in this version."
  echo "  - Smoke test — open Claude Code and type:  /guide"
else
  echo "Done. CCPR is installed in $DEST."
  echo
  echo "Next:"
  echo "  1. Personalize $DEST/CLAUDE.md (Personal Context, Infrastructure, language)."
  echo "  2. Smoke test — open Claude Code in any project and type:  /guide"
  echo "     You should see a status snapshot and suggested next steps."
  echo "  3. Start a project with:  /track-decision"
fi
