"""sweep.py – `ccpr workitems sweep`: reconciles abandoned claims into Parked
(ADR-0005).

Remote-only in EFFECT, without needing to special-case any provider name: local
never sets a heartbeat (local.py always reports heartbeat=None on every item), and
this function skips any item with no heartbeat at all — so it is naturally a no-op
against a local backend, the same way migrate()/lift() stay backend-agnostic.

Per ADR-0005: an `In Progress` item transitions to `Parked` only when BOTH
conditions hold — its heartbeat is stale (no refresh within `staleAfter`) AND its
`ticket/<id>` branch has commits (there is work to resume). A stale heartbeat alone
is not enough (nothing to resume yet); commits alone are not enough (the runner
might still be alive). This is the rule the ADR calls out explicitly: "Parked":
work exists, no live runner, resumable.

Both `clock` (a zero-arg callable -> datetime) and `has_branch_commits` (a callable
item_id -> bool) are injected, the same pattern as `migrate()`'s clock: tests never
need a real "now" or a real git repository. The CLI wires a default git-based
`has_branch_commits` (see `make_git_branch_commits_checker`).
"""

import datetime
import subprocess

from workitems import DEFAULT_STALE_AFTER_SECONDS, safe_parse_datetime


def default_clock():
    return datetime.datetime.now(datetime.timezone.utc)


def sweep(backend, clock=None, has_branch_commits=None, stale_after_seconds=None):
    """One reconciliation pass over `backend`'s `In Progress` items.

    Returns a report dict: `parked` (ids transitioned to Parked) and
    `left_in_progress` (ids whose heartbeat is stale but have no branch commits yet
    — nothing to resume, so left alone).
    """
    clock = clock or default_clock
    has_branch_commits = has_branch_commits or (lambda item_id: False)
    stale_after_seconds = (
        stale_after_seconds if stale_after_seconds is not None else DEFAULT_STALE_AFTER_SECONDS
    )

    now = clock()
    report = {"parked": [], "left_in_progress": []}

    for item in backend.list(status="In Progress"):
        # A malformed heartbeat (any backend could hand us one -- a hand-edited
        # tracker field, a bug) degrades to "no valid heartbeat", same as missing:
        # never considered live, never swept, never a crash.
        heartbeat_dt = safe_parse_datetime(item.get("heartbeat"), datetime.datetime.fromisoformat)
        if heartbeat_dt is None:
            continue

        age_seconds = (now - heartbeat_dt).total_seconds()
        if age_seconds < stale_after_seconds:
            continue  # still alive

        if not has_branch_commits(item["id"]):
            report["left_in_progress"].append(item["id"])
            continue  # stale but nothing to resume yet -- ADR-0005 requires BOTH

        backend.set_status(item["id"], "Parked")
        report["parked"].append(item["id"])

    return report


def make_git_branch_commits_checker(project_dir, base="main"):
    """Default has_branch_commits for the CLI: `git rev-list <base>..ticket/<id>
    --count` > 0. Returns False (nothing to resume) if the branch doesn't exist, git
    isn't available, or anything else goes wrong -- a missing branch is not an error
    here, it just means there is nothing to Park yet."""

    def has_branch_commits(item_id):
        branch = f"ticket/{item_id}"
        try:
            result = subprocess.run(
                ["git", "rev-list", f"{base}..{branch}", "--count"],
                cwd=project_dir, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode != 0:
            return False
        try:
            return int(result.stdout.strip()) > 0
        except ValueError:
            return False

    return has_branch_commits
