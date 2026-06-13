# /p5-docs – Keep Code Documentation Up to Date

Keeps code documentation in sync with the implemented code: inline comments, API documentation, changes to README or CONTRIBUTING, and updates to technical specifications if the code deviates from them. Called after implementing a feature.

## Argument: $ARGUMENTS = [Module/feature/file]

If provided: Focus documentation work on the named module, feature or file.
If not provided: Read SPRINT.md and update the documentation for all features implemented in the current sprint. If context is missing, ask for the area to be documented.

## Execution

### 1. Read Context
Read the following files (if available):
- **SPRINT.md** (which features were implemented?)
- The implemented code: **$ARGUMENTS** (or all new/changed files from the sprint)
- **API_SPEC.md** (does the specification still match the code?)
- **ARCHITECTURE.md** (does the architecture description still match?)
- **README.md** / **CONTRIBUTING.md** (does setup or developer documentation need to be updated?)

### 2. Delegation to Tech-Writer Agent (Lead)
Delegate documentation work to the **tech-writer** agent:

> Update the documentation for: **$ARGUMENTS**
> Context: [Insert implemented code, SPRINT.md, API_SPEC.md key points]
>
> **A. Check and supplement inline code documentation**
> Check the implemented code for the following documentation gaps:
> - Public functions/methods: do they have JSDoc / docstring / equivalent with parameters and return values?
> - Non-obvious algorithms or decisions: are they commented?
> - Complex data structures: are their fields described?
> - TODO/FIXME comments: are they captured as tasks in BACKLOG.md?
>
> **B. Update API documentation**
> Compare the implemented code with API_SPEC.md:
> - Are there new endpoints not yet specified?
> - Have request/response schemas changed?
> - Are there new error codes or messages?
> - Update API_SPEC.md where needed and mark deviations from the original design.
>
> **C. Reconcile technical specifications**
> Check ARCHITECTURE.md and DATA_MODEL.md:
> - Does the implemented code deviate from the architecture? (If yes: document as a deliberate decision or add ADR)
> - Have data model details changed (new fields, changed types)?
>
> **D. Update README / CONTRIBUTING**
> Check whether new information is needed:
> - New dependencies or configuration steps?
> - New scripts or make targets?
> - Add new environment variables to .env.example?

### 3. Delegation to Senior-Developer Agent (Support)
Delegate technical accuracy check to the **senior-developer** agent:

> Check the tech-writer's documentation updates for technical accuracy:
> 1. Are all code comments factually correct?
> 2. Do the documented API schemas match the actual code?
> 3. Is there relevant developer information that the tech-writer overlooked?

### 4. Document Result
No separate artifact – changes are made directly in the existing documents:
- Code files (inline comments added)
- **API_SPEC.md** (updated)
- **ARCHITECTURE.md** (deviations documented, ADR added if needed)
- **README.md** / **CONTRIBUTING.md** (updated if needed)
- **.env.example** (new variables added)

Update **SPRINT.md**: mark documentation task as completed.

## Result

- Updated code documentation (inline comments, docstrings)
- Updated **API_SPEC.md**
- If applicable: updated **ARCHITECTURE.md**, **README.md**, **.env.example**
- **SPRINT.md** updated
- Story is only fully "Done" when documentation is current

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
