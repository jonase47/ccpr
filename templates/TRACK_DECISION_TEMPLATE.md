# Track Decision Template

> Formal schema for `docs/TRACK_DECISION.md` — documents the Lean-vs-Full decision
> (or a re-assessment) for a project. Created by `/track-decision` and extended on every
> re-assessment (history format).

## Required fields

| Field | Values | Description |
|---|---|---|
| `kind` | `track-decision` | Doc-type marker. |
| `current_track` | `lean` \| `full` | Currently active Track after the last decision. |
| `last_updated` | `DD.MM.YYYY` | Date of the last decision. |

## Optional fields

| Field | Values | Description |
|---|---|---|
| `re_assessment_count` | Integer | Number of re-assessments since the initial decision. |

## Body structure

The file contains one entry per decision (newest on top). Each entry documents
the prerequisite check, Knockout answers, Indicator score, and rationale.

```markdown
---
kind: track-decision
current_track: {lean|full}
last_updated: DD.MM.YYYY
re_assessment_count: 0
---

# Track Decision – {Project Name}

## Decision #{N} – DD.MM.YYYY

**Result:** {Lean | Full}
**Trigger:** {Initial-Decision | Mid-Flight Re-Assessment: <reason>}

### Prerequisite

- [ ] Solo or mini-team (≤3 people) — {yes/no}
- [ ] Goal: validate/learn/tech-spike — not ship — {yes/no}
- [ ] Data: mock / test data / own demo data — {yes/no}
- [ ] Runs locally or on a non-public URL — {yes/no}

→ All 4 met? {yes/no}. If **no** → Track = Full, further checks skipped.

### Knockout questions (1× yes = Full)

| # | Question | Answer |
|---|---|---|
| K1 | Personal data (Art. 4 DSGVO) — including logs/analytics/test accounts? | {yes/no} |
| K2 | Special categories of data (Art. 9 DSGVO)? | {yes/no} |
| K3 | Production launch in <4 weeks, public or for third parties? | {yes/no} |
| K4 | Regulatory scope (BFSG / KRITIS / MDR / BaFin / sector-specific)? | {yes/no, if applicable which regulation} |
| K5 | External stakeholders with sign-off authority? | {yes/no} |

→ At least 1× yes? {yes/no}. If **yes** → Track = Full.

### Indicator score (only when all Knockouts are "no")

| # | Question | Point |
|---|---|---|
| I1 | Planned lifespan >3 months? | {0/1} |
| I2 | Team growth foreseeable? | {0/1} |
| I3 | Complex business logic (pricing, workflows, permissions)? | {0/1} |
| I4 | Architecture decision non-trivial? | {0/1} |
| I5 | Investor/management communication required? | {0/1} |

**Total:** {0–5}. ≥2 → Full, otherwise → Lean.

### Rationale

{Free text: 2–3 sentences. Which factors were decisive? Which assumptions underlie the decision?}

### Promotion triggers (active for Lean-Track)

As soon as *any one* of these occurs → re-run `/track-decision` immediately:
1. First real user with PII enters the system
2. Lifespan assumption breaks (prototype lives >3 months)
3. External stakeholder demands roadmap/Gate delivery
4. Compliance request or audit announced
5. Codebase exceeds ~5,000 LOC

---

## Decision #{N-1} – DD.MM.YYYY
{previous entry, if re-assessment}
```

## Rules

- **No downgrade Full → Lean.** If a re-assessment results in Full-Track, it stays Full-Track.
- **Preserve history:** Earlier decisions are not deleted; they are shifted downward.
- **Date order:** Newest entry on top.

## Size limit

- Target size: ≤10 KB. With more than 5 re-assessments, move the oldest entries to `docs/lean-archive/TRACK_DECISION_OLD.md`.
