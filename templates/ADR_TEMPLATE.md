# ADR Template

> Formal schema for an Architecture Decision Record. Written by `/p3-arch-adr`.
>
> **This template was reconstructed by measurement, not by design.** No template existed while
> this repository's first thirteen ADRs were written, so the convention below was derived from
> the corpus on 05.09.2026 (`docs/adr/ADR-0001…ADR-0013`, thirteen files, numbers gap-free,
> measured by directory listing). Section
> frequencies are quoted as `n/13` throughout, so a reader can tell a universal section from a
> common one. Where the corpus and the prescribing command (`commands/p3-arch-adr.md`) disagree,
> both are recorded — see **Two frontmatter dialects** below.
>
> Extracted because a shared block propagated by copy-paste is a block that drifts: the
> `adr_status`/`status` split had already drifted once (WI-0128) before anything bound it.

## Two frontmatter dialects — pick by where the ADR lives

There are two, they are both correct, and the difference is not stylistic.

| Where | Frontmatter | Why |
|---|---|---|
| **A project's own ADRs**, under `docs/architecture/ADR/` | The six fields below **plus** `phase: P3` and `subskill: arch-adr` | That directory sits inside a phase folder, so `scripts/phase-docs-lint.sh` validates it like any other phase-detail file and requires the phase triple. Prescribed by `commands/p3-arch-adr.md:67-77`. |
| **A framework/meta repository's own ADRs**, under `docs/adr/` | The six fields below, **without** `phase`/`subskill` | `adr` is not among `phase-docs-lint.sh:61`'s `PHASE_FOLDERS`, so a scopeless lint run never walks it. Measured: 13/13 of this repository's own ADRs use this shape. |

Everything else in this template applies to both.

## Required fields

Measured: all six present, in this order, on lines 2–7 of all 13 ADRs.

| Field | Values | Description |
|---|---|---|
| `kind` | `adr` | Doc-type marker. Validated against `scripts/manual-lint.sh`'s `VALID_KINDS` when that lint is pointed at the tree; `adr` is in the known set. |
| `adr_id` | `ADR-NNNN` | Four digits, matching the filename. The **decision's** identity. |
| `adr_status` | `accepted` \| `proposed` \| `rejected` \| `superseded`, **open beyond those four** | The **decision's** lifecycle. The four core values are universal ADR vocabulary; a project may mint its own (this repository uses `partially-implemented` for an accepted decision whose implementation has not fully landed) as long as its mapped `status` is valid. |
| `status` | `skeleton` \| `draft` \| `active` \| `frozen` \| `archived` \| `living` | The **document's** lifecycle — the enum `scripts/phase-docs-lint.sh` enforces (`VALID_STATUS`). Never the decision word. |
| `last_updated` | `DD.MM.YYYY` | Date of the last substantive edit to the file. |
| `related` | YAML block list, ≥1 entry | Paths to related ADRs and documents, **document-relative** (`ADR-0009-….md`, `../CONSTITUTION.md`, `../../templates/PHASE_DOC_SCHEMA.md`). Measured: 13/13 use the block form with at least one entry; none uses an inline list. |

### `adr_status` → `status` mapping

`status` and `adr_status` are two different lifecycles on two different fields. Writing the
decision word into `status` collides with the document-status enum and fails the lint.

| `adr_status` | `status` |
|---|---|
| `accepted` | `active` |
| `proposed` | `draft` |
| `rejected` | `archived` |
| `superseded` | `archived` |

A project-minted value maps to whichever of the six `status` values describes whether the
document currently governs the codebase — not how completely the decision has been carried out.
`partially-implemented` therefore maps to `active`. `scripts/tests/test_adr_status_mapping.py`
binds this table to the lint enum and to the real corpus.

## Optional fields

| Field | Values | Description |
|---|---|---|
| `verified` | `DD.MM.YYYY` | Date the document's factual claims were last checked against the thing they describe — not the date the file was edited (`last_updated`). |
| `verified_against` | Commit SHA, or a branch + date | The state the check ran against. A SHA is the preferred form. |
| `owner` | Role slug | Who is accountable for the document's accuracy. A role, not a person, so the field survives a handover. |

**These three are not mandatory in an ADR.** ADR-0014 scopes them to the human-documentation
tree (`handbook/`), explicitly excluding `docs/` and the framework allowlist entries. ADR-0014
itself carries them voluntarily, as a worked example. Do not read their presence in one ADR as a
requirement for the next one. Note also that `owner:` is a **homonym** of the work-item field of
the same name, which means "who has claimed this item" — see ADR-0014, decision 2.

## Filename

`ADR-NNNN-kebab-title.md` — four digits, lower-case kebab slug, `.md`. The next free number is
the highest existing plus one; derive it from the directory rather than from a list
(ADR-0012). A rejected or superseded ADR keeps its file and its number — it moves to
`adr_status: rejected|superseded` / `status: archived`, and `commands/cross-check.md:66,73`
reads that field to report active references to it. Whether a *number* may be reused is
untested: this repository has never rejected an ADR, so the corpus says nothing about it.

## Sections

Frequencies measured across the 13-ADR corpus, 05.09.2026.

| Section | Frequency | Status |
|---|---|---|
| `## Context` | **13/13** | Universal — always write it. |
| `## Decision` | **13/13** | Universal. |
| `## Consequences` | **13/13** | Universal. |
| `## Alternatives considered` | **12/13** | Near-universal. The one omission (ADR-0012) records a rule with no competing option, not a shortcut. Omit only when you can say why there was no alternative. |
| `## Follow-ups` | 6/13 | Optional — write it when the decision leaves open questions. |
| `## Notes` | 4/13 | Optional. |
| `## What this does not …` | 3/13, under three different headings | Optional but strongly encouraged for any ADR that decides a *mechanism*. See below. |
| `## Addendum (DD.MM.YYYY): …` | 9 headings across 5 files | Appended over time, never written up front. See below. |
| One-off sections | 1 each | e.g. `## Vendor coupling`, `## Implementation notes (validated against a live instance)`. Add one when the decision has a dimension the standard sections bury. |

**Order.** `Context → Decision → Consequences → Alternatives considered → Follow-ups` is the
dominant order: of the 12 ADRs carrying both, 10 put `Consequences` before
`Alternatives considered` and 2 invert it. Neither order is wrong; prefer the majority unless
the alternatives are what the consequences are *about*.

### The `## What this does not …` section

Three ADRs carry one, under three different headings (`What this cannot catch`,
`What this does not achieve`, `What this ADR does not contain`) — the wording follows the
decision, the section does not. Write it whenever the ADR decides a check, a gate or any other
mechanism: a strong-looking mechanism next to an unstated gap creates a sense of coverage the
gap does not support. Include **environment-dependency** gaps (a runtime the mechanism assumes
and does not have), not only design-scope gaps.

### Follow-ups and addenda — the two rules that keep them honest

An ADR carrying an open-questions list will drift, because resolving a question and updating the
list that advertises it are two separate acts and only the first is satisfying. The reader most
likely to be misled is the one using the list the way it invites: as a work queue.

1. **A resolved follow-up is struck through in place, with a pointer to what resolved it —
   never silently deleted.**

   ```markdown
   4. ~~**The original wording, kept.**~~ **Resolved in Addendum 3 (21.08.2026):
      the answer, in one sentence.**
   ```

   Half-resolved counts as half: say which half is settled and which is still open. If the
   answer diverged from what the follow-up asked for, record the divergence rather than
   smoothing it over.

2. **An addendum's heading names what it resolves** —
   `## Addendum 2 (21.08.2026): A7 resolved — where the scope anchor lives`. A reader working
   down the follow-up list has no other way to find the answer.

Applies to a framework repository's own ADRs. Whether adopter projects should follow it is a
separate question (`CONTRIBUTING.md`, "Record an ADR's resolutions in place").

## Skeleton

```markdown
---
kind: adr
adr_id: ADR-NNNN
adr_status: accepted
status: active
last_updated: DD.MM.YYYY
related:
  - ADR-MMMM-other-decision.md
  - ../CONSTITUTION.md
---

# ADR-NNNN: {The decision, as a statement — not a topic}

**Status:** {Accepted|Proposed|Rejected|Superseded} (DD.MM.YYYY){; qualifier, if any}
**Decision-makers:** {Role, e.g. Repo owner}

## Context

{What is the situation, and what forced a decision now? Cite `file:line` for every claim about
the repository — a number nobody measured is a claim, not a fact. Name what was measured, when,
and with which instrument.}

## Decision

### 1. {The decision, one heading per part}

{What was decided, and the reasoning recorded so the question is not re-litigated.}

## Consequences

**Positive.** {What this buys.}

**Negative.** {What it costs. An ADR with no negative consequences has not been thought
through — say what was traded away and why that was acceptable.}

## Alternatives considered

**{Option A}.** Rejected: {reason, specific enough that someone could disagree with it}.

**{Option B}.** Rejected: {reason}.

## Follow-ups

1. {Open question, phrased so it can be closed. Struck through in place when it is.}
```

## Lint

An ADR under `docs/architecture/ADR/` is validated by
`bash ~/.claude/scripts/phase-docs-lint.sh [<project-dir>]` (the `phase`/`subskill`/`status`/
`last_updated` schema). An ADR under a framework repository's own `docs/adr/` is outside
`PHASE_FOLDERS` and is not reached by a scopeless run. `bash ~/.claude/scripts/manual-lint.sh
[<root-dir>]` validates the `kind`/`parent_index` contract over whichever root it is pointed
at. Exit codes for both: 0 clean, 1 warnings, 2 errors.
