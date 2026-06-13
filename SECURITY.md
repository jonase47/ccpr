# Security Policy

## Scope

CCPR is a configuration and prompt framework for Claude Code — Markdown agent and
command definitions, templates, documentation, and a set of local automation
scripts (`scripts/`) and hooks (`hooks/`). It is not a hosted service and ships no
runtime server. The realistic security surface is therefore:

- **Local scripts and hooks** (`scripts/**`, `hooks/**`) that run on your machine.
- **`settings.json`** permission and hook configuration.
- **Prompt content** that could instruct an agent to take an unsafe action.

## Reporting a vulnerability

Please report security issues **privately** — do **not** open a public issue or
pull request, and do not disclose details publicly until a fix is available.

- Contact the maintainer via GitHub: **[@jonase47](https://github.com/jonase47)**.

Include where you can:
- The affected file(s) or command(s) and the version / tag or commit.
- A description of the issue and its impact.
- Steps to reproduce, and a proof of concept if available.

This is a small open-source project maintained on a best-effort basis. You can
expect an acknowledgement and, for confirmed issues, a fix on `main` and a note in
`CHANGELOG.md`. Coordinated disclosure is appreciated.

## Supported versions

Fixes land on `main` and in the latest tagged release. Pre-1.0, only the most recent
`v0.x.0` tag is maintained — see [`CHANGELOG.md`](CHANGELOG.md).

## Hardening notes for users

- Review `settings.json` permissions before adopting them; the allowlist is a
  starting point, not a recommendation to grant every entry.
- Inspect `scripts/**` and `hooks/**` before running them — every shipped artifact
  is plain text and meant to be read (Constitution Inviolable: self-contained,
  inspectable distribution).
