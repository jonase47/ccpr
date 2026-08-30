---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: monitoring-scripts-llm
last_updated: 20.08.2026
---

# Monitoring, Local Scripts & Ollama

## Hook Architecture

A central Python script (`~/.claude/hooks/agent-monitor.py`) processes all hook events.

**Registered events (in settings.json):**

| Event | When | What the monitor does |
|---|---|---|
| `SessionStart` | Claude session starts | Create fresh loop state, start logging, sweep stale loop-state files, run `log-cleanup.sh` at most once a day |
| `SessionEnd` | Session ends | Write summary, log incomplete agents, clean up state |

`SessionEnd` is not guaranteed to arrive — a killed process or a crash skips it. That is why
both cleanups also run at `SessionStart`, where an interrupted session's leftovers are still
there to find.
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

**Loop state:** `/tmp/claude-loop-{session_id}.json` (temporary, deleted at SessionEnd, and swept by age at the next SessionStart for the sessions that never emitted one)

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

> Editing one of these scripts (in the repo's `scripts/`, not the installed
> `~/.claude/scripts/` copy)? Two conventions are enforced by tests before a
> change ships — see [scripts-conventions.md](scripts-conventions.md).

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
| `memory-sync.sh` | `~/.claude/scripts/memory-sync.sh pull\|promote\|gate\|status` | Sync a shared org-tier memory/instincts repo into `~/.claude` (read-only overlay); share local entries via a discipline gate. Details: [memory-instincts.md → Team Sharing (Org Tier)](memory-instincts.md) |

### Doc Hygiene & Validation

Read-only validators. Each exits 0 clean, non-zero on findings — see each script's
header for its exact exit-code contract.

| Script | Usage | Purpose |
|---|---|---|
| `memory-lint.sh` | `~/.claude/scripts/memory-lint.sh [projectdir]` | Validates `docs/memory/**` and the global tiers: frontmatter schema and naming, `related:` cross-refs, index consistency both ways, `last_updated` age, size caps on the global instinct files. Exits 0 / 1 warn / 2 error / 3 own-config error. Details: [memory-instincts.md → Memory Lint](memory-instincts.md) |
| `phase-docs-lint.sh` | `~/.claude/scripts/phase-docs-lint.sh [projectdir] [--scope <glob>]` | Validates phase-doc frontmatter. **Scoped by folder name** — a project with none of the nine phase folders reports `Files scanned: 0`, which is not a pass. |
| `manual-lint.sh` | `~/.claude/scripts/manual-lint.sh <root>` | Validates a documentation index↔detail contract: `parent_index` resolves, the named index links the detail file **back**, and `kind` against the vocabulary in `templates/PHASE_DOC_SCHEMA.md`. An unrecognised `kind` is a **warning** — that vocabulary is the known set, not the allowed set. Run by `/cleanup`. |
| `doc-volume-check.sh` | `~/.claude/scripts/doc-volume-check.sh [docs-root]` | Size watch: info 25–40 KB, warning 40–50, error ≥50. Exit 2 / 1 / 0 — the info band does not raise it. |
| `instinct-check.sh` | `~/.claude/scripts/instinct-check.sh [projectdir]` | Instinct decay report across the index + topic-file layout. No LLM. |
| `conformance-run.sh` | `~/.claude/scripts/conformance-run.sh [--require-consumers] [--consumer <id>] [--show-paths]` | Runs the five checks above (memory-lint, phase-docs-lint, manual-lint, doc-volume-check, anchor) against real, personally-configured **consumer projects** — a check exercised only against this repository's own fixtures is a hypothesis, not a proof. Sorts every finding into C1 (contract violation) / C2 (zero scope) / C3 (a pinned expectation violated) / P (a real consumer finding, never escalates the exit code); a check refusing an unsuitable target is its own fifth class, Could Not Run. Not-configured is a loud exit 0, not silence. Not yet in any tagged release. Design: `docs/adr/ADR-0010`. Details: [conformance.md](conformance.md) |

### State, Baselines & Migration

| Script | Usage | Purpose |
|---|---|---|
| `anchor.sh` | `~/.claude/scripts/anchor.sh` (via `/anchor`) | Stage-1 **mechanical, no-verdict** check: compares a phase document's recorded `anchor_commit` / `anchor_date` against the repository's real git history and reports drift. The verdict is the command's job, not the script's. Design: `docs/adr/ADR-0009`. Details: [anchored-state.md](anchored-state.md) |
| `freeze-phase-docs.sh` | `~/.claude/scripts/freeze-phase-docs.sh` | Sets `status: frozen` on phase detail files after a Gate-Go — **only** from `draft` or `active`; `skeleton`, `living`, `archived` and already-`frozen` are left untouched. P5 and P8 are no-ops by design (iterative and operational phases never freeze). Details: [anchored-state.md](anchored-state.md) |
| `baseline.sh` | `~/.claude/scripts/baseline.sh <version> [projectdir]` | Mechanical preparation for a release baseline cut. Writes `docs/.baseline-prep.md` (a volatile report, not `BASELINE.md` itself) for `/release-baseline` to work from. **`<version>` is required**, not optional. |
| `workitems.py` | `~/.claude/scripts/workitems.py <subcommand>` | Work-item CLI dispatcher (ADR-0002). Reads `workitems.provider` from **`.claude/settings.json`** — not a repo-root settings file — and dispatches to `lib/workitems/<provider>.py`. Default and reference backend is `local`: no server, no token, structured Markdown under `docs/workitems/`. Full reference: [../WORKITEMS.md](../WORKITEMS.md) |
| `migrate-review-headers.sh` | `~/.claude/scripts/migrate-review-headers.sh [projectdir]` | One-off backfill of `kind: review` + `sprint` + the commit-anchor family onto `docs/reviews/SPRINT-<N>-review.md` files that predate the header schema. Idempotent; a no-op once migrated. |
| `log-cleanup.sh` | `~/.claude/scripts/log-cleanup.sh [--days N] [--dry-run]` | Trims session and aggregated logs under `~/.claude/logs/`. Default: everything older than **7 days**. Runs automatically at `SessionStart`, throttled to once a day; call it by hand for a different `--days` or a `--dry-run`. |
| `artifact-gate.sh` | `~/.claude/scripts/artifact-gate.sh [--repo <dir>] [--require-denylist] [<file> ...]` | Sweeps a repository's tracked files for secrets, personal data and configured tenant/project names (Constitution Inviolable enforcement). Shipped since **`v0.3.0-beta`**. Details: [discipline-gate.md](discipline-gate.md) |

### Shared Libraries

Python and shell modules in `~/.claude/scripts/lib/`:
- `next_steps.py` – Phase-to-commands mapping, HANDOVER.md parser
- `artefacts.py` – Phase-to-expected-files mapping
- `gate_checklists.py` – Gate checklists with required sections + content pattern checks (regex)
- `discipline_gate.sh` – shared secret/personal-data/deny-list pattern library, sourced by `artifact-gate.sh` and `memory-sync.sh promote` — see [discipline-gate.md](discipline-gate.md)

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
