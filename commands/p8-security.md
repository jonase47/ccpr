---
disable-model-invocation: true
---
# /p8-security – Ongoing Security: Dependency Updates, Scans & Re-Tests

Keeps the security of the running system current: regular dependency updates, security scans, checking for new CVEs, and periodic re-tests of critical areas. Security is not a one-time task – it must be continuously maintained.

## Argument: $ARGUMENTS = [Focus, e.g. "Dependencies", "full scan", "Re-Test Auth", "CVE check"]

If provided: Execute the specified security task.
If not provided: Read TECH_STACK.md and SECURITY.md and conduct a complete security update review. If any context is missing, ask about the desired focus or recommend the standard procedure.

## 0. Work-item adoption guard (ADR-0002 §8)

Run `python3 ~/.claude/scripts/workitems.py list`.
- **Non-empty array** → the project uses the structured store. Use the CLI for the Critical
  findings in step 4 below (instead of appending BACKLOG.md prose).
- **`[]` and no `docs/workitems/` directory** → still on prose. Append Critical findings to
  BACKLOG.md as before. Emit one line: *"Tip: run `lift` to adopt the structured work-item store."*
- **`[]` but `docs/workitems/` exists** → adopted store, just empty right now. Treat as adopted: use
  the CLI, not the prose fallback.

See Manual/WORKITEMS.md §8 for the full guard rationale and the status-verb mapping.

## Execution

### 1. Read Context
Read the following files (if available):
- **SECURITY.md** (security architecture and requirements – reference document)
- **TECH_STACK.md** (all dependencies and versions)
- **SECURITY_AUDIT_REPORT.md** (most recent audit as comparison basis)
- **PENTEST_REPORT.md** (most recent pentest findings as re-test baseline)

### 2. Delegation to Security Master Agent (Lead)
Delegate security maintenance to the **security-master** agent:

> Execute the following security measures: **$ARGUMENTS**
> Reference: SECURITY.md, TECH_STACK.md, most recent audit/pentest as comparison basis.
>
> **A. Dependency Audit**
> - Scan all direct and transitive dependencies for known vulnerabilities (CVE database)
> - Prioritisation by CVSS score: critical (≥ 9.0) / high (7.0–8.9) / medium (4.0–6.9)
> - For each critical and high vulnerability: affected package, CVE ID, available update, effort
> - Are there packages without active maintenance or with announced end-of-life?
> - Recommendation: what must be updated immediately, what can wait?
>
> **B. Update Plan**
> - Which updates are breaking changes (major version)?
> - Which updates are low-risk (patch level)?
> - Order: first critical security patches, then minor, then major
> - Test strategy: which tests must remain green after the updates?
>
> **C. Security Scan (SAST & Configuration)**
> - Static code analysis: new vulnerabilities since the last scan?
> - Configuration check: have any security-relevant configurations changed?
> - Secrets scan: have any secrets accidentally ended up in the code or git history?
> - Security headers: are all HTTP security headers still set correctly?
>
> **D. Periodic Re-Test** (recommended: quarterly)
> Check whether known vulnerabilities from the last pentest are truly resolved:
> - Take the fixed findings from PENTEST_REPORT.md
> - Test each fix: is it still effective? Has an update reverted it?
> - Are there new attack surfaces from new features since the last pentest?

### 3. Delegation to Pentester Agent (Support)
Delegate re-testing of critical areas to the **pentester** agent:

> Conduct a targeted re-test if new features or changes have been deployed since the last pentest:
> 1. Which new features since the last pentest are security-relevant?
> 2. Test these specifically against the most common attack vectors (Auth, IDOR, Injection)
> 3. Are the fixes from PENTEST_REPORT.md still effective?

### 4. Write Detail File
This subskill maintains a **living** detail file `docs/operations/SECURITY.md`. It is overwritten on each call with the latest security update; full per-update detail can optionally be archived as `docs/operations/snapshots/SECURITY_UPDATE_<YYYY-MM-DD>.md`.

Write `docs/operations/SECURITY.md` (overwrite). Frontmatter:

```yaml
---
phase: P8
subskill: security
status: living
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Update Period`, `## Dependency Audit Results`, `## Updates Performed`, `## Scan Results` (new vs. resolved findings), `## Re-Test Results`, `## Open Items` (with deadline).

Cross-file update: refresh `docs/architecture/SECURITY.md` (P3 sub-index) if new findings affect the security architecture; bump its `last_updated`.

### 5. Update Phase Index
Update `docs/operations/OPS.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[SECURITY.md](SECURITY.md)` with status `living`.
- Lift any active Critical/High security finding into **Open Risks**.

Cross-file update, using the guard result from step 0:
- Structured store: `workitems create --title "<finding>" --type fix --tag security --description
  "<finding + CVE/CVSS + remediation>"` per Critical finding (check the full, unfiltered `workitems
  list` for a matching title first — trim + casefold — so a re-run never duplicates an
  already-created finding; record the assigned `**Work-Item:** WI-NNNN` id in this file's `## Open
  Items`). `--tag` marks the finding as `security` as a real, queryable field (`list --tag
  security`) — no more description prefix.
- Prose fallback: append Critical findings as new items to `docs/planning/BACKLOG.md` (for
  `/p8-iteration`) and bump its `last_updated`.

## Result

- **`docs/operations/SECURITY.md`** (latest security update log)
- Optional **`docs/operations/snapshots/SECURITY_UPDATE_<date>.md`** (per-update detail)
- Updated dependencies in the repository
- Updated **`docs/architecture/SECURITY.md`** (P3 sub-index) if applicable
- **`docs/operations/OPS.md`** (phase index updated)
- Critical findings as new work items (structured store) or new items in `docs/planning/BACKLOG.md` (prose fallback) — either way, input for `/p8-iteration`

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
