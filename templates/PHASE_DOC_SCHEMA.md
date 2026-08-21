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
| `related` | YAML list (inline or block) | Paths to related phase docs. **Document-relative** (relative to the file's own directory) is the documented, preferred form. The lint also accepts a **project-root-relative** path (e.g. `docs/architecture/SECURITY.md`) as a fallback when the document-relative resolution misses — reported as an `info` finding, not silently, so root-relative usage stays visible instead of unnoticed drift (WI-0071). |
| `parent_index` | Path | Sub-indexes link to their phase index (e.g. `ARCHITECTURE.md`). Phase indexes leave this field empty. Resolved the same document-relative-first, project-root-fallback way as `related` above. |
| `base_commit`, `reviewed_head`, `reviewed_base` | Commit SHA | Written by `/p4-sprint` (`base_commit`, the sprint's starting `HEAD`) and by `/p5-review-sprint` (`reviewed_head`, the `HEAD` the review covered); `/gate-p5` compares `reviewed_head` against the current `HEAD` to decide whether a sprint review is stale. When present, the lint checks the **form** (7–40 hex characters, error) and, in a git repository, whether the SHA **resolves** to a commit (warning — a shallow clone, a rewritten history or a SHA from another repository are legitimate reasons to miss). Not to be confused with the anchor of ADR-0009, which is a separate key. |
| `gate` | `pending` \| `conditional_go` \| `go` \| `no_go` | Only meaningful for `GATE_PX.md` files. |
| `covers` | YAML list (inline or block) | **Code** paths (not doc paths) this document describes, e.g. `internal/auth/`, `src/domain/` — **relative to the project root**, exclusively (no document-relative fallback, unlike `related`/`parent_index` above). Lint checks path existence and flags an existing-but-empty directory. |

## Status semantics (vs. Memory schema)

Phase docs have **no stale detection** (unlike Memory). Instead:
- `frozen` ≠ `stale` — frozen is the intended state after a Gate pass.
- `archived` = document was superseded by a newer version; remains in the repo for historical reference.
- `skeleton` = file exists but has no substantive content yet (pre-P6 guards pattern).

## Index-↔-detail consistency

The lint enforces **one** part of this:

- If a detail file declares `parent_index: SECURITY.md`, then `SECURITY.md` must **exist** — a path
  check, resolved document-relative first and against the project root as a fallback (see the
  `parent_index` row above; a root-relative hit is reported as `info`).

Two further expectations are **conventions, not validations**. Nothing checks them:

1. Every file with frontmatter under `docs/<phase>/**` should be listed in the phase index or a
   sub-index.
2. The index named by `parent_index:` should list the detail file back.

Both would require the lint to parse an index's contents, which it does not do. Do not read a clean
lint run as evidence that either holds.

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
