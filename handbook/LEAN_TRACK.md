# Lean-Track for CCPR

**Status:** Transient — sunset planned
**Date:** 13.05.2026
**Goal:** Optional Lean-Track running in parallel to the existing P0–P8 Full-Track, with a clear bridge into the Full-Track

> **Transient feature.** Lean exists primarily as a **fast-test shortcut for CCPR itself** — to dogfood the pipeline without paying the full P0–P8 cost. It also serves as preparatory work that bridges into the Full-Track via `/lean-promote`.
>
> **Sunset criterion:** Lean-Track is scheduled for removal once CCPR ships a stable v1.0 release (see future versioning ADR). Until then, treat Lean as a *temporary parallel pathway*, not a permanent track. Mandant/team projects should default to Full-Track from the start; Lean is for internal experimentation and bridge-only.

---

## 1. Motivation & scope

The full phase track (P0–P8) is overkill for:
- Solo prototypes
- Tech spikes / PoCs
- Hypothesis validation with mock data

The Lean-Track compresses P0 + P1 + P3 into a single "Frame" phase, skips P2/P4/P6/P7/P8, and keeps TDD discipline.

### Core elements

- **Lean-Track** with 4 skills + Constitution-Light in `FRAME.md`
- **Constitution** as a versioned project anchor in the Full-Track (`docs/CONSTITUTION.md`)
- **Cross-artifact consistency check** (`/cross-check`) as an optional pre-gate check
- **Clear bridge** between tracks via `/lean-promote` → `/project-init`

### Deliberately not introduced

- Issue sync to GitHub/Gitea (CCPR is markdown-first)
- Linear "one-shot Constitution → Implement" path (would weaken the sprint loop and evolution loop)
- A dedicated `/clarify` skill (functionally covered by `/cross-check`)

---

## 2. Decision tree: Lean vs. Full

### Prerequisite (otherwise Full, no further checks)
- Solo or mini team (≤3 people)
- Goal: validate, learn, tech spike — **not** ship
- Data: mock / test data / your own demo data
- Runs locally or on a non-public URL

### Phase A — knockout questions (1× Yes = Full, non-negotiable)

| # | Question | Reason |
|---|---|---|
| K1 | Personal data (Art. 4 GDPR) of real people — including logs, analytics, test accounts? | Retrofitting is expensive, deletion duty applies immediately |
| K2 | Special data categories (Art. 9) — health, biometric, religion, sexual orientation, union membership? | DPIA required from day one |
| K3 | Production launch in <4 weeks — public or accessible to third parties? | Cannot be released responsibly without P6/P7 |
| K4 | Regulatorily in scope? (see below) | Knockout check requires P0 |
| K5 | External stakeholders with sign-off rights (customer, client expecting gates)? | Lean produces no gate artefacts |

**K4 detail — scope reached if ONE applies:**
- **BFSG** (since 28.06.2025): B2C offer AND publicly / consumer-accessible AND in a BFSG sector (online shops, banking, passenger transport, e-books, telecommunications, hardware computing systems, ATMs/ticketing/check-in)
  - NOT BFSG: B2B tools, internal tools, closed pilot groups, solo demos, research spikes
- **KRITIS** (energy, water, health, finance, transport, ICT, food, waste disposal, state & administration)
- **MDR** (medical device under Regulation (EU) 2017/745, including software-as-medical-device)
- **BaFin supervision** (banking, insurance, payment services, crypto custody)
- **Other sector duties** (GwG, TKG, JuSchG/JMStV, ProdSG depending on domain)

### Phase B — indicator questions (score, 1 point each)

| # | Question | +1 if… |
|---|---|---|
| I1 | Planned lifetime | …>3 months |
| I2 | Team growth foreseeable | …hiring / outsourcing planned |
| I3 | Complex business logic | …pricing, workflows, permissions, state machines |
| I4 | Architectural decision non-trivial | …multiple competing approaches |
| I5 | Investor / management communication | …roadmap / reporting required |

### Decision output (binary)

- **0 KO + 0–1 points** → **Lean-Track**
- **0 KO + ≥2 points** → **Full-Track**
- **≥1 KO** → **Full-Track** (indicators irrelevant)

### Mid-flight promotion trigger (Lean → Full)

As soon as *one* of these hits → initiate promotion immediately:
1. First real user with PII lands in the system
2. Lifetime assumption breaks (prototype lives >3 months)
3. External stakeholder demands a roadmap / gate delivery
4. Compliance enquiry or audit announced
5. Codebase exceeds ~5,000 LOC (heuristic complexity marker)

### No downgrade

Full → Lean is **not foreseen**. Once knockouts or indicators are positive, they stay positive. Reassessment via `/track-decision` is allowed; it does not retroactively change the track decision.

*Rationale:* Lean is the **fast-test shortcut** (and bridge into Full), not a reframing path out of Full. Once a project commits to Full, the discipline of P0–P8 is the value; collapsing back to Lean would discard that investment without a clean process. If a Full project really turns out to be a throwaway spike, the correct action is to archive it explicitly — not to downgrade the track.

---

## 3. Lean-Track design

### Flow

```
/track-decision  →  Lean ok
       ↓
/lean-frame  →  docs/FRAME.md + docs/CLAUDE-lean.md  (+ optional /constitution)
       ↓
   Build (free, senior-developer + standard TDD loop, no dedicated skill)
       ↓
/lean-learn  →  docs/LEARNINGS.md  →  drop / pivot / promote
       ↓ (promote)
/lean-promote  →  docs/PROMOTION_BRIEF.md
       ↓
/project-init  →  reads promotion brief, adopts anchors, starts Full-Track from P0
```

### Skills (4)

| Skill | Purpose | Lead |
|---|---|---|
| `/track-decision` | Prerequisites + knockouts + indicators → Lean or Full | (no agent, interactive) |
| `/lean-frame` | Create FRAME.md + CLAUDE-lean.md, optionally trigger `/constitution` | konzeptor (support: system-architekt) |
| `/lean-learn` | LEARNINGS.md + decision drop/pivot/promote | konzeptor (support: business-analyst) |
| `/lean-promote` | PROMOTION_BRIEF.md as input for `/project-init` | konzeptor + project-planner |

**No `/lean-build`** — build runs freely with senior-developer and the standard TDD loop. Discipline comes from FRAME (scope, Constitution-Light) and HANDOVER, not from a skill.

### `docs/FRAME.md` — structure

YAML frontmatter (`track: lean`, `status: active`, `last_updated`) plus:
1. **Problem** (1–2 sentences)
2. **Hypothesis** (1 sentence: what will be proven/refuted?)
3. **Demo audience** (3–5 people, feedback source)
4. **MVP scope** (max. 5 bullets, explicitly also what is intentionally out)
5. **Tech stack** (3–5 lines with mini reasoning)
6. **Constitution-Light** (3–5 hard boundaries; if `/constitution` was invoked, reference it)
7. **Risk assumptions**
8. **Promotion trigger** (copy from `TRACK_DECISION.md`)

Max size: ~5 KB (one screen).

### `docs/CLAUDE-lean.md` — slim CLAUDE variant

**Keeps:**
- Language & communication
- Personal context (a11y, colour-vision deficiency, GDPR sensitivity)
- Code standards (TDD, conventional commits, date format)
- Reduced agent team: konzeptor, system-architekt, senior-developer, code-reviewer, debugger, tech-writer
- HANDOVER protocol (without Baseline mode)
- Instincts (global)
- Memory Tier 1 (sparingly)

**Drops:**
- Phase model P0–P8 + phase lead assignments
- Document-splitting convention + phase-docs-lint
- Next-steps reference
- Memory Tier 2 (agent silos)
- Pre-session bootstrap / gate-preflight / quality-scan hooks
- Task system rules (BACKLOG/SPRINT don't exist)

**Header:** "Lean-Track active — on promotion this file is replaced by the full CLAUDE.md. Lean artefacts move to `docs/lean-archive/`."

Estimated size: ~6–8 KB (instead of 15 KB).

### `docs/LEARNINGS.md` — validation & decision

Contents:
1. Hypothesis check (confirmed / refuted / unclear)
2. What works? (factual, not gut feeling)
3. What doesn't? (with suspected cause)
4. Surprises (what was unexpected)
5. Decision: **PROMOTE** / **PIVOT** / **DROP**

### Pivot variants

| Variant | FRAME | Code | When sensible |
|---|---|---|---|
| **Soft pivot** | `FRAME.md` → `lean-archive/FRAME_v1.md`, new FRAME.md | Stays, modules tagged (keep/refactor/rebuild) | New hypothesis on same tech base |
| **Hard pivot** | `FRAME.md` → `lean-archive/v1/FRAME.md` | Code → `lean-archive/v1/code/` (or branch `lean-archive/v1`), repo restarts | Wrong tech assumption, fundamental reorientation |

`/lean-learn` produces a module table on pivot:
```
| Module/File          | Status     | Reason                  |
|----------------------|------------|-------------------------|
| src/auth/            | rebuild    | Wrong assumption        |
| src/ui/components/   | keep       | Hypothesis-independent  |
| src/api/scraper.py   | refactor   | Logic OK, interface     |
```

On soft pivot: senior-developer works through the table. On hard pivot: table = lessons-learned doc in the archive.

### `docs/PROMOTION_BRIEF.md` — bridge to Full-Track

Instead of generating Full-Track skeletons directly, a structured brief as input for `/project-init`:

YAML frontmatter (`generated_from: lean-track`, `date`, `trigger`, `code_baseline_commit`) plus:
1. **Validated findings** (from LEARNINGS.md, with evidence)
2. **Confirmed assumptions** (Full-Track input)
3. **Refuted assumptions** (what we should NOT believe any more)
4. **Open questions** (what Lean did not answer → input for P0/P1)
5. **Code anchors** (modules: working / needs-rebuild)
6. **Constitution candidates** (Lean boundaries to be adopted as hard principles)
7. **Catch-up duties** (P0 regulatory, P1 privacy, P3 security, P6 a11y → BACKLOG suggestions)

`/project-init` reads the brief and uses it as bootstrap. Lean artefacts (FRAME, LEARNINGS, CLAUDE-lean) move to `docs/lean-archive/`. Code stays in the same repo — Full-Track decides per module: keep / refactor / rebuild.

---

## 4. Full-Track adaptations

### A) Constitution sub-skill `/constitution`

**Dedicated skill.** Invoked in two scenarios:
1. **Lean precursor:** optionally triggered from `/lean-frame` (Constitution-Light becomes a full constitution)
2. **Full direct-start without Lean:** invoked by `/project-init`, alternatively as a sub-skill of P0

**Output:** `docs/CONSTITUTION.md` with three sections:
- **Inviolable** (non-negotiable: GDPR, BFSG a11y, no secrets in code, …)
- **Default** (standard, deviation allowed with reason: tech stack, language, TDD)
- **Aspirational** (goals: performance budget, test-coverage threshold)

**Integration:**
- All gate commands read the constitution as mandatory input
- Every ADR must address the constitution explicitly on conflict
- Versioning: git history is enough for v1; ADR-style headers possible later

### B) `/track-decision` track-agnostic

Prerequisite check **and** reassessment tool. Useful inside an ongoing Full-Track too (pivot, scope cut, spike sub-project).

**Output:** `docs/TRACK_DECISION.md` with history (every new run = new entry with date, answers, result).

### C) `/cross-check` — cross-artifact consistency check

Reads phase indices & detail files, checks inconsistencies across phases.

**Example rules:**
- FEATURES.md mentions login, but AUTH.md has no login flow
- TECHSTACK.md says PostgreSQL, DATA_MODEL.md shows MongoDB syntax
- THREATS.md has T-04, but AUTH.md has no mitigation for it
- NFR demands <200 ms p95, but TEST_STRATEGY.md has no performance test
- ADR-XX was rejected, but a component still references it

**First iteration:** 5–7 high-quality rules, organic growth. Skill optional before gates.

### Deliberately not introduced
- Dedicated `/clarify` skill (functionally covered by `/cross-check`)
- Automatic issue sync to Gitea/GitHub (CCPR stays markdown-first)

---

## 5. Implementation order

| # | Step | Effort | Prerequisite |
|---|---|---|---|
| 1 | `/track-decision` skill + TRACK_DECISION.md template | small | — |
| 2 | `/constitution` skill + CONSTITUTION.md template (Inviolable/Default/Aspirational) | small | — |
| 3 | `/lean-frame` skill + FRAME.md template + CLAUDE-lean.md template | small | 1, 2 |
| 4 | `/lean-learn` skill + LEARNINGS.md template incl. pivot module table | small | 3 |
| 5 | `/lean-promote` skill + PROMOTION_BRIEF.md template | small | 3, 4 |
| 6 | Full-Track integration: gates read constitution; `/project-init` reads PROMOTION_BRIEF when present | medium | 2, 5 |
| 7 | `/cross-check` skill + initial rule catalogue (5–7 rules) | medium | after first Full project with constitution |

---

## 6. Distribution sync (~/Workspace/ccpr/)

After rollout, update SYNC.md:
- **New commands:** `track-decision.md`, `constitution.md`, `lean-frame.md`, `lean-learn.md`, `lean-promote.md`, `cross-check.md` → +6 commands (109 → 115)
- **New templates:** `CLAUDE_LEAN_TEMPLATE.md`, `FRAME_TEMPLATE.md`, `LEARNINGS_TEMPLATE.md`, `PROMOTION_BRIEF_TEMPLATE.md`, `CONSTITUTION_TEMPLATE.md`, `TRACK_DECISION_TEMPLATE.md`
- **README.md:** update command count, mention Lean-Track in the phase model, decision-tree short version
- **CLAUDE.md (Full):** note `/track-decision` as the entry point + reference Lean-Track
- **docs/NEXT_STEPS_REFERENCE.md:** add Lean-Track transitions

---

## 7. Open detail questions for implementation

1. **Constitution versioning:** is git history sufficient, or ADR-style versioning in the frontmatter?
2. **Cross-check rule catalogue v1:** which 5–7 rules first? (see examples above)
3. **Lean-archive layout:** flat (`lean-archive/FRAME_v1.md`) or versioned subfolders (`lean-archive/v1/`)? Proposal: flat on soft pivot, subfolders on hard pivot.
4. **`/project-init` without PROMOTION_BRIEF:** keep current behaviour; brief is optional input, not mandatory.
5. **`/constitution` in Full-Track without Lean precursor:** sub-skill of `/project-init` (interactive Q&A) or a dedicated step before P0? Proposal: `/project-init` calls `/constitution` directly.
