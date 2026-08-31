---
kind: adr
adr_id: ADR-0012
adr_status: accepted
status: active
last_updated: 31.08.2026
related:
  - ADR-0009-anchored-state-verification.md
  - ../CONSTITUTION.md
---

# ADR-0012: Derived values are not stored

**Status:** Accepted (31.08.2026)
**Decision-makers:** Repo owner (Jonas)

## Context

This repository keeps being bitten by one class of defect: a number or a claim that could be
derived from a source is instead typed into a second place, where it ages without anyone
noticing. The register and its subject are edited at different times by different hands, so
nothing contradicts the stale copy.

The rule against it has been applied, cited and reasoned from for months — under the label
"R1", and once as "the A1 rule". Neither is defined anywhere. A search across `docs/`,
`Manual/`, `CLAUDE.md`, the ADRs, `docs/decisions/` and the memory silos on 31.08.2026 found
"R1"/"R2" used as labels for past work slices, and an "A1 rule" attributed in a memory file to
no document that exists.

A rule cited by a name that resolves to nothing is the same defect it forbids: a reference whose
target is not there. This ADR gives the label an address.

## Decision

**What is derivable is generated, not stored.** If a value can be computed from a source this
repository already holds — a file count, a catalogue size, a threshold, a status — the consumer
derives it at runtime. It is not typed into prose, a docstring, a second register or a report
that outlives the run.

**Pins are the named exception.** A pin stores a derived value on purpose so that a change to
the source *breaks the build*. Breaking is the pin's entire function, not a side effect. A pin
is therefore not a violation of this ADR; it is the mechanism by which the ADR is enforced where
runtime derivation would silently absorb the change instead of reporting it.

Two obligations follow, and both are part of the decision:

1. **A pin names itself as a pin, at its own site.** Whoever reads it must be able to tell it
   from an ordinary stored value, or they will "repair" it by deriving it — and remove the guard.
2. **A pin records how it moved.** A count delta cannot distinguish "one added" from "one added,
   one gone", so a bump carries a **set** proof: the additions named individually, the removals
   stated explicitly, measured against a specific commit.

## Consequences

Deriving costs more at write time than typing a number, and a pin costs a deliberate bump
whenever its source legitimately changes. Both are accepted: the alternative is a value that is
wrong without being noticed, which this repository has now paid for repeatedly.

Where a value cannot be derived — an editorial judgement, a decision that belongs to a person —
this ADR does not apply. Such a value is declared, and what is placed under test is **drift**:
a new input the declaration does not cover fails as unclassified rather than passing silently.

## What this ADR does not contain

**A list of instances.** The occurrences of this class are recorded as work items and are
referenced by ID from the places that need them (`python3 scripts/workitems.py get WI-0133`).
A hand-maintained instance list inside an ADR about stored derivations would be the next
instance of the class.
