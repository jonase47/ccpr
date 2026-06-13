# /p5-review-sprint – Holistic Sprint Code Review (whole-context)

Runs ONE final code review over the **entire sprint** at sprint end, with a stronger model, to catch issues that single-story reviews structurally cannot see: cross-story interactions, the schema/data model as a whole, conformance to ADRs and Constitution Inviolables, and consistency with prior lessons/instincts.

This is **complementary** to `/p5-review-code`, not a repeat of it. The per-story review runs during the sprint, is narrow and local, and also surfaces "good things". This pass is broad and architectural — it deliberately does **not** re-do the per-story nitpicking.

## Argument: $ARGUMENTS = [optional: sprint number or git base ref]

- Without argument: review the current sprint (stories from `docs/planning/SPRINT.md`, diff from the sprint's base commit to `HEAD`).
- With a sprint number (e.g. `6`): review that sprint.
- With a git ref (e.g. a tag or SHA): use it as the diff base.

## Prerequisites
- Sprint implementation complete (all stories at least through `/p5-review` per story).
- Either run manually before `/gate-p5`, or let `/gate-p5` run it automatically (the gate triggers this review on opus when no current report exists). Mirrors `/cross-check` for docs, but unlike `/cross-check` the sprint gate runs it for you.
- Working tree committed, so the diff reflects the committed sprint work.

## Agent
- **Type**: code-reviewer
- **Model**: opus

*Rationale (why opus here, cheaper models elsewhere): this pass reasons across the full sprint diff and the architecture anchors at once. The findings it targets — a constraint anti-pattern repeated across a migration, a job-queue/coalescing semantics gap, drift from an ADR or Inviolable, a lesson applied in one module but not its sibling — require holding the whole sprint in context and the stronger model to connect the dots. That cross-context reasoning is the entire point of the pass, and it runs once per sprint, so the cost is bounded. Per-story reviews stay on the cheaper model.*

## Context (Orchestrator prepares)
Orchestrator gathers and provides inline:
- **Sprint diff**: resolve `<sprint-base>` in this order — (1) `base_commit` from the current sprint's frontmatter (`docs/planning/SPRINT.md`, or the active `sprint/SPRINT-NN.md` if SPRINT.md is a sub-index); (2) a `sprint-<n>-start` tag if present; (3) ask the user once if still unresolved. Then provide `git diff <sprint-base>..HEAD --stat` plus the full `git diff <sprint-base>..HEAD`.
- **Sprint goal + story list**: from `docs/planning/SPRINT.md` — what the sprint set out to deliver.
- **Conformance anchors** (read-only context, not re-reviewed line by line):
  - `docs/CONSTITUTION.md` — Inviolables, verbatim.
  - `docs/architecture/ADR/*.md` — the active ADRs the diff touches.
  - Migrations contained in the diff — full text (the schema is reviewed as a whole, not table by table).
- **Prior lessons**: `docs/memory/code-reviewer/instincts.md` and `docs/memory/MEMORY.md`, so recurring patterns can be checked against what was already learned and new instinct candidates surfaced.

## Prompt Template
> **Goal**: Holistic end-of-sprint code review for Sprint [N] — find what per-story reviews cannot see.
>
> **Sprint goal & stories**:
> [from SPRINT.md]
>
> **Full sprint diff**:
> [git diff <base>..HEAD]
>
> **Conformance anchors**:
> - Inviolables: [verbatim from CONSTITUTION.md]
> - Relevant ADRs: [inline]
> - Migrations: [full text from the diff]
>
> **Prior lessons / instincts**:
> [from code-reviewer instincts + MEMORY.md]
>
> **What to focus on — this is the whole value of the pass:**
> 1. **Cross-story interactions** — does code from one story break an assumption of another? Shared tables, shared helpers, ordering, transactions.
> 2. **Schema / data model as a whole** — constraints, nullability, indexes, RLS posture across *all* migrations in the sprint together. An anti-pattern that repeats across the migration is signal, not noise — flag the pattern, not just one instance.
> 3. **Conformance** — every shipped story against the Inviolables; the code against the ADRs it touches (no reintroduction of a rejected mechanism, no silent drift from a decided approach).
> 4. **Consistency with prior lessons** — does the sprint repeat a class of issue already encoded as an instinct, or apply a lesson in one place but not its sibling (e.g. a determinism or SQL-construction norm enforced in module A but not module B)?
> 5. **Async / concurrency correctness** — job-queue semantics, coalescing/uniqueness, transactional boundaries, retries, idempotency, staleness windows.
> 6. **Test confidence** — do the sprint's tests actually exercise the invariant their name claims? Flag false-confidence tests.
>
> **Do NOT** re-do local per-story nitpicks (naming, a single-function null check) — those were covered by `/p5-review-code`. If a local issue recurs across many files, report it once as a pattern.
>
> **Output Format**:
> ```markdown
> # Sprint [N] — Holistic Code Review (code-reviewer @ opus)
> _Reviewed range: `<sprint-base>..<HEAD-sha>` — record both SHAs (esp. `reviewed_head`) so `/gate-p5` can detect staleness._
>
> ## Verdict
> [2-3 sentences: overall posture, biggest risk]
>
> ## Findings
> | # | Severity | Scope | Finding | Direction |
> |---|---|---|---|---|
> | 1 | CRITICAL/HIGH/MEDIUM/LOW | cross-story / schema / conformance / async / test | what it is & why it matters across the sprint | suggested direction (no full code needed) |
>
> ## Conformance
> - Inviolables: [each — OK / BREACH + which story]
> - ADRs touched: [each — consistent / drift]
>
> ## Instinct candidates
> [Any whole-context pattern worth encoding as a new instinct (PI-NNN style): rule + why + a suggested confidence. Suggest only — do not write the instinct file.]
>
> ## Confirmed positives
> [What the sprint did well at the architectural level — preserve these.]
> ```
>
> **Constraints**:
> - Severity: CRITICAL (correctness/security blocker), HIGH (fix before gate), MEDIUM, LOW.
> - This is a holistic pass: produce findings and flag assumptions inline rather than blocking on questions.
> - Scope: code correctness + cross-cutting + conformance. Security-relevant cross-cutting may be noted, but the full security review stays with `/p5-review-security` and deep pentest with `/p6-pentest`.

## Orchestrator Checkpoint
- [ ] Diff base resolved correctly (covers the whole sprint, no unrelated commits)?
- [ ] Inviolables + touched ADRs actually passed into the prompt?
- [ ] Findings are cross-cutting (not duplicating per-story nitpicks)?
- [ ] Instinct candidates separated from findings?

## Output
- Sprint review report: `docs/reviews/SPRINT-[N]-review.md`
- Record the reviewed range in the report header — the base commit and the **reviewed `HEAD` SHA** (`reviewed_head`). `/gate-p5` reuses the report only while `reviewed_head` matches the current `HEAD`, and re-runs this review otherwise (e.g. after a `/p5-bugfix`).
- This report is the input for `/gate-p5` (read under "Code review: no open critical findings"). `/gate-p5` runs this review automatically when no current report exists, so running it manually here is optional — an early look before the gate; the gate then reuses the fresh report rather than spending opus twice.

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points (esp. any CRITICAL/HIGH carried into the gate)
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. On CRITICAL/HIGH findings: `/p5-bugfix` before `/gate-p5`.
2. Otherwise: `/gate-p5`.
3. If an instinct candidate was surfaced: consider `/instinct` to evaluate and (if accepted) record it.
