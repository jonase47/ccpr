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
| `subskill` | A slash-command name where one applies, `index` for a phase or sub-index, `gate` for a gate document, otherwise a project-local label | e.g. `p3-sec-threats`, `p4-backlog`. For sub-indexes (e.g. `SECURITY.md`): the orchestrator skill (`p3-security`), or `index`. Not a closed vocabulary tied 1:1 to `commands/*.md`: measured 26.08.2026 against a real CCPR-using project, 117 distinct `subskill` values against this repository's 116 shipped commands — many map to no command at all (`arch-scale`, `fe-optimization`, `business-model-vpc`). Presence-checked only (`phase-docs-lint.sh`'s `fm_validate_required`); no enum, no uniqueness check, nothing reads the value. |
| `status` | `skeleton` \| `draft` \| `active` \| `frozen` \| `archived` \| `living` | Status. `skeleton` = empty template, `draft` = in progress, `active` = usable, `frozen` = completed (phase passed Gate), `archived` = superseded, `living` = actively maintained detail file (e.g. SPRINT-XX.md, RISKS.md) designed to keep growing. |
| `last_updated` | `DD.MM.YYYY` or `DD.MM.YYYY (note)` | Date of the last substantive change. Parenthetical suffix optional as human context (e.g. "04.05.2026 (cross-phase update from /p3-cost)"). |

## Optional fields

| Field | Values | Description |
|---|---|---|
| `related` | YAML list (inline or block) | Paths to related phase docs. **Document-relative** (relative to the file's own directory) is the documented, preferred form. The lint also accepts a **project-root-relative** path (e.g. `docs/architecture/SECURITY.md`) as a fallback when the document-relative resolution misses — reported as an `info` finding, not silently, so root-relative usage stays visible instead of unnoticed drift (WI-0071). |
| `parent_index` | Path | Sub-indexes link to their phase index (e.g. `ARCHITECTURE.md`). Phase indexes leave this field empty. Resolved the same document-relative-first, project-root-fallback way as `related` above. |
| `kind` | See `## kind` below | Document genre — a free-standing marker used ALONGSIDE (`commands/*.md` templates) or INSTEAD OF (`Manual/**`, `docs/adr/*.md`, `templates/*_TEMPLATE.md`) the phase/subskill/status triple above. Validated against a fixed vocabulary by `scripts/manual-lint.sh` when set; `phase-docs-lint.sh` does not read this field at all except for the single literal `review` (see below). |
| `base_commit`, `reviewed_head`, `reviewed_base` | Commit SHA | Written by `/p4-sprint` (`base_commit`, the sprint's starting `HEAD`) and by `/p5-review-sprint` (`reviewed_head`, the `HEAD` the review covered); `/gate-p5` compares `reviewed_head` against the current `HEAD` to decide whether a sprint review is stale. When present, the lint checks the **form** (7–40 hex characters, error) and, in a git repository, whether the SHA **resolves** to a commit (warning — a shallow clone, a rewritten history or a SHA from another repository are legitimate reasons to miss). Not to be confused with the anchor of ADR-0009, which is a separate key. |
| `gate` | `pending` \| `conditional_go` \| `go` \| `no_go` | Only meaningful for `GATE_PX.md` files. |
| `covers` | YAML list (inline or block) | **Code** paths (not doc paths) this document describes, e.g. `internal/auth/`, `src/domain/` — **relative to the project root**, exclusively (no document-relative fallback, unlike `related`/`parent_index` above). Lint checks path existence and flags an existing-but-empty directory. |

## kind

The vocabulary below is the **KNOWN set, not the ALLOWED set** (WI-0112a follow-up, measured
26.08.2026 — no separate WI filed for this severity change). It started as every distinct `kind:`
value any shipped file, template, or command in this repository prescribed (WI-0112a) — mirrored
verbatim in `VALID_KINDS` in
`scripts/manual-lint.sh`; keep both in sync when a new kind is deliberately added. CCPR cannot
enumerate every document genre a downstream project will legitimately invent: measured the same
day against two real CCPR-using projects, `manual-lint.sh`'s then-closed enum rejected 16
distinct values between them (`memory-archive`, `handover-archive`, `story-detail`,
`portable-learnings`, … — none of them wrong, all of them unforeseen). So `scripts/manual-lint.sh`
check (c) reports an unrecognised `kind:` as a **warning**, not an error — the value being
*named* somewhere is useful signal; the value being *unknown* to this list is not a defect. Add a
value here only when it is a genuinely generic CCPR concept (not a project-local label) — the
default response to an unfamiliar value is to leave it as a warning, not to widen the list, or
the next project just invents the seventeenth.

`adr` · `api-resource-detail` · `commands-doc-detail` · `component-detail` · `constitution` ·
`detail` · `entity-detail` · `epic-detail` · `frame` · `learnings` · `promotion-brief` ·
`review` · `risk-detail` · `setup-detail` · `sprint-detail` · `sub-index` ·
`system-doc-detail` · `track-decision` · `wireframe-detail`

**`review` is load-bearing, not decorative — and that is unaffected by the warning-severity
change above.** `scripts/phase-docs-lint.sh` reads `kind:` exactly once (`fm_field "$file" kind`,
called at the top of the `reviews` profile branch) and uses the literal value `review` as a
behavioural switch: a document under `docs/reviews/**` only gets the WI-0072 required-fields
check (`sprint`, `reviewed_head`/`reviewed_base`, `reviewer`, `last_updated`) when it
self-identifies via `kind: review`. Any other value — no `kind:` at all, or a different one such
as `story-review`/`review-convention` — stays silent there. This switch reads the frontmatter
field directly; it does not consult `manual-lint.sh` or its severity at all, so demoting an
*unrecognised* `kind:` to a warning does not touch it — `review` staying a **recognised** value
in the list above is what keeps it silent in `manual-lint.sh` too. No other `kind:` value changes
`phase-docs-lint.sh`'s behaviour; the rest of this vocabulary is enforced only by
`manual-lint.sh`, and only on a tree you point it at.

## manual-lint.sh — index-↔-detail contract for a `kind`/`parent_index` tree

`bash ~/.claude/scripts/manual-lint.sh [<root-dir>]` validates the checks below over any
documentation tree that carries `kind:`/`parent_index:` frontmatter — generic over the root
argument, NOT hardwired to `Manual/` (this repository's own `Manual/` is the reference
example, but `install.sh` does not ship it into `~/.claude/`, so the script cannot default to
it). Exit codes: 0 clean, 1 warnings, 2 errors.

- **(a) `parent_index` resolves** — same document-relative-first, root-fallback cascade as
  `phase-docs-lint.sh`'s checks (f)/(g) above, with the script's own `ROOT` argument standing
  in for `PROJECT_DIR`.
- **(b) the reverse direction** — the index a working `parent_index:` resolves to must itself
  contain a markdown link to the claiming file (document-relative from the index's own
  directory, the exact shape this repository's `Manual/` links already use — no leading `./`,
  no anchor). A miss is a `warning`, not an `error`: the child's own pointer is still correct,
  only the index's back-reference is missing.
- **(c) `kind:` vocabulary** — checked against the known list above; opt-in, only fires when the
  field is actually set. A recognised value stays silent; an unrecognised one is a `warning`,
  not an `error` — see the "KNOWN set, not the ALLOWED set" paragraph above.

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

Two further expectations are **conventions**, unchecked **by `phase-docs-lint.sh` itself**:

1. Every file with frontmatter under `docs/<phase>/**` should be listed in the phase index or a
   sub-index. Still unvalidated by anything shipped as of WI-0112a.
2. The index named by `parent_index:` should list the detail file back. `manual-lint.sh`'s check
   (b) above now validates exactly this — but it is a separate script you must point at the tree
   in question (`docs/<phase>/`, `Manual/`, or any other `kind`/`parent_index` tree); it does not
   run as part of `phase-docs-lint.sh`, and a clean `phase-docs-lint.sh` run is still not evidence
   that (2) holds.

(1) would require the lint to parse an index's contents to discover what it does NOT list, which
neither script does. Do not read a clean `phase-docs-lint.sh` run as evidence that (1) holds.

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

`bash ~/.claude/scripts/phase-docs-lint.sh [<project-dir>] [--scope <glob>]` validates the
`phase`/`subskill`/`status`/`last_updated` schema above. `bash ~/.claude/scripts/manual-lint.sh
[<root-dir>]` validates the `kind`/`parent_index` index-↔-detail contract (see `## kind` and
`## manual-lint.sh` above) — a separate script, over whichever root you point it at. Exit codes
for both: 0 clean, 1 warnings, 2 errors.
