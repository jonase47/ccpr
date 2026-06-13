---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: monitoring-scripts-llm
last_updated: 15.05.2026
---

# Monitoring, Local Scripts & Ollama

## Hook Architecture

A central Python script (`~/.claude/hooks/agent-monitor.py`) processes all hook events.

**Registered events (in settings.json):**

| Event | When | What the monitor does |
|---|---|---|
| `SessionStart` | Claude session starts | Create fresh loop state, start logging |
| `SessionEnd` | Session ends | Write summary, log incomplete agents, clean up state |
| `PreToolUse` | Before every tool call | Loop detection, tool count, stagnation check |
| `PostToolUse` | After every tool call | Performance tracking (duration) |
| `SubagentStart` | Agent is started | Record start time, duplicate batch detection |
| `SubagentStop` | Agent finishes | Calculate duration, slow agent warning |

## Loop Detection

Detects and blocks infinite loops:

```
Same tool call 3x -> Warning (log)
Same tool call 5x -> BLOCKED (exit 2, feedback to Claude)
```

Additionally:
- EISDIR pattern: 3x "Is a directory" error -> Warning
- Duplicate batch: Same agent set started again within 30 min -> Warning

## Tool Count Warnings

| Threshold | Action |
|---|---|
| 100 tool calls | Compact reminder (stderr -> Claude) |
| 150 tool calls | Token budget warning + update HANDOVER |
| 200 tool calls | High tool count in error log |
| 500 tool calls | Critical tool count in error log |

## Stagnation Detection

When no `Write` or `Edit` is executed for 15 minutes:
- Warning to Claude: "Stuck? Consider rethinking approach or asking user."
- Resets once a productive tool call occurs again

## Slow Agent Warning

When an agent runs longer than 10 minutes -> Warning to Claude via stderr.

## Input Validation

Certain tool inputs are validated before execution:
- `AskUserQuestion`: Every question needs 2-4 options. Invalid calls are blocked.

## Log Files

```
~/.claude/logs/
+-- activity.jsonl          # Aggregated activity log (rotates at 10MB)
+-- errors.jsonl            # Aggregated error log (rotates at 10MB)
+-- performance.jsonl       # Aggregated performance log (rotates at 10MB)
+-- sessions/
    +-- {session_id}/
        +-- activity.jsonl   # Session-specific
        +-- errors.jsonl     # Session-specific
        +-- performance.jsonl# Session-specific
        +-- session-summary.json  # Summary at SessionEnd
```

**Loop state:** `/tmp/claude-loop-{session_id}.json` (temporary, deleted at SessionEnd)

## Log Analysis

The script `logs-summary.py` analyzes the logs:
```bash
~/.claude/scripts/logs-summary.py errors        # Show errors
~/.claude/scripts/logs-summary.py performance   # Performance data
~/.claude/scripts/logs-summary.py agents        # Agent statistics
~/.claude/scripts/logs-summary.py loops         # Loop events
~/.claude/scripts/logs-summary.py all           # Everything
```

Periods: `today`, `week`, `all`

---

## Local Scripts

Shell and Python scripts in `~/.claude/scripts/` for mechanical tasks. Save Claude tokens because they run outside the session.

### Before Session Start

| Script | Usage | Result |
|---|---|---|
| `bootstrap.sh` | `~/.claude/scripts/bootstrap.sh [projectdir]` | `docs/.session-context.md` – Git status, HANDOVER, artifacts, instincts |
| `gate-preflight.py` | `~/.claude/scripts/gate-preflight.py p3 [projectdir]` | `docs/.gate-preflight-p3.md` – Artifacts, content patterns, Ollama summaries |
| `command-check.py` | `~/.claude/scripts/command-check.py p5-implement [projectdir]` | Stdout: ready/blocked with reason |

Claude reads generated files (if < 10 min old) automatically as compact context.

### During Work

| Script | Usage | Result |
|---|---|---|
| `run-tests.sh` | `~/.claude/scripts/run-tests.sh [testpath] [projectdir]` | JSON output (detects pytest/jest/vitest/cargo/go) |
| `quality-scan.sh` | `~/.claude/scripts/quality-scan.sh [scope] [projectdir]` | `docs/.quality-scan-report.json` |

Scopes for quality-scan: `all`, `deps`, `sast`, `config`, `dsgvo`

### One-Time / As Needed

| Script | Usage | Purpose |
|---|---|---|
| `project-init.sh` | `~/.claude/scripts/project-init.sh name [template]` | Project scaffolding (default/webapp/api/library) |
| `logs-summary.py` | `~/.claude/scripts/logs-summary.py [focus] [period]` | Analyze session logs |
| `setup-ollama.sh` | `~/.claude/scripts/setup-ollama.sh` | Install Ollama + gemma3:4b, generate wrapper scripts |
| `instinct-check.sh` | `~/.claude/scripts/instinct-check.sh` | Check instinct decay (no LLM needed) |

### Shared Libraries

Python modules in `~/.claude/scripts/lib/`:
- `next_steps.py` – Phase-to-commands mapping, HANDOVER.md parser
- `artefacts.py` – Phase-to-expected-files mapping
- `gate_checklists.py` – Gate checklists with required sections + content pattern checks (regex)

### Shell Aliases

Configured in `~/.zshrc`:

```
cb        -> bootstrap.sh + start Claude
cgate     -> gate-preflight.py
ctest     -> run-tests.sh
ccheck    -> command-check.py
cscan     -> quality-scan.sh
clogs     -> logs-summary.py
cmsg      -> commit-msg.sh (Ollama)
cinstinct -> instinct-check.sh
```

### How Claude Uses the Scripts

Claude automatically detects generated files and uses them as context:
- `docs/.session-context.md` (< 10 min old) -> reads instead of HANDOVER + git + instincts individually
- `docs/.gate-preflight-pX.md` (< 10 min old) -> uses as gate basis, focuses on content
- `docs/.quality-scan-report.json` -> uses as basis for /p6-audit and /p6-pentest

---

## Local LLM (Ollama)

### Setup

- **Framework:** Ollama (CLI-first, OpenAI-compatible API)
- **Model:** gemma3:4b (~3.3GB, Google Gemma 3)
- **Server:** runs as brew service (`brew services start ollama`)
- **API:** `http://localhost:11434` (Generate API with stream=false)

### Wrapper Scripts

Located in `~/.claude/scripts/local-llm/`:

| Script | Purpose | Caller |
|---|---|---|
| `ollama-query.sh` | Shared helper – sends prompt to Ollama Chat API | Internal (from other scripts) |
| `summarize.sh <file>` | Summarize file in 3-5 sentences | Claude or user |
| `handover-draft.sh [dir]` | HANDOVER.md draft from git status | Claude or user |
| `commit-msg.sh` | Commit message from staged diff | Claude, user, or git hook |
| `install-git-hook.sh <dir>` | Install prepare-commit-msg hook | User (one-time per project) |

### Token Delegation by Claude

Claude delegates routine tasks to Ollama when the server is reachable:

**Delegate:**
- Long file summaries -> `summarize.sh`
- HANDOVER drafts -> `handover-draft.sh` as starting point, then refine
- Commit messages -> get `commit-msg.sh` suggestion

**Don't delegate:**
- Architecture decisions, code reviews, security analyses
- Anything that requires judgment

**Fallback:** If Ollama is not reachable, Claude handles the task itself.

### Git Hook (optional)

`install-git-hook.sh` installs a `prepare-commit-msg` hook:
- On every `git commit`, a message is automatically suggested
- The suggestion appears in the editor and can be overwritten
- Skipped on merge, amend, squash, or when Ollama is not running

### Technical Details

- gemma3:4b responds directly without thinking overhead (~12s per summary)
- `num_predict: 512` is sufficient for summaries and commit messages
- Generate API (`/api/generate`) for simple prompt-response
- `stream: false` for script usage (no spinner, no ANSI)
- Previous model qwen3.5 (14B) was too large for 24GB M4 (22 min per summary)
- qwen3:4b had thinking problem (empty content, output only in thinking field)

### Gate Preflight Integration

`gate-preflight.py` uses Ollama automatically for document summaries:
- Per gate artifact, `summarize.sh` is called (3-5 sentences per document)
- Summaries end up in the preflight report under "Document Summaries"
- Timeout: 90s per file. On timeout or Ollama failure: section is omitted
- Saves ~16k tokens per gate run (agent reads summaries instead of raw documents)
