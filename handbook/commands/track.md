---
kind: commands-doc-detail
parent_index: ../SECTIONS_COMMANDS.md
section: track-skills
last_updated: 26.08.2026
---

# Track Skills (cross-cutting, 6 commands)

Entry-point and cross-cutting commands. `/track-decision` runs first; the others compose Lean-Track / Full-Track / consistency checks.

| Command | Title | Description |
|---|---|---|
| `/track-decision` | Decide Lean vs. Full-Track (or reassess) | Prerequisite check + Knockout (K1–K5) + Indicator score (I1–I5). Determines Lean (prototype/PoC/spike) or Full (P0–P8). Also for mid-flight reassessment. No downgrade Full → Lean. |
| `/constitution` | Create or revise the project Constitution | Creates `docs/CONSTITUTION.md` with Inviolable/Default/Aspirational. Hybrid mode: greenfield with domain bootstrap, existing Full-Track reads phase docs, Lean precursor reads FRAME. Read as mandatory input by all gates. |
| `/lean-frame` | Create Lean-Track Single-Source-of-Truth | Creates `docs/FRAME.md` (max. 5 KB, 8 sections) + `docs/CLAUDE-lean.md`. Replaces the P0+P1+P3 conception work for prototypes. |
| `/lean-learn` | Validate Lean-Track and make a decision | Creates `docs/LEARNINGS.md` with hypothesis check and decision PROMOTE/PIVOT-soft/PIVOT-hard/DROP. On pivot: module table (keep/refactor/rebuild). |
| `/lean-promote` | Promote Lean → Full-Track via Promotion Brief | Creates `docs/PROMOTION_BRIEF.md` (7 sections) as bootstrap input for `/project-init`. Archives FRAME/LEARNINGS/CLAUDE-lean to `docs/lean-archive/`. |
| `/cross-check` | Cross-Artifact Consistency Check Across Phases | Checks inconsistencies across phases (features ↔ auth, NFR ↔ tests, ADRs ↔ Constitution, …). 7 rules initially, growing iteratively. Recommended before gates. |
