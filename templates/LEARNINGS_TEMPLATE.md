# Learnings Template

> Formal schema for `docs/LEARNINGS.md` — validation and decision document at the end
> of a Lean-Track cycle. Created by `/lean-learn`.

## Required Fields

| Field | Values | Description |
|---|---|---|
| `kind` | `learnings` | Doc-type marker. |
| `track` | `lean` | Lean-Track indicator. |
| `decision` | `promote` \| `pivot-soft` \| `pivot-hard` \| `drop` | Validation result. |
| `last_updated` | `DD.MM.YYYY` | Date of the decision. |

## Optional Fields

| Field | Values | Description |
|---|---|---|
| `pivot_version` | Integer | On pivot: which version is being archived (counts alongside FRAME `pivot_version`). |
| `related` | YAML list | Paths to FRAME.md, code pointers, etc. |

## Sections (required order)

```markdown
---
kind: learnings
track: lean
decision: {promote|pivot-soft|pivot-hard|drop}
last_updated: DD.MM.YYYY
related:
  - FRAME.md
---

# Learnings – {Project Name}

## 1. Hypothesis Check

**Original hypothesis** (from FRAME.md): {…}

**Result:** {confirmed | refuted | unclear}

**Evidence:** {concrete data points, observations, user feedback — not "gut feeling"}

## 2. What works?

- {Factual observation 1}
- {Factual observation 2}
- …

## 3. What does not work?

- {Observation}: {Suspected cause}
- …

## 4. Surprises

What was unexpected?
- {Surprise 1}
- …

## 5. Decision

**Result:** {PROMOTE | PIVOT (Soft) | PIVOT (Hard) | DROP}

**Rationale:** {2–3 sentences}

---

### On PIVOT (Soft or Hard) — Module table

| Module / File | Status | Rationale |
|---|---|---|
| `src/…/foo.py` | keep | Hypothesis-independent, functionally correct |
| `src/…/bar/` | refactor | Logic OK, interface must change |
| `src/…/baz.py` | rebuild | Incorrect base assumption |

On **Soft-Pivot**: senior-developer works through the table; the old `FRAME.md` becomes `lean-archive/FRAME_v{N}.md`.

On **Hard-Pivot**: the table serves as lessons-learned documentation. All code moves to `lean-archive/v{N}/code/` (or branch `lean-archive/v{N}`).

---

### On PROMOTE — Next steps

→ Run `/lean-promote`. `docs/PROMOTION_BRIEF.md` is created and serves as input for `/project-init`.

---

### On DROP

Repo is frozen. `LEARNINGS.md` remains as a lessons-learned archive. Optional: set code tag `lean-final`.
```

## Size limit

- Target size: ≤8 KB. If exceeded, condense — LEARNINGS is a decision with evidence, not a report.

## Rules

- **Evidence over opinion:** Every "works"/"does not work" point requires an observation, not just a feeling.
- **Surprises honestly:** If nothing was surprising, the hypothesis was probably too weak. Document it anyway.
- **Module table only on Pivot:** Omit for PROMOTE/DROP.
