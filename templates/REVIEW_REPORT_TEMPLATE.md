---
kind: review
sprint: {{N}}
base_commit: {{sprint-base-sha}}
reviewed_head: {{HEAD-sha}}
reviewer: code-reviewer @ opus
last_updated: {{DD.MM.YYYY}}
---

<!-- New reports always write `base_commit` — this template prescribes one
     form, not a choice (WI-0072 correction, 22.08.2026). `phase-docs-lint.sh`
     ALSO accepts `reviewed_base` for the same field, purely so grown corpora
     that already wrote it under that name are not forced into a rewrite —
     do not "clean up" this template to accept either name; the point of a
     template is to prescribe one. -->

# Sprint {{N}} — Holistic Code Review (code-reviewer @ opus)

## Verdict

<!-- 2-3 sentences: overall posture, biggest risk. -->

## Findings

| # | Severity | Scope | Finding | Direction |
|---|---|---|---|---|

<!-- Severity: CRITICAL (correctness/security blocker), HIGH (fix before gate), MEDIUM, LOW.
     Scope: cross-story / schema / conformance / async / test. -->

## Conformance

- Inviolables: <!-- each — OK / BREACH + which story -->
- ADRs touched: <!-- each — consistent / drift -->

## Instinct candidates

<!-- Any whole-context pattern worth encoding as a new instinct: rule + why + a suggested
     confidence. Suggest only — do not write the instinct file from here. -->

## Confirmed positives

<!-- What the sprint did well at the architectural level — preserve these. -->
