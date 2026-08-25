---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: memory-doc-splitting-instincts
last_updated: 25.08.2026 (WI-0104)
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
status: active|superseded|archived        # optional
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

`~/.claude/scripts/memory-lint.sh [projectdir]` validates `docs/memory/**` in the project plus the
global tiers under `~/.claude/`.

**This is the only check-by-check list in the Manual** — `SYSTEM_OVERVIEW.md` links here instead of
restating it, because a list that grows when the script grows cannot be maintained in two places.
Ground truth is the script itself: every entry below names the check letter it documents, so a
bullet can be traced to the code block that implements it.

| Exit | Meaning |
|---|---|
| 0 | clean — info findings do not raise it |
| 1 | at least one warning |
| 2 | at least one error |
| 3 | configuration error — the run produced no report, so its findings are unknown |

**Per file** — every `.md` under `docs/memory/`, except the `MEMORY.md` indexes and `instincts.md`:

- **(a) Frontmatter present** — a file without a leading `---` block errors and is skipped.
- **(b) Required fields** — `name`, `description`, `type`, `last_updated`; each missing one errors.
- **(c) `type` enum, tier-aware** — Tier 1 (`docs/memory/*.md`) is closed: a value outside
  `feedback`/`project`/`reference`/`user` errors. Tier 2 (`docs/memory/{agent}/*.md`) adds
  `patterns` and stays open — an unrecognised value warns rather than errors (WI-0008).
- **(c2) `status` enum** — `active`/`superseded`/`archived`, or absent; any other value errors.
  `stale` was removed outright (WI-0074): it was the one value check (e) told the reader to set,
  and setting it did not silence the warning.
- **(d) Tier-1 naming** — a Tier-1 file whose name does not start with `{type}_` warns.
- **(e) `last_updated` — form first, then age.** The form is `DD.MM.YYYY`, optionally followed by
  whitespace and a parenthesised note (`24.08.2026 (WI-0102)`); anything else errors, as does a
  well-formed but impossible date. A parsed date older than 90 days warns, unless `status` is
  `archived` or `superseded`.
- **(f) `related:` cross-refs** — resolved relative to the file's own directory (the documented
  form, silent on a hit). A path that only resolves from the project root is reported as info
  rather than accepted silently; a path that resolves from neither errors.

**Index consistency, both directions:**

- **(g) Tier-1 file missing from the index** — every `docs/memory/{type}_{slug}.md` must appear by
  basename in `docs/memory/MEMORY.md`, or it warns. The match is literal, so `foo.md` does not
  satisfy `foo-bar.md`.
- **(n) Dead index links** — the reverse direction, over `docs/memory/MEMORY.md` and every
  `docs/memory/{agent}/MEMORY.md`. A Markdown link whose target file does not exist **errors** by
  default since 24.08.2026 (WI-0005); `MEMORY_INDEX_LINK_SEVERITY=warn` downgrades it to a warning,
  and any other value — the empty string included — exits 3 as a configuration error. It catches a
  missing target *file*, not a wrong anchor into a file that exists. Two extraction limits are
  reported rather than hidden: an unclosed code fence or HTML comment stops link checking for the
  rest of that file (warning, naming the opening line), and a target carrying an unresolved named
  HTML entity such as `&num;` is reported as info, because it cannot be resolved in either
  direction.

**Global tiers under `~/.claude/`:**

- **(h) Tier-1-global cap** — `~/.claude/instincts.md` warns above 50 KB, errors above 100 KB.
- **(i) Tier-2-global schema** — for `~/.claude/memory/{agent}/*.md` (except `MEMORY.md`): missing
  frontmatter errors; a missing or wrong `scope: tier-2-global` warns; an `agent:` field that is
  absent or does not match the parent directory warns.
- **(j) Skeleton silos** — a project Tier-2 directory holding only a `MEMORY.md` with fewer than
  400 bytes of body and no topic files is reported as info. A short index *with* topic files is a
  compact silo, not a skeleton, and is not flagged.
- **(k) Decay tripwire** — counts the entries marked confidence 0.3 or 0.4 across
  `~/.claude/instincts.md` and `~/.claude/instincts/*.md` and reports the number as info. A
  tripwire only; the dated decay check belongs to `/postmortem`.
- **(l) Split-layout topic files** — only when `~/.claude/instincts/` exists. Per file: missing
  frontmatter errors; a missing `type: instincts` or `scope: tier-1-global-topic` warns; size warns
  above 30 KB and errors above 50 KB. A directory that exists but holds no `*.md` is reported as
  info.
- **(m) Archive presence** — a split layout without `~/.claude/instincts-archive/HISTORY.md` is
  reported as info; `/postmortem` expects to append its narrative there.

Nothing is deliberately omitted: the fifteen entries above are every check the script runs. When a
check is added, removed, or changes severity, this section is the one place to say so.

### Templates

| File | Purpose |
|---|---|
| `templates/MEMORY_SCHEMA.md` | Full field reference |
| `templates/MEMORY_PAGE_TEMPLATE.md` | Starter for a new memory file |
| `templates/MEMORY_INDEX_TEMPLATE.md` | Starter for `MEMORY.md` index |
| `templates/MEMORY_LINT_REPORT_TEMPLATE.md` | Lint output format reference |

### Team Sharing (Org Tier)

Shipped since v0.2.0-beta. `~/.claude/scripts/memory-sync.sh` shares
instincts/memory across a team through a shared Git repository (the org
tier), materialised locally as a **read-only overlay**.

| Verb | Effect |
|---|---|
| `pull` | Fetch the shared repo and materialise the overlay: shared instincts → `~/.claude/instincts/<shared>.md` (plus an autoloaded index-block entry per instinct), shared persona instincts → `~/.claude/memory/{agent}/<shared>.md`, shared facts → `~/.claude/memory/<namespace>/` |
| `promote <src> <dst>` | Run the discipline gate on `<src>`, copy it into the shared clone at repo-relative `<dst>` (must be a file path, never a directory), commit, push |
| `gate <file>` | Run the discipline gate on `<file>` only, no side effects — exit 0 clean |
| `status` | Show config + clone state, no network mutation |

Config: `$MEMORY_SYNC_CONFIG` or `~/.claude/memory-sync.json` — personal,
**never** committed to any repository (template:
`templates/memory-sync.example.json`). Key fields: `repo`/`repoUrl`/
`apiBase`, `tokenFile` (path to the access-token file), `clonePath`,
`namespace`, `gate.denyNames`/`gate.ipAllowlist`, `overlay.*` (where shared
content materialises locally).

`promote` runs the discipline gate first and refuses on a finding — see
[discipline-gate.md](discipline-gate.md) for what it checks and how to
configure the deny list.

Namespaces keep sources from colliding and re-syncs idempotent: native
`G-NNN`, imported foreign-contributor `{SRC}-G-NNN` (externally maintained),
shared org-tier `{ORG}-G-NNN` (team-maintained by push, not by your own
`/postmortem` decay clock).

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
last_updated: 12.05.2026      # required, DD.MM.YYYY or "DD.MM.YYYY (note)"
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
