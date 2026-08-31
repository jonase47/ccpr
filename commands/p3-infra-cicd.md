---
disable-model-invocation: true
---
# /p3-infra-cicd – CI/CD Pipeline

Designs the CI/CD pipeline with stages, branch strategy and rollback concept.

## Argument: $ARGUMENTS = [Pipeline tool, e.g. "GitHub Actions", "Gitea Actions", "GitLab CI"]

If provided: Use the tool as the specification.
If not provided: Recommend based on hosting and infrastructure.

## Prerequisites
- Hosting strategy from `/p3-infra-hosting` available
- TECH_STACK.md exists

## Agent
- **Type**: devops
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From INFRASTRUCTURE.md: Hosting strategy and environments
- From TECH_STACK.md: Build tools and frameworks
- From CLAUDE.md: Infrastructure preferences (Gitea, self-hosted)

## Prompt Template
> **Goal**: Design CI/CD pipeline. Tool: $ARGUMENTS
>
> **Context**:
> [inline from INFRASTRUCTURE.md, TECH_STACK.md]
>
> **Output Format**:
> 1. Pipeline tool with justification (1 sentence)
> 2. Stages: numbered list | Stage | Content | Duration (estimated) |
> 3. Branch strategy: trunk-based / gitflow with justification (1 sentence)
> 4. Rollback strategy: method and process (2-3 sentences)
>
> **Constraints**:
> - ONLY CI/CD pipeline, NO hosting, NO monitoring
> - Max. 8 pipeline stages
> - Rollback strategy must be concrete (not just "we do a rollback")

## Orchestrator Checkpoint
- [ ] All stages sensible for the tech stack?
- [ ] Security scan included in the pipeline?

## Write Detail File
Write the result to `docs/architecture/CICD.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: infra-cicd
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Pipeline Tool` (with justification), `## Stages` (numbered table stage / content / duration), `## Branch Strategy`, `## Rollback Strategy`.

## Update Sub-Index
Update `docs/architecture/INFRA.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[CICD.md](CICD.md)` with status `complete`.
- Lift the pipeline tool + branch strategy into **Key Decisions** of the sub-index.
- Do not edit `ARCHITECTURE.md` directly.

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
