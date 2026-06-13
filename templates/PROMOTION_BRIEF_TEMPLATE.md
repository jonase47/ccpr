# Promotion Brief Template

> Formal schema for `docs/PROMOTION_BRIEF.md` — bridge document between Lean-Track and Full-Track.
> Created by `/lean-promote`; read by `/project-init` as bootstrap input.

## Required Fields

| Field | Values | Description |
|---|---|---|
| `kind` | `promotion-brief` | Doc-type marker. |
| `generated_from` | `lean-track` | Source of the promotion. |
| `last_updated` | `DD.MM.YYYY` | Creation date. |
| `trigger` | `promote-decision` \| `mid-flight-1` \| `mid-flight-2` \| … \| `mid-flight-5` | What triggered the promotion (decision from `/lean-learn` or promotion trigger 1–5). |
| `code_baseline_commit` | SHA | Commit hash at which the promotion is anchored. |

## Optional Fields

| Field | Values | Description |
|---|---|---|
| `related` | YAML list | FRAME.md, LEARNINGS.md, TRACK_DECISION.md (archived but still referenced). |

## Sections (Required Order)

```markdown
---
kind: promotion-brief
generated_from: lean-track
trigger: {promote-decision | mid-flight-N}
code_baseline_commit: {SHA}
last_updated: DD.MM.YYYY
related:
  - lean-archive/FRAME.md
  - lean-archive/LEARNINGS.md
  - lean-archive/TRACK_DECISION.md
---

# Promotion Brief – {Project-Name}

## 1. Validated Findings

Findings backed by evidence from LEARNINGS.md that feed into Full-Track phases:
- {Finding 1 — with evidence reference}
- …

## 2. Confirmed Assumptions

Assumptions from FRAME.md that held. Carried forward as input for P0/P1/P3:
- {Assumption} → relevant for: {P0-problem | P1-features | P3-techstack | …}
- …

## 3. Refuted Assumptions

Assumptions that failed in Lean-Track. Full-Track must NOT carry them forward:
- {Assumption} → Lessons: {…}
- …

## 4. Open Questions

What did Lean leave unanswered? Input for deeper investigation in Full-Track:
- {Question} → resolve in: {P0 | P1 | P2 | …}
- …

## 5. Code Anchors

Module status for Full-Track adoption:

| Module / File | Status | Rationale |
|---|---|---|
| `src/…/foo.py` | working | Hypothesis-validated, can be adopted |
| `src/…/bar/` | needs-rebuild | Quick-and-dirty, Full-Track should reimplement cleanly |
| `src/…/baz.py` | needs-tests | Functionally OK, but test coverage insufficient |

## 6. Constitution Candidates

Lean constraints from FRAME.md section 6 that should be adopted as Inviolable/Default in `docs/CONSTITUTION.md`:

- **{Short-Name}** (proposed: Inviolable): {Rationale}
- **{Short-Name}** (proposed: Default): {Rationale}

`/project-init` will call `/constitution` — feed these candidates into it.

## 7. Catch-Up Obligations

Full-Track topics not addressed during Lean that must be completed. Created as BACKLOG stories by `/project-init`:

- [ ] `/p0-regulatory` — regulatory check (e.g. clarify BFSG scope)
- [ ] `/p1-privacy` — DSGVO data classification
- [ ] `/p3-security` — threat model + auth concept
- [ ] `/p3-ux-a11y` — A11y concept (concrete WCAG level)
- [ ] `/p6-audit` — security audit + dependency check
- [ ] `/p6-a11y` — A11y check
- [ ] {additional project-specific items}

```

## Size Limit

- Target size: ≤10 KB.
- If the brief grows too long → the Lean-Track was probably too long; promotion should have happened earlier.

## Archiving Rules

`/lean-promote` archives the following when generating the brief:

```
docs/FRAME.md           → docs/lean-archive/FRAME.md
docs/LEARNINGS.md       → docs/lean-archive/LEARNINGS.md
docs/CLAUDE-lean.md     → docs/lean-archive/CLAUDE-lean.md
docs/TRACK_DECISION.md  → stays in place (Full-Track continues to read from it)
```

On pivot versions, existing archives are not overwritten (FRAME_v1.md is preserved).
