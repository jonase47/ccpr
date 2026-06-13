# Constitution Template

> Formal schema for `docs/CONSTITUTION.md` — the project constitution, which is mandatory reading in every Full-Track project
> and can optionally be extended in Lean-Track projects.
>
> Content is split into three parts: **Inviolable** (non-negotiable), **Default** (standard, deviate with justification),
> **Aspirational** (aspirational targets). Gate commands read the Inviolable section as a mandatory input; ADRs must
> explicitly address any conflict with it.

## Required Fields

| Field | Values | Description |
|---|---|---|
| `kind` | `constitution` | Doc-type marker. Constitution is neither a phase doc nor memory — it has its own type. |
| `status` | `draft` \| `active` \| `archived` | `draft` = not yet ratified. `active` = binding. `archived` = superseded by a version bump. |
| `version` | `MAJOR.MINOR` | Semver-light: MAJOR on Inviolable change, MINOR on Default/Aspirational change. |
| `last_updated` | `DD.MM.YYYY` | Date of the last substantive change. |

## Optional Fields

| Field | Values | Description |
|---|---|---|
| `track` | `full` \| `lean` | When set: indicates which Track the Constitution was created for. |
| `bootstrap` | Domain slug | e.g. `saas-b2c`, `mobile-b2c`, `b2b-tool`, `b2c-marketplace`, `on-device-privacy`. Only set when the Constitution was generated via `/constitution` domain bootstrap. |
| `related` | YAML list | Paths to source documents (ADRs, regulatory.md, briefing.md, …) that feed this Constitution. |

## Sections (Required Order)

### 1. Inviolable (Non-Negotiable)

Hard limits that **must not** be broken without a Constitution change. This section is mandatory reading for all Gates. Typical examples:
- DSGVO obligations (Art. 25, Art. 32, Art. 9)
- BFSG/A11y minimum standard (WCAG level)
- Data security (no secrets in code, no PII in logs)
- Architecture guardrails marked "inviolable" by ADR
- Sector-specific obligations (KRITIS, MDR, BaFin, EU AI Act)

Format per bullet: `**Short-Name:** Rule. Rationale. {Reference: ADR-XXX | Art. X DSGVO | …}`

### 2. Default (Deviate with Justification)

Standards from which you may **deviate with justification**. Deviation requires an ADR or documented discussion. Typical examples:
- Tech stack (language, framework, DB)
- TDD discipline, coding style
- Language (UI/Docs)
- Platform targets (iOS/Android/Web)
- Monetization pattern (Freemium, IAP, Subscription)

Format per bullet: `**Short-Name:** Default. When is it appropriate to deviate? {Who decides?}`

### 3. Aspirational

Targets that are measured but do not trigger a hard failure. Typical examples:
- Test coverage threshold
- Performance budget (latency, bundle size)
- A11y audit quality
- Minimum user research sample (e.g. n=30 beta testers)
- Adoption/engagement KPIs

Format per bullet: `**Short-Name:** Target value. Measurement method. {Review frequency}`

## Versioning

- **Patch change** (typo, clarification): no version bump, update `last_updated` only.
- **MINOR bump**: new Default/Aspirational bullet, or an existing one relaxed.
- **MAJOR bump**: Inviolable change (add, remove, tighten, or relax). Requires ADR.

Version history is tracked via Git log. Optional: add a `## Changelog` section at the end of the file
for a human-readable summary of MAJOR/MINOR bumps.

## Body Structure (Example Skeleton)

```markdown
---
kind: constitution
status: active
version: 1.0
last_updated: DD.MM.YYYY
track: full
related:
  - docs/architecture/ADR/ADR-0001-xxx.md
  - docs/discovery/REGULATORY.md
---

# Constitution – {Project-Name}

## Inviolable (Non-Negotiable)

- **{Short-Name}:** {Rule}. {Rationale}. {Reference}
- …

## Default (Deviate with Justification)

- **{Short-Name}:** {Default}. {When to deviate?}. {Who decides?}
- …

## Aspirational

- **{Short-Name}:** {Target value}. {Measurement method}. {Review frequency}
- …

## Changelog (optional)

- **v1.0** (DD.MM.YYYY): Initial ratification.
```

## Size limit

- Target size: ≤8 KB. `doc-volume-check.sh` warns at ≥25 KB.
- If the Inviolable section grows large (>10 bullets), verify that each item is truly non-negotiable.
  When in doubt, move it to Default.

## Gate Integration

- `gate-preflight.py` extracts the Inviolable section into `docs/.gate-preflight-pX.md`
- All `/gate-pX` commands read Inviolable as a mandatory input
- If a phase decision violates Inviolable: the gate verdict is marked "Inviolable breach"

## Lint

Constitution is checked by a dedicated lint extension:
- All required fields present
- All three sections present (Inviolable, Default, Aspirational)
- Size ≤25 KB (hard cap)
- When `status: active`, at least 1 Inviolable bullet must exist
