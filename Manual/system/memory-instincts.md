---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: memory-doc-splitting-instincts
last_updated: 15.05.2026
---

# Memory, Document Splitting & Instincts

## Memory

### Concept

Memory is organised in a 2×2 matrix (tier × scope): cross-cutting (Tier 1) coexists with persona-specific silos (Tier 2), each at global and project scope. Project-scoped memory is versioned in the project repository and pushable. Global memory stays in personal global storage and is not pushed.

### Tiers and scopes

|  | **Tier 1 — cross-cutting** | **Tier 2 — persona-specific** |
|---|---|---|
| **Global** (`~/.claude/`) | `~/.claude/instincts.md` (slim index) + `~/.claude/instincts/{theme}.md` (full Rule/Why/How) + `~/.claude/instincts-archive/HISTORY.md` (rolling postmortem stream, not autoloaded) | `~/.claude/memory/{agent}/instincts.md` (+ topic files) |
| **Project** (`docs/memory/`) | `docs/memory/{type}_{slug}.md` (flat) | `docs/memory/{agent}/MEMORY.md` + topic files |

**Tier-separation rule** — cross-cutting → Tier 1; persona-specific → Tier 2. Global vs. project: code-independent rule (Apple toolchain, language idioms, vendor APIs) → global; codebase-specific → project.

**When in doubt** — do **not** default to Tier 1. Decision order:
1. Rule names a specific agent, file path, skill, or tool-chain symbol → Tier 2.
2. ≥2 agent domains genuinely consume the rule today → Tier 1.
3. Still uncertain → start in Tier 2 of the surfacing persona; promote to Tier 1 at the 3rd cross-reference from a different domain.

### Memory Types (Tier 1)

| Type | Use case |
|---|---|
| `feedback` | Guidance from the user — what to do, what to avoid, with reasoning |
| `project` | Project-specific facts, decisions, deadlines, constraints |
| `reference` | Pointers to external systems (URLs, dashboards, ticket trackers) |
| `user` | Personal user info — stays in `~/.claude/projects/.../memory/`, not pushed |

### Frontmatter Schema

```yaml
---
name: short-slug-or-title                 # required
description: one-line summary             # required
type: feedback|project|reference          # required (user stays global)
last_updated: DD.MM.YYYY                  # required
status: active|stale|superseded|archived  # optional
related: [other_memory.md]                # optional, paths relative to file
confidence: 0.4                           # optional, for instinct memories
scope: tier-2-global                      # required for ~/.claude/memory/{agent}/*
agent: <name>                             # required for Tier-2-global files
---
```

Full schema: `templates/MEMORY_SCHEMA.md`.

### Indexes

- Tier 1 index: `docs/memory/MEMORY.md` (template: `templates/MEMORY_INDEX_TEMPLATE.md`)
- Tier 2 index: `docs/memory/{agent}/MEMORY.md` (one per agent silo, slim)
- Tier-2-global: no index required — just `instincts.md` + optional topic files

Indexes are listings — no frontmatter required.

### Memory Lint

`~/.claude/scripts/memory-lint.sh [projectdir]` checks:
- Required frontmatter fields present
- Naming convention (`{type}_{slug}.md` for Tier 1)
- Cross-refs in `related:` resolve to existing files
- `last_updated` older than 90 days → suggests `status: stale`
- Each Tier 1 file referenced in `MEMORY.md`
- **Tier-1-global cap**: warns at 50 KB, errors at 100 KB on `~/.claude/instincts.md` (drift pressure)
- **Tier-2-global schema**: required `scope: tier-2-global` field and `agent`-matches-directory check
- **Skeleton silos**: project Tier-2 directory with only a short MEMORY.md (no topic files, <400 bytes body) is flagged
- **Decay tripwire**: counts of Tier-1-global entries at confidence ≤ 0.4 as review candidates

### Templates

| File | Purpose |
|---|---|
| `templates/MEMORY_SCHEMA.md` | Full field reference |
| `templates/MEMORY_PAGE_TEMPLATE.md` | Starter for a new memory file |
| `templates/MEMORY_INDEX_TEMPLATE.md` | Starter for `MEMORY.md` index |
| `templates/MEMORY_LINT_REPORT_TEMPLATE.md` | Lint output format reference |

---

## Document Splitting (P3 + P6)

### Concept

Phases P3 (Architecture & Design) and P6 (Quality Assurance) produce many concerns. A single monolithic phase document would bloat past 30–50 KB and force re-reading large blocks. The solution: a **two-level pattern** — slim phase index + one detail file per sub-skill.

### Pattern

```
docs/<phase-folder>/
+-- <PHASE>.md              # Phase index (5–15 KB) — current state, key decisions, file pointers
+-- <DETAIL_1>.md           # Sub-skill detail file with full content
+-- <DETAIL_2>.md
+-- <SUB_INDEX>.md          # P3/P6 only — groups several detail files under one lead command
```

**Examples**
- P3: `architecture/ARCHITECTURE.md` (index) + `THREATS.md`, `ADRs.md`, `SECURITY.md` (sub-index for `/p3-sec-*`)
- P6: `quality/QA.md` (index) + sub-indexes for each lead command (`A11Y.md`, `AUDIT.md`, `PENTEST.md`, …)

### Sub-Skill Responsibilities

Each `/pX-...` sub-skill command must:

1. **Write detail file** — overwrite (not append) `docs/<phase>/<DETAIL>.md` with YAML frontmatter
2. **Update phase index** — refresh the detail-file row, lift any one-line key decision or risk into the index

### Frontmatter Schema

```yaml
---
phase: P3                     # required, P0..P8
subskill: p3-sec-threats      # required, slash command without leading /
status: active                # required: skeleton|draft|active|frozen|archived|living
last_updated: 12.05.2026      # required, DD.MM.YYYY (optional " (Notiz)" suffix)
related: [ARCHITECTURE.md]    # optional, paths relative to file
parent_index: SECURITY.md     # optional, for detail files under a sub-index
gate: pending                 # optional, for GATE_PX.md files
---
```

Full schema: `templates/PHASE_DOC_SCHEMA.md`.

### Status Semantics

| Status | Meaning |
|---|---|
| `skeleton` | Empty placeholder (e.g. P6 sub-index pre-implementation) |
| `draft` | Work in progress |
| `active` | Usable, current |
| `frozen` | Locked after gate pass; baseline mode |
| `archived` | Replaced by newer file, kept for history |
| `living` | Detail file designed to grow over time (e.g. `SPRINT-XX.md`, `RISKS.md`) |

Phase docs have **no stale detection** (unlike memory) — `frozen` is a wanted state, not a warning.

### Gate Reading Pattern

Gate commands (`/gate-pX`) read the phase index first. Detail files are pulled only when content checks demand it. This keeps the gate's context window small.

### Validation

`~/.claude/scripts/phase-docs-lint.sh [projectdir] [--scope <glob>]` checks:
- Required frontmatter fields present
- `status` is one of the allowed enum values
- Cross-refs in `related:` and `parent_index:` resolve
- Each detail file referenced in its phase index or sub-index

### Volume Watch

`~/.claude/scripts/doc-volume-check.sh [docs-root]` flags files at thresholds:
- ≥25 KB → review whether splitting helps
- ≥40 KB → split recommended
- ≥50 KB → split required (G-017 protection — large files erode Claude's effectiveness)

---

## Continuous Learning (Instincts)

### Concept

Instincts are experience-based rules with confidence score (0.3-0.9). They emerge from session experience and are confirmed or rejected over time.

### Scopes

| Scope | File | Applies to |
|---|---|---|
| Global Tier 1 | `~/.claude/instincts.md` (slim index) + `~/.claude/instincts/{theme}.md` (full Rule/Why/How) + `~/.claude/instincts-archive/HISTORY.md` (rolling postmortem stream, not autoloaded) | All projects, all agents |
| Global Tier 2 | `~/.claude/memory/{agent}/instincts.md` | All projects, single persona |
| Project Tier 1 | `docs/instincts.md` | One project, all agents |
| Project Tier 2 | `docs/memory/{agent}/instincts.md` | One project, single persona |

### Instinct Format

```markdown
### [ID] Short Title
**Confidence: 0.X** | Source: [context]
> Rule in one sentence.
```

**ID schema:** `G-NNN` (Global Tier-1), `{prefix}-G-NNN` (Global Tier-2: `DV-G-001`, `SD-G-001`, `SM-G-001`, …), `SD-NNN`/`QA-NNN`/... (Project Tier-2).

### Confidence Rules

| Action | Effect |
|---|---|
| Newly created | 0.4-0.5 |
| Confirmed (`/instinct confirm`) | +0.1 (max 0.9) |
| Contradicted (`/instinct reject`) | -0.2 (min 0.3) |
| Decay (> 30 days unconfirmed) | -0.1 |

Claude follows instincts proportional to their confidence score.

### Management Commands

| Command | Effect |
|---|---|
| `/postmortem` | Analyze session, propose instincts |
| `/instinct list` | Show all instincts |
| `/instinct add [rule]` | Create new instinct |
| `/instinct confirm [ID]` | Increase confidence |
| `/instinct reject [ID]` | Decrease confidence |
| `/instinct promote [ID]` | Promote agent instinct to global |
| `/instinct cleanup` | Remove outdated instincts |

### Instinct Check (Script)

`~/.claude/scripts/instinct-check.sh` checks without LLM:
- Age of instincts.md
- Number of active instincts
- Warning if > 30 days since last update
