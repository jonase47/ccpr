#!/usr/bin/env python3
"""workitems.py – CLI dispatcher for the CCPR work-item backend contract (ADR-0002).

Reads `workitems.provider` from settings.json (default: local) and dispatches to the
provider implementation in scripts/lib/workitems/<provider>.py. `local` is the default
and reference backend: no server, no token, structured Markdown at docs/workitems/.

Usage:
  workitems.py list [--status STATUS] [--owner OWNER] [--project DIR]
  workitems.py get <id> [--project DIR]
  workitems.py claim <id> [--owner OWNER] [--project DIR]
  workitems.py set-status <id> <status> [--project DIR]
  workitems.py append-result <id> <ref> [--project DIR]

Output: JSON on stdout for every operation (a list for `list`, an object otherwise).
"""

import argparse
import importlib
import json
import os
import sys

DEFAULT_PROVIDER = "local"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from workitems import WorkItemError  # noqa: E402


def load_settings(project_dir):
    settings_path = os.path.join(project_dir, "settings.json")
    if not os.path.isfile(settings_path):
        return {}
    with open(settings_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_provider(settings, project_dir):
    """Return (provider_name, provider_config) from settings.json's `workitems` block."""
    workitems_settings = settings.get("workitems", {})
    provider = workitems_settings.get("provider", DEFAULT_PROVIDER)
    config = dict(workitems_settings.get(provider, {}))
    if provider == "local" and "workitems_dir" not in config:
        config["workitems_dir"] = os.path.join(project_dir, "docs", "workitems")
    return provider, config


def load_backend(provider, config):
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

    p_list = sub.add_parser("list", help="Enumerate work items (JSON array)", parents=[project_arg])
    p_list.add_argument("--status")
    p_list.add_argument("--owner")

    p_get = sub.add_parser("get", help="Fetch one item (JSON object)", parents=[project_arg])
    p_get.add_argument("id")

    p_claim = sub.add_parser("claim", help="Take ownership / mark active", parents=[project_arg])
    p_claim.add_argument("id")
    p_claim.add_argument("--owner")

    p_set_status = sub.add_parser("set-status", help="Move an item through its lifecycle", parents=[project_arg])
    p_set_status.add_argument("id")
    p_set_status.add_argument("status")

    p_append = sub.add_parser("append-result", help="Attach a result reference (PR/commit link)", parents=[project_arg])
    p_append.add_argument("id")
    p_append.add_argument("ref")

    return parser


def dispatch(backend, args):
    if args.operation == "list":
        return backend.list(status=args.status, owner=args.owner)
    if args.operation == "get":
        return backend.get(args.id)
    if args.operation == "claim":
        return backend.claim(args.id, owner=args.owner)
    if args.operation == "set-status":
        return backend.set_status(args.id, args.status)
    if args.operation == "append-result":
        return backend.append_result(args.id, args.ref)
    raise ValueError(f"Unknown operation: {args.operation}")


def main(argv=None):
    args = build_parser().parse_args(argv)

    settings = load_settings(args.project_dir)
    provider, config = resolve_provider(settings, args.project_dir)

    try:
        backend = load_backend(provider, config)
    except ModuleNotFoundError:
        print(f"Unknown work-item provider: {provider}", file=sys.stderr)
        return 1

    try:
        result = dispatch(backend, args)
    except WorkItemError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
