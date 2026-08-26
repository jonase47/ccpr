# Memory Schema

> Formal frontmatter schema for memory files. Applies to Tier 1 (`docs/memory/{type}_{slug}.md`)
> and Tier-2 topic files (`docs/memory/{agent}/{topic}.md`).
> Indexes (`docs/memory/MEMORY.md` and `docs/memory/{agent}/MEMORY.md`) follow their own
> template convention and do not require frontmatter (they are lists, not memories) — but
> "do not require" means what it says: an index MAY carry a frontmatter block, and when it
> does, `bash ~/.claude/scripts/memory-lint.sh` validates its fields, `type`, `last_updated`
> and `related:` cross-refs the same way it would for any other memory file, instead of
> skipping it by filename (WI-0108) — with ONE exception: the Tier-1 `{type}_{slug}.md`
> naming convention below does not apply to `docs/memory/MEMORY.md` itself, since it is the
> index, not a Tier-1 memory file. An index with no frontmatter stays silent either way.

## Required fields

| Field | Values | Description |
|---|---|---|
| `name` | free text (1 line) | Human-readable title — also visible in the index. |
| `description` | free text (1 line) | One-sentence summary. Used for relevance decisions. |
| `type` | Tier 1: `feedback` \| `project` \| `reference` \| `user` \| `index`. Tier 2: the same set, plus `patterns` (a persona's general working conventions, not tied to one project fact). | Memory category (see `~/.claude/CLAUDE.md`). `user` stays global, not pushable. `index` is for `docs/memory/MEMORY.md` / `docs/memory/{agent}/MEMORY.md` files that chose to carry a frontmatter block (WI-0108) — it says "this file is the list, not a memory record", distinct from `project`/`reference`/etc. The Tier-2 vocabulary is deliberately open: `bash ~/.claude/scripts/memory-lint.sh` only warns — never errors — on a Tier-2 `type` value outside this set, so a persona reaching for a value the schema has not yet named does not fail the lint. Tier 1 keeps the closed enum and errors on drift; `index` is a member of it, not an exception to it. |
| `last_updated` | `DD.MM.YYYY`, optionally followed by whitespace and a parenthesised note: `DD.MM.YYYY (note)` | Date of last substantive change. The note is optional and says **why** the date moved — which round, which item — e.g. `24.08.2026 (WI-0102)` or `16.05.2026 (Note: agent migration verified later same day)`. That is context no other field carries, which is why the suffix is part of the schema rather than tolerated beside it (WI-0106); the same optional suffix is specified for phase documents in `PHASE_DOC_SCHEMA.md`. Enforceable form: the date, then either end-of-value or one or more spaces followed by a single `(` … `)` group running to the end — everything inside the parentheses is free text. A value shaped otherwise (`24.08.2026 a note without parentheses`, `24.08.2026(WI-0102)`, `24.08.2026 (unclosed`, `2026-08-24`) is an error, and so is a well-formed date that is not a day (`32.13.2026`). Checked by `bash ~/.claude/scripts/memory-lint.sh`, check (e). |

## Optional fields

| Field | Values | Description |
|---|---|---|
| `status` | `active` (default) \| `superseded` \| `archived` | Manual status marker. `archived`/`superseded` suppress lint's stale-age warning (WI-0074) — they mean "intentionally no longer maintained". There is no `stale` value: lint's warning names the file's age, it does not ask for a status label that only restates it. |
| `related` | YAML list (inline `[a.md, b.md]` or block) | Paths to related memory files, **relative to the file's own directory**. Cross-refs are checked by lint. |
| `confidence` | float `0.3` … `0.9` | Instincts (behavioral rules) only. See `~/.claude/instincts.md`. |

## Naming convention

- Tier 1 (cross-cutting): `docs/memory/{type}_{slug}.md` — e.g. `feedback_wording.md`, `project_watch_penetration.md`, `reference_apple_review_guidelines.md`.
- Tier 2 (persona-specific): `docs/memory/{agent}/{topic}.md` — topic slug is freely chosen (e.g. `patterns.md`, `swiftdata-tdd-patterns.md`).
- `docs/memory/MEMORY.md` itself is exempt from the Tier-1 `{type}_{slug}.md` rule even when it
  carries `type: index` — it is the index the rule's `{type}_` prefix would otherwise misfile
  it into looking for (`index_MEMORY.md`), not a Tier-1 memory file.

## Instinct ID namespaces

Instincts (behavioral rules, `confidence` field) carry a stable ID. The prefix encodes **scope and
provenance** so IDs from different sources never collide and re-syncs stay idempotent:

| Namespace | Scope | Maintained by |
|---|---|---|
| `G-NNN` | native global Tier-1 (all projects, all agents) | your own `/postmortem` decay/bump clock |
| `{XX}-G-NNN` | native global Tier-2 persona silo (e.g. `SD-G-`, `DV-G-`, `SM-G-`) | your own clock, one persona |
| `P-NNN` | project-scoped instinct | your own clock, one project |
| `{SRC}-G-NNN` / `{SRC}-{XX}-G-NNN` | **imported foreign-contributor** overlay (e.g. `OL-` from a teammate's repo) | the source repo; **not** touched by your decay clock. Keeps the source's original number, confidence, date. Each imported file carries a Contributor Register + re-sync recipe in its header. |
| `{ORG}-G-NNN` / `{ORG}-{XX}-G-NNN` | **shared org-tier** overlay — team-maintained knowledge synced from a shared repo (see `scripts/memory-sync.sh`) | the shared repo; updated by push, not by any single member's decay clock. |

Rules:
- Native and prefixed IDs **never collide by namespace** — the same number can mean different things
  across sources (native `G-081` ≠ imported `OL-G-081`).
- When you independently confirm an imported/shared pattern on your own stack, either add a
  `confirmed:` note on the overlay entry, or adopt it as a fresh native `G-NNN` with `supersedes: {SRC}-G-NNN`.
- Overlay files (imported + org-tier) are materialized read-only; edit them at the source, not in place.

## Body structure

Recommended for `feedback` and `project` (described in `~/.claude/CLAUDE.md`):

```
{Rule or fact — 1–3 sentences}

**Why:**
{Context, rationale, background}

**How to apply:**
- {Decision guidance for future sessions}
- {Edge cases, limits}
```

For `reference` (pointer to external resources): brief note + link/source.

## Example (Tier 1, type `feedback`)

```markdown
---
name: Copy strictly wellness-focused, no medical or therapeutic claims
description: ExampleApp texts (UI, docs, marketing, App Store) refer exclusively to wellness tracking — never to medical outcomes, treatment, or therapeutic effects.
type: feedback
last_updated: 25.04.2026
status: active
related:
  - project_apple_review_risk.md
---

Every text in ExampleApp — UI copy, onboarding, notifications, …

**Why:** App Store review policy prohibits unsubstantiated health claims. …

**How to apply:**
- Apply this filter to every user-facing or public-facing copy …
- App description & screenshots: wellness and habit-tracking features only …
```

## Lint

`bash ~/.claude/scripts/memory-lint.sh [<project-dir>]` validates this schema. Exit codes: 0 clean, 1 warnings, 2 errors, 3 configuration error (the run produced no report). See report format in `MEMORY_LINT_REPORT_TEMPLATE.md`.
