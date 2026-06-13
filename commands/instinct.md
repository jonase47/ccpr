# Instinct Management

Manage instincts (confidence-based rules from session experience).

## Actions

Determine the desired action from `$ARGUMENTS`:

### `list` – Show all instincts
1. Read `~/.claude/instincts.md` (slim global Tier-1 index) — one-liner per entry already gives ID + confidence + theme
2. Optional: load any of the topic files `~/.claude/instincts/{agents,files,workflow,shell-git,external}.md` for full Rule/Why/How when the user wants details
3. Search all `docs/memory/*/instincts.md` (agent instincts)
4. Check whether `docs/instincts.md` exists (project instincts)
5. Check whether `docs/memory/MEMORY.md` exists (project memory as cross-reference)
6. Show all instincts grouped by scope (Global / Agent / Project) with ID and confidence
7. If project memory exists: show number of memory entries as info

### `add [rule]` – Create a new instinct
1. Ask the user for the scope:
   - **Global** (`G-NNN`): Applies to all agents → add the H3 Rule block to the matching topic file under `~/.claude/instincts/{theme}.md`, then add a one-liner bullet to `~/.claude/instincts.md` (slim index). Pick the topic file by domain (agents / files / workflow / shell-git / external).
   - **Agent** (`XX-NNN`): Applies to one agent → `docs/memory/{agent}/instincts.md`
   - **Project** (`P-NNN`): Applies only in the current project → `docs/instincts.md`
2. Generate the next available ID for the chosen scope
3. Create the instinct with confidence 0.4:
```markdown
### [ID] Short title
- **Confidence**: 0.4
- **Source**: User feedback from DD.MM.YYYY
- **Last confirmed**: DD.MM.YYYY
- **Rule**: [Rule from $ARGUMENTS]
- **Context**: [Ask the user for the context]
```
4. Add it to the chosen file (global → topic file + index bullet; agent → that agent's instincts.md; project → docs/instincts.md)
5. Update "Last updated"

### `confirm [ID]` – Confirm an instinct
1. Find the instinct with the given ID (global, agent, or project)
2. Increase confidence by 0.1 (max 0.9)
3. Update "Last confirmed" to today
4. Show the updated instinct

### `reject [ID]` – Reject an instinct
1. Find the instinct with the given ID
2. Reduce confidence by 0.2
3. If confidence <= 0.3: ask whether to delete or keep
4. If deleting: remove the entire instinct block
5. Update "Last updated"

### `promote [ID]` – Promote an agent instinct to global
1. Find the agent instinct with the given ID
2. Generate a new global ID (`G-NNN`)
3. Copy the instinct into the matching topic file under `~/.claude/instincts/{theme}.md` with the new ID, then add a one-liner bullet to `~/.claude/instincts.md` (slim index)
4. Keep the original agent version (as reference)
5. Set confidence of the global instinct to 0.4 (fresh start)

### `cleanup` – Remove outdated instincts
1. Read all instinct files (global + agent + project)
2. Find instincts with confidence <= 0.3
3. List them and ask the user whether they should be deleted
4. Delete after confirmation

## Rules
- NEVER write an instinct without user confirmation
- Keep instinct rules to one sentence
- Context should make clear WHEN the rule applies
- Always update "Last updated" in the file header

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
