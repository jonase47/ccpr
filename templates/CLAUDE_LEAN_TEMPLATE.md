# Project CLAUDE (Lean-Track) – Template

> **Lean-Track active.** This file replaces the full `CLAUDE.md` for Lean projects (prototype, PoC, spike).
> On promotion to Full-Track it is replaced by the full variant (`~/.claude/templates/PROJECT_CLAUDE_TEMPLATE.md`);
> Lean artefacts (FRAME, LEARNINGS, CLAUDE-lean) move to `docs/lean-archive/`.
>
> Path in project: `docs/CLAUDE-lean.md`
> Target size: ≤8 KB

---

# {Project-Name} – Lean-Track

## Track-Status

- **Track:** Lean
- **Single Source of Truth:** `docs/FRAME.md`
- **Constitution-Light** (Inviolables for the prototype): see FRAME.md, section 6 — or `docs/CONSTITUTION.md` if expanded.
- **Track-Decision:** `docs/TRACK_DECISION.md` (including promotion triggers)

## Language & Communication

- Communication language: English (default; adjust to your preferred language)
- Code, comments, variable names: English
- Direct, technically precise. No filler phrases.

## Code Standards

- Test-Driven Development: Red → Green → Refactor
- 1 TDD-Cycle = 1 Commit (Conventional Commits: feat/fix/refactor/docs/chore)
- Simplest solution that works. YAGNI.
- No production code without tests, even on the Lean-Track.

## Personal Context (inherited from global CLAUDE.md)

- Your role and background (replace with your own)
- Accessibility is a high priority — use color-blind-friendly palettes (blue/orange instead of red/green), always pair status with icon/text
- Accessibility applies even in prototypes where feasible
- Dark Mode is always considered

## Date Format

- DD.MM.YYYY

## Reduced Agent Team

Active on the Lean-Track:

| Agent | When to use |
|---|---|
| **konzeptor** | `/lean-frame`, `/lean-learn`, `/lean-promote` |
| **system-architekt** | Tech-stack advice in FRAME, architecture decisions during build |
| **senior-developer** | TDD cycle, implementation |
| **code-reviewer** | Spot-check on risky areas (no mandatory gate) |
| **debugger** | When stuck during build |
| **tech-writer** | README/docs on promotion |

**Not active on the Lean-Track** (available but rarely needed): business-analyst, project-planner, ux-designer (except a quick A11y check), qa-tester, devops, security-master, pentester.

## Handover Protocol

- At session end: update `docs/HANDOVER.md` (template: `~/.claude/templates/HANDOVER_TEMPLATE.md`)
- Maximum 5 open items in HANDOVER.md — otherwise check promotion triggers
- Strategic Compact: update HANDOVER before `/compact`, read it after

## Continuous Learning (Instincts)

- Global instincts: `~/.claude/instincts.md` (read at session start)
- Project instincts (optional): `docs/instincts.md` — only when project-specific heuristics emerge

## Memory (Tier 1 only, sparse)

The Lean-Track uses **Tier-1 memory only** (cross-cutting). No agent silos.

- Index: `docs/memory/MEMORY.md` (create if needed)
- Files: `docs/memory/{type}_{slug}.md` (types: `feedback`, `project`, `reference`)
- Schema: `~/.claude/templates/MEMORY_SCHEMA.md`

Memory is rarely needed on the Lean-Track — when insights emerge, they belong in FRAME or LEARNINGS, not in memory files.

## Lean-Track Skills

- `/track-decision` — re-assessment if conditions change
- `/lean-frame` — revise FRAME.md
- `/constitution` — expand Constitution-Light to a full CONSTITUTION.md (optional)
- `/lean-learn` — LEARNINGS.md + decision Drop/Pivot/Promote
- `/lean-promote` — bridge to Full-Track via `docs/PROMOTION_BRIEF.md`

## What Lean deliberately omits

- No gates (FRAME completeness is the only check)
- No BACKLOG/SPRINT
- No dedicated P0–P8 phase model
- No phase-doc splitting convention
- No `/p*-*` skills

If any of this machinery is needed, the promotion trigger has fired → `/lean-learn` → `/lean-promote`.

## Promotion Path (reminder)

```
/lean-learn → PROMOTE
   ↓
/lean-promote → docs/PROMOTION_BRIEF.md
   ↓
/project-init → reads brief, replaces CLAUDE-lean.md with full CLAUDE.md
   ↓
Full-Track from P0 (with substantial prior work carried over from Lean)
```
