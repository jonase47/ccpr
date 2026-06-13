---
name: {{Descriptive title — visible in the index}}
description: {{One-sentence summary — used for relevance decisions}}
type: {{feedback|project|reference|user}}
last_updated: {{DD.MM.YYYY}}
status: active
related:
  - {{path/to/related-file.md}}
---

{{Rule or fact — 1–3 sentences, the core of this memory entry.}}

**Why:**
{{Context, rationale, background. What triggered this? Which incident, discussion, or constraint?}}

**How to apply:**
- {{When does this rule apply? In which skill contexts?}}
- {{Edge cases, limits, exceptions}}
- {{On conflict with other rules: which takes precedence?}}

## Related

- [{{related-file Titel}}]({{path/to/related-file.md}})

<!-- Type-specific notes:

  type=feedback   → Behavior rule (explicitly set or confirmed by the user).
  type=project    → Ongoing work, decisions, context (stakeholder decision, hypothesis, assumption).
  type=reference  → Pointer to external resources (Linear project, Grafana board, …).
  type=user       → Stays in global memory, not pushable. Do not commit to the project repo.

  If `related:` is empty, the `## Related` section and field may be omitted.
-->
