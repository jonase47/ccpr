# Session Postmortem

Analyze the last session and extract instinct proposals.

## Execution

### 1. Load session data (project-aware)
Find the last session **for the current project**, not simply the most recent globally:

1. Read all `~/.claude/sessions/*.json` (PID mapping files with `sessionId` and `cwd`)
2. Filter for sessions whose `cwd` matches the current working directory
   (exact match or parent directory)
3. Take the most recent matching session ID (by `startedAt`)
4. Load the logs from `~/.claude/logs/sessions/{session-id}/`
5. **Fallback**: If no cwd match, take the most recent session directory under
   `~/.claude/logs/sessions/` (backwards compatible)

- Read `session-summary.json`, `errors.jsonl`, and `activity.jsonl`
- **Abort only when there is no usable data** — that is, all three are missing or unreadable.
  A missing `session-summary.json` alone is not a reason to stop: it is written at session end, so
  analysing a session that is still running is a normal case, and `activity.jsonl` + `errors.jsonl`
  carry the material.
- **A summary that IS present may be a mid-session snapshot.** Sanity-check its tool-call count
  against `wc -l` on `activity.jsonl` before reporting any of its numbers; a stale summary is worse
  than an absent one, because its figures look plausible. When they disagree, `activity.jsonl` wins
  and the discrepancy belongs in the report.

### 2. Analyze error patterns
Search the session data for recurring patterns:
- **EISDIR pattern**: Repeated "Is a directory" errors (agent reads directory instead of file)
- **Loop pattern**: Tool calls that were warned/blocked by loop detection
- **Stagnation**: Long phases without productive Write/Edit calls
- **Ghost events**: SubagentStop without SubagentStart (compact artifact)
- **Incomplete agents**: Agents that did not terminate cleanly
- **Tool failures**: Repeated errors on specific tools

### 3. Generate instinct proposals (0-3 per session)
For each recognized pattern, propose an instinct. This is the **proposal format shown to the user**
for confirmation — the *stored* block written in §6 has a different, richer shape:

```markdown
### [ID] Short title
- **Confidence**: 0.4
- **Source**: Session from DD.MM.YYYY
- **Last confirmed**: DD.MM.YYYY
- **Rule**: [One sentence: what to do/avoid]
- **Context**: [When does this rule apply?]
```

**ID schema**: `G-NNN` (Global), `SD-NNN` (Senior-Dev), `QA-NNN` (QA-Tester), `KZ-NNN` (Konzeptor), etc.

**Rules for proposals:**
- Only patterns that actually caused problems
- Maximum 3 proposals per session (quality over quantity)
- New instinct starts with confidence 0.4
- When an existing instinct is confirmed: +0.1 (max 0.9)
- When an existing instinct is contradicted: -0.2 (min 0.3)

### 4. Check decay
Read the slim index `~/.claude/instincts.md` first (one-liner per instinct + confidence). For each candidate, load the matching topic file under `~/.claude/instincts/{theme}.md` to inspect the "Last confirmed" line.
- If "Last confirmed" > 30 days ago: propose decay (-0.1)
- If confidence after decay <= 0.3: propose deletion (remove from the topic file AND the index line)
- Show the user which instincts are affected
- Use `~/.claude/instincts-archive/HISTORY.md` only for retrospective evidence; never decay-check the archive itself

### 5. Recognize project context
- Check whether you are in a project directory (`.claude/CLAUDE.md` or `docs/` present)
- If yes: suggest storing project-specific instincts in `docs/instincts.md` instead of globally
- If the session produced project-specific factual knowledge
  (decisions, corrections, external references), suggest storing it as Memory.
  **Apply the tier separation rule** (full definition in `~/.claude/CLAUDE.md`):
  - **Tier 1 (cross-cutting)** — relevant to >1 persona or to the orchestrator →
    `docs/memory/{type}_{slug}.md` (type: feedback/project/reference), update `docs/memory/MEMORY.md`
  - **Tier 2 (persona-specific)** — only meaningful inside one agent's domain →
    `docs/memory/{agent}/{topic}.md`, update `docs/memory/{agent}/MEMORY.md`
  - **When in doubt, do NOT default to Tier 1** — that tiebreaker was withdrawn because it caused
    Tier-1 drift (persona-specific patterns leaking into the global file). Decision order:
    1. Does the rule name a specific agent, file path, skill, or tool-chain symbol? → **Tier 2**.
    2. Do **≥2 agent domains genuinely consume it today** (not "might one day")? → **Tier 1**.
    3. Still uncertain → **Tier 2** of the persona that surfaced it; promote to Tier 1 at the
       **3rd cross-reference from a different domain**.
- Create `docs/memory/` and `docs/memory/MEMORY.md` if necessary
  (template: `~/.claude/templates/MEMORY_INDEX_TEMPLATE.md`)
- If an agent instinct appears universally applicable: suggest cross-agent promotion

### 6. User confirmation
Present to the user:
1. **Session summary**: Brief summary of the session data
2. **Instinct proposals**: New instincts with proposed ID and confidence
3. **Decay proposals**: Instincts that are aging
4. **Promotion proposals**: Agent instincts that could become global

Wait for confirmation. Only update after explicit OK:
- **Global instincts**: append/update the full Rule block in the matching topic file under
  `~/.claude/instincts/`, then add or update the one-liner in `~/.claude/instincts.md` (the slim index).

  The **stored** block shape (not §3's proposal format) — match the file you are appending to:

  ```markdown
  ### G-NNN: One-line rule as the heading, after a colon
  **Confidence: 0.4** | Source: Session from DD.MM.YYYY | Last confirmed: DD.MM.YYYY — what confirmed it

  **Rule:** [one sentence: what to do or avoid]

  **Why:** [the evidence event — what went wrong, concretely]

  **How to apply:** [bullets: the checks that make the rule operational]

  **Related:** [other IDs and how they differ from this one]

  **Context:** [when the rule applies]
  ```

  Older files wrap Rule/Why/How to apply in a `>` blockquote — follow whichever form the target file
  already uses, so one file never mixes both.

  **Choosing the file.** The shipped starter set has five themes — this list is the starting point,
  **not exhaustive**:
  - `agents.md` — subagent orchestration, briefing, wingman, parallel/sequential shapes
  - `files.md` — Read/Edit discipline, large-file handling, path verification before Read
  - `workflow.md` — skill pipelines, gates, plan-mode, sprint mechanics, PO decisions, push policy, memory override
  - `shell-git.md` — Bash CWD, mass-substitution tooling, commit-hook conventions, tranche-based mass-edits, destructive-action verification
  - `external.md` — WebFetch fallbacks, MCP-server registration, OS-specific filename quirks, PII protection in external HTTP

  A mature set outgrows these: `memory-lint.sh` warns at a 30 KB soft cap and `/postmortem` is what
  pushes files there, so themes get split and renamed over time. **List the directory
  (`ls ~/.claude/instincts/`) and pick by theme** rather than assuming the five names above still
  describe the local set — one of them may no longer exist. If no file fits, propose a new topic file
  to the user instead of forcing the entry into the nearest one.
- The long postmortem-narrative block (sprint summary, tool-call counts, bumps, decay-watch) goes into
  `~/.claude/instincts-archive/HISTORY.md` under the existing "Header Snapshot" section. The write is
  **two moves, not one**: the new block goes on top as the current head, and the block that *was* the
  head is demoted to `Previous:`. The archive states this convention itself — follow the section's own
  description there rather than this summary if the two ever diverge. The demotion is what makes the
  archive complete: the slim index keeps only `Last updated: ...` plus the two most recent `Previous:`
  bullets, so every head it drops has to be caught here. **Do not** prepend a new header block to
  `~/.claude/instincts.md`.
- `docs/memory/{agent}/instincts.md` for agent instincts
- `docs/instincts.md` for project instincts
- `docs/memory/{type}_{slug}.md` for Tier-1 memory entries (and update `docs/memory/MEMORY.md`)
- `docs/memory/{agent}/{topic}.md` for Tier-2 memory entries (and update `docs/memory/{agent}/MEMORY.md`)

Update "Last updated" in `~/.claude/instincts.md` (slim index) and in the affected topic file frontmatter; project files keep their existing convention.

$ARGUMENTS

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
