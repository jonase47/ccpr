# /project-init

Initializes a new project with directory structure, project-specific CLAUDE.md, and Git repository.

## Argument: $ARGUMENTS = [Project name]

If provided: use as project name (also used as directory name).
If not provided: ask for the project name.

## Execution

### 0. Detect Promotion Brief (Lean → Full Promotion)

If `docs/PROMOTION_BRIEF.md` exists (created by `/lean-promote`):
- Read the brief in full
- Take the project name from the path / repo name (do not ask again)
- Use the brief as bootstrap input instead of a greenfield prompt:
  - **Validated findings** → P0 input (proposal for `/p0-problem`)
  - **Confirmed assumptions** → carry into CLAUDE.md under "Key Decisions" with date
  - **Refuted assumptions** → note in CLAUDE.md under "Open Risks" as "Lean-Lessons"
  - **Constitution candidates** → hand off to `/constitution` (step 4 below)
  - **Catch-up obligations** → schedule later via `/p4-backlog` as stories; note in HANDOVER.md now

If `docs/PROMOTION_BRIEF.md` does not exist: follow the normal greenfield path (steps 1–6).

### 1. Collect project information

Ask the user for the following information (if not already known):

- **Project name**: Name of the project (used as directory name, kebab-case)
- **Project type**: Software | Business | Software+Business
- **Short description**: 1-2 sentences describing what the project is
- **Project goals**: What should be achieved at the end? (1-3 goals)
- **Target audience**: Who uses the result?
- **Budget**: Rough estimate or "still unclear"
- **Timeline**: When should it be done? or "open"
- **Regulatory**: DSGVO (GDPR), health data, financial regulation, or "Standard"
- **Tech preferences**: For software – are there requirements? or "open"
- **Agent notes**: Special instructions for specific agents? (optional)

### 2. Create directory structure

Create the following structure in the current directory:

```bash
mkdir -p $PROJECTNAME/.claude
mkdir -p $PROJECTNAME/docs/{discovery,concept,validation,architecture,planning,quality,launch}
mkdir -p $PROJECTNAME/src
mkdir -p $PROJECTNAME/tests
```

### 3. Create project CLAUDE.md

Read the template from `~/.claude/templates/PROJECT_CLAUDE_TEMPLATE.md`.
Replace all `{{PLACEHOLDER}}` with the collected information.
Save as `$PROJECTNAME/.claude/CLAUDE.md`.

Important: The placeholders are:
- `{{PROJECT_NAME}}` → Project name
- `{{PROJECT_TYPE}}` → Project type
- `{{PROJECT_DESCRIPTION}}` → Short description
- `{{GOAL_1}}`, `{{GOAL_2}}` → Project goals
- `{{TARGET_AUDIENCE}}` → Target audience
- `{{BUDGET}}` → Budget
- `{{TIMELINE}}` → Timeline
- `{{REGULATORY}}` → Regulatory
- `{{TECH_PREFERENCES}}` → Tech preferences
- `{{AGENT_NOTES}}` → Agent notes (or leave empty)

### 4. Initialize Git

```bash
cd $PROJECTNAME
git init
```

Create a `.gitignore` with sensible defaults:
```
# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp

# Dependencies
node_modules/
venv/
__pycache__/

# Environment
.env
.env.local

# Build
dist/
build/
*.egg-info/

# Logs
*.log

# Temp
/tmp/
```

### 4a. Create Constitution (Full-Track mandatory)

Full-Track projects require `docs/CONSTITUTION.md`. Call `/constitution` as a subskill:

- **On promotion** (step 0 detected a brief): pass the Constitution candidates from the brief to `/constitution`. "Lean-precursor" mode applies implicitly (brief serves as template).
- **On greenfield** (no brief): `/constitution` runs in greenfield mode with domain bootstrap selection (`saas-b2c`, `mobile-b2c`, `b2b-tool`, `b2c-marketplace`, `on-device-privacy`, or `custom`).

Result: `docs/CONSTITUTION.md` with Inviolable/Default/Aspirational is created before step 5 (initial commit) runs.

### 4b. Archive Lean artifacts (promotion only)

If `docs/PROMOTION_BRIEF.md` exists and the Lean artifacts (`docs/FRAME.md`, `docs/LEARNINGS.md`, `docs/CLAUDE-lean.md`) are not yet in `docs/lean-archive/`:

```bash
mkdir -p docs/lean-archive
mv docs/FRAME.md docs/LEARNINGS.md docs/CLAUDE-lean.md docs/lean-archive/ 2>/dev/null || true
```

`docs/TRACK_DECISION.md` and `docs/PROMOTION_BRIEF.md` stay in place — Full-Track continues to read from them.

### 5. Create initial commit

```bash
git add .
git commit -m "chore: Project $PROJECTNAME initialized (Phase P0)"
```

### 6. Output summary

Show the user:
- Created directory structure
- Path to the project CLAUDE.md
- Next step: `/p0-problem` to start the discovery phase
- Note: `cd $PROJECTNAME` and then start Claude Code so that the project CLAUDE.md is loaded

## Result

- Project directory with complete structure
- Project-specific `.claude/CLAUDE.md` (loaded automatically by Claude Code)
- Git repository with initial commit
- `.gitignore` with sensible defaults

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
