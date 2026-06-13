# /lean-frame – Create Lean-Track Single-Source-of-Truth

Creates or revises `docs/FRAME.md` (Single-Source-of-Truth of the Lean-Track) and
`docs/CLAUDE-lean.md` (slim project CLAUDE for Lean mode). Replaces the entire
P0+P1+P3 conception work in the Lean-Track with a compact single-screen document.

## Argument: $ARGUMENTS = [optional: projectdir]

- No argument: operates on `$(pwd)`.

## Prerequisites

- `docs/TRACK_DECISION.md` exists and specifies `current_track: lean` (otherwise: run `/track-decision` first)
- Templates: `~/.claude/templates/FRAME_TEMPLATE.md`, `~/.claude/templates/CLAUDE_LEAN_TEMPLATE.md`

## Lead Agent

**konzeptor** with **system-architekt** for tech-stack guidance.

## Execution

### 1. Prerequisites check

If `docs/TRACK_DECISION.md` is missing or `current_track: full` → STOP with note: "Lean-Track not active. Run `/track-decision` first."

If `docs/FRAME.md` already exists → Re-Frame mode: load the existing FRAME as base, ask per section "keep / change".

### 2. Collect FRAME sections interactively

Ask interactively (keep it brief — Lean is not P0 depth):

1. **Problem** (1–2 sentences): Which problem, for whom?
2. **Hypothesis** (1 sentence): What do we believe the prototype will prove or disprove?
3. **Demo-Audience** (3–5 people / personas): Who tests it, how does feedback flow?
4. **MVP-Scope** (max. 5 bullets in + max. 5 bullets deliberately out)
5. **Tech-Stack** (3–5 lines, with a brief rationale per choice)
6. **Constitution-Light** (3–5 hard constraints for this prototype — e.g. "no PII", "local only", "no auth")
7. **Risk assumptions**:
   - What can fail? (list)
   - What must work without fail? (make-or-break)

**Note on section 6:** If Constitution-Light wants to grow beyond 5 bullets → offer: "Should I call `/constitution` and create a full `docs/CONSTITUTION.md`? FRAME will then reference it."

### 3. Embed promotion triggers

Copy the 5 promotion triggers from `docs/TRACK_DECISION.md` into section 8 of the FRAME (or from the template default if TRACK_DECISION does not contain them).

### 4. Write FRAME.md

Write `docs/FRAME.md` with:
- YAML frontmatter: `kind: frame`, `track: lean`, `status: active`, `last_updated: DD.MM.YYYY`, optional `pivot_version` (on Re-Frame after pivot), `related: [TRACK_DECISION.md]`
- 8 sections in fixed order

**Size check:** Hard cap 5 KB. If exceeded, force condensation or check promotion triggers (scope is likely too large for Lean).

### 5. Write CLAUDE-lean.md (initial frame only)

If `docs/CLAUDE-lean.md` does not yet exist:
- Load `~/.claude/templates/CLAUDE_LEAN_TEMPLATE.md`
- Replace `{Projekt-Name}` with the current project name
- Write to `docs/CLAUDE-lean.md`

If it already exists: do not overwrite (preserve user customisations).

### 6. Ensure directory structure

```
docs/
├── FRAME.md              ← Single Source of Truth
├── CLAUDE-lean.md        ← Slim project CLAUDE
├── TRACK_DECISION.md     ← Track decision with history
├── HANDOVER.md           ← Session handover (create if needed)
└── lean-archive/         ← For pivot/promotion (empty for now)
```

Run `mkdir -p docs/lean-archive` (preparatory).

### 7. Optional `/constitution` recommendation

If the user wanted more than 5 Constitution-Light bullets in section 6: recommend an explicit `/constitution` call as a follow-up step.

## Pivot behaviour

If `/lean-frame` runs as a result of a soft pivot (`/lean-learn` decided PIVOT-Soft):
- Old FRAME.md → `docs/lean-archive/FRAME_v{N}.md`
- New FRAME with `pivot_version: N+1`
- Code stays in the repo; module table from LEARNINGS.md flows into section 7 as risk assumptions

On hard pivot: `/lean-learn` has already moved code + FRAME to `lean-archive/v{N}/`; `/lean-frame` starts as initial.

## When to use

- **Lean-Track start:** After `/track-decision` with Lean result
- **Re-Frame:** On scope adjustment or new hypothesis
- **Soft-pivot follow-up:** After `/lean-learn` decision PIVOT-Soft

## When NOT to use

- Full-Track project: use `/p0-problem`, `/p1-features`, `/p3-arch-techstack` instead
- If FRAME is already current (≤14 days old) and no trigger for Re-Frame

## Result

- `docs/FRAME.md` created or updated (≤5 KB)
- `docs/CLAUDE-lean.md` created initially (if not present)
- `docs/lean-archive/` directory prepared

### Handover Epilogue

Update `docs/HANDOVER.md`:
- FRAME created/revised (initial / Re-Frame / after soft pivot)
- Constitution-Light (or reference to CONSTITUTION.md if extended)
- Recommendation: start build in senior-developer mode (TDD, no Sprint ceremony)
- Reminder: keep promotion triggers in view
