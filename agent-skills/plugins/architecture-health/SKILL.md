---
name: architecture-health
description: "Architecture health, validation, and living architecture maintenance. Use when the user needs to check whether diagrams, models, or reports match code/config/runtime/ADR evidence, establish traceability, detect stale artifacts, diff architecture changes, or set up CI-style architecture update checks."
---

# Architecture Health

Use this skill when the architectural question is: **Are these architecture artifacts trustworthy and maintainable over time?**

It is both a scenario skill and a supporting validation skill, similar to how analytical validation can be called independently or by another workflow.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use generated artifacts from `system-modeler`, `flow-visualizer`, `dependency-impact-analyzer`, `deployment-topology-analyzer`, or `evolution-planner` as inputs.

Read `../../references/business-application-fitness.md` when validating a business-application model, Business Application Fitness scorecard, business workflow diagram, or agent-readiness architecture report.

## Scene Boundary

Use `architecture-health` for:

- Checking diagrams against code, config, IaC, OpenAPI/IDL, schemas, runtime traces, ADRs, or docs.
- Building diagram-to-code traceability and evidence indexes.
- Detecting missing, stale, conflicting, or low-confidence nodes/edges.
- Setting up living architecture updates, CI checks, model diffs, and regeneration summaries.

Do not use it to create the first architecture model unless validation is the primary user request.

## Git Change Evidence

Use git to decide whether a diagram/model may be stale, whether architecture evidence changed without a matching visual update, or whether two model snapshots need semantic diffing.

Local working tree:

```bash
git status --short
git diff --name-status --find-renames -- docs references artifacts examples skills
git diff --stat --find-renames -- docs references artifacts examples skills
git log --follow --format="%h %cs %s" -- <diagram-or-model-path>
```

PR or branch against a base branch:

Replace `origin/main` with the actual PR base branch when needed, such as `origin/master`.

```bash
base=$(git merge-base HEAD origin/main)
git diff --name-status --find-renames "$base"...HEAD -- docs references artifacts examples skills
git diff --name-only --find-renames "$base"...HEAD -- <code-or-config-path>
git diff --name-only --find-renames "$base"...HEAD -- <diagram-or-model-path>
```

When a diagram file is versioned in git, compare the base snapshot with the current file:

Replace `origin/main` with the actual PR base branch when needed, such as `origin/master`.

```bash
base=$(git merge-base HEAD origin/main)
git show "$base:<diagram-path>" > /tmp/before.structurizr.dsl
git diff --no-index /tmp/before.structurizr.dsl <diagram-path> > diagram-diff.patch || true
```

Treat code/config changes without diagram/model changes as a possible staleness finding, not automatic proof that the visual is wrong.

## Workflow

1. Identify the canonical diagram/model source and the controlling evidence sources.
2. Parse or inspect nodes, edges, labels, confidence, sourceRefs, and diagram format.
3. Re-check evidence from code/config/docs/runtime and classify each item: confirmed, stale, missing, conflicting, inferred, or unknown.
4. Build a traceability index from diagram elements to paths, contracts, configs, traces, ADRs, and artifact provenance.
5. For Qoder plugin or skill-routing changes, run a project-local skill discovery and activation smoke before trusting the route.
6. Propose model patches, diagram annotations, or CI/living architecture checks.
7. Report what is safe to trust now, what must be updated, and what needs more evidence.

## View Recipes

- Consistency report: Markdown table plus annotated model diff.
- Traceability index: JSON/CSV/Markdown.
- Living architecture pipeline: Mermaid flowchart plus commands.
- Qoder plugin skill smoke: project-local skill discovery, activation signal, and generated model/validation/DOT artifact checks.
- Diagram diff: current vs regenerated evidence model.

Read these only when needed:

- `references/consistency-validation-recipes.md`
- `references/living-architecture-recipes.md`

## Quality Gates

- Do not mark a diagram current unless controlling evidence was inspected.
- Treat missing sourceRefs as a finding, not as proof the diagram is wrong.
- Separate stale diagram, stale code/docs, and ambiguous evidence.
- CI gates should be deterministic enough to rerun without hidden manual steps.
- Every confirmed node and edge must have at least one `sourceRef`; elements without resolvable evidence are inferred, stale, or unknown until validated.
- For business-application models, validate that domain entities, workflows, permissions, tenant/workspace boundaries, lifecycle states, regression paths, and Business Application Fitness claims are traceable to evidence or explicitly marked as assumptions.

## Artifacts

These artifacts capture architecture freshness, traceability, diff evidence, and the checks needed to keep architecture sources maintainable.

- `architecture-health-report.md`: validation result covering freshness, traceability, stale claims, and trust level.
- `diagram-diff.md|patch`: semantic diff report or raw patch between architecture artifact versions when comparison is needed.
- `living-architecture-checks.md`: CI or periodic checks that keep architecture artifacts aligned with source evidence.
- `regeneration-summary.md`: notes for how artifacts should be refreshed, including required evidence and manual review points.

## Summary

Write a concise validation summary in prose. Make clear what was checked, what
can be trusted, what is stale or untraced, and which updates are needed. Include
artifact paths and concrete follow-up checks when they help the user act.
