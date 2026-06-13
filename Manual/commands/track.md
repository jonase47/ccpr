---
kind: commands-doc-detail
parent_index: ../SECTIONS_COMMANDS.md
section: track-skills
last_updated: 15.05.2026
---

# Track Skills (cross-cutting, 6 commands)

Entry-point and cross-cutting commands. `/track-decision` runs first; the others compose Lean-Track / Full-Track / consistency checks.

| Command | Title | Description |
|---|---|---|
| `/track-decision` | Decide Lean vs. Full-Track (or reassess) | Prerequisite check + knockout (K1–K5) + indicator score (I1–I5). Determines Lean (prototype/PoC/spike) or Full (P0–P8). Also for mid-flight reassessment. No downgrade Full → Lean. |
| `/constitution` | Create or update the project constitution | Creates `docs/CONSTITUTION.md` with Inviolable/Default/Aspirational. Hybrid mode: greenfield with domain bootstrap, existing Full-Track reads phase docs, Lean precursor reads FRAME. Read as mandatory input by all gates. |
| `/lean-frame` | Lean-Track single source of truth | Creates `docs/FRAME.md` (max. 5 KB, 8 sections) + `docs/CLAUDE-lean.md`. Replaces the P0+P1+P3 conception work for prototypes. |
| `/lean-learn` | Validate the Lean-Track and decide | Creates `docs/LEARNINGS.md` with hypothesis check and decision PROMOTE/PIVOT-soft/PIVOT-hard/DROP. On pivot: module table (keep/refactor/rebuild). |
| `/lean-promote` | Promote Lean → Full-Track via promotion brief | Creates `docs/PROMOTION_BRIEF.md` (7 sections) as bootstrap input for `/project-init`. Archives FRAME/LEARNINGS/CLAUDE-lean under `docs/lean-archive/`. |
| `/cross-check` | Cross-artifact consistency check | Checks inconsistencies across phases (features ↔ auth, NFR ↔ tests, ADRs ↔ constitution, …). 7 rules initially, growing iteratively. Recommended before gates. |
