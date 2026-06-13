# Memory Lint Report

> Output format template for `memory-lint.sh` and `phase-docs-lint.sh`.
> Human-readable (Markdown on stdout). Severity order: errors → warnings → info.

**Scope:** {{`docs/memory/**` or `docs/<phase>/**`}}
**Run:** {{DD.MM.YYYY HH:MM}}
**Files scanned:** {{N}}

## Errors ({{count}})

- `{{path/to/file.md}}` — {{description}}
- `{{path/to/file.md}}:{{line}}` — {{description}}

## Warnings ({{count}})

- `{{path/to/file.md}}` — {{description}}

## Info ({{count}})

- `{{path/to/file.md}}` — {{description}}

---

**Summary:** {{errors}} errors, {{warnings}} warnings, {{info}} info.
**Exit:** {{0|1|2}}

<!-- Severity semantics:

  error   = Schema violation or broken cross-ref (e.g. missing required field, `related:` entry points to non-existent file). Exit 2.
  warning = Content consistency drift (e.g. stale file older than 90 days, index does not list file). Exit 1.
  info    = Improvement suggestion (e.g. duplicate heuristic triggered, optional fields missing). Exit 0.
-->
