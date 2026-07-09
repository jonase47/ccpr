#!/usr/bin/env python3
"""workitems.py – CLI dispatcher for the CCPR work-item backend contract (ADR-0002).

Reads `workitems.provider` from `.claude/settings.json` (default: local) and dispatches
to the provider implementation in scripts/lib/workitems/<provider>.py. `local` is the
default and reference backend: no server, no token, structured Markdown at
docs/workitems/. Project config lives under `.claude/` (Claude Code's own convention),
not a repo-root settings.json -- see load_settings()'s docstring for the exact
precedence, including the `.claude/settings.local.json` dev override.

Usage:
  workitems.py create --title T [--type X] [--owner O] [--description D]
                       [--tag T ...] [--project DIR]
  workitems.py list [--status STATUS] [--owner OWNER] [--tag T ...] [--type X]
                     [--sprint N] [--query Q] [--project DIR]
  workitems.py get <id> [--project DIR]
  workitems.py claim <id> [--owner OWNER] [--runner R] [--project DIR]
  workitems.py heartbeat <id> --runner R [--project DIR]
  workitems.py set-status <id> <status> [--project DIR]
  workitems.py append-result <id> <ref> [--project DIR]
  workitems.py comment <id> <text> [--project DIR]
  workitems.py set-description <id> <text> [--project DIR]
  workitems.py set-title <id> <text> [--project DIR]
  workitems.py set-type <id> <type> [--project DIR]
  workitems.py add-tag <id> <tag> [--project DIR]
  workitems.py remove-tag <id> <tag> [--project DIR]
  workitems.py add-link <id> <type> <target-id> [--project DIR]
  workitems.py remove-link <id> <type> <target-id> [--project DIR]
  workitems.py set-sprint <id> <n> [--project DIR]
  workitems.py migrate --to <provider> [--project DIR]
  workitems.py lift <source-file...> [--apply] [--exclude PATTERN=REASON ...] [--project DIR]
  workitems.py sweep [--project DIR]

Output: JSON on stdout for every operation (a list for `list`, an object otherwise).

Tags (ADR-0002 2nd addendum): --tag is repeatable everywhere it appears; on `list` it
is AND semantics (an item must carry every named tag to match). --query is a
project-scoped passthrough to the youtrack backend's own query language; the local
backend raises on --query (no server-side query language to pass through to).

Claiming (ADR-0005): --runner records the runner:<id> signal + a heartbeat and sets
In Progress; mandatory for remote backends, a no-op for `local`. `sweep` reconciles
abandoned claims into Parked based on `workitems.claiming.staleAfter` in `.claude/settings.json`.

Typed links (ADR-0008): <type> is one of depends-on/blocks/relates-to/subtask-of.
`blocks` is client-side sugar for the inverse of depends-on (delegates to
`add-link <target-id> depends-on <id>`); add-link/remove-link are idempotent.

Planning fields (ADR-0002 2nd addendum): set-sprint is single-valued (a later set
overwrites); set-priority/set-estimate follow in a later increment. `--sprint` on
`list` is a client-side exact-match filter, both backends.
"""

import argparse
import importlib
import importlib.util
import json
import os
import sys

DEFAULT_PROVIDER = "local"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from workitems import WorkItemError, parse_duration_seconds  # noqa: E402
from workitems import lift as lift_module  # noqa: E402
from workitems import migrate as migrate_module  # noqa: E402
from workitems import sweep as sweep_module  # noqa: E402


class UnknownProviderError(Exception):
    """Raised when .claude/settings.json names a provider with no matching
    lib/workitems/<provider>.py."""


def _claude_settings_path(project_dir):
    return os.path.join(project_dir, ".claude", "settings.json")


def _claude_settings_local_path(project_dir):
    return os.path.join(project_dir, ".claude", "settings.local.json")


def _read_json_file(path):
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            raise WorkItemError(f"invalid JSON in {path}: {exc}") from exc


def load_settings(project_dir):
    """Reads the project's Claude Code settings, `.claude/settings.json` -- NOT a
    repo-root settings.json (a CCPR project's config lives under `.claude/`, same as
    Claude Code's own settings). Missing file -> {} (falls through to the default
    `local` provider), same as before.

    Mirrors Claude Code's own local-override precedence: if
    `.claude/settings.local.json` also exists, it overrides the base file's
    `workitems` block (a shallow merge at that key only -- not a deep merge of every
    nested field) so a developer can point at a different provider locally without
    committing the change. Any other top-level key in settings.local.json (there
    normally isn't one relevant here) is ignored; `_update_provider_in_settings`
    always writes back to the base, committed file, never to .local.
    """
    settings = _read_json_file(_claude_settings_path(project_dir))
    local_settings = _read_json_file(_claude_settings_local_path(project_dir))
    if "workitems" in local_settings:
        settings = dict(settings)
        settings["workitems"] = local_settings["workitems"]
    return settings


def resolve_provider_config(settings, project_dir, provider):
    """Return the `.claude/settings.json` config block for a specific provider name."""
    workitems_settings = settings.get("workitems", {})
    config = dict(workitems_settings.get(provider, {}))
    if provider == "local" and "workitems_dir" not in config:
        config["workitems_dir"] = os.path.join(project_dir, "docs", "workitems")

    # Claiming (ADR-0005): workitems.claiming.staleAfter is a project-wide setting,
    # not per-provider, but every backend that implements claiming needs it (for the
    # takeover-check) -- merged in here so any provider's create(config) can read
    # config["stale_after_seconds"] the same way. heartbeatInterval is deliberately
    # NOT consumed anywhere in this repo: it's advisory for whatever schedules a
    # runner's heartbeat calls (the external runner-loop's concern), not something
    # the backend itself needs to act on.
    claiming_settings = workitems_settings.get("claiming") or {}
    if not isinstance(claiming_settings, dict):
        raise WorkItemError(
            "Invalid workitems.claiming in .claude/settings.json: expected an object "
            f'(e.g. {{"staleAfter": "1h"}}), got {claiming_settings!r}'
        )
    if "staleAfter" in claiming_settings:
        config["stale_after_seconds"] = parse_duration_seconds(claiming_settings["staleAfter"])

    return config


def resolve_provider(settings, project_dir):
    """Return (provider_name, provider_config) for the CURRENTLY ACTIVE provider."""
    provider = settings.get("workitems", {}).get("provider", DEFAULT_PROVIDER)
    return provider, resolve_provider_config(settings, project_dir, provider)


def load_backend(provider, config):
    # find_spec() first so a missing dependency *inside* a valid provider module
    # (e.g. a future youtrack.py importing `requests`) surfaces as its own error
    # instead of being misreported as "unknown provider" by a broad
    # `except ModuleNotFoundError` around the actual import.
    if importlib.util.find_spec(f"workitems.{provider}") is None:
        raise UnknownProviderError(provider)
    module = importlib.import_module(f"workitems.{provider}")
    return module.create(config)


def build_parser():
    # `--project` is defined on a shared parent so it can appear either before or after
    # the subcommand (argparse hands everything past the subcommand name to the chosen
    # subparser, which otherwise would not recognise a parent-level-only option).
    #
    # default=SUPPRESS here, NOT os.getcwd(): every subparser gets its OWN copy of this
    # action (parents=[project_arg] on each one), and argparse's subparser handling
    # parses the remaining args into a FRESH namespace, then merges every key from
    # that namespace into the outer one -- including project_dir's default, even when
    # --project was never given to the subparser at all. With a real default, that
    # merge SILENTLY OVERWRITES a --project value already parsed by the top-level
    # parser when it appeared BEFORE the subcommand (a data-safety footgun: writes
    # redirect to the wrong directory with no error). SUPPRESS means the action sets
    # nothing at all unless --project was explicitly given in that exact argv segment,
    # so the merge can never clobber an already-parsed value. The actual default
    # (os.getcwd()) is resolved exactly once, in main(), after parsing completes.
    project_arg = argparse.ArgumentParser(add_help=False)
    project_arg.add_argument(
        "--project", dest="project_dir", default=argparse.SUPPRESS,
        help="Project root (default: cwd)",
    )

    parser = argparse.ArgumentParser(prog="workitems.py", description="CCPR work-item backend CLI", parents=[project_arg])
    sub = parser.add_subparsers(dest="operation", required=True)

    p_create = sub.add_parser("create", help="Create a new item; the backend assigns the id", parents=[project_arg])
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--type", dest="type")
    p_create.add_argument("--owner")
    p_create.add_argument("--description")
    p_create.add_argument(
        "--tag", dest="tags", action="append", default=[],
        help="Attach a tag (repeatable)",
    )

    p_list = sub.add_parser("list", help="Enumerate work items (JSON array)", parents=[project_arg])
    p_list.add_argument("--status")
    p_list.add_argument("--owner")
    p_list.add_argument(
        "--tag", dest="tags", action="append", default=[],
        help="Filter by tag (repeatable; AND semantics)",
    )
    p_list.add_argument("--type", dest="type")
    p_list.add_argument("--sprint", help="Filter by the Sprint field (exact match)")
    p_list.add_argument(
        "--query", help="YouTrack-only passthrough query (rejected by the local backend)",
    )

    p_get = sub.add_parser("get", help="Fetch one item (JSON object)", parents=[project_arg])
    p_get.add_argument("id")

    p_claim = sub.add_parser("claim", help="Take ownership / mark active", parents=[project_arg])
    p_claim.add_argument("id")
    p_claim.add_argument("--owner")
    p_claim.add_argument("--runner", help="Runner identity (ADR-0005); mandatory-claiming on remote backends")

    p_heartbeat = sub.add_parser(
        "heartbeat", help="Refresh the liveness signal for a claimed item (ADR-0005)",
        parents=[project_arg],
    )
    p_heartbeat.add_argument("id")
    p_heartbeat.add_argument("--runner", required=True)

    p_set_status = sub.add_parser("set-status", help="Move an item through its lifecycle", parents=[project_arg])
    p_set_status.add_argument("id")
    p_set_status.add_argument("status")

    p_append = sub.add_parser("append-result", help="Attach a result reference (PR/commit link)", parents=[project_arg])
    p_append.add_argument("id")
    p_append.add_argument("ref")

    p_comment = sub.add_parser(
        "comment", help="Append a plain human comment (no result marker)", parents=[project_arg],
    )
    p_comment.add_argument("id")
    p_comment.add_argument("text")

    p_set_description = sub.add_parser(
        "set-description", help="Replace the description in full (empty string clears it)",
        parents=[project_arg],
    )
    p_set_description.add_argument("id")
    p_set_description.add_argument("text")

    p_set_title = sub.add_parser("set-title", help="Replace the title", parents=[project_arg])
    p_set_title.add_argument("id")
    p_set_title.add_argument("text")

    p_set_type = sub.add_parser(
        "set-type", help="Replace/set the type extension field (fails hard on rejection)",
        parents=[project_arg],
    )
    p_set_type.add_argument("id")
    p_set_type.add_argument("type")

    p_add_tag = sub.add_parser(
        "add-tag", help="Attach a tag (idempotent)", parents=[project_arg],
    )
    p_add_tag.add_argument("id")
    p_add_tag.add_argument("tag")

    p_remove_tag = sub.add_parser(
        "remove-tag", help="Detach a tag (idempotent)", parents=[project_arg],
    )
    p_remove_tag.add_argument("id")
    p_remove_tag.add_argument("tag")

    p_add_link = sub.add_parser(
        "add-link", help="Create a typed edge to another item (idempotent)", parents=[project_arg],
    )
    p_add_link.add_argument("id")
    p_add_link.add_argument("type")
    p_add_link.add_argument("target")

    p_remove_link = sub.add_parser(
        "remove-link", help="Remove an exact typed edge (idempotent)", parents=[project_arg],
    )
    p_remove_link.add_argument("id")
    p_remove_link.add_argument("type")
    p_remove_link.add_argument("target")

    p_set_sprint = sub.add_parser(
        "set-sprint", help="Set the Sprint field (single-valued; fails hard on rejection)",
        parents=[project_arg],
    )
    p_set_sprint.add_argument("id")
    p_set_sprint.add_argument("sprint")

    p_migrate = sub.add_parser(
        "migrate", help="Move items to a target backend, once, reversibly (ADR-0004)",
        parents=[project_arg],
    )
    p_migrate.add_argument("--to", required=True, help="Target provider name")

    p_lift = sub.add_parser(
        "lift", help="Propose local items from prose sources; dry-run by default (ADR-0004)",
        parents=[project_arg],
    )
    p_lift.add_argument("source_files", nargs="+", metavar="SOURCE_FILE")
    p_lift.add_argument("--apply", action="store_true", help="Write proposed items (default: dry-run)")
    p_lift.add_argument(
        "--exclude", action="append", default=[], metavar="PATTERN=REASON",
        help="Exclude lines matching PATTERN (regex), reported with REASON (repeatable)",
    )

    sub.add_parser(
        "sweep", help="Reconcile abandoned claims into Parked (ADR-0005)",
        parents=[project_arg],
    )

    return parser


def dispatch(backend, args):
    if args.operation == "create":
        return backend.create(
            title=args.title, item_type=args.type, owner=args.owner,
            description=args.description, tags=args.tags,
        )
    if args.operation == "list":
        return backend.list(
            status=args.status, owner=args.owner, tags=args.tags, item_type=args.type,
            query=args.query, sprint=args.sprint,
        )
    if args.operation == "get":
        return backend.get(args.id)
    if args.operation == "claim":
        return backend.claim(args.id, owner=args.owner, runner=args.runner)
    if args.operation == "heartbeat":
        return backend.heartbeat(args.id, runner=args.runner)
    if args.operation == "set-status":
        return backend.set_status(args.id, args.status)
    if args.operation == "append-result":
        return backend.append_result(args.id, args.ref)
    if args.operation == "comment":
        return backend.comment(args.id, args.text)
    if args.operation == "set-description":
        return backend.set_description(args.id, args.text)
    if args.operation == "set-title":
        return backend.set_title(args.id, args.text)
    if args.operation == "set-type":
        return backend.set_type(args.id, args.type)
    if args.operation == "add-tag":
        return backend.add_tag(args.id, args.tag)
    if args.operation == "remove-tag":
        return backend.remove_tag(args.id, args.tag)
    if args.operation == "add-link":
        return backend.add_link(args.id, args.type, args.target)
    if args.operation == "remove-link":
        return backend.remove_link(args.id, args.type, args.target)
    if args.operation == "set-sprint":
        return backend.set_sprint(args.id, args.sprint)
    raise ValueError(f"Unknown operation: {args.operation}")


def _run_migrate(settings, args, source_provider, source_config, source_backend):
    """`migrate --to <provider>`: not a per-backend contract op (it spans TWO
    backends), so it's handled here rather than in dispatch()."""
    target_provider = args.to

    if target_provider == source_provider:
        # A prior successful migrate already flipped the active provider to this
        # target. Re-running would look "unmigrated" from the wrong side: the idmap
        # holds OLD (source) ids as keys, but source_backend.list() now returns the
        # TARGET's own ids (since it IS the active/source backend here) -- none of
        # which are idmap keys, so every item would look never-migrated and get
        # recreated. Refuse instead of silently duplicating everything.
        raise WorkItemError(
            f"'{target_provider}' is already the active provider; nothing to migrate. "
            "Re-running migrate --to would duplicate every item."
        )

    target_config = resolve_provider_config(settings, args.project_dir, target_provider)
    target_backend = load_backend(target_provider, target_config)

    idmap_path = os.path.join(args.project_dir, "docs", "workitems-idmap.yml")
    source_workitems_dir = (
        source_config.get("workitems_dir") if source_provider == "local" else None
    )

    report = migrate_module.migrate(
        source_backend, target_backend, idmap_path,
        source_workitems_dir=source_workitems_dir,
    )

    # Leave exactly one active backend afterward (ADR-0002/ADR-0004): flip
    # .claude/settings.json's active provider once every source item is accounted for.
    # Gated on fully_migrated, NOT archived -- archived is only ever True for a
    # filesystem-based (local) source, so gating on it meant a non-local source
    # never flipped the provider even on complete, successful migration.
    if report.get("fully_migrated"):
        _update_provider_in_settings(args.project_dir, target_provider)

    # Rollback path (ADR-0004): archiving moves the directory, never deletes it,
    # but nothing moves it back automatically. Spell out the exact restore command
    # -- migrate() already gives the mv half; the CLI adds the provider-name half,
    # since migrate() only ever sees backend instances, not provider name strings.
    if report.get("archived"):
        restore_instructions = (
            f"{report['restore_command']} && set workitems.provider back to "
            f"{source_provider!r} in .claude/settings.json"
        )
        report["restore_instructions"] = restore_instructions
        print(f"Rollback: to restore the previous state, run: {restore_instructions}", file=sys.stderr)

    return report


def _update_provider_in_settings(project_dir, new_provider):
    """Flips `workitems.provider` after a completed migration. Reads and writes the
    BASE `.claude/settings.json` directly (not via load_settings(), which applies the
    .local override for resolution) -- writing back the merged view would leak a
    developer's local-only override into the committed file. Read-modify-write:
    any other top-level key already in settings.json (permissions, hooks, ...) is
    preserved untouched. Never writes to `.claude/settings.local.json`."""
    settings_path = _claude_settings_path(project_dir)
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    settings = _read_json_file(settings_path)
    settings.setdefault("workitems", {})["provider"] = new_provider
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def _run_sweep(settings, args, config, backend):
    """`sweep`: reconciles the CURRENTLY ACTIVE backend's abandoned claims (a
    per-backend contract op wouldn't make sense here either -- it operates over
    every In Progress item, not one id -- so it's handled here like migrate/lift)."""
    stale_after_seconds = config.get("stale_after_seconds")
    has_branch_commits = sweep_module.make_git_branch_commits_checker(args.project_dir)
    return sweep_module.sweep(
        backend, has_branch_commits=has_branch_commits,
        stale_after_seconds=stale_after_seconds,
    )


def _run_lift(settings, args):
    """`lift` always targets the `local` backend (ADR-0004: heterogeneous -> local),
    regardless of whichever provider is currently active — it must not fail just
    because the active provider (e.g. a remote one) happens to be misconfigured."""
    local_config = resolve_provider_config(settings, args.project_dir, "local")
    local_backend = load_backend("local", local_config)
    exclude_rules = [lift_module.parse_exclude_rule(raw) for raw in args.exclude]
    return lift_module.lift(
        args.source_files, local_backend, exclude_rules=exclude_rules, apply=args.apply,
    )


def main(argv=None):
    args = build_parser().parse_args(argv)
    # The single place the --project default is resolved (see build_parser()'s
    # comment on why it's SUPPRESS'd on the argparse side): args.project_dir is only
    # absent here if --project was never given anywhere in argv.
    if not hasattr(args, "project_dir"):
        args.project_dir = os.getcwd()

    try:
        settings = load_settings(args.project_dir)
        if args.operation == "lift":
            result = _run_lift(settings, args)
        else:
            provider, config = resolve_provider(settings, args.project_dir)
            backend = load_backend(provider, config)
            if args.operation == "migrate":
                result = _run_migrate(settings, args, provider, config, backend)
            elif args.operation == "sweep":
                result = _run_sweep(settings, args, config, backend)
            else:
                result = dispatch(backend, args)
    except UnknownProviderError as exc:
        print(f"Unknown work-item provider: {exc}", file=sys.stderr)
        return 1
    except WorkItemError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
