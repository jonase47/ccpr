---
kind: adr
adr_id: ADR-0013
adr_status: accepted
status: active
last_updated: 03.09.2026
related:
  - ADR-0007-shared-vault-storage.md
  - ../CONSTITUTION.md
  - ../../Manual/system/discipline-gate.md
---

# ADR-0013: A server-side push gate for the org-tier vault repo

**Status:** Accepted (03.09.2026)
**Decision-makers:** Repo owner (Jonas)

## Context

### The gap

The discipline gate (`scripts/lib/discipline_gate.sh`) scans content for secrets, personal data,
network literals and configured tenant/project names. It runs on exactly two client-side paths:
`memory-sync.sh promote` and `artifact-gate.sh`. A direct `git commit && git push` against the
shared org-tier vault repo (ADR-0007's `org:<name>` storage tier) reaches neither. This is not a
bypass trick — it is the more common route: the check sits on one of two paths, and the unchecked
one is the busier one.

### The incident that forced the decision

On 02.09.2026, 53 commits against the public distribution repo carried a private instance's
project short names in shipped content: ten occurrences as test-fixture ids in a `.py` file, one
prose sentence in an ADR, two code comments. This was found by a question from the PO, not by a
check — three code reviews across the same round read the affected files and reported nothing. The
repository was in violation of an Inviolable it states about itself (`docs/CONSTITUTION.md`: no
tenant identifiers in `scripts/` and `docs/`).

That incident travelled a different repo and a different transport than the one this ADR closes
(see "Reach", below) — it is cited here as the evidence that a check sitting only on the
`promote`/`artifact-gate.sh` paths is not sufficient discipline, not as a claim that this
mechanism would have caught it directly.

### Why not fix the dormant hook that already existed

A hook already existed in the vault repo, unused, from an earlier attempt. It read its gate logic
from `$newrev:tools/memory-sync.sh` — the pushed tip's own copy of the sync tool, materialized at
push time. Reusing it was rejected for two reasons, the second stronger than the first:

1. **Drift.** The vault repo's copy of the sync tool had gone stale — roughly eight weeks old, and
   the pattern definitions had since moved into `discipline_gate.sh`, which the vault repo's copy
   never sourced. Measured directly: the deny-list mechanism this incident concerns had **zero**
   occurrences of its own identifiers in that copy. Even active, this hook would not have caught the
   incident's pattern class.
2. **Self-defeat.** A gate that judges a push using code the same push can replace lets one commit
   rewrite the gate to `exit 0` and have that commit approve itself. This is a structural bypass in
   one line, not a staleness problem — no amount of freshness-checking on the pushed copy closes it,
   because the freshness check would itself be part of what the push replaces.

The gate's own code therefore always comes from the server's own deployed copy, resolved at the
hook's own filesystem location, never from the ref being evaluated.

## Decision

### 1. Server-side, `pre-receive`

The gate runs as a Forgejo `pre-receive` hook: git pipes every `<oldrev> <newrev> <refname>` line for
a push to the hook before any ref moves; a nonzero exit rejects the whole push and the incoming
object quarantine is discarded — nothing the hook saw ever lands in the repository. This is the
enforcement point a client-side check structurally cannot be: a local `pre-push` hook is bypassable
by anyone who can pass `--no-verify` or skip installing it, and this instance's collaborators push
directly to `main` by convention (see the CONSTITUTION.md Default rule this ADR's Part 2 adds). A
local hook remains valuable as fast feedback, but it is never the enforcement boundary.

### 2. One registry, not a copy

The scan patterns live exactly once, in `scripts/lib/discipline_gate.sh`. `artifact-gate.sh` remains
the scan-and-report layer. `push-gate.sh` owns exactly two things: **scope** — which paths, at which
blob, a push actually introduces — and the **translation** of the sub-gates' results into one exit
code. It calls `artifact-gate.sh` and `memory-sync.sh gate` as siblings resolved next to itself on
the server's own deployed copy; it does not reimplement pattern matching, text/binary classification
or finding rendering. Copying any of that into `push-gate.sh` would recreate the exact second-register
failure `discipline_gate.sh` exists to prevent — the failure this ADR's own "why not fix the dormant
hook" section describes happening once already.

### 3. Profile by path, not one profile for everything

The `artifact` profile (path-deny plus secret/personal/network/denylist checks) runs over every path a
push touches. The `memory` profile additionally runs over paths under `memory/` and `instincts/`
(configurable). The vault repo also carries ADR documents, a README and CI-adjacent files where a
checkbox, a "Next Steps" heading or a `type: user`-shaped line is legitimate structure, not a leaked
memory-promotion artifact — `discipline_gate.sh` already documents this as the reason the two
profiles are kept apart. The cost, named rather than left implicit: a file outside `memory/`/
`instincts/` carrying a TODO marker or `type: user` passes unexamined by the `memory` profile. For an
ADR that is intended. The residual gap is a memory-shaped page filed under a path neither profile's
`memory` prefix list covers.

### 4. Scan scope: every new commit, never the net diff

A leak that commit N introduces and commit N+1 removes is invisible in a diff between the push's old
and new tip, and would otherwise ship in history forever — rewriting history to remove it is out of
scope by design (this instance's own operating decision: no forced rewrite of shared history). The
scan set is therefore the union of every path touched by every commit the push introduces
(`git rev-list "$newrev" --not --all`), diffed one at a time. Above a configured commit-count cap the
push is **refused outright**, never silently degraded to a partial scan — an earlier draft of this
script fell back to a single diff against the ref's own old tip once the cap was exceeded, which a
review caught going blind to exactly the plant-then-remove shape this rule exists to close.

### 5. Five carriers, not one

The first draft of this mechanism checked file content and file path. A threat-model pass before
implementation, reproducing each carrier directly rather than reasoning about it abstractly, found
three more paths a leak can travel that never cross a content or path check at all:

- a **ref/branch name** carrying a name (a plant that would sit in every UI branch listing and every
  `git ls-remote` output, permanently, without ever being scanned as "content");
- a **commit message** (never seen by `git diff-tree`, which reports tree/blob diffs only);
- an **annotated tag's own payload** (a distinct object from the commit it names, with a message
  `git diff-tree` never touches, and — the harder case — a tag pointing at a commit some other ref
  already reaches, where the per-commit diff loop never runs at all).

All five are checked before a push is accepted. This is recorded as a lesson, not only a feature: a
gate built against "content and path" alone would have shipped with three unscanned carriers, found
only by deliberately trying to reproduce each shape rather than by inspecting the finished code.

## What this does not achieve

Stated in full, because a strong-looking check next to an unstated gap is worse than no check —
it creates a sense of coverage the gap does not support.

- **Binary content is never scanned**, only its path and the commit message that introduced it. A
  push consisting solely of binary content with a clean commit message is therefore **accepted**.
  This is a deliberate PO decision (03.09.2026), and a reversal of an earlier draft's stance: the
  earlier draft rejected an all-binary push outright, reasoning that nothing about it could be
  verified. That reasoning stopped holding once the commit message became an unconditional,
  independent scan candidate for every introduced commit (§5) — "nothing could be verified" is no
  longer true once the message is checked, even though the file bytes remain unverified. The
  underlying principle — "nothing scanned must never read as nothing found" — is unchanged; what
  changed is which content actually counts as "nothing".
- **Reach is limited to this one vault repo.** Other repositories on the same instance legitimately
  carry their own project names in their own content, so this hook is not installed instance-wide —
  a global hook would fire on exactly the content those repos are supposed to hold. This is a
  deliberate scope decision, not an oversight.
- **The transport on which the 02.09.2026 incident actually happened is not reached by this
  mechanism.** That incident travelled a public GitHub-hosted repository, not this instance's
  self-hosted Forgejo. This hook covers only pushes to the vault repo described here; the GitHub path
  is covered only by whichever machine has a local `pre-push` hook installed — a materially weaker
  guarantee, since it depends on installation and is bypassable by whoever pushes. A strong
  server-side hook on one repository must not be read as coverage for a different transport it never
  touches.
- **The checks are a regex best-effort over structural patterns**, not a language model reading
  intent. A plain name written out in prose, a paraphrased customer reference, or a screenshot
  carrying identifying information in its pixels are not caught. The GDPR-relevant boundary follows
  directly from this: the `personal` check class matches structural shapes — home paths, session
  hashes, email addresses — and demonstrably nothing beyond that. It does not catch free-text
  references to a natural person and it is not a control for Art. 9 special-category data. Anyone
  relying on this mechanism for a GDPR compliance claim beyond "structural leak patterns are
  mechanically checked" is relying on more than it provides.
- **The canary test proves the mechanism runs, not that the real list is correct.** A fixture name
  (this instance uses one already present in this repository's own shipped test fixtures, so the
  canary needs no real customer data and doubles as a post-deploy self-test) blocking a push proves
  the pipeline — ref parsing, scanning, exit-code translation, the whole path from git to rejection —
  actually executes. It says nothing about whether the deployed deny list contains the real names it
  is supposed to. Only a separate, direct verification of the deployed list closes that gap, and this
  ADR does not claim the canary substitutes for it.
- **The target server's runtime environment shapes what the gate can rely on, and it currently lacks
  two things the sub-gates otherwise assume.** The Forgejo container's base image has no `python3` —
  without it, the IP-allowlist configuration silently fails to load and every internal IP literal in
  scanned content becomes a finding. And its `grep` is BusyBox, which accepts the `-I`
  (treat-binary-as-non-matching) flag but silently ignores it rather than either honoring it or
  refusing it loudly — text/binary classification on this server therefore misclassifies binary
  content as text unless the deployment substitutes a capable `grep`. Both are deployment-layer
  gaps, not gaps in the gate's own logic, and both must be closed by the server's runtime image for
  the gate's stated guarantees to hold on this particular host.
- **`receive.fsckObjects` is not enabled on the target server**, and is not something this repository
  controls — it is a server-side git configuration outside this repository's artifacts. Git's own
  object-format validation (which would independently reject a tree entry with a path-escaping
  component such as a literal `..`) is therefore not active as a second, independent layer; the
  path-safety check inside `push-gate.sh` itself is the only active guard against that specific shape
  on this deployment, not a redundant belt-and-braces addition to one Git already provides.

## Alternatives considered

- **Keep sourcing the gate from the pushed tip's own copy of the sync tool.** Rejected — see "Why not
  fix the dormant hook that already existed" above: proven drift plus a structural self-approval
  bypass, not a staleness problem fixable by a freshness check.
- **Reimplement pattern matching directly inside `push-gate.sh`.** Rejected: recreates the exact
  second-register failure this ADR's own incident section describes, in a new file instead of an old
  one.
- **One global profile for every path, dropping the artifact/memory split.** Rejected: legitimate ADR
  and README structure (checkboxes, "Next Steps" headings) would trigger the memory-specific checks on
  every ADR push, training operators to ignore the gate's output — the same reasoning
  `discipline_gate.sh` already states for keeping the two profiles apart.
- **Scan only the push's net diff (old tip vs. new tip) instead of every introduced commit.** Rejected:
  blind to a leak planted in one commit and removed in a later commit of the same push, which still
  ships in permanent history.
- **Degrade to a partial scan once a commit-count cap is exceeded, rather than refusing outright.**
  Rejected during review: reproduces the exact plant-then-remove blind spot the commit-cap exists to
  close, just at a higher commit count.
- **Reject an all-binary push outright as unverifiable, keeping the earlier draft's stance.** Reversed
  by PO decision once the commit-message scan made "unverifiable" no longer accurate for that case (see
  "What this does not achieve", first bullet).
- **A warn-only fail-open switch for emergencies (a "break glass" environment variable).** Rejected: a
  fail-open toggle, once set under pressure, tends not to be reverted — the same failure shape this
  instance has already retired elsewhere (a silenced check swallowing its own non-zero exit). Rollback
  instead relies on making the hook non-executable, which is equally fast and leaves a visible trace.

## Consequences

**Positive.** The busier of the two push paths against the shared vault repo now runs the same
pattern definitions the client-side tools already use, with no second copy of the patterns to drift.
Five carriers are checked instead of the two (content, path) an unreviewed first draft would have
shipped with. A leak that a later commit in the same push removes is still caught. The mechanism is
self-testing on every deploy via its own canary.

**Negative.** The gate's guarantees are scoped to one repository, one transport (this instance's
self-hosted Forgejo, not the GitHub path the founding incident actually used) and structural pattern
matching — none of which is a small print detail, all of which is stated above rather than left to be
discovered later. The server's runtime environment (missing `python3`, a `grep` that silently
mis-handles a flag the gate relies on, `receive.fsckObjects` left at its default) means the gate's
correctness on this specific deployment depends on an image the deployment provides, not on
`push-gate.sh` alone. And an all-binary push with a clean commit message is now accepted, a real
narrowing of the earlier, stricter draft's guarantee, made deliberately and for a stated reason rather
than as an oversight.

## Follow-ups

1. **The GitHub-hosted public repository, the transport the founding incident actually used, has no
   server-side equivalent of this gate.** Coverage there is whatever local `pre-push` hooks happen to
   be installed on a given contributor's machine — materially weaker, and worth naming explicitly
   rather than letting this ADR's strength on the vault repo imply strength it does not have elsewhere.
2. **`grep -I` portability is a defect independent of this deployment.** Any Forgejo (or other forge)
   instance running on a BusyBox-based image inherits the same silent misclassification this ADR
   records for the target server. Worth tracking as a shipped-template concern, not only as a
   deployment note for this one instance.
3. **The two deny-name occurrences found in the vault repo's own tracked content during pre-activation
   sweeping are a sighting review, not a decision made by this ADR** — the PO reviews them before the
   hook is activated, and any tree cleanup that results is its own commit, tracked separately from
   this decision.
