---
disable-model-invocation: true
---
# /anchor – Anchored State Verification (Docs vs. Implementation)

Checks phase documents against the code they describe, not against other documents. Where
`/cross-check` compares Markdown to Markdown, `/anchor` compares a document's declared
`anchor_commit` to the repository's actual history — the two-stage check design of
`docs/adr/ADR-0009-anchored-state-verification.md` (both addenda).

## Argument: $ARGUMENTS = [optional: projectdir] [--scope <folder>]

- Without argument: operates on `$(pwd)`.
- `--scope <folder>` restricts the run to one phase folder (`discovery`, `concept`,
  `validation`, `architecture`, `planning`, `quality`, `launch`, `operations`).

## Prerequisites

- A git repository with at least one commit.
- At least one phase folder under `docs/` (`discovery/`, `concept/`, `validation/`,
  `architecture/`, `planning/`, `quality/`, `launch/`, `operations/`).
- Not required, but the reason a run reports mostly "not verified": an anchor written on the
  phase index via `anchor set` (normally done by the freeze hook on a Gate-Go, ADR-0009
  Addendum 2).

## Lead Agent

Orchestrator runs Stage 1 directly (a mechanical script call, nothing to delegate). Stage 2's
per-document judgment can be done by the orchestrator or delegated to **code-reviewer** /
**system-architekt** for a scope with unfamiliar code — in either case, the agent doing Stage 2
is bound by **The agent clause** below (§3 is the escalation step, not the clause).

## Execution

### 1. Stage 1 — mechanical delta (no verdict)

Run exactly:

```
bash ~/.claude/scripts/anchor.sh check [projectdir] [--scope <folder>]
```

This is the **only** source for Stage 1 data — do not re-derive the delta by hand (e.g. `git
diff` against a guessed commit). The report already contains, per scope: the resolved
`anchor_commit`/`anchor_date`, the last production-code commit, the changed production-code
paths, which document(s) claim each path via `covers:`, and the full "Affected documents"
list per scope with each document's own `status`.

**Exit-code discipline (read this before touching the exit code):** `check` follows a
contract that is deliberately different from `phase-docs-lint.sh`. **Exit 0 means "a report
was produced" — with or without drift.** A drift finding never makes `check` exit non-zero;
staleness is not itself a verdict (ADR-0009, "the check is two-stage, and staleness is never
itself a verdict"). A **non-zero exit is always an operational failure** — no git repository,
no `docs/` structure, or a bad argument — never a content finding. Treat exit ≠ 0 as "the run
could not be performed", not as "drift found", and stop before Stage 2: there is no delta to
evaluate.

If no scope in the report carries an anchor at all, say so plainly and stop — this is the
project's **"not verified"** state, not a failure of the check and not something to paper
over as "clean". Report it exactly as the script does (`not verified — no phase index` /
`not verified — index has no anchor_commit`).

### 2. Stage 2 — severity, scoped to the delta only

For every document that Stage 1 lists as **affected** in a scope carrying a real delta (case
`ok` with a non-empty changed-path list), ask exactly one question, scoped to that document's
**delta only** — the changed production-code paths claiming it, not the whole document:

> Does this delta invalidate a statement in this document?

Do **not** re-read the whole document against the whole codebase; that reintroduces the
base-rate problem ADR-0009's two-stage design exists to defuse (staleness is common,
invalidated claims are rare — the question must stay narrow enough that only the rare case
answers "yes").

- **No** → no finding for this document. A document can be stale (code moved under it) with
  no invalidated claim; that is the expected, majority case during active development and
  carries no severity by itself.
- **Yes** → severity comes from the document's **own** `status` field — never the scope
  index's `status`, which may differ (ADR-0009 Addendum 2, "the phase index's `status` is not
  machine-guaranteed, so severity must not read it"):

| Document's own `status` | Severity | Action |
|---|---|---|
| `living` | info | report only |
| `active` | warning | report **and** open a work item (§3) |
| `frozen` | error | report **and** open a work item (§3) |

A document with no anchor of its own and no index anchor for its scope never reaches this
step — it stays "not verified" from Stage 1, which is neither a pass nor a finding.

### 3. Escalation — one work item per confirmed invalidation

For every "Yes" finding at `active` or `frozen` severity, open exactly **one** work item —
one per confirmed invalidation, not one per changed path and not one per document that merely
shows drift with no invalidated claim:

```
python3 ~/.claude/scripts/workitems.py create --title "Anchor drift: <document> vs <path(s)>" \
  --type chore --tag anchor-drift \
  --description "<what changed, which claim it invalidates, the anchor delta (old..new SHA)>"
```

This is `workitems create` exactly as specified in `Manual/WORKITEMS.md` §1/§4 — no contract
change, `local` backend by default. Apply the adoption guard from `Manual/WORKITEMS.md` §8
before calling it: check `python3 ~/.claude/scripts/workitems.py list` **and** whether
`docs/workitems/` exists: an adopted store gets the CLI call above; a project still on prose
gets the finding written into `docs/HANDOVER.md`'s `## Open Points` inbox instead (marker
format per `commands/cleanup.md` §1), plus the one-line tip `Manual/WORKITEMS.md` §8
specifies.

### 4. The quittance statistic — every run, not a separate call

Every `/anchor` run, `check` or `status` alike, ends by running:

```
bash ~/.claude/scripts/anchor.sh status [projectdir]
```

and reporting its closing line verbatim:

```
**Anchors:** N anchored · M asserted without doc change · K stale
```

If more than one actor has an `asserted` acknowledgement anywhere in the project, a second
line follows, breaking the count down by who acknowledged (`anchor_ack_by`, grouped by
email — ADR-0009 Addendum 3):

```
   asserted by: a@example.org (6), b@example.org (1)
```

Report that line too, verbatim, when it appears; a single actor prints none. This is not
optional and not a separate invocation the user has to remember to run — ADR-0009 §6
requires it as the detector against the mechanism turning into ceremony. A rising count of
`asserted without doc change` relative to `anchored` is the early warning; call it out
explicitly if the ratio looks high (no fixed threshold is defined yet — use judgement and say
why you flagged it). The per-actor breakdown is the same detector made actor-aware: one
person's assertions dominating the count is now visible without `ack` refusing anyone or
checking who they are — acknowledgement authority is **attribution, not restriction**
(ADR-0009 Addendum 3), so do not read a lopsided breakdown as a permission problem to fix in
the script; it is a working-agreement question for the team.

## The agent clause — binding, and stated honestly

**Never run `anchor ack` yourself. Report the delta, let the user decide.**

This applies to `/anchor` itself and to every subagent briefing `/anchor` writes when it
delegates Stage 2 — copy this clause into that briefing verbatim, it does not travel by
implication.

State plainly what this clause is and is not: **prevention, not enforcement.** `anchor ack`
does check for a terminal on stdin (`[ -t 0 ]`) and refuses its **interactive** fallback
prompt without one — measured directly: a plain pipe into `ack` with no flags dies with exit
2, "ack requires --assert or --update when stdin is not a terminal", and writes nothing. But
that guard covers only the interactive prompt. The flagged path —
`anchor ack <target> --assert --note "…"` (or `--update`) — needs no terminal at all and runs
to completion non-interactively; **measured directly**, it writes `anchor_ack: asserted` from
a plain non-interactive shell call, no pipe trick, no TTY. Nothing in the script stops an
agent with Bash access from calling it. So: **there is no hard technical boundary here.** The
clause above is the prevention; §4's statistic is the detection; only the two together are
the honest construction ADR-0009 asks for. Do not claim a safety that does not exist.

## When to use

- After a Gate-Go freeze, once `anchor set` (via the freeze hook) has written a fresh
  scope anchor — to see whether anything already moved.
- Before a Gate, alongside `/cross-check` as a sensible neighbour run: `/cross-check` finds
  Markdown-vs-Markdown drift, `/anchor` finds docs-vs-implementation drift; neither
  substitutes for the other (see `/cross-check`'s R6 note).
- On suspected staleness — a component doc that "hasn't been touched in a while" while its
  `covers:` paths keep changing.
- Periodically during a long-running P5/P8 phase, as a light check-in (`anchor status` alone,
  no `check`, is cheap and needs no Stage-2 judgement).

## When NOT to use

- On a project with no phase index anchored yet — the run will report "not verified"
  everywhere and nothing else; run `anchor set --scope <folder>` (normally via the freeze
  hook) first, or accept that there is nothing to check yet.
- During an active TDD cycle — disruptive, and the delta will include your own
  work-in-progress commits.
- As a substitute for `/cross-check` — the two rule sets do not overlap; see `/cross-check`'s
  R6 note for the boundary.
- To decide whether an anchor is still valid — that is what `anchor ack` is for, and it is a
  **human** decision (see the agent clause above), never something `/anchor` itself resolves.

## Result

- Console output: Stage 1's report, the Stage 2 findings (if any), any work items opened, and
  the closing quittance line from §4.
- `docs/.anchor-report.md` (volatile file, overwritten on every re-run — same convention as
  `docs/.cross-check-report.md`).

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md` only if a warning- or error-severity finding was confirmed — otherwise
the report file and the console summary are sufficient.
