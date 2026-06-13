# /lean-learn – Validate Lean-Track and make a decision

Creates `docs/LEARNINGS.md` with hypothesis check, observations, and decision
(**PROMOTE** / **PIVOT-Soft** / **PIVOT-Hard** / **DROP**). Closes a Lean cycle
and determines what happens next.

## Argument: $ARGUMENTS = [optional: projectdir]

- Without argument: operates on `$(pwd)`.

## Prerequisites

- `docs/FRAME.md` exists with hypothesis
- Code exists in the repo (otherwise there is nothing to learn from)
- Template: `~/.claude/templates/LEARNINGS_TEMPLATE.md`

## Lead Agent

**konzeptor** for hypothesis analysis, **business-analyst** as support for market/user signals.

## Execution

### 1. Prerequisites check

- If `docs/FRAME.md` is missing → STOP, note: run `/lean-frame` first
- If no code files exist in `src/` (or repo root) → warn, continue with user confirmation

### 2. Load hypothesis from FRAME

Read `docs/FRAME.md` section 2 (hypothesis) and section 7 (risk assumptions: what must work without fail?). List them for the user.

### 3. Walk through validation interactively

Ask interactively:

1. **Hypothesis check:** Is the hypothesis confirmed, refuted, or unclear?
   - **Evidence:** What concrete data points/observations/user reactions are available? (Not "felt", but concrete.)

2. **What works?** (factual observations, each with a brief rationale)

3. **What does not work?** (observations with suspected cause)

4. **Surprises:** What was unexpected? (If nothing: record explicitly — the hypothesis was probably too weak.)

### 4. Make a decision

Present 4 options:

| Option | When appropriate |
|---|---|
| **PROMOTE** | Hypothesis confirmed; prototype becomes the basis for Full-Track |
| **PIVOT-Soft** | New hypothesis on the same tech base; most code stays |
| **PIVOT-Hard** | Wrong core assumption (tech, market, user); code reset required |
| **DROP** | Lean answered the question (negatively); project is frozen |

### 5. On PIVOT (Soft or Hard): module table

Ask per module/directory:
- **keep** — functionally correct, hypothesis-independent
- **refactor** — logic OK, interface must change
- **rebuild** — wrong core assumption, rewrite

Format:

```
| Module / File       | Status   | Rationale            |
|---------------------|----------|----------------------|
| src/foo.py          | keep     | …                    |
| src/bar/            | refactor | interface changed    |
| src/baz.py          | rebuild  | wrong assumption     |
```

### 6. Write LEARNINGS.md

Write `docs/LEARNINGS.md` with:
- YAML frontmatter: `kind: learnings`, `track: lean`, `decision: {promote|pivot-soft|pivot-hard|drop}`, `last_updated: DD.MM.YYYY`, optional `pivot_version`, `related: [FRAME.md]`
- 5 sections: hypothesis check, what works, what does not, surprises, decision
- On Pivot: module table as a sub-section under decision

**Size check:** Target ≤8 KB. If exceeded, condense — LEARNINGS is decision documentation, not a report.

### 7. Action per decision

**PROMOTE:**
- Recommend as next step: `/lean-promote`
- Note: PROMOTION_BRIEF will be created, then `/project-init` for Full-Track

**PIVOT-Soft:**
- Move `docs/FRAME.md` → `docs/lean-archive/FRAME_v{N}.md` (N = current pivot_version + 1)
- Moving `docs/LEARNINGS.md` itself (the file just written) → `docs/lean-archive/LEARNINGS_v{N}.md`? — **No:** LEARNINGS stays as the current document and is overwritten on the next /lean-learn run. Across multiple pivot rounds only the latest LEARNINGS is active; older ones are referenced in the archive subdirectories.

  Correction: on Soft-Pivot **copy** LEARNINGS.md to `lean-archive/LEARNINGS_v{N}.md` (archive copy); the original LEARNINGS.md stays in place for the user workflow.
- Recommend `/lean-frame` (new FRAME with pivot_version: N+1) as next step
- Code stays in the repo; senior-developer works through the module table

**PIVOT-Hard:**
- Create `docs/lean-archive/v{N}/` and move everything:
  - `docs/FRAME.md` → `docs/lean-archive/v{N}/FRAME.md`
  - `docs/LEARNINGS.md` as a copy → `docs/lean-archive/v{N}/LEARNINGS.md`
  - `docs/CLAUDE-lean.md` → `docs/lean-archive/v{N}/CLAUDE-lean.md`
  - Code: present two options to the user:
    - (a) Create branch `lean-archive/v{N}`, freeze code there, delete from main branch
    - (b) Move `src/` → `docs/lean-archive/v{N}/code/` (code archived in the same branch)
- Recommend `/lean-frame` (fresh start without pivot_version)

**DROP:**
- `LEARNINGS.md` stays in the repo as a lessons-learned archive
- Optional: set Git tag `lean-final`
- Recommendation: freeze the repo (no further skill needed)
- Note to user: on later re-use, read the lessons learned from this file

## When to use

- **Before a promotion decision:** when the Lean-Track has reached its goal or mid-flight triggers fire
- **Before a pivot:** when it becomes clear the hypothesis is refuted
- **Before drop:** when the question is answered and no follow-up project makes sense
- **Periodically** (every 2–4 weeks) as a reflection point

## When NOT to use

- In the middle of an active TDD cycle with no clear need for reflection — decisions require observations, not pressure
- When the FRAME hypothesis is not clearly stated — re-frame with `/lean-frame` first, then learn

## Result

- `docs/LEARNINGS.md` created
- Decision in frontmatter (`decision: promote|pivot-soft|pivot-hard|drop`)
- On Pivot: archive structures created
- On Pivot-Hard: code archiving documented (branch or subdirectory)

### Handover Epilogue

Update `docs/HANDOVER.md`:
- LEARNINGS decision
- On Pivot: module table as open items for senior-developer
- Recommended next skill (lean-promote / lean-frame / freeze repo)
