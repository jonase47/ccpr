# Memory Schema

> Formal frontmatter schema for memory files. Applies to Tier 1 (`docs/memory/{type}_{slug}.md`)
> and Tier-2 topic files (`docs/memory/{agent}/{topic}.md`).
> Indexes (`docs/memory/MEMORY.md` and `docs/memory/{agent}/MEMORY.md`) follow their own
> template convention and do not require frontmatter (they are lists, not memories).

## Required fields

| Field | Values | Description |
|---|---|---|
| `name` | free text (1 line) | Human-readable title — also visible in the index. |
| `description` | free text (1 line) | One-sentence summary. Used for relevance decisions. |
| `type` | `feedback` \| `project` \| `reference` \| `user` | Memory category (see `~/.claude/CLAUDE.md`). `user` stays global, not pushable. |
| `last_updated` | `DD.MM.YYYY` | Date of last substantive change. |

## Optional fields

| Field | Values | Description |
|---|---|---|
| `status` | `active` (default) \| `stale` \| `superseded` \| `archived` | Manual status marker. `stale` is suggested automatically by lint when `last_updated` is older than 90 days. |
| `related` | YAML list (inline `[a.md, b.md]` or block) | Paths to related memory files, **relative to the file's own directory**. Cross-refs are checked by lint. |
| `confidence` | float `0.3` … `0.9` | Instincts (behavioral rules) only. See `~/.claude/instincts.md`. |

## Naming convention

- Tier 1 (cross-cutting): `docs/memory/{type}_{slug}.md` — e.g. `feedback_wording.md`, `project_watch_penetration.md`, `reference_apple_review_guidelines.md`.
- Tier 2 (persona-specific): `docs/memory/{agent}/{topic}.md` — topic slug is freely chosen (e.g. `patterns.md`, `swiftdata-tdd-patterns.md`).

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

`bash ~/.claude/scripts/memory-lint.sh [<project-dir>]` validates this schema. Exit codes: 0 clean, 1 warnings, 2 errors. See report format in `MEMORY_LINT_REPORT_TEMPLATE.md`.
