#!/usr/bin/env python3
"""workitems.py – CLI dispatcher for the CCPR work-item backend contract (ADR-0002).

Reads `workitems.provider` from settings.json (default: local) and dispatches to the
provider implementation in scripts/lib/workitems/<provider>.py. `local` is the default
and reference backend: no server, no token, structured Markdown at docs/workitems/.

Usage:
  workitems.py create --title T [--type X] [--owner O] [--description D] [--project DIR]
  workitems.py list [--status STATUS] [--owner OWNER] [--project DIR]
  workitems.py get <id> [--project DIR]
  workitems.py claim <id> [--owner OWNER] [--project DIR]
  workitems.py set-status <id> <status> [--project DIR]
  workitems.py append-result <id> <ref> [--project DIR]
  workitems.py migrate --to <provider> [--project DIR]
  workitems.py lift <source-file...> [--apply] [--exclude PATTERN=REASON ...] [--project DIR]

Output: JSON on stdout for every operation (a list for `list`, an object otherwise).
"""

import argparse
import importlib
import importlib.util
import json
import os
import sys

DEFAULT_PROVIDER = "local"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from workitems import WorkItemError  # noqa: E402
from workitems import lift as lift_module  # noqa: E402
from workitems import migrate as migrate_module  # noqa: E402


class UnknownProviderError(Exception):
    """Raised when settings.json names a provider with no matching lib/workitems/<provider>.py."""


def load_settings(project_dir):
    settings_path = os.path.join(project_dir, "settings.json")
    if not os.path.isfile(settings_path):
        return {}
    with open(settings_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            raise WorkItemError(f"invalid JSON in {settings_path}: {exc}") from exc


def resolve_provider_config(settings, project_dir, provider):
    """Return the settings.json config block for a specific provider name."""
    workitems_settings = settings.get("workitems", {})
    config = dict(workitems_settings.get(provider, {}))
    if provider == "local" and "workitems_dir" not in config:
        config["workitems_dir"] = os.path.join(project_dir, "docs", "workitems")
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
    project_arg = argparse.ArgumentParser(add_help=False)
    project_arg.add_argument("--project", dest="project_dir", default=os.getcwd(), help="Project root (default: cwd)")

    parser = argparse.ArgumentParser(prog="workitems.py", description="CCPR work-item backend CLI", parents=[project_arg])
    sub = parser.add_subparsers(dest="operation", required=True)

    p_create = sub.add_parser("create", help="Create a new item; the backend assigns the id", parents=[project_arg])
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--type", dest="type")
    p_create.add_argument("--owner")
    p_create.add_argument("--description")

    p_list = sub.add_parser("list", help="Enumerate work items (JSON array)", parents=[project_arg])
    p_list.add_argument("--status")
    p_list.add_argument("--owner")

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

    return parser


def dispatch(backend, args):
    if args.operation == "create":
        return backend.create(
            title=args.title, item_type=args.type, owner=args.owner,
            description=args.description,
        )
    if args.operation == "list":
        return backend.list(status=args.status, owner=args.owner)
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
    # settings.json's active provider once every source item is accounted for.
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
            f"{source_provider!r} in settings.json"
        )
        report["restore_instructions"] = restore_instructions
        print(f"Rollback: to restore the previous state, run: {restore_instructions}", file=sys.stderr)

    return report


def _update_provider_in_settings(project_dir, new_provider):
    settings_path = os.path.join(project_dir, "settings.json")
    settings = load_settings(project_dir)
    settings.setdefault("workitems", {})["provider"] = new_provider
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


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

    try:
        settings = load_settings(args.project_dir)
        if args.operation == "lift":
            result = _run_lift(settings, args)
        else:
            provider, config = resolve_provider(settings, args.project_dir)
            backend = load_backend(provider, config)
            if args.operation == "migrate":
                result = _run_migrate(settings, args, provider, config, backend)
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
