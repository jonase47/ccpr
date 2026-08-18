# Handover – Work State

> **Size cap**: HANDOVER.md is a **snapshot**, not a journal. Keep it ≤5 KB (~150 lines).
> When this file grows beyond the cap, move the oldest content block (a previous session's
> "What Was Achieved" / "Last Action" / postmortem entry) to
> `docs/.handover-archive/<YYYY-MM-DD>-<slug>.md` (one file per archived block).
> The current file should always answer one question: **"Where do I pick up from here?"**
>
> **This is watched for you**: `~/.claude/hooks/agent-monitor.py` measures this file at session start
> and after every write to it, and prints a warning as it approaches the cap and again once it is
> over. The warning never blocks and never edits the file — run `/cleanup` to archive the oldest
> block. Approaching the cap, `/cleanup` offers the archive and you may decline; over the cap it
> archives on confirmation.

**Last Updated**: [Date, Time]
**Session ID**: [if known]

## Current Phase
**Phase**: [P0-P8]
**Status**: [What is currently running]

## Last Agent / Command
**Last Active**: [Agent name or Command]
**Result**: [1-2 sentences of what happened]

## What Was Achieved (this session only)
- [Completed item 1]
- [Completed item 2]

## Open Decisions
| Decision | Context | Urgency |
|---|---|---|
| [What needs to be decided?] | [Why?] | High/Medium/Low |

## Next Steps
1. [Next concrete step]
2. [After that]

## Open Points (append-only inbox)
> Findings made **outside** the current assignment (stale doc, missing check, follow-up idea).
> Any agent **appends** one line; nobody rewrites or deletes another's line. `/cleanup` triages and
> clears this section — the only place lines are removed, and only after you confirm. `/p5-polish`
> lands its `handover`-triage items here. What the PO must decide belongs in **Open Decisions** above.
> One line, ≤120 characters, no sub-bullets — detail goes in the file you reference, not here.
> **Ceiling 10 entries (~1 KB)**: at the ceiling append anyway, then flag "inbox full → `/cleanup`".
>
> **Format** — five ` | `-separated fields, starting at column 1 with the marker `- INBOX`:
> `- INBOX | DD.MM.YYYY | who noticed it | the finding, one line | file:line, POL-/WI-ID, or -`
>
> - `/cleanup` finds entries by that marker (`grep -c '^- INBOX [|]' docs/HANDOVER.md`), not by this
>   heading — so a renamed heading still works, and this quoted example is **not** an entry: a fresh
>   HANDOVER counts 0.
> - No `|` inside the finding text — write `/` instead. The **last** field is always the reference.
> - Placement is load-bearing: keep this section **below** the next-steps section.
>   `scripts/lib/next_steps.py` takes the first match in the file, so an entry sitting above it
>   would rewrite the project's allowed commands.

<!-- append inbox entries below this line -->

## Modified Files (this session)
| File | Action | Status |
|---|---|---|
| [file path] | Created/Modified | Done/In Progress |

## Context for Next Session
[Everything the next session needs to know to continue seamlessly.
Maximum 5 sentences.]

## Archive
Past sessions live in `docs/.handover-archive/`. Reference relevant archived entries here only when their context is still load-bearing for the current state — link by date:
- `docs/.handover-archive/<YYYY-MM-DD>-<slug>.md` — [1-line summary why it still matters]
