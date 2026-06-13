---
name: instincts-history
description: Rolling postmortem history of `~/.claude/instincts.md` — full Last-updated/Previous narrative blocks plus long-form "Last confirmed" decay diagnostics that were trimmed from the topic files. Each `/postmortem` appends one block to the Header-Snapshot code box (newest on top). Not autoloaded — read on demand for retrospective analysis. **In CCPR this file ships empty as a demo placeholder; populate it locally via `/postmortem` in your own sessions.**
type: archive
scope: tier-1-global-history
last_updated: 19.05.2026
---

# Instincts History (Demo Placeholder)

This file demonstrates the archive slot of the **Index + Topic + Archive** instincts structure. In CCPR it ships as a placeholder; in your local `~/.claude/instincts-archive/HISTORY.md` it grows over time as `/postmortem` appends the verbose postmortem narrative that was trimmed from the slim index.

## Purpose

- Keep the slim index (`~/.claude/instincts.md`) fast to autoload at session start (target: ≤25 KB).
- Keep the topic files (`~/.claude/instincts/{theme}.md`) focused on the actual Rule / Why / How to apply, with a single-line `Last confirmed` summary per instinct.
- Park the verbose postmortem prose — session hashes, tool-call counts, bump narratives, decay diagnostics — in this archive file, where it stays available for retrospective analysis without weighing down the autoloaded path.

## Convention

Every `/postmortem` adds one block at the top of the **Header Snapshot** section below (newest on top). The previous `Last updated:` block moves one position down to become `Previous:`. Older blocks roll further down. The slim index keeps only the latest `Last updated:` + the two most recent `Previous:` one-liners — full context lives here.

## Header Snapshot (rolling postmortem stream — newest on top)

```
# Global Instincts

Confidence-based rules from session experience (0.3-0.9).
Last updated: <DD.MM.YYYY> (your first postmortem will replace this placeholder — see `~/.claude/commands/postmortem.md` for the write convention)

(no previous postmortem blocks yet — start populating via `/postmortem`)
```

## Decay narratives (long-form, optional)

The slim "Last confirmed" line in each topic-file entry stays at ≤2 lines. When a `/postmortem` documents a confidence bump or decay with detailed evidence (multiple session hashes, cross-story confirmations, sub-rule additions), the long-form rationale is appended here under an `## Instinct Bump/Decay Narratives` section. The topic file only carries the resulting confidence value and the one-line summary.

```
## Instinct Bump/Decay Narratives

(populated by /postmortem when an entry's bump/decay rationale is longer than one line)
```
