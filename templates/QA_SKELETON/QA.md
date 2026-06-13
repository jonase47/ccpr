---
phase: P6
subskill: p6-functional
status: skeleton
last_updated: {{DD.MM.YYYY}}
related:
  - A11Y.md
  - AUDIT.md
  - FUNCTIONAL.md
  - PENTEST.md
  - AUTHZ.md
---

# Quality Assurance (P6) — Phase Index

**Status:** Skeleton — populated by `/p6-*` skills. Sub-indexes already exist as skeletons.

## Key Decisions

<!-- One-liners lifted by /p6-*-Sub-Skills, with link to sub-index. -->

## Open Risks / Open Questions

<!-- Critical items that /p6 must surface. -->

| Risk / Question | Severity | Status | Where to resolve |
|---|---|---|---|

## Sub-Indizes

| Sub-Index | File | Lead-Skill | Status |
|---|---|---|---|
| Accessibility | [A11Y.md](A11Y.md) | `/p6-a11y` | skeleton |
| Audit (SAST/Deps/DSGVO/Config/Auth) | [AUDIT.md](AUDIT.md) | `/p6-audit` | skeleton |
| Functional (Integration/E2E/Regression) | [FUNCTIONAL.md](FUNCTIONAL.md) | `/p6-functional` | skeleton |
| Pentest | [PENTEST.md](PENTEST.md) | `/p6-pentest` | skeleton |
| Authorization Tests | [AUTHZ.md](AUTHZ.md) | `/p6-pentest-authz` | skeleton |

## Gate Notes

<!-- Filled by /gate-p6 once all sub-skills complete. -->

**Sequence (per `~/.claude/docs/NEXT_STEPS_REFERENCE.md`):**
1. `/p6-functional` (Integration/E2E/Regression — Baseline-Tests)
2. `/p6-exploratory` (parallel zu Functional)
3. `/p6-a11y` (can run in parallel)
4. `/p6-audit` (sequential — requires Functional output)
5. `/p6-pentest` (sequential — requires Threat-Model + Audit)
6. `/p6-bugfix` (loop until QA-Gate and Security-Gate both pass)
