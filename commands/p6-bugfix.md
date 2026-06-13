# /p6-bugfix – Fix QA Findings

Fixes bugs and vulnerabilities found during the QA phase (functional tests, exploratory tests, accessibility check, security audit, pentest). Each fix is secured by a regression test.

## Argument: $ARGUMENTS = [bug description/finding ID from a QA protocol]

If provided: Fix the specified finding or the bug with the given ID.
If not provided: Read all QA protocols (TESTPROTOCOL_*.md, SECURITY_AUDIT_REPORT.md, PENTEST_REPORT.md) and ask which findings should be fixed with priority. Do not make assumptions about the order.

## Execution

### 1. Read Context
Read the following files (if present) to understand the finding context:
- **TESTPROTOCOL_FUNCTIONAL.md** (functional bugs)
- **TESTPROTOCOL_EXPLORATORY.md** (exploratory findings)
- **TESTPROTOCOL_A11Y.md** (accessibility findings)
- **SECURITY_AUDIT_REPORT.md** (security audit findings)
- **PENTEST_REPORT.md** (pentest findings)
- Relevant source code files (derive from finding description)

### 2. Delegation to Debugger Agent (Lead)
Delegate the root cause analysis to the **debugger** agent:

> Analyse the following finding from the QA phase: **$ARGUMENTS**
> Finding details: [Insert description, affected component, severity from QA protocol]
>
> **A. Root Cause Analysis**
> - Where exactly is the cause in the code? (file, function, line)
> - Why does the problem occur? (logic error, missing validation, insecure implementation)
> - Is the finding present only at this location or at multiple places in the code?
> - Are there related findings that share the same cause?
>
> **B. Security Findings (for security audit / pentest)**
> For security findings, additionally:
> - Which attack scenario does the fix prevent?
> - Are there mitigation measures that take immediate effect until the clean fix is deployed?
> - Does the Security Architecture in SECURITY.md need to be updated?
>
> **C. Accessibility Findings**
> For accessibility findings, additionally:
> - Which WCAG criterion does the fix satisfy?
> - Which user group benefits from the fix?
>
> **D. Fix Strategy**
> - Minimal, correct fix – what needs to be changed?
> - Risk: Does the fix affect other areas?
> - Which regression test needs to be written?

### 3. Delegation to Senior Developer Agent (Support)
Delegate the fix implementation to the **senior-developer** agent:

> Implement the fix for the following QA finding: **$ARGUMENTS**
> Root cause and fix strategy from the debugger analysis: [Insert results]
>
> 1. **Regression test first**: Write a test that reproduces the finding and fails (Red)
> 2. **Implement fix**: Minimal, correct fix (Green)
> 3. **All tests green**: Ensure all existing tests continue to pass
> 4. **Document fix**: What was changed, why, and which finding is thereby closed?

### 4. Commit & Update Detail File + Index
Commit after fix: `fix: [finding-ID] [description]` (build + tests must be green).

Append a row to **`docs/quality/BUGFIX.md`** (create with the following frontmatter on first run):

```yaml
---
phase: P6
subskill: bugfix
status: active
last_updated: <DD.MM.YYYY>
---
```

Body: `## Fix Log` table with columns `Date | Finding ID | Source File | Fix Summary | Regression Test`. Each `/p6-bugfix` run appends one row; the file accumulates all P6 fixes for traceability.

Also update the **originating** detail file in `docs/quality/` (e.g. `func_e2e.md`, `pentest_authz.md`, `audit_dsgvo.md`): mark the affected finding's status as `Fixed` in the findings table; if all blocking findings of that detail file are now Fixed, set its frontmatter `status: active` (or back to `complete`) and refresh the row in the relevant sub-index.

Update `docs/quality/QA.md` (phase index):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- Ensure `[BUGFIX.md](BUGFIX.md)` is in the **Detail Files** table.
- Reduce the corresponding entry in **Open Risks** when the underlying finding is closed.

## Result

- Bug fix code with regression test
- Updated detail file in `docs/quality/` (originating finding marked Fixed)
- Updated `docs/quality/BUGFIX.md` log + `docs/quality/QA.md` index
- Next step: Return to the originating command (e.g. `/p6-functional` or `/p6-pentest`) to verify the fix, then proceed to `/gate-p6`

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
