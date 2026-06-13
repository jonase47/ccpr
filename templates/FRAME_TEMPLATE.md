# Frame Template

> Formal schema for `docs/FRAME.md` — the Single-Source-of-Truth of a Lean-Track project.
> One screen, one truth. Created by `/lean-frame`.

## Required fields

| Field | Values | Description |
|---|---|---|
| `kind` | `frame` | Doc-type marker. |
| `track` | `lean` | Lean-Track indicator. |
| `status` | `active` \| `archived` | `active` = running Lean-Track. `archived` = after promotion/drop into `lean-archive/`. |
| `last_updated` | `DD.MM.YYYY` | Date of last substantive change. |

## Optional fields

| Field | Values | Description |
|---|---|---|
| `pivot_version` | Integer | Incremented on soft/hard pivot (FRAME_v1, FRAME_v2, …). |
| `related` | YAML list | Paths to `TRACK_DECISION.md`, `CONSTITUTION.md` (if created), …. |

## Sections (required order)

```markdown
---
kind: frame
track: lean
status: active
last_updated: DD.MM.YYYY
related:
  - TRACK_DECISION.md
---

# Frame – {Project-Name}

## 1. Problem
{1–2 sentences: which problem, for whom?}

## 2. Hypothesis
{1 sentence: what do we believe the prototype will prove or disprove?}

## 3. Demo-Audience
{3–5 people / personas: who tests it, how does feedback arrive?}

## 4. MVP-Scope
**In (max. 5 bullets):**
- …

**Deliberately out (max. 5 bullets):**
- …

## 5. Tech-Stack
- **Language/Framework:** {…} — {rationale in 1 line}
- **Data storage:** {…} — {rationale}
- **Other dependencies:** {keep minimal}

## 6. Constitution-Light
3–5 hard limits for this prototype:
- {e.g. "No PII, not even in logs"}
- {e.g. "Local only, no deploy"}
- {e.g. "No auth — static token if needed"}

> If this list wants to grow beyond 5 bullets → call `/constitution` and create a full
> `docs/CONSTITUTION.md`. FRAME then references CONSTITUTION.md.

## 7. Risk Assumptions
- **What can fail?** {list of risks — technical, domain, regulatory}
- **What must work without fail?** {make-or-break assumptions}

## 8. Promotion-Trigger
(Copy from `TRACK_DECISION.md` — mid-flight triggers that force Full-Track)
1. First real user with PII enters the system
2. Lifetime assumption breaks (prototype lives >3 months)
3. External stakeholder demands roadmap/gate delivery
4. Compliance request or audit announced
5. Codebase exceeds ~5,000 LOC
```

## Size limit

- **Hard cap:** 5 KB. If larger → either trim scope (FRAME is Single-Source, not a spec collection)
  or promote to Full-Track.
- `doc-volume-check.sh` warns at 5 KB for Lean files.

## Pivot behaviour

- **Soft pivot** (same tech base): `FRAME.md` → `lean-archive/FRAME_v1.md`, new FRAME.md with `pivot_version: 2`.
- **Hard pivot** (tech reset): `FRAME.md` → `lean-archive/v1/FRAME.md`, new FRAME without `pivot_version` (fresh start).

`/lean-learn` produces a module table on pivot that serves as a reference in the new FRAME.
