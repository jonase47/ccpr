# Phase Doc Schema

> Formal frontmatter schema for phase-detail files and sub-index files
> (e.g. `docs/architecture/THREATS.md`, `docs/architecture/SECURITY.md`).
> Phase-index files (e.g. `docs/architecture/ARCHITECTURE.md`, `docs/planning/PROJECT_PLAN.md`)
> may also carry this schema; the lint checks them more leniently (status enum is sufficient).
>
> Living documents (`HANDOVER.md`, `BASELINE.md`, `BACKLOG.md`, `SPRINT.md`) are explicitly excluded —
> they use their own header conventions (see `~/.claude/templates/HANDOVER_TEMPLATE.md`).

## Required fields

| Field | Values | Description |
|---|---|---|
| `phase` | `P0` \| `P1` \| … \| `P8` | Which project phase produces this document. |
| `subskill` | Slash-command without leading `/` | e.g. `p3-sec-threats`, `p4-backlog`. For sub-indexes (e.g. `SECURITY.md`): the orchestrator skill (`p3-security`). |
| `status` | `skeleton` \| `draft` \| `active` \| `frozen` \| `archived` \| `living` | Status. `skeleton` = empty template, `draft` = in progress, `active` = usable, `frozen` = completed (phase passed Gate), `archived` = superseded, `living` = actively maintained detail file (e.g. SPRINT-XX.md, RISKS.md) designed to keep growing. |
| `last_updated` | `DD.MM.YYYY` or `DD.MM.YYYY (note)` | Date of the last substantive change. Parenthetical suffix optional as human context (e.g. "04.05.2026 (cross-phase update from /p3-cost)"). |

## Optional fields

| Field | Values | Description |
|---|---|---|
| `related` | YAML list (inline or block) | Paths to related phase docs, **relative to the file's own directory**. Lint checks cross-ref existence. |
| `parent_index` | Path | Sub-indexes link to their phase index (e.g. `ARCHITECTURE.md`). Phase indexes leave this field empty. |
| `gate` | `pending` \| `conditional_go` \| `go` \| `no_go` | Only meaningful for `GATE_PX.md` files. |

## Status semantics (vs. Memory schema)

Phase docs have **no stale detection** (unlike Memory). Instead:
- `frozen` ≠ `stale` — frozen is the intended state after a Gate pass.
- `archived` = document was superseded by a newer version; remains in the repo for historical reference.
- `skeleton` = file exists but has no substantive content yet (pre-P6 guards pattern).

## Index-↔-detail consistency

The lint also checks:
1. Every file with frontmatter under `docs/<phase>/**` is listed in the phase index or a sub-index.
2. If a detail file declares `parent_index: SECURITY.md`, then `SECURITY.md` must exist and list it.

## Example (sub-index)

```markdown
---
phase: P3
subskill: p3-security
status: active
last_updated: 02.05.2026
related:
  - ARCHITECTURE.md
  - ADR/ADR-0006-zero-third-party-policy.md
---

# Security (P3 Sub-Index) – Index

…
```

## Example (skeleton for pre-P6)

```markdown
---
phase: P6
subskill: p6-a11y
status: skeleton
last_updated: 11.05.2026
parent_index: QA.md
---

# Accessibility (P6 Sub-Index) – Index

**Status:** Skeleton — populated by `/p6-a11y`.

## Findings
<!-- /p6-a11y writes here -->

## Detail Files
<!-- /p6-a11y-keyboard, /p6-a11y-screenreader, /p6-a11y-visual write here -->
```

## Lint

`bash ~/.claude/scripts/phase-docs-lint.sh [<project-dir>] [--scope <glob>]` validates this schema.
Exit codes: 0 clean, 1 warnings, 2 errors.
