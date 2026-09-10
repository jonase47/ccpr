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
#   ./install.sh --force-fresh   # allow a fresh install onto a target already in
#                                #   use (refused otherwise; --yes does not imply it)
#   ./install.sh --verify        # install nothing: compare the target against
#                                #   the provenance marker a previous install left
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
#             NOTE: if you sync a shared org-tier overlay (scripts/memory-sync.sh), its
#             materialized files under instincts/ are sync-managed and self-healing —
#             re-run `memory-sync.sh pull` after --with-instincts to restore them.
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

# WI-0018: docs/ ships both framework documentation (adr/, CONSTITUTION.md,
# ...) and, in a working checkout, THIS repository's own working state
# (docs/workitems/, docs/memory/, docs/HANDOVER.md, docs/decisions/, ...).
# .gitignore keeps that state out of a fresh clone, but a checkout that
# predates the gitignore rule -- or one that has simply been worked in for a
# while, like a maintainer's own dogfooding directory -- still carries it on
# disk, and a plain wholesale `cp -R docs` would ship it into every install.
#
# DOCS_ALLOWLIST_FILE is the single source of truth for which top-level
# docs/ entries are framework: the SAME file scripts/artifact-gate.sh
# enforces against the repository's tracked files (its docs/ boundary
# check). Neither script keeps its own copy of the list.
DOCS_ALLOWLIST_FILE="$SRC/scripts/lib/docs-framework-allowlist.txt"

# docs_entry_is_allowlisted <name> — true when <name> (a top-level docs/
# child's own basename) is listed in DOCS_ALLOWLIST_FILE. Mirrors
# scripts/artifact-gate.sh's gate_docs_boundary_violation(): a trailing "/"
# entry matches a directory of that name, an entry without one matches a
# file of that exact name. Comments (#) and blank lines are ignored.
docs_entry_is_allowlisted() {
  local name="$1" entry
  while IFS= read -r entry; do
    case "$entry" in
      ''|'#'*) continue ;;
    esac
    case "$entry" in
      */) [[ "$name" == "${entry%/}" ]] && return 0 ;;
      *) [[ "$name" == "$entry" ]] && return 0 ;;
    esac
  done < "$DOCS_ALLOWLIST_FILE"
  return 1
}

# install_docs — replaces the generic wholesale directory copy for the
# single artifact "docs": copies only the top-level entries listed in
# DOCS_ALLOWLIST_FILE from $SRC/docs into $DEST/docs, and reports whatever it
# skipped (name + approximate size) instead of leaving the operator to
# wonder later where files went.
# docs_partition -- classify every top-level child of $SRC/docs into framework
# (installable) and working state (skipped), WITHOUT touching the filesystem.
# WI-0064: install_docs() used to decide and copy in one pass, which left
# --dry-run no way to report the split and made it announce a wholesale copy
# the real run never performs. Both callers now read the same verdict from
# here, so the preview cannot disagree with the run it previews.
# Results land in DOCS_PART_INSTALL / DOCS_PART_SKIP / DOCS_PART_SKIP_KB.
docs_partition() {
  local src_docs="$SRC/docs" name size
  DOCS_PART_INSTALL=() DOCS_PART_SKIP=() DOCS_PART_SKIP_KB=0
  [[ -d "$src_docs" ]] || return 1
  if [[ ! -r "$DOCS_ALLOWLIST_FILE" ]]; then
    echo "ERROR: docs/ framework allowlist not found: $DOCS_ALLOWLIST_FILE" >&2
    exit 1
  fi
  # dotglob: a plain `*` never matches a dotfile, and docs/ is where the
  # project's OWN dotfiles/dot-directories accumulate (docs/.DS_Store,
  # docs/.handover-archive/) -- without it those entries are neither copied
  # nor reported, the exact silent-scope-loss shape this check exists to
  # close, just for a different glob than the one that usually causes it.
  # `.` and `..` are never matched by shell filename generation regardless.
  local had_dotglob=0
  shopt -q dotglob && had_dotglob=1
  shopt -s dotglob
  for entry_path in "$src_docs"/*; do
    [[ -e "$entry_path" ]] || continue
    name="$(basename "$entry_path")"
    if docs_entry_is_allowlisted "$name"; then
      DOCS_PART_INSTALL+=("$name")
    else
      size="$(du -sk "$entry_path" 2>/dev/null | cut -f1)"
      DOCS_PART_SKIP+=("$name")
      DOCS_PART_SKIP_KB=$((DOCS_PART_SKIP_KB + ${size:-0}))
    fi
  done
  [[ "$had_dotglob" -eq 1 ]] || shopt -u dotglob
  return 0
}

# docs_report_skips <indent> -- the shared skip paragraph, so the dry-run and
# the real run cannot drift into two different reports of one verdict.
docs_report_skips() {
  local indent="$1" name
  [[ ${#DOCS_PART_SKIP[@]} -gt 0 ]] || return 0   # also the set -u guard, see install_docs()
  echo "${indent}skipped ${#DOCS_PART_SKIP[@]} working-state path(s) under docs/ (~${DOCS_PART_SKIP_KB}K, not installed):"
  for name in "${DOCS_PART_SKIP[@]}"; do
    echo "${indent}  - docs/$name"
  done
  echo "${indent}(likely a checkout predating the docs/.gitignore rule -- see .gitignore and"
  echo "${indent} scripts/lib/docs-framework-allowlist.txt. If one of these IS framework"
  echo "${indent} documentation, add it to the allowlist and re-run.)"
}

install_docs() {
  local src_docs="$SRC/docs" dest_docs="$DEST/docs" name
  [[ -d "$src_docs" ]] || { echo "  (skip: docs not present in source)"; return; }
  docs_partition

  echo "  installing docs"
  rm -rf "${dest_docs:?}"
  mkdir -p "$dest_docs"

  # Guarded: under `set -u`, bash 3.2 (the macOS default) treats "${arr[@]}"
  # on an EMPTY array as an unbound variable. A docs/ tree with no allowlisted
  # entry is legitimate, so this list really can be empty.
  if [[ ${#DOCS_PART_INSTALL[@]} -gt 0 ]]; then
    for name in "${DOCS_PART_INSTALL[@]}"; do
      cp -R "$src_docs/$name" "$dest_docs/$name"
    done
  fi
  docs_report_skips "    "
}


# --- provenance: what was installed, and from what ---------------------------
#
# A copied tree carries no record of its own origin. Reconstructing which
# state a $DEST was installed from used to be possible only by hand-comparing
# it against a checkout, and only while nothing had been touched since --
# after that the question is unanswerable from disk. So the install writes
# the answer down, and --verify checks the installation against it.
#
# TWO SEPARATE QUESTIONS, deliberately not merged:
#   ORIGIN  -- which state was installed?  Answered by this marker. A record.
#   PRESENT -- does the installed tree still agree with that state?  Answered
#              by --verify, which compares. Editing a file under $DEST does
#              not change the marker, so only a comparison can see it.
#
# The marker must be able to carry every claim it makes. Three cases where a
# bare SHA would be a lie, each recorded explicitly instead:
#   * the source tree was DIRTY -- what was installed is that commit PLUS
#     uncommitted changes (source_state=dirty; the commit is still recorded,
#     "dirty" qualifies it rather than replacing it);
#   * the source was NOT a git checkout at all (unpacked archive, copied
#     directory) -- there is no commit, so none is written
#     (source_kind=non-git, no source_commit line at all: absent, never
#     invented);
#   * an --update over an older install -- the marker is REPLACED, so it
#     always describes the current state and never accumulates history.
PROVENANCE_FILE=".ccpr-install-provenance"

# VERIFY_SCOPE -- which artifacts --verify compares. EVERY FRAMEWORK
# directory, i.e. everything install.sh writes into $DEST except the
# artifacts that are SUPPOSED to diverge because they mature on your
# machine (instincts*, CLAUDE.md, settings.json). --verify reports this
# scope in its own output: a comparison whose extent is not stated is not a
# result.
#
# It used to be the four directories copied VERBATIM -- agents, commands,
# hooks, templates -- with docs/ and scripts/ excluded wholesale because
# neither is copied verbatim. Measured 09.09.2026 against a fresh install:
# that scope reached 162 of 409 installed files, and the 247 it did not
# reach were the shipped SCRIPTS (222) and DOCS (23). A tampered
# artifact-gate.sh, check-all.sh, manual-lint.sh, memory-sync.sh or
# CONSTITUTION.md reported VERIFIED. Probed rather than reasoned: one
# appended line in scripts/artifact-gate.sh and one in docs/CONSTITUTION.md
# each exited 0/VERIFIED, against exit 1/DIVERGENT for the same edit under
# agents/. A check whose reach stops short of its subject's reach is not a
# check of that subject (CCP-1166).
#
# The two reasons for the old exclusion are real and did not go away, so
# each became a NAMED carve-out INSIDE the scope rather than a directory
# left outside it. Both are derived from the register install.sh already
# uses on the copy side, never a second list typed in here:
#   * PROTECTED sub-paths     -> path_is_user_owned()        (BOTH sides)
#   * docs/ allowlist filter  -> path_is_docs_working_state() (EXPECTED only)
# Locally generated files (__pycache__, .DS_Store) already had their answer
# in path_is_source_ignored() and needed no change; measured, they are 97
# of the 98 extras a fresh install grows under scripts/ on macOS.
#
# Both carve-outs are printed in their own report block. An exclusion
# nobody can see is the next drifting skip list -- the same argument the
# IGNORED block and install_docs()'s skip paragraph already make.
VERIFY_SCOPE=( agents commands docs hooks scripts templates )

# path_is_user_owned <relpath> -- does this path lie inside a PROTECTED
# sub-path, i.e. one install.sh declares yours rather than the framework's?
#
# The one carve-out applied in BOTH directions, and the reason is ownership
# rather than noise. A wholesale directory replace stashes these sub-paths
# and restores them afterwards, YOUR copy winning over anything shipped
# (see PROTECTED above). Three consequences, each of which is a false
# finding if this predicate is applied to only one side:
#   * scripts/local-llm ships five starter wrappers, so the paths ARE in
#     the commit and ARE in the installation. Subtracting them from the
#     EXPECTED set alone would move every one of them into UNEXPECTED;
#     subtracting neither would report your own model choice as CHANGED.
#   * a wrapper you added there was in no commit and never will be.
#   * scripts/lib/scan_rules and scripts/lib/test_parsers are tracked by
#     nothing in this checkout at all -- on a machine where the harness has
#     written them, every file under them is UNEXPECTED by construction.
#
# This is exactly where the rule parts company with path_is_source_ignored(),
# which is one-directional on purpose: an ignored path is excused only for
# paths the commit does not carry, so MISSING and CHANGED are out of its
# reach. Here the commit CAN carry the path and the carve-out still holds,
# because the installer's own contract says the user's copy is the correct
# content. That is a stronger exemption and it is why it is spelled out in
# the report by prefix rather than merely counted.
path_is_user_owned() {
  local rel="$1" prefix
  for prefix in "${PROTECTED[@]}"; do
    if [[ "$rel" == "$prefix" || "$rel" == "$prefix/"* ]]; then
      return 0
    fi
  done
  return 1
}

# path_is_docs_working_state <relpath> -- would install_docs() refuse to
# ship this docs/ path?
#
# EXPECTED side only, and that asymmetry is the whole point. docs/ is the
# one FRAMEWORK directory install.sh does not copy wholesale: install_docs()
# ships exactly the top-level entries listed in DOCS_ALLOWLIST_FILE and
# reports the rest as working state. A comparison that expected the commit's
# WHOLE docs/ tree in the target would report every one of those as MISSING
# on a correct installation -- 89 files for docs/workitems/ alone in this
# repository's own history (`git log --all --name-only -- docs` still shows
# docs/memory and docs/workitems as tracked back then, and a marker can
# point at such a commit).
#
# NOT applied to the walk of the installation. A path install.sh never
# ships that is sitting in $DEST anyway did not come from the recorded
# commit, so it must stay REPORTABLE rather than be subtracted a second
# time -- subtracting it from both sides would make the installer's own
# docs/ boundary unenforceable from the one check that could enforce it.
#
# "Reportable" is the honest word, and it is NOT the same as "UNEXPECTED".
# An earlier draft of this comment said UNEXPECTED and was wrong; measured
# 09.09.2026, on this repository, with docs/HANDOVER.md planted in $DEST:
# it lands in **IGNORED**, exit 0. The walk still consults
# path_is_source_ignored() afterwards, and this repository's own .gitignore
# names exactly these paths (docs/HANDOVER.md, docs/workitems/,
# docs/memory/, docs/decisions/, docs/.*). Which block it lands in is
# decided by the INDEX, because check-ignore is index-aware:
#
#   tracked in $SRC   -> not ignored -> UNEXPECTED, a finding, exit 1
#   untracked in $SRC -> ignored     -> IGNORED, excused, exit 0
#
# The second row is the normal state of this repository and therefore the
# production shape; the first is what a commit predating the .gitignore
# rule looks like. Both are pinned by tests. What matters for this check is
# the invariant that holds across both: such a path is NAMED in a block,
# never silently dropped, and never reported as MISSING. Whether the
# excusing row should instead be a finding is a POLICY question about the
# two rules overlapping -- both say "not part of the delivered tree" -- and
# it is deliberately not decided here.
#
# The rule is READ FROM the file install_docs() reads, through the same
# evaluator (docs_entry_is_allowlisted above); scripts/artifact-gate.sh
# enforces that same file from the other side. Two hand-kept copies of one
# boundary is the defect shape WI-0059 already produced once.
#
# Same working-tree door as path_is_source_ignored(), declared rather than
# discovered: the allowlist is read from $SRC AS IT STANDS, not from a
# checkout of $p_commit, so an uncommitted edit to it already changes the
# classification. Same reasoning too -- "what does the installer ship" is a
# property of the TOOLING, and the program answering the question is
# $SRC/install.sh.
path_is_docs_working_state() {
  local rel="$1" name
  case "$rel" in
    docs/*) ;;
    *) return 1 ;;
  esac
  name="${rel#docs/}"
  name="${name%%/*}"
  if docs_entry_is_allowlisted "$name"; then
    return 1
  fi
  return 0
}

# path_is_source_ignored <relpath> -- would the SOURCE repository refuse to
# track this path?
#
# An installation grows files nobody installed. Running a hook once leaves
# `hooks/__pycache__/*.pyc`; opening the tree in a macOS file browser leaves
# `.DS_Store`. Both sit inside VERIFY_SCOPE and neither is in any commit, so
# the UNEXPECTED half reported both -- DIVERGENT on a correct installation,
# on every macOS machine, from the first run onward. That is the one defect
# scripts/check-all.sh names in its own header as fatal to a check: red when
# nothing is wrong is red nobody reads, and the run that finds something
# real goes unread with it.
#
# The exclusion is DERIVED rather than typed, which is the rule d85c2bd
# settled: the source repository already states which paths are not part of
# its delivered tree, in .gitignore, and `git check-ignore` is the reference
# implementation of that statement. A path this repository will not track
# cannot be inside any commit, so its presence in the installation is not
# drift FROM one. A typed pattern list here would be a second register of
# the same fact, free to drift from the first (G-091).
#
# THE ONE PLACE --verify IS NOT PINNED TO THE RECORDED COMMIT. Everything
# else here resolves against $p_commit (`ls-tree`, `hash-object`). The ignore
# rules cannot: `check-ignore` is a working-tree operation and takes no
# commit, so it reads $SRC AS IT STANDS ON DISK -- including a .gitignore
# edit that is uncommitted, or not even `git add`ed, and including
# .git/info/exclude. Measured, not assumed: an untracked one-line .gitignore
# in $SRC moves an already-planted foreign file from UNEXPECTED to IGNORED
# on the next run, with nothing about $DEST or the marker changed.
#
# Kept deliberately, because the question this branch answers is not the
# same question as the comparison's. "What should be installed" is a
# property OF the recorded commit. "What gets generated locally" is a
# property of the TOOLING, and today's checkout knows about a generator a
# six-month-old commit never met. The cost is the door above; the price of
# closing it is evaluating the rules against a clean checkout of $p_commit
# (a temporary worktree -- `core.excludesFile` alone cannot do it, the
# worktree's own .gitignore still applies on top), which is a bigger change
# than this one. Whoever revisits it should note that $SRC is inside the
# trust boundary regardless: the program answering the question IS
# $SRC/install.sh.
#
# Three properties this shape has and a typed list would not:
#   * index-aware: `check-ignore` reports a TRACKED path as NOT ignored even
#     when a pattern matches it. That buys one narrow case -- the checkout
#     has moved on and now tracks a file the RECORDED commit never had, and
#     a copy of it turns up in the installation: still drift, still named.
#     It is NOT what keeps MISSING and CHANGED out of reach; that is
#     structural, since this branch is consulted only for paths the recorded
#     commit does not carry and a shipped file is carried by definition.
#     Measured, not assumed: switching this to `--no-index` leaves every
#     test in scripts/tests/test_install_provenance.py green except the one
#     written for exactly it.
#   * `core.excludesFile=/dev/null` cuts out the adopter's PERSONAL global
#     ignore file. That file says what its owner does not want to see in ANY
#     repository; it says nothing about what CCPR ships, and one broad
#     pattern in it (`*.md`) would otherwise excuse every foreign agent file
#     in the installation. This is the one exclude source that is cut; the
#     checkout's own files stay in scope per the paragraph above.
#   * fail-closed: any status other than 0 (including git erroring out, 128)
#     leaves the path in UNEXPECTED, which is the behaviour that existed
#     before this exemption. A broken exclusion is loud, never silent.
#
# BREADTH: it inherits EVERY rule in that .gitignore, not only the two the
# defect named. Measured against the shipped file, `*.egg-info/`, `.vscode/`,
# `.idea/`, `*.log`, `*.swp`, `*~`, `Thumbs.db` and `desktop.ini` all ride
# along, so a foreign file wearing one of those shapes is excused too. What
# does NOT ride along is every shape the framework actually loads --
# `agents/*.md`, `commands/*.md`, `hooks/*.py`, `hooks/*.sh`,
# `templates/*.md` are all reported, and a test pins exactly that.
#
# What it excuses is reported by name in its own IGNORED block rather than
# dropped -- an exemption nobody can see is the next drifting skip list.
#
# CCP-1170: reports which RULE excused the path, not only whether one did,
# via a global (`PATH_IGNORE_RULE`) rather than a return value -- this
# script has no other channel for a function result besides its exit code.
# `-v` and `-q` cannot be combined (`git check-ignore` refuses that
# combination outright, exit 128), so this reads `-v`'s own stdout and
# decides ignored-or-not from ITS exit code instead: measured to carry the
# same 0/1 semantics `-q` had, one call, nothing decided twice.
path_is_source_ignored() {
  local rc=0 out=""
  out="$(git -C "$SRC" -c core.excludesFile=/dev/null check-ignore -v -- "$1" 2>/dev/null)" \
    || rc=$?
  if [[ "$rc" -ne 0 ]]; then
    PATH_IGNORE_RULE=""
    return 1
  fi
  # check-ignore -v prints one line, `<source>:<line>:<pattern>\t<path>`;
  # the rule is everything before the first tab.
  PATH_IGNORE_RULE="${out%%$'\t'*}"
  return 0
}

SRC_PHYS=""
SRC_KIND="non-git"
SRC_COMMIT=""
SRC_STATE="unknown"

# source_provenance -- classify $SRC into (kind, commit, state) without ever
# guessing. `git rev-parse` walks UP the directory tree, so a copied
# directory sitting inside somebody else's checkout would otherwise inherit
# that repository's HEAD: the toplevel must be $SRC ITSELF.
#
# "Itself" is an identity question about DIRECTORIES, not a question about
# the strings that name them -- checked with `-ef` (bash: same device+inode)
# rather than `==` (CCP-1174). Two reasons neither side of a string compare
# can be trusted to agree here even when they name the same directory:
#   * macOS /tmp is a symlink to /private/tmp, so the logical and physical
#     spellings differ (both sides already go through `pwd -P` to fold
#     this, which is why this comment used to stop there).
#   * On a case-insensitive filesystem, `pwd -P` does NOT canonicalise
#     case -- it returns the path AS TRAVERSED. The directory the script
#     was invoked through need not be the spelling git itself stored at
#     init time (CCP-1114), so `$SRC`'s own resolved path and git's
#     reported toplevel can be the IDENTICAL directory and still differ
#     as strings (CCP-1174, observed in production 10.09.2026). Routing
#     both through `pwd -P` again does not fix this, because they already
#     went through it once and still disagree -- they were entered
#     through different doors.
# `-ef` answers "is this the same directory" directly, needs no assumption
# about the filesystem's case sensitivity, and stays correct on a
# case-SENSITIVE volume where two differently-cased directories are
# genuinely two directories -- which a case-folding string compare would
# wrongly merge, silently widening the guard this exists for. It is also
# false (not an error) when either side does not exist, so a `$toplevel`
# that failed to resolve above still falls through to `non-git` here
# rather than tripping `set -e`.
source_provenance() {
  local toplevel=""
  SRC_PHYS="$(cd "$SRC" && pwd -P)"
  SRC_KIND="non-git"
  SRC_COMMIT=""
  SRC_STATE="unknown"
  command -v git >/dev/null 2>&1 || return 0
  toplevel="$(git -C "$SRC" rev-parse --show-toplevel 2>/dev/null)" || return 0
  [[ -n "$toplevel" ]] || return 0
  toplevel="$(cd "$toplevel" 2>/dev/null && pwd -P)" || return 0
  [[ "$toplevel" -ef "$SRC_PHYS" ]] || return 0
  SRC_COMMIT="$(git -C "$SRC" rev-parse HEAD 2>/dev/null)" || SRC_COMMIT=""
  [[ -n "$SRC_COMMIT" ]] || return 0
  SRC_KIND="git"
  if [[ -n "$(git -C "$SRC" status --porcelain 2>/dev/null)" ]]; then
    SRC_STATE="dirty"
  else
    SRC_STATE="clean"
  fi
}

# write_provenance <mode> -- overwrite (never append) the marker.
write_provenance() {
  local mode="$1"
  source_provenance
  {
    echo "# CCPR install provenance -- written by install.sh. Do not edit by hand."
    echo "# Read by: install.sh --verify"
    echo "schema=1"
    echo "installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "install_mode=$mode"
    echo "source_path=$SRC_PHYS"
    echo "source_kind=$SRC_KIND"
    if [[ -n "$SRC_COMMIT" ]]; then
      echo "source_commit=$SRC_COMMIT"
    fi
    echo "source_state=$SRC_STATE"
  } > "$DEST/$PROVENANCE_FILE"
  echo "  wrote $PROVENANCE_FILE (source: $SRC_KIND${SRC_COMMIT:+ $SRC_COMMIT}, $SRC_STATE)"
}

# verify_cannot_run <reason> -- the one wording for "nothing was compared".
# Kept distinct from both verdicts on purpose: a check that could not look is
# not a check that looked and found nothing, and an exit code alone cannot
# tell the two apart. Same carve-out scripts/memory-lint.sh,
# scripts/conformance-run.sh and scripts/shellcheck-run.sh each state in
# their own reports, and which scripts/check-all.sh reads back out of them.
verify_cannot_run() {
  echo
  echo "Result: COULD NOT RUN -- $1"
  echo "  Nothing was compared. This is NOT the same as 'no divergence'."
  echo "  the install-provenance check DID NOT RUN"
}

# verify_installation -- answers the PRESENT question and reports the ORIGIN
# one alongside it, plus a THIRD question: is the recorded commit still
# where the source checkout stands (see "Origin freshness" below)?
# Exit: 0 verified or behind, no divergence · 1 divergence found (file-level,
# or the recorded commit is not an ancestor of this checkout's HEAD) ·
# 3 could-not-run (nothing compared).
verify_installation() {
  local marker="$DEST/$PROVENANCE_FILE"
  local p_schema="" p_installed_at="" p_mode="" p_path="" p_kind="" p_commit="" p_state=""
  local line key val
  local expected_raw meta path sha ahash
  local expected_count=0 compared=0
  local missing="" differing="" extra="" ignored=""
  local missing_n=0 differing_n=0 extra_n=0 ignored_n=0 ignored_rules_n=0
  local ignored_groups="" gline gcount grule
  local exp_paths d f rel total toplevel scan_out prefix dname
  local enum_incomplete=0
  local allowlist_ok=0 docs_unclassifiable=0
  local docs_skipped="" docs_skipped_n=0 user_owned_n=0
  local src_head="" origin_state="unknown" behind_n=""

  echo "CCPR install verification"
  echo "  target:        $DEST"
  echo "  this checkout: $SRC"
  echo "  scope:         ${VERIFY_SCOPE[*]}"
  echo "                 (every directory install.sh copies. Two carve-outs sit"
  echo "                  INSIDE it, because two of those directories are not"
  echo "                  copied verbatim: the user-owned PROTECTED sub-paths are"
  echo "                  compared in NEITHER direction, and docs/ is filtered"
  echo "                  through scripts/lib/docs-framework-allowlist.txt, so a"
  echo "                  docs/ entry the installer does not ship is not expected"
  echo "                  here. Each carve-out names its own paths in its own"
  echo "                  block below, so neither is invisible from the report."
  echo "                  Still out entirely: instincts*, CLAUDE.md and"
  echo "                  settings.json -- those mature on your machine.)"

  if [[ ! -d "$DEST" ]]; then
    verify_cannot_run "the target directory does not exist: $DEST"
    return 3
  fi
  if [[ ! -r "$marker" ]]; then
    verify_cannot_run "no provenance marker at $marker -- this installation predates provenance recording, so its origin is NOT DETERMINABLE"
    return 3
  fi

  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    [[ "$key" != "$line" ]] || continue   # no '=' on this line: not a field
    case "$key" in
      schema)        p_schema="$val" ;;
      installed_at)  p_installed_at="$val" ;;
      install_mode)  p_mode="$val" ;;
      source_path)   p_path="$val" ;;
      source_kind)   p_kind="$val" ;;
      source_commit) p_commit="$val" ;;
      source_state)  p_state="$val" ;;
    esac
  done < "$marker"

  echo
  echo "Origin (recorded at install time, not measured now):"
  echo "  installed at:  ${p_installed_at:-(not recorded)}"
  echo "  install mode:  ${p_mode:-(not recorded)}"
  echo "  source path:   ${p_path:-(not recorded)}"
  echo "  source kind:   ${p_kind:-(not recorded)}"
  echo "  source commit: ${p_commit:-(none recorded)}"
  echo "  source state:  ${p_state:-(not recorded)}"

  if [[ -z "$p_schema" || -z "$p_kind" ]]; then
    verify_cannot_run "$marker does not read as a provenance marker (no schema/source_kind field)"
    return 3
  fi
  if [[ "$p_kind" != "git" || -z "$p_commit" ]]; then
    verify_cannot_run "the source was not a git checkout (source_kind=$p_kind), so no state was recorded that the installation could be compared against"
    return 3
  fi
  if [[ "$p_state" == "dirty" ]]; then
    verify_cannot_run "the source tree was dirty at install time -- what was installed is $p_commit PLUS uncommitted changes, so a difference found now could not be attributed to either"
    return 3
  fi
  if [[ "$p_state" != "clean" ]]; then
    verify_cannot_run "the recorded source state is '${p_state:-unknown}', not 'clean'"
    return 3
  fi

  command -v git >/dev/null 2>&1 || {
    verify_cannot_run "git is not available on PATH, so the recorded commit cannot be resolved"
    return 3
  }
  toplevel="$(git -C "$SRC" rev-parse --show-toplevel 2>/dev/null)" || toplevel=""
  if [[ -z "$toplevel" ]]; then
    verify_cannot_run "this checkout ($SRC) is not a git repository, so the recorded commit cannot be resolved"
    return 3
  fi
  if ! git -C "$SRC" rev-parse --verify --quiet "${p_commit}^{commit}" >/dev/null 2>&1; then
    verify_cannot_run "commit $p_commit is not present in this checkout ($SRC) -- fetch it, or run --verify from the checkout it was installed from"
    return 3
  fi

  # Origin freshness -- a QUESTION SEPARATE FROM the installed-tree
  # comparison below. That comparison answers "does $DEST still match
  # $p_commit"; this answers "is $p_commit still where $SRC stands", i.e.
  # has the checkout this installation came from moved on since. An
  # installation can be byte-identical to what it recorded (VERIFIED) while
  # the checkout it was installed from is 100 commits ahead -- nothing above
  # this point would ever say so.
  #
  # `merge-base --is-ancestor A B` is REFLEXIVE (a commit is its own
  # ancestor, exit 0), so "the recorded commit IS current HEAD" is checked
  # separately rather than folded into the ancestor test -- otherwise every
  # up-to-date installation would misreport as BEHIND-by-zero. Exit-code
  # semantics measured empirically (not assumed): 0 = is-an-ancestor
  # (including "is the same commit"), 1 = is-not-an-ancestor, 128 = not a
  # valid object -- the last case cannot occur here, $p_commit was already
  # confirmed to resolve above.
  src_head="$(git -C "$SRC" rev-parse HEAD 2>/dev/null)" || src_head=""
  if [[ -n "$src_head" ]]; then
    if [[ "$p_commit" == "$src_head" ]]; then
      origin_state="current"
    elif git -C "$SRC" merge-base --is-ancestor "$p_commit" "$src_head" 2>/dev/null; then
      origin_state="behind"
      behind_n="$(git -C "$SRC" rev-list --count "${p_commit}..${src_head}" 2>/dev/null)" || behind_n=""
    else
      # $p_commit resolves (checked above) but is NOT an ancestor of
      # $src_head: rewritten history (amend/rebase), a different branch, or
      # a source that has been swapped out from under the same path. Worse
      # than BEHIND -- "ahead on the same line of history" is not what this
      # is -- so it gets its own state, never folded into "behind".
      origin_state="diverged"
    fi
  fi

  # Decided once, before the loop, so every docs/ path in the commit is
  # classified by the same answer -- and so an unreadable allowlist becomes
  # a refusal rather than a silently narrower scope (see below).
  # `if`, not `[[ ... ]] && ...`: the latter's own status is 1 when the file
  # is unreadable, and this function only survives that because errexit is
  # suspended for it (it runs as an `||` operand). Not a contract to lean
  # on -- the review of d85c2bd already found one bare call in here that
  # depended on it.
  if [[ -r "$DOCS_ALLOWLIST_FILE" ]]; then
    allowlist_ok=1
  fi

  expected_raw="$(git -C "$SRC" ls-tree -r "$p_commit" -- "${VERIFY_SCOPE[@]}")"
  exp_paths=$'\n'
  while IFS=$'\t' read -r meta path; do
    [[ -n "$path" ]] || continue
    case "$meta" in
      *" blob "*) ;;
      *) continue ;;
    esac
    sha="${meta##* }"
    # Carve-out 1: yours in both directions, so it is not an expectation.
    if path_is_user_owned "$path"; then
      continue
    fi
    # Carve-out 2: the commit carries docs/ paths install.sh deliberately
    # never installs. Expecting them in $DEST would report the installer
    # doing its job as drift.
    if [[ "$path" == docs/* ]]; then
      if [[ "$allowlist_ok" -eq 0 ]]; then
        docs_unclassifiable=$((docs_unclassifiable + 1))
        continue
      fi
      if path_is_docs_working_state "$path"; then
        dname="${path#docs/}"
        dname="${dname%%/*}"
        docs_skipped="${docs_skipped}docs/${dname}"$'\n'
        docs_skipped_n=$((docs_skipped_n + 1))
        continue
      fi
    fi
    expected_count=$((expected_count + 1))
    exp_paths="${exp_paths}${path}"$'\n'
    if [[ ! -f "$DEST/$path" ]]; then
      missing="${missing}${path}"$'\n'
      missing_n=$((missing_n + 1))
      continue
    fi
    # </dev/null so hash-object cannot swallow this loop's own here-string.
    # An unreadable file yields an empty hash, which then cannot match and
    # is reported as CHANGED. That is the deliberate direction: a file this
    # check could not read is not a file it verified, and the fail-open
    # alternative (treat it as matching) is the one outcome that must never
    # happen here.
    ahash="$(git hash-object -- "$DEST/$path" </dev/null 2>/dev/null)" || ahash=""
    compared=$((compared + 1))
    if [[ "$ahash" != "$sha" ]]; then
      differing="${differing}${path}"$'\n'
      differing_n=$((differing_n + 1))
    fi
  done <<< "$expected_raw"

  # An unreadable allowlist means the docs/ half of the scope cannot be
  # classified at all: every docs/ path in the commit is neither provably
  # framework nor provably working state. Reporting the other directories
  # and staying quiet about this one would be a run whose stated scope is
  # not the scope it covered (KA-G-017), so it refuses instead. Note this
  # is NOT reachable by simply treating docs/ as working state -- that
  # would exit 0 with a silently smaller comparison, which is the shape
  # this whole check exists against.
  if [[ "$docs_unclassifiable" -gt 0 ]]; then
    verify_cannot_run "commit $p_commit carries $docs_unclassifiable path(s) under docs/, and scripts/lib/docs-framework-allowlist.txt -- the file that says which of them install.sh actually ships -- is not readable at $DOCS_ALLOWLIST_FILE, so the docs/ half of the scope cannot be classified"
    return 3
  fi
  if [[ "$expected_count" -eq 0 ]]; then
    verify_cannot_run "commit $p_commit carries no file under the compared scope (${VERIFY_SCOPE[*]}) -- 0 files compared is not a pass"
    return 3
  fi

  # The UNEXPECTED half is the one direction the git tree cannot supply: it
  # has to walk the installation itself. `find` failing partway (an
  # unreadable subtree) would otherwise just yield FEWER lines and be
  # indistinguishable from "there was nothing extra there" -- silent scope
  # loss, in a check whose whole purpose is that a scope it could not cover
  # is never reported as a clean one. Its status is therefore captured and
  # folded into the verdict below. `$(...)` rather than a process
  # substitution precisely because a process substitution's exit status is
  # not observable; command substitution's is.
  for d in "${VERIFY_SCOPE[@]}"; do
    [[ -d "$DEST/$d" ]] || continue
    scan_out="$(find "$DEST/$d" -type f 2>/dev/null)" || enum_incomplete=1
    while IFS= read -r f; do
      [[ -n "$f" ]] || continue
      rel="${f#"$DEST"/}"
      # Carve-out 1, the other direction. Checked BEFORE the expected-set
      # lookup because these paths were removed from that set above, so
      # every one of them would otherwise fall through to UNEXPECTED --
      # including the five starter wrappers a fresh install itself places.
      if path_is_user_owned "$rel"; then
        user_owned_n=$((user_owned_n + 1))
        continue
      fi
      case "$exp_paths" in
        *$'\n'"$rel"$'\n'*) ;;
        *)
          if path_is_source_ignored "$rel"; then
            # "<rule>\t<rel>\n" -- one line per excused path, keyed by the
            # rule that excused it. bash 3.2 (macOS /bin/bash) has no
            # associative arrays, so grouping happens at print time via a
            # cut/sort/uniq pipeline over these lines, not here.
            ignored="${ignored}${PATH_IGNORE_RULE}"$'\t'"${rel}"$'\n'
            ignored_n=$((ignored_n + 1))
          else
            extra="${extra}${rel}"$'\n'; extra_n=$((extra_n + 1))
          fi
          ;;
      esac
    done <<< "$scan_out"
  done

  echo
  echo "Current state (installed tree vs. commit $p_commit):"
  echo "  compared $compared file(s), of $expected_count in scope at that commit"

  if [[ "$missing_n" -gt 0 ]]; then
    echo "  MISSING -- in the recorded commit, absent from the installation:"
    printf '%s' "$missing" | LC_ALL=C sort | sed 's/^/    - /'
  fi
  if [[ "$differing_n" -gt 0 ]]; then
    echo "  CHANGED -- present in both, contents differ:"
    printf '%s' "$differing" | LC_ALL=C sort | sed 's/^/    - /'
  fi
  if [[ "$extra_n" -gt 0 ]]; then
    echo "  UNEXPECTED -- in the installation, not in the recorded commit:"
    printf '%s' "$extra" | LC_ALL=C sort | sed 's/^/    - /'
  fi
  # Printed UNCONDITIONALLY (CCP-1170), unlike the NOT FRAMEWORK block below
  # -- see the comment ahead of USER-OWNED for why. The rule set is derived
  # per run and CAN be empty on a correct installation, but "nothing was
  # excused this run" is exactly the number a reader needs without having
  # to cause an excused file first.
  echo "  IGNORED -- in the installation, ignored by the SOURCE CHECKOUT (excused, not skipped):"
  # Grouped by the .gitignore RULE `git check-ignore -v` named for each
  # path (CCP-1170), not listed one path per line -- a correct installation
  # can grow dozens of __pycache__ entries under one rule, and a per-path
  # listing buried the report under them. bash 3.2 has no associative
  # arrays, so the grouping runs as a cut/sort/uniq pipeline over the
  # "<rule>\t<rel>" lines collected during the walk, sorted by count
  # descending (most-excused rule first), rule string breaking ties.
  ignored_groups="$(printf '%s' "$ignored" | cut -f1 | LC_ALL=C sort \
    | uniq -c | LC_ALL=C sort -k1,1nr -k2)"
  while IFS= read -r gline; do
    [[ -n "$gline" ]] || continue
    ignored_rules_n=$((ignored_rules_n + 1))
    read -r gcount grule <<< "$gline"
    printf '%8d file(s)  %s\n' "$gcount" "$grule"
  done <<< "$ignored_groups"
  echo "    ($ignored_n file(s) excused by $ignored_rules_n rule(s), named by"
  echo "     \`git check-ignore -v\` against $SRC as it stands now -- the same call"
  echo "     that made the decision, and the one place here NOT resolved from"
  echo "     commit $p_commit: check-ignore is a working-tree operation, so a path"
  echo "     this repository will not track is in no commit, and having it here is"
  echo "     not drift from one -- it is locally generated. Not counted as a finding.)"

  if [[ "$docs_skipped_n" -gt 0 ]]; then
    echo "  NOT FRAMEWORK -- under docs/ in the recorded commit, never installed:"
    printf '%s' "$docs_skipped" | LC_ALL=C sort -u | sed 's/^/    - /'
    echo "    ($docs_skipped_n file(s) in the recorded commit sit under those"
    echo "     entries. install_docs() ships only the top-level docs/ entries"
    echo "     listed in scripts/lib/docs-framework-allowlist.txt -- the same"
    echo "     file scripts/artifact-gate.sh enforces from the other side -- so"
    echo "     their absence here is the installer working, not drift. That"
    echo "     allowlist is read from this checkout as it stands, not from the"
    echo "     recorded commit: same door the IGNORED rule declares above.)"
  fi
  # Printed UNCONDITIONALLY, unlike the NOT FRAMEWORK block above, which
  # stays gated on having something to say. IGNORED used to be gated the
  # same way and moved to this side of the line (CCP-1170) -- its own
  # comment above states why. NOT FRAMEWORK is left where it was: its
  # empty case genuinely means "nothing under docs/ was skipped this
  # run", worth nothing to print, and it cannot hide a MISSING (an
  # allowlisted docs/ path was never in the expected set to begin with).
  # USER-OWNED is different from both: it is a FIXED list that is in force
  # on every run, applies in BOTH directions, and can hide a MISSING --
  # the only exclusion here that can. A reader must be able to see it
  # without first having to trigger it.
  echo "  USER-OWNED -- inside the scope but yours: compared in NEITHER direction:"
  for prefix in "${PROTECTED[@]}"; do
    echo "    - $prefix"
  done
  echo "    (install.sh's PROTECTED list. A wholesale directory replace stashes and"
  echo "     restores these, so your copy is the correct content by design: a"
  echo "     difference here is not drift, and a MISSING here would be a false alarm."
  echo "     $user_owned_n file(s) present in the installation under them, none compared.)"

  echo
  echo "Origin freshness ($p_commit vs. this checkout's current HEAD):"
  case "$origin_state" in
    current)
      echo "  current -- this checkout's HEAD is still $p_commit."
      ;;
    behind)
      echo "  BEHIND -- this checkout has moved on: HEAD is now $src_head,"
      echo "            ${behind_n:-an unknown number of} commit(s) ahead of $p_commit."
      ;;
    diverged)
      echo "  DIVERGED-ORIGIN -- $p_commit is NOT an ancestor of this checkout's"
      echo "                      current HEAD ($src_head) -- rewritten history, a"
      echo "                      different branch, or a moved source."
      ;;
    *)
      echo "  (not determined -- could not resolve this checkout's current HEAD)"
      ;;
  esac

  total=$((missing_n + differing_n + extra_n))
  echo
  # An incomplete walk of the installation cannot produce a clean verdict:
  # the UNEXPECTED half of the comparison did not cover its declared scope.
  # It does NOT suppress findings that were genuinely made -- a divergence
  # is a divergence whether or not the rest of the walk finished -- so the
  # two verdicts are ordered: findings first, then the coverage refusal.
  if [[ "$total" -eq 0 && "$enum_incomplete" -eq 1 ]]; then
    verify_cannot_run "the installation under $DEST could not be walked completely (an unreadable path under ${VERIFY_SCOPE[*]}), so 'nothing unexpected' is not a result this run can report"
    return 3
  fi
  if [[ "$total" -eq 0 ]]; then
    if [[ "$origin_state" == "diverged" ]]; then
      echo "Result: DIVERGED-ORIGIN -- installed tree matches commit $p_commit exactly,"
      echo "  but that commit is not an ancestor of this checkout's HEAD ($src_head)."
      echo "  So \"unchanged since install\" is a statement about a state this checkout no"
      echo "  longer carries on its current line of history: the tree is intact, the"
      echo "  provenance is not checkable from here. This is a missing reference point,"
      echo "  not a damaged installation."
      echo
      echo "  What to do, in this order:"
      echo "    1. Most often you are simply verifying from the wrong checkout. Run"
      echo "       --verify from the one this was installed from, and this state goes away."
      echo "    2. Otherwise the source history was rewritten (amend/rebase/force-push) or"
      echo "       the source directory was replaced. Nothing is wrong with the installed"
      echo "       files; only their origin is unreachable. \`install.sh --update\` reinstalls"
      echo "       from the current HEAD and restores a provenance that can be verified."
      return 1
    fi
    if [[ "$origin_state" == "behind" ]]; then
      echo "Result: BEHIND -- installed tree matches commit $p_commit exactly, but"
      echo "  this checkout is ${behind_n:-some} commit(s) ahead of it (HEAD $src_head)."
      # POLICY DECISION TAKEN 01.09.2026 (WI-0134): BEHIND exits 0, the same
      # as VERIFIED, so scripts/check-all.sh (which reads this exit code)
      # stays green on a stale-but-intact installation.
      #
      # The two freshness states answer DIFFERENT questions, and that is why
      # their exit codes are deliberately asymmetric. BEHIND says "intact,
      # origin known, the way forward is --update" -- the normal condition
      # for anyone working from a second checkout, whose marker trails from
      # the first foreign commit onward. Failing there would leave every
      # working machine permanently red, and a check that is red when
      # nothing is wrong gets ignored within a fortnight -- the one defect
      # scripts/check-all.sh names in its own header as fatal to a check.
      # DIVERGED-ORIGIN, handled in the branch just above, says "origin not
      # resolvable": a check without a reference point, which is the heavier
      # statement, so it rides on exit 1.
      return 0
    fi
    if [[ "$origin_state" != "current" ]]; then
      # This checkout's HEAD could not be resolved at all (e.g. an unborn
      # branch after `checkout --orphan`) -- origin_state never left its
      # initial "unknown". An undetermined origin freshness question is NOT
      # the same claim as "checked and current": still exit 0 (this is not
      # a divergence, MISSING/CHANGED/UNEXPECTED are still all empty), but
      # the wording must not silently collapse into plain VERIFIED, or a
      # real "could not determine" answers the same as "determined and
      # clean" -- exactly the fail-open shape this function refuses
      # everywhere else (see verify_cannot_run's callers above).
      echo "Result: VERIFIED -- no divergence from commit $p_commit, but this"
      echo "  checkout's current HEAD could not be resolved, so origin"
      echo "  freshness (BEHIND/DIVERGED-ORIGIN) could not be determined."
      return 0
    fi
    echo "Result: VERIFIED -- no divergence from commit $p_commit."
    return 0
  fi
  if [[ "$enum_incomplete" -eq 1 ]]; then
    echo "  NOTE -- the installation could not be walked completely; there may be"
    echo "         further unexpected files this run did not see."
  fi
  echo "Result: DIVERGENT -- $total finding(s) against commit $p_commit."
  # BEHIND/DIVERGED-ORIGIN never MASK a real DIVERGENT finding: DIVERGENT
  # keeps the Result: line and the failing exit code, the origin state rides
  # along as a note. Composition, not replacement -- the two answer
  # different questions (installed-tree-vs-marker, marker-vs-checkout-HEAD)
  # and both can be true at once.
  if [[ "$origin_state" == "behind" ]]; then
    echo "  ALSO BEHIND -- this checkout is ${behind_n:-some} commit(s) ahead of"
    echo "                 $p_commit (HEAD $src_head)."
  elif [[ "$origin_state" == "diverged" ]]; then
    echo "  ALSO DIVERGED-ORIGIN -- $p_commit is not an ancestor of this checkout's"
    echo "                          HEAD ($src_head)."
  fi
  echo "  (Shipped files are replaced wholesale on the next install; re-apply"
  echo "   any deliberate local edits from a backup afterwards.)"
  return 1
}


# Does $DEST hold anything at all? Dotfiles count -- `ls` would call such a
# directory empty, but an installation whose visible files were removed by
# hand is still not an empty directory. Written as a glob loop rather than
# `ls -A`/`find` so it stays inside the shell's own semantics under `set -u`
# on bash 3.2 (macOS): with nullglob unset an unmatched pattern comes back as
# its own literal, which the -e test then rejects.
#
# PRECONDITION: $DEST is readable and searchable. Both globs need those bits;
# without them each pattern comes back as its own unmatched literal and this
# function would report "empty" for a directory that may hold a full
# installation. The caller establishes that first (see the guard below) so
# the unreadable case gets a reason of its own rather than a wrong answer.
target_is_occupied() {
  [[ -e "$DEST" || -L "$DEST" ]] || return 1
  [[ -d "$DEST" ]] || return 0
  local entry
  for entry in "$DEST"/* "$DEST"/.*; do
    case "$entry" in
      "$DEST"/. | "$DEST"/..) continue ;;
    esac
    if [[ -e "$entry" || -L "$entry" ]]; then
      return 0
    fi
  done
  return 1
}


# fresh_install_refusal_reason -- the DECISION half of the CCP-1173 guard,
# separated from acting on it so the preview can ask without triggering it.
# Echoes the reason a fresh install must be refused, or nothing at all when
# there is none; never exits, never writes. Same decide/act split WI-0064
# introduced for install_docs(), and for the same reason: the two callers
# below must agree by construction rather than by both being maintained.
#
# Returns 0 unconditionally -- an empty answer IS the answer "no reason", and
# a non-zero return here would abort the caller's command substitution under
# `set -e`.
fresh_install_refusal_reason() {
  [[ "$UPDATE" -eq 0 && "$FORCE_FRESH" -eq 0 ]] || return 0
  if [[ -f "$DEST/$PROVENANCE_FILE" ]]; then
    printf '%s' "it carries a provenance marker ($PROVENANCE_FILE) from an earlier install"
  elif [[ -d "$DEST" && ( ! -r "$DEST" || ! -x "$DEST" ) ]]; then
    # A check that COULD NOT LOOK must not answer "nothing there" -- the same
    # distinction --verify draws between could-not-run and no-divergence.
    printf '%s' "it exists but cannot be read, so whether it holds an installation cannot be established"
  elif target_is_occupied; then
    printf '%s' "it already exists and is not empty"
  fi
  return 0
}


ASSUME_YES=0
DRY_RUN=0
UPDATE=0
WITH_INSTINCTS=0
VERIFY=0
FORCE_FRESH=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    -n|--dry-run) DRY_RUN=1 ;;
    -u|--update) UPDATE=1 ;;
    --with-instincts) WITH_INSTINCTS=1 ;;
    --verify) VERIFY=1 ;;
    --force-fresh) FORCE_FRESH=1 ;;
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

  --verify           Compare, don't install. Reads the provenance marker
                     this installer leaves in the target and reports whether
                     the installed tree still matches the state it records.
                     Two separate answers: WHERE it was installed from (the
                     marker) and WHETHER it still agrees (the comparison).
                     Also reports a THIRD answer, origin freshness: whether
                     the recorded commit is still where this checkout's HEAD
                     stands (current), a strict ancestor of it (BEHIND — the
                     checkout has moved on), or not an ancestor at all
                     (DIVERGED-ORIGIN — rewritten history, a different
                     branch, or a moved source).
                     Exit 0 verified · 1 divergence · 3 could not run
                     (no target, no marker, or a source that was not a
                     clean git checkout — none of which is "no divergence").
                     BEHIND rides on exit 0 (same as verified) and
                     DIVERGED-ORIGIN on exit 1 (same as divergence) — neither
                     has an exit code of its own. Decided 01.09.2026
                     (WI-0134): the two states answer different questions.
                     "Intact but trailing" is the normal condition on a
                     working machine and must not be red; "origin not
                     resolvable" is a check without a reference point and
                     must be.

Options:
  --dry-run          Show what would happen, change nothing.
  --yes              Skip the confirmation prompt (still backs up).
  --force-fresh      Allow a fresh install onto a target that is already in
                     use. Without it, a fresh install REFUSES a target that
                     carries this installer's provenance marker or that
                     merely exists and is not empty — an empty or missing
                     target is the only one it writes into silently. The
                     refusal is hard, not a prompt, so --yes cannot wave it
                     through: replacing an existing installation
                     non-interactively needs BOTH flags. Prefer --update,
                     which keeps your files. Exit 4 on refusal.
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

# --verify is a read-only mode: it takes precedence over every install flag
# and returns its own three-way verdict (see verify_installation()). The
# `|| verify_rc=$?` shape is required under `set -e`, which would otherwise
# abort on the 1 and 3 return paths before they can be reported.
if [[ "$VERIFY" -eq 1 ]]; then
  verify_rc=0
  verify_installation || verify_rc=$?
  exit "$verify_rc"
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

# CCP-1173: a fresh install onto a target that is already in use is a
# wholesale replace, and --yes waves it through without a word. That is how a
# throwaway probe run landed on a real ~/.claude on 09.09.2026 (18 instinct
# files deleted, instincts.md 37488 -> 9242 bytes, CLAUDE.md and settings.json
# overwritten; recovered from the backup this script had just taken).
#
# The cause was the DEFAULT, not a typo: DEST falls back to $HOME/.claude when
# CCPR_DEST is ABSENT, so a safe invocation loses its safety by being reworded
# or copied, and what is left is syntactically perfect and reports nothing
# unusual. A briefing that says "never point this at ~/.claude" is a request;
# this is the barrier.
#
# The refusal is HARD, not a prompt. A prompt is exactly what --yes exists to
# skip, and the incident ran with --yes -- so --force-fresh is the only way
# past, and the two flags are independent: replacing an existing installation
# non-interactively needs BOTH.
#
# Two triggers, not one (PO decision 09.09.2026). The marker proves an
# installation lives here, but an installation predating the marker cannot be
# seen that way -- and those are the oldest ones, whose loss costs most. So a
# target that merely exists and is not empty is refused as well. Nothing
# legitimate is caught by that: a throwaway probe target is fresh or empty by
# construction and a real installation is never empty, which makes "empty vs
# not" exactly the line.
#
# --update and --verify are deliberately out of reach: neither replaces the
# target wholesale, and --update is the path this refusal points at.
#
# Decided here, BEFORE the "already exist ... WILL be overwritten" listing
# below, and acted on in two ways. The position is not cosmetic: that listing
# describes a replace, which is false for a run that is about to refuse -- a
# refusal must not disagree with the paragraph above it any more than a
# preview may disagree with the run it previews.
refuse_reason="$(fresh_install_refusal_reason)"
if [[ -n "$refuse_reason" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    # PO decision 09.09.2026, route 2: the preview ANNOUNCES the refusal and
    # still exits 0. A preview that aborts (route 1) defeats its own purpose
    # -- one runs it precisely to learn what would happen, so it has to
    # answer; and leaving it to promise an install that would not happen
    # (route 3) contradicts the WI-0064 rule this file states twice.
    echo "[dry-run] The real run would REFUSE this target and change nothing:"
    echo "[dry-run]   $refuse_reason."
    echo "[dry-run] It would exit 4 -- no backup, no copy, nothing written."
    echo "[dry-run] Two ways forward:"
    echo "[dry-run]   --update       upgrade this installation in place; keeps CLAUDE.md,"
    echo "[dry-run]                  settings.json and the instincts matured on this machine"
    echo "[dry-run]   --force-fresh  replace it wholesale (--yes does not imply it, and it"
    echo "[dry-run]                  does not imply --yes)"
    echo "[dry-run] No changes made."
    exit 0
  fi
  echo "REFUSED: a fresh install would replace everything in" >&2
  echo "  $DEST" >&2
  echo "  -- $refuse_reason." >&2
  echo >&2
  echo "  Use --update instead. It is the intended path for a target already in" >&2
  echo "  use: it copies the framework only and keeps CLAUDE.md, settings.json and" >&2
  echo "  the instincts that matured on this machine." >&2
  echo >&2
  echo "  If replacing it wholesale is what you mean, say so with --force-fresh." >&2
  echo "  --yes does not imply it, and it does not imply --yes." >&2
  echo >&2
  echo "  (\`--dry-run\` describes this without running it.)" >&2
  exit 4
fi

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
    # WI-0064: "docs" is the one artifact the real run does NOT copy wholesale
    # -- the loop special-cases it into install_docs(). Printing the plain
    # "$SRC/docs -> $DEST/docs" line here announced exactly the wholesale copy
    # the allowlist exists to prevent, so the preview contradicted the run.
    if [[ "$item" == "docs" ]] && docs_partition; then
      echo "  docs: filtered per scripts/lib/docs-framework-allowlist.txt, not copied wholesale"
      echo "    would install ${#DOCS_PART_INSTALL[@]} framework entr$([[ ${#DOCS_PART_INSTALL[@]} -eq 1 ]] && echo y || echo ies):"
      if [[ ${#DOCS_PART_INSTALL[@]} -gt 0 ]]; then
        for name in "${DOCS_PART_INSTALL[@]}"; do
          echo "      + docs/$name -> $DEST/docs/$name"
        done
      fi
      docs_report_skips "    "
      continue
    fi
    echo "  $SRC/$item -> $DEST/$item"
  done
  # Announced for the same reason WI-0064 made the docs verdict shared: a
  # run that writes a file the preview never mentions is the preview
  # disagreeing with the run, just in the other direction.
  echo "  $DEST/$PROVENANCE_FILE (provenance marker, would be written last)"
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
  # WI-0018: "docs" is the one FRAMEWORK artifact that is not shipped
  # wholesale -- see install_docs() above.
  if [[ "$item" == "docs" ]]; then
    install_docs
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
          rm -rf "${DEST:?}/$p"
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

# Written LAST, and only on a run that actually copied something: the marker
# describes what is now on disk, so it must not exist for a --dry-run or an
# aborted confirmation, both of which exit above.
if [[ "$UPDATE" -eq 1 ]]; then
  write_provenance "update"
else
  write_provenance "fresh"
fi

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
