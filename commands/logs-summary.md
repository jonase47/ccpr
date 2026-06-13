# /logs-summary

Analyzes and summarizes the agent monitor logs.

## Argument: $ARGUMENTS = [focus or session ID]

Possible arguments:
- **No argument**: Summary of the last session
- **`all`**: Overview of all sessions
- **`errors`**: Show errors only
- **`performance`**: Performance data only
- **`loops`**: Loop warnings and blockings only
- **`{session-id}`**: Analyze a specific session

## Execution

### 1. Locate log files

Check the following directories:
- `~/.claude/logs/sessions/` – Session-based logs
- `~/.claude/logs/activity.jsonl` – Aggregated activity log
- `~/.claude/logs/errors.jsonl` – Aggregated error log
- `~/.claude/logs/performance.jsonl` – Aggregated performance log

If no logs are present, report this to the user.

### 2. Analysis by focus

#### Default (last session):
Read the most recent session from `~/.claude/logs/sessions/` and create:
- **Session overview**: Start, end, duration, reason for termination
- **Agent activity**: Which agents ran, how long, how many tool calls
- **Errors**: All errors with timestamp and context
- **Loop events**: Warnings and blockings
- **Performance**: Top 5 slowest tool calls, top 5 slowest agents

#### `all` (all sessions):
Read `~/.claude/logs/activity.jsonl` and create:
- Table of all sessions: ID, date, duration, number of tool calls, error count
- Sorted by date (newest first)
- Maximum the last 20 sessions

#### `errors` (errors only):
Read `~/.claude/logs/errors.jsonl` and show:
- All errors grouped by type (ToolFailure, LoopWarning, LoopBlocked, etc.)
- With timestamp, affected tool, error message
- Sorted by frequency

#### `performance` (performance only):
Read `~/.claude/logs/performance.jsonl` and show:
- Average duration per agent
- Average duration per tool type
- Slowest individual calls
- Total tool calls per session

#### `loops` (loop events only):
Filter from `~/.claude/logs/errors.jsonl` only events of type LoopWarning and LoopBlocked:
- Which tool, how many repetitions, when
- Recognize patterns: which tools loop most frequently?

### 3. Output

Format the results as a clear summary directly in the chat.
Use tables for tabular data.
Provide recommendations at the end if anomalies were found (many errors, frequent loops, slow agents).

### 4. Optional: Clean up

If the user asks, offer to:
- Delete old sessions (older than X days)
- Clean up rotated log files
- Clean up loop state files in /tmp
