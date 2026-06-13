# /p7-release-docs – Release Notes, User Guide & Privacy Documents

Creates all user-facing documents for the launch: release notes, user guide or onboarding materials, and the legally required mandatory documents (privacy policy, legal notice). These documents must be available before go-live.

## Argument: $ARGUMENTS = [Version, e.g. "v1.0.0", "v1.2.0-beta"]

If provided: Use as the version number in release notes and documents.
If not provided: Read PROJECT_PLAN.md or DEPLOYMENT_LOG.md and derive the version number. If any context is missing, ask for the version.

## Execution

### 1. Read Context
Read the following files (if available):
- **FEATURES.md** / **BACKLOG.md** (what was built in this version?)
- **CONCEPT.md** (product description and value proposition)
- **USER_JOURNEYS.md** (personas – who is the guide written for?)
- **DSGVO_INITIAL_ASSESSMENT.md** (DSGVO (GDPR) requirements for the privacy policy)
- **BUSINESS_MODEL.md** (pricing, provider information for legal notice)
- **UX_CONCEPT.md** (screenshots / screen descriptions for the guide)

### 2. Delegation to Tech Writer Agent (Lead)
Delegate documentation creation to the **tech-writer** agent:

> Create all release documents for version: **$ARGUMENTS**
> Context from FEATURES.md, CONCEPT.md, USER_JOURNEYS.md: [Apply implemented features, product description, target audiences]
>
> **A. Release Notes (RELEASE_NOTES.md)**
> - **Version and date**
> - **What's new**: All new features in plain language (no tech jargon)
> - **Improvements**: What was improved or optimised?
> - **Bug fixes**: Relevant bug fixes (without internal ticket IDs, user-friendly language)
> - **Breaking changes** (if any): What changes for existing users?
> - **Known limitations**: What is not yet perfect, what is being worked on?
> - Tone: positive, clear, user-oriented – no marketing exaggerations
>
> **B. User Guide / Onboarding Material**
> Create a guide tailored to the target audience from USER_JOURNEYS.md:
> - **Getting started**: How does a new user achieve their first success in 5 minutes?
> - **Core features explained**: The most important features with step-by-step instructions
> - **Frequently asked questions (FAQ)**: Answer the 5–10 most likely user questions in advance
> - **Troubleshooting**: What to do when something doesn't work?
> - **Contact/Support**: How do users get help?
> - Tone: friendly, direct, tailored to the target persona
>
> **C. Privacy Policy (basic structure)**
> Create a legally compliant privacy policy based on DSGVO_INITIAL_ASSESSMENT.md:
> - Data controller (name, address, contact)
> - What data is collected and why (per processing purpose)
> - Legal basis per processing purpose (Art. 6 DSGVO)
> - Transfer to third parties (data processors with DPA)
> - Retention period per data category
> - Data subject rights and how to exercise them
> - Right to lodge a complaint with the supervisory authority
> - Note: This basic structure must be reviewed by a lawyer.
>
> **D. Legal Notice (basic structure)**
> Create a legal notice template according to §5 TMG:
> - Provider details (name, address)
> - Contact details (email, telephone if applicable)
> - Commercial register entry, VAT ID if applicable
> - Person responsible for content
> - Note: Completeness must be verified.

### 3. Delegation to Business Analyst Agent (Support)
Delegate the business perspective review to the **business-analyst** agent:

> Review the release documents from the tech writer:
> 1. Do the release notes communicate the user benefit clearly enough?
> 2. Is pricing information in the user guide correct (if relevant)?
> 3. Is any important information missing that users need before getting started?

### 4. Write Files & Detail File
This subskill produces user-facing files at the project root (not under `docs/`):
- **`RELEASE_NOTES.md`** (release notes for v$ARGUMENTS — append-only across releases)
- **`USER_GUIDE.md`** (user guide / onboarding)
- **`PRIVACY_POLICY.md`** (privacy policy – basic structure, legal review recommended)
- **`LEGAL_NOTICE.md`** (legal notice – basic structure, verify completeness)

In addition, write a phase-internal summary at `docs/launch/RELEASE_DOCS.md`. Frontmatter:

```yaml
---
phase: P7
subskill: release-docs
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Release Notes Summary` (1-paragraph + link to `../../RELEASE_NOTES.md`), `## User Guide Summary` (link to `../../USER_GUIDE.md`), `## Privacy & Legal Summary` (links to `../../PRIVACY_POLICY.md` and `../../LEGAL_NOTICE.md` plus a note on whether legal review is still pending), `## Release Version Tracking` (table of versions released to date with date and headline change).

### 5. Update Phase Index
Update `docs/launch/LAUNCH.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[RELEASE_DOCS.md](RELEASE_DOCS.md)` with status `complete`.
- Lift the released version (v$ARGUMENTS) into **Key Decisions**.
- If a legal review is still pending, add a 1-liner under **Open Risks**.

## Result

- **`RELEASE_NOTES.md`** (user-facing release notes, project root)
- **`USER_GUIDE.md`** (user guide / onboarding material, project root)
- **PRIVACY_POLICY.md** (privacy policy)
- **LEGAL_NOTICE.md** (legal notice)
- Foundation for `/gate-p7` (mandatory documents before go-live)

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open items
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
