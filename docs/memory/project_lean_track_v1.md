---
name: Lean-Track + Constitution + Cross-Check ratified (v1)
description: The CCPR distribution was extended on 13.05.2026 with the Lean-Track (4 skills), the Constitution artefact (mandatory in Full-Track), and Cross-Check (optional pre-gate). Command count 109 → 115.
type: project
last_updated: 13.05.2026
status: active
related:
  - ../../Manual/LEAN_TRACK.md
  - project_repo_conventions.md
---

Lean-Track + Constitution + Cross-Check were ratified on **13.05.2026** in a single-session wave (session `943997b1`). CCPR command count: 109 → **115**. The distribution repo sits on `d5e5e08..633dcdc` (main).

**Why:** comparison with an external spec-driven development framework led to the realisation that the existing Full-Track (P0–P8) is overkill for prototypes / PoCs / tech spikes. The Lean-Track was introduced as a parallel line with a clear bridge to the Full-Track via `/lean-promote → /project-init`. The Constitution artefact + Cross-Check are additional mechanisms that are also valuable inside the Full-Track.

**How to apply:**

- **For new projects**: run `/track-decision` first — it chooses between Lean and Full based on knockouts (K1–K5: GDPR PII, special data categories, launch-imminent, BFSG/regulatory, external stakeholders) and the indicator score (I1–I5). **No downgrade Full → Lean** — reassessment is allowed, but once Full, always Full.
- **Lean-Track**: 4 skills (`/lean-frame`, `/lean-learn`, `/lean-promote` + entry point `/track-decision`), no gates, no BACKLOG/SPRINT. The single source of truth is `docs/FRAME.md` (max. 5 KB, 8 sections). Slim `docs/CLAUDE-lean.md` instead of the full CLAUDE.md.
- **Full-Track**: P0–P8 as before, plus `docs/CONSTITUTION.md` as a mandatory artefact. `/project-init` calls `/constitution` automatically. The constitution has three sections (Inviolable / Default / Aspirational). All gates (P0–P7) read the Inviolable section via `gate-preflight.py constitution_check` as a mandatory input. Violation = **"Inviolable breach"** = no-go signal in the gate verdict.
- **Constitution modes**: greenfield (5 domain bootstraps: saas-b2c, mobile-b2c, b2b-tool, b2c-marketplace, on-device-privacy), Lean precursor (reads FRAME.md Constitution-Light), existing Full-Track (reads ADRs, REGULATORY.md, A11Y.md, SECURITY.md, NFR.md).
- **Mid-flight promotion triggers (Lean → Full)**: PII of real people lands in the system, lifetime >3 months, stakeholder demands gates, compliance audit announced, codebase >5,000 LOC.
- **Pivot variants (in `/lean-learn`)**: soft pivot (code stays, FRAME → `lean-archive/FRAME_v{N}.md`) or hard pivot (code + FRAME → `lean-archive/v{N}/`).
- **Cross-Check (`/cross-check`)**: optional pre-gate step with 7 initial rules (features ↔ auth, tech-stack ↔ data-model, threats ↔ mitigations, NFR ↔ tests, ADR status ↔ components, constitution ↔ ADRs, stories ↔ epics). Output: `docs/.cross-check-report.md` (volatile, in `.gitignore`).

**Test applications (real-project validation):**
- **ExampleApp**: Constitution v1.0 ratified on 13.05.2026 (`docs/CONSTITUTION.md`, ~6.4 KB, 5 inviolables: EXIF strip + local-only + zero 3rd-party + WCAG 2.2 AA + App Store copy must not make medical or therapeutic claims). Consolidated ADRs + NFR.md + P0 regulatory decisions.
- **Second real-world project**: Constitution v1.0 ratified on 13.05.2026 (`docs/CONSTITUTION.md`, ~7.1 KB, 5 inviolables: on-device-first + data ≠ model + WCAG 2.1 AA + GDPR mitigation + EU AI Act Art. 50). Expected MINOR bumps in P2/P3: concretise latency budget A-16, firm up licensing strategy after legal review.

**Volatile outputs (in `.gitignore` of all Full-Track projects)**:
- `docs/.gate-preflight-pX.md` (gate-preflight.py)
- `docs/.session-context.md` (bootstrap.sh)
- `docs/.quality-scan-report.json` (quality-scan.sh)
- `docs/.cross-check-report.md` (cross-check skill)

## Related

- [LEAN_TRACK.md](../../Manual/LEAN_TRACK.md) — complete spec (decision tree, Lean-Track design, adaptations, implementation order)
- [Repo conventions](project_repo_conventions.md) — language convention (English in CCPR) led to the Full-Track terminology rename on the same day

<!-- type=project: ongoing decision/context for the CCPR distribution itself. Should be maintained with MINOR/MAJOR bumps of the constitution or extensions of the cross-check rule catalogue. -->
