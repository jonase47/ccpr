---
name: instincts-shell-git
description: Global instincts for Bash CWD, destructive-action verification, mass-substitution tooling, commit-hook conventions and tranche-based mass-edit patterns. Loaded as Tier-1-global topic file alongside the slim index in `~/.claude/instincts.md`. Curated starter examples — adapt and extend through your own `/postmortem` runs.
type: instincts
scope: tier-1-global-topic
last_updated: 01.06.2026
---

# Shell / Git / Mass-Edit Instincts

Behavioural rules around Bash state (CWD persistence), verifying user claims before destructive git actions, robust mass-substitution tooling, single-token commit scopes and tranche-disciplined bulk edits. Sorted by confidence (descending).

---

### G-040: Verify user claims before destructive action
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When the user claims "X is already gone / done / deleted" and a destructive action is supposed to follow (`git rm -r`, `force-push`, `reset --hard`, `branch -D`, drop table, migration revert): diagnose first (`ls`, `git ls-files`, `git log --diff-filter=AD`, `find` for file existence), then execute. The user claim is a hypothesis, not a fact.
>
> **Why**: User perception ≠ repo state. Typical incident: "the PoC is gone locally" → diagnosis revealed 5 tracked files and 32 KB of code still git-tracked. Blind `git rm -r poc/` + push would have caused remote code loss + lost reference material.
>
> **How to apply**:
> 1. On a "X is gone/done"-style user claim: do NOT blindly execute the destructive action.
> 2. Pick a diagnostic command based on the domain:
>    - File existence: `ls -d <path>`, `find . -name <pattern>`
>    - Git tracking: `git ls-files <path>`, `git log --diff-filter=AD --name-status -- <path>`
>    - Code integration: `grep -rE <pattern> --include="*.{ext}" <src>/`
>    - Domain-specific: schema state, DB state, deployment state
> 3. Present the diagnostic output and confirm OR refute the user assumption.
> 4. On refutation: re-ask the user with the corrected fact base (a single clarifying question saves potential code loss). Even in auto-mode, this clarification is cheaper than a recovery commit.
> 5. On confirmation: execute the action.
>
> **Related**: G-030 (orchestrator reads with verified filename) and G-032 (optional memory paths verified ahead of time) follow the same verify-first philosophy for non-destructive operations.

---

### G-048: Mass substitution via find+xargs+perl instead of bash for-loop
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: For mass substitutions across >5 files: `find <dirs> -type f \( -name "*.md" -o -name "*.py" \) -print0 | xargs -0 perl -i -pe '<single-line>'` instead of `for f in $(grep -rln ...); do perl -i -pe '<multi-line>' "$f"; done`.
>
> **Why**: Multi-line perl in a bash for-loop isn't reliable (word splitting, multi-line quoting, "Can't open" / "File name too long" errors). find+xargs is robust against special characters and path variations.
>
> **How to apply**:
> - **>5 files = find+xargs**: `find ... -print0 | xargs -0 perl -i -pe 'SUBST1; SUBST2; ...'` (single-line, `;`-separated)
> - **<5 files = direct perl**: `perl -i -pe 'SUBST' file1 file2 file3` (multiple files as args)
> - **Never**: multi-line perl in a for-loop
> - **Verification required**: `grep -rln 'OLD_PATTERN' <dirs>` to confirm coverage
>
> **Related**: G-014 in `agents.md` delegates the same problem to an agent for very large bulk operations; G-048 is the self-execution variant for ≤50 files.

---

### G-052: Multi-tranche pattern for mass-edit / translation / refactor sweeps
**Confidence: 0.4** | Last confirmed: 14.05.2026 — CCPR English consolidation across ~25 files / ~13k words in 4 tranches: 0 rollbacks, 0 forgotten files, clear review granularity.

> **Rule**: For mass operations across >15 files / >5k words / >10 KB diff: structured split into tier-prioritised tranches (HOT → MEDIUM → LOW), **1 tranche = 1 commit**, grep verification between tranches, `TaskCreate`/`TaskUpdate` for tranche tracking, push only after all tranches (or interim push on user request).
>
> **Why**: A big-bang commit across 25+ files is not reviewable. Structured tranches give each commit a clear scope, allow per-tranche verification, and surface forgotten files before the next tranche starts.
>
> **How to apply**:
> 1. **Scope inventory first**: Phase 1 (Explore) lists every affected file with volume estimate + classification (HOT/MEDIUM/LOW or Tier 1/2/3/4).
> 2. **Tranche structure in the plan**: per tranche a separate list + verification command + commit-message skeleton in the plan file.
> 3. **1 commit per tranche**: Conventional-Commits style, tranche scope documented in the commit body.
> 4. **Grep verification between tranches**: `grep -rnE 'pattern1|pattern2' <scope>` with an expected hit list; if needed with an out-of-scope whitelist.
> 5. **Task tracking**: each tranche one task, status `in_progress` → `completed` per finish.
> 6. **Push strategy**: default at the end of all tranches; interim push only on explicit user request or when a tranche exceeds 50 files.
>
> **Related**:
> - G-014 in `agents.md` — delegate-to-agent variant for very large bulk operations.
> - G-048 above — tool choice within a tranche.
> - G-050 in `workflow.md` — scope inventory builds on glob lists.

---

### G-053: Conventional-commits scope takes no comma
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: Conventional-Commits pre-commit hooks typically reject comma-separated scopes like `test(domain,persistence): ...`. Scope is a single token. For cross-cutting changes:
> 1. **Broader umbrella term**: `test(persistence)` (mention domain in the body).
> 2. **No scope**: `test: ...` when no sensible single-token scope exists.
> 3. **Pick the primary domain**: files in multiple areas → the leading scope is the domain where the non-trivial code change lives; mention sibling changes in the body.
>
> **Why**: Most Conventional-Commits regex implementations enforce `<type>(<scope>): <subject>` with a single alphanumeric token for `<scope>`. A comma-separated list fails the regex.
>
> **How to apply**:
> 1. Before `git commit -m`: pick one scope instead of a list.
> 2. If unsure about the project's convention: omit the scope (`test: ...`) — most hooks accept that.
> 3. If a hook deviates (e.g. scope whitelist): read the hook regex once, note the allowed scopes.
>
> **Anti-pattern indicator**: commit message with `(scope1,scope2)` or `(scope1/scope2)` → hook rejects, commit must be rewritten.

---

### G-060: Skill-output commits need a standard conventional-commit type
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When a skill output is committed (gate result, postmortem update, polish closeout), the commit type must come **only from the project hook whitelist** — typically `{feat, fix, refactor, docs, test, chore, perf, build, ci, style, revert}`. Skill-specific custom types like `gate(...)`, `postmortem(...)`, `polish(...)` are rejected by the hook even when they seem semantically fitting. The skill name goes into the **scope**, not the type.
>
> **Pattern for skill outputs**:
> - Gate result: `docs(gate-pN):` or `docs(gate-pN-sprint-NN):`
> - Postmortem: `docs(postmortem):` (or `chore(postmortem):` for a pure memory/hygiene update)
> - Polish closeout (doc): `docs(p5-polish):`
> - Cleanup output: `chore(cleanup):`
> - Sprint plan (`/p4-sprint`): `docs(p4-sprint):`
>
> **Why**: A pre-commit hook validates only the 11 standard Conventional-Commits types — skill names are not hook-compatible. A custom-type attempt (e.g. `gate(p5-sprint-8): …`) is rejected and forces a re-commit, which can break the atomic-commit flow.
>
> **Anti-pattern indicator**: commit type is a skill name (`gate`, `postmortem`, `polish`, `sprint`, `cleanup`, `review`, `acceptance`, `bugfix`) → hook rejects.
>
> **Related**: G-053 above (conventional-commits scope takes no comma) — sister rule on scope form. G-044 in `workflow.md` (skill-prescribed frontmatter vs project schema) — same base rule: project convention beats skill default.
