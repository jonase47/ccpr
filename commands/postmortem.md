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
- If no session-summary.json is present: inform the user and abort

### 2. Analyze error patterns
Search the session data for recurring patterns:
- **EISDIR pattern**: Repeated "Is a directory" errors (agent reads directory instead of file)
- **Loop pattern**: Tool calls that were warned/blocked by loop detection
- **Stagnation**: Long phases without productive Write/Edit calls
- **Ghost events**: SubagentStop without SubagentStart (compact artifact)
- **Incomplete agents**: Agents that did not terminate cleanly
- **Tool failures**: Repeated errors on specific tools

### 3. Generate instinct proposals (0-3 per session)
For each recognized pattern, propose an instinct in the following format:

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
  - When in doubt, prefer Tier 1 (visibility wins over isolation)
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
- **Global instincts**: append/update the full Rule block in the matching topic file `~/.claude/instincts/{agents,files,workflow,shell-git,external}.md`, then add or update the one-liner in `~/.claude/instincts.md` (the slim index). Pick the topic file by domain:
  - `agents.md` — subagent orchestration, briefing, wingman, parallel/sequential shapes
  - `files.md` — Read/Edit discipline, large-file handling, path verification before Read
  - `workflow.md` — skill pipelines, gates, plan-mode, sprint mechanics, PO decisions, push policy, memory override
  - `shell-git.md` — Bash CWD, mass-substitution tooling, commit-hook conventions, tranche-based mass-edits, destructive-action verification
  - `external.md` — WebFetch fallbacks, MCP-server registration, OS-specific filename quirks, PII protection in external HTTP
- The long postmortem-narrative block (sprint summary, tool-call counts, bumps, decay-watch) goes into `~/.claude/instincts-archive/HISTORY.md` under the existing "Header Snapshot" section — append a new `Previous: DD.MM.YYYY (...)`-style block at the top of that section. **Do not** prepend a new header block to `~/.claude/instincts.md`; the slim index keeps only `Last updated: ...` + the two most recent `Previous:` bullets.
- `docs/memory/{agent}/instincts.md` for agent instincts
- `docs/instincts.md` for project instincts
- `docs/memory/{type}_{slug}.md` for Tier-1 memory entries (and update `docs/memory/MEMORY.md`)
- `docs/memory/{agent}/{topic}.md` for Tier-2 memory entries (and update `docs/memory/{agent}/MEMORY.md`)

Update "Last updated" in `~/.claude/instincts.md` (slim index) and in the affected topic file frontmatter; project files keep their existing convention.

$ARGUMENTS

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
