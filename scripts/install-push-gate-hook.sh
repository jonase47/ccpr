#!/usr/bin/env bash
# install-push-gate-hook.sh — CCP-1137 Auflage 2: installs a `pre-push` hook
# that runs push-gate.sh CLIENT-side, in the client-safe scope mode (no
# `--server` argument — see push-gate.sh's own header, "--server vs the
# client-safe default").
#
# This hook is FAST FEEDBACK, not the protection line. The server's own
# `pre-receive` hook (push-gate.sh invoked with the literal `--server`
# argument by the deployed shim — see push-gate.sh's header) is what
# actually enforces the discipline gate; nothing this side of the wire can
# be trusted to run at all. `git push --no-verify` bypasses THIS hook
# entirely — it does not, and cannot, bypass the server-side gate.
#
# Modeled on scripts/local-llm/install-git-hook.sh: same usage shape,
# same git-repo check, same timestamped-backup-before-overwrite discipline,
# same "resolve the real tool under ${HOME}/.claude/scripts/…" pattern
# `install.sh` itself establishes (a plain `install.sh` / `install.sh
# --update` run ships scripts/push-gate.sh and its siblings there
# wholesale — see install.sh's own FRAMEWORK array).
#
# Usage: install-push-gate-hook.sh <projectdir>

set -euo pipefail

PROJECT_DIR="${1:-}"
if [[ -z "${PROJECT_DIR}" ]]; then
  echo "Usage: install-push-gate-hook.sh <projectdir>" >&2
  exit 2
fi

cd "${PROJECT_DIR}"

# `VAR="$(cmd)" || VAR=""` rather than `if ! VAR="$(cmd)"; then` -- the
# latter reads as checked (and is), but a `git`/`sed`/`awk`/`python3`/`grep`
# invocation sitting inside a `$(...)` nested one level down from its own
# governing `if` is a shape scripts/tests/test_external_tool_exit_status.py's
# backward walk does not see through (documented directly at
# scripts/push-gate.sh's own git-cat-file site, CCP-1137 round 2): the walk
# stops at the substitution's own opening `(` and never reaches the `if !`
# outside it. This chained-fallback form keeps the exact same observable
# behavior -- an empty GIT_DIR on failure, caught by the `[[ -z ]]` test
# below -- while landing in the scanner's own recognised "checked-chain"
# bucket, so no exemption marker is needed for something that is genuinely
# checked.
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)" || GIT_DIR=""
if [[ -z "${GIT_DIR}" ]]; then
  echo "install-push-gate-hook: not a git repo: ${PROJECT_DIR}" >&2
  exit 2
fi

HOOK_PATH="${GIT_DIR}/hooks/pre-push"

# `[ -L ]` before any `[ -f ]` test on ${HOOK_PATH} -- a symlink onto an
# existing file satisfies BOTH, and `[ -f ]` alone would silently follow
# it. Hook managers (husky, pre-commit, lefthook) routinely leave
# `.git/hooks/pre-push` as a symlink onto a file they themselves manage;
# following it here would let `cp` read the EXTERNAL target's content into
# a backup file inside this repo (an information leak) and let `cat >`
# overwrite that same external target (an integrity loss) -- the same
# "a shape that has no legitimate reason to exist here is its own finding,
# never routed around" rule push-gate.sh's own is_unsafe_repo_path()
# already applies to a tree entry escaping its scan sandbox. Refused
# outright, before touching a backup or the hook path at all.
if [[ -L "${HOOK_PATH}" ]]; then
  echo "install-push-gate-hook: ${HOOK_PATH} is a symlink to $(readlink "${HOOK_PATH}") -- refusing to follow it (remove or replace it manually, then re-run this installer)" >&2
  exit 2
fi

if [[ -f "${HOOK_PATH}" ]]; then
  BACKUP="${HOOK_PATH}.bak.$(date +%Y%m%d_%H%M%S)"
  # Second-resolution name, no uniqueness suffix -- two installer runs
  # within the same second compute the SAME ${BACKUP} name. Appending
  # "$$" (the installer's own PID) would dodge the collision but not
  # DETECT it, and this repo's own convention (is_unsafe_repo_path above,
  # PUSH_GATE_MAX_COMMITS in push-gate.sh) is to refuse outright rather
  # than silently route around a shape that should not happen -- a
  # same-second re-run is rare enough that a loud abort (re-run a second
  # later) costs nothing, while a silent PID-based dodge would still let a
  # *third*, unrelated coincidence (a restored/copied backup file landing
  # on the exact same name) overwrite the true original without saying so.
  # Checked HERE, before the copy -- not after -- so the ORIGINAL, still
  # only at ${HOOK_PATH} at this point, is never even read into a
  # colliding backup in the first place.
  if [[ -e "${BACKUP}" ]]; then
    echo "install-push-gate-hook: backup target already exists: ${BACKUP} -- refusing to overwrite it (re-run a moment later, or remove/rename it manually first)" >&2
    exit 2
  fi
  cp "${HOOK_PATH}" "${BACKUP}"
  echo "install-push-gate-hook: existing hook backed up to ${BACKUP}"
fi

cat > "${HOOK_PATH}" <<'HOOK'
#!/usr/bin/env bash
# Installed by install-push-gate-hook.sh (CCP-1137). FAST FEEDBACK ONLY --
# the server's own pre-receive hook (push-gate.sh --server) is the actual
# protection line; this hook exists so a leak is caught before a round
# trip to the server, not instead of the server check. `git push
# --no-verify` skips this hook entirely and reaches the server gate
# unfiltered by this one -- exactly as it should: --no-verify is a LOCAL
# git flag, it has no way to reach across the wire and disable a hook
# that lives in the server's own repository.
set -euo pipefail

GATE="${HOME}/.claude/scripts/push-gate.sh"
SYNC_GATE_CONFIG="${HOME}/.claude/scripts/sync-gate-config.sh"

# An optional, separately-shipped config sync/verify step (not part of
# this repository -- see push-gate.sh's own header, "what a verify-gate.sh
# ... must check", the sibling concern on the server side). Its ABSENCE is
# not an error: most installs never carry it. Its PRESENCE-but-FAILURE is
# treated the same as every other "never silent" decision this whole gate
# already follows -- config drift a verify step exists to catch is exactly
# the shape that must not pass through quietly just because the check that
# would have caught it happened to run client-side first.
#
# `-x` (executable), not `-f` (exists): this script is invoked directly
# (`"${SYNC_GATE_CONFIG}" --verify`, not `bash "${SYNC_GATE_CONFIG}"
# --verify`), so the executable bit is genuinely what determines whether it
# runs at all -- but that also means a copy that EXISTS but lost its exec
# bit (a bad file transfer, an overzealous `chmod`) silently reads as
# "absent" here rather than tripping the presence-but-failure path above.
# Known, accepted gap: closing it would mean re-adding it as a NON-executable
# file and invoking it via `bash`, which this script has no way to require
# of whatever ships sync-gate-config.sh in the future.
#
# Neither this call nor the main gate invocation below carries a timeout.
# Code review (CCP-1137 Auflage 2) flagged this: a hang in either blocks
# every `git push` for that developer indefinitely, with `--no-verify` as
# the only escape -- which requires already suspecting this hook as the
# cause. Left unaddressed here on purpose rather than reached for a
# `timeout`/`gtimeout` wrapper: neither is guaranteed present on a stock
# macOS install (this repo's own ADR-0011 bash-3.2 portability stance
# implies no GNU-coreutils dependency either), and no shipped script in
# this repository uses one today -- adding a first, hand-rolled
# background-process-plus-`kill` timeout to a hook that must be reliable is
# a real risk of its own, not obviously smaller than the hang it guards
# against. Reported to the PO as an open point rather than resolved here.
if [ -x "${SYNC_GATE_CONFIG}" ]; then
  "${SYNC_GATE_CONFIG}" --verify
fi

# The gate missing at its expected, install.sh-shipped location is refused
# loudly -- never a silent "nothing to check, push proceeds". A stale or
# partially-removed local install must not read as "no problems found".
if [ ! -f "${GATE}" ]; then
  echo "pre-push: push-gate.sh not found at ${GATE} -- refusing to push without it (run 'install.sh --update' from your CCPR checkout)" >&2
  exit 2
fi

# git feeds this hook one line per ref being pushed, on stdin, BEFORE any
# push starts:
#   <local ref> <local sha1> <remote ref> <remote sha1>
# push-gate.sh reads the pre-receive shape instead:
#   <oldrev> <newrev> <refname>
# The mapping: oldrev=<remote sha1> (what the remote currently has),
# newrev=<local sha1> (what this push is trying to introduce),
# refname=<remote ref> (the ref being updated, remote-side).
#
# Both all-zero shapes need no special casing here, by construction:
#   * A DELETION push has <local sha1> = 40 zeros. Forwarded unfiltered,
#     this becomes push-gate.sh's own `newrev` field, and its very first
#     check (`if [[ "$newrev" =~ ^0+$ ]]`) already accepts a deletion
#     without scanning -- reusing that branch here, rather than a second
#     zero-check in THIS hook, keeps the deletion rule defined in exactly
#     one place (the same "patterns live once" discipline push-gate.sh's
#     own header states for its two sub-gates).
#   * A FIRST push into an empty remote has <remote sha1> = 40 zeros. That
#     becomes push-gate.sh's `oldrev` -- which push-gate.sh never actually
#     reads for anything beyond its own blank-line skip (confirmed: `grep
#     -n oldrev push-gate.sh` has exactly two hits, the header comment and
#     the `read` + empty-check line). The commit-reachability scope is
#     computed from `newrev` alone (`git rev-list "$newrev" --not
#     <scope>`), so an all-zero oldrev needs no translation here either --
#     it is inert by construction, not by an added guard.
TMP_REFS="$(mktemp -t push-gate-refs.XXXXXX)"
trap 'rm -f "${TMP_REFS}"' EXIT

while read -r local_ref local_sha remote_ref remote_sha; do
  [ -n "${local_ref:-}" ] || continue
  printf '%s %s %s\n' "${remote_sha}" "${local_sha}" "${remote_ref}" >> "${TMP_REFS}"
done

# One single invocation, not one per ref: push-gate.sh's own main loop
# already reads multiple "<oldrev> <newrev> <refname>" lines from one
# stdin stream and scans every ref a push touches (see
# MultipleRefsInOnePushTest in scripts/tests/test_push_gate.py) -- calling
# it once per ref here would duplicate that loop instead of reusing it,
# and would lose the "one push, one verdict" shape pre-receive gets for
# free. No `--server` argument: the client-safe default
# (`--not --remotes`) is exactly what a client-side caller needs -- see
# push-gate.sh's own header for why `--server` here would be silently
# blind.
bash "${GATE}" < "${TMP_REFS}"
HOOK

chmod +x "${HOOK_PATH}"
echo "install-push-gate-hook: installed pre-push hook at ${HOOK_PATH}"
echo "  -> resolves push-gate.sh at \${HOME}/.claude/scripts/push-gate.sh (client-safe scope, no --server)"
echo "  -> FAST FEEDBACK ONLY -- the server's own pre-receive hook (push-gate.sh --server) is the real protection line"
echo "  -> 'git push --no-verify' bypasses this hook; it does NOT bypass the server-side gate"
