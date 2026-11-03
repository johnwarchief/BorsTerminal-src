---
name: evolution-planner
description: "Architecture evolution planning. Use when the user needs to compare current and target architecture, explain decisions and tradeoffs, plan migration slices, sequence modernization work, or turn ADRs and target-state gaps into a visual roadmap."
---

# Evolution Planner

Use this skill when the architectural question is: **How should the architecture change, and why?**

It combines target-state gap analysis and architecture decision modeling because migration plans and decisions are usually one governance conversation.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../c4model/SKILL.md` for current/target C4 variants and `../graphviz/SKILL.md` for migration dependency or sequencing graphs.

Read `../../references/business-application-fitness.md` when evolution or modernization work changes business entities, workflows, permissions, tenant/workspace boundaries, data lifecycle, agent readiness, or business validation paths.

## Scene Boundary

Use `evolution-planner` for:

- Current vs target architecture comparison.
- Migration, modernization, decomposition, platform adoption, or strangler planning.
- ADRs, decision records, option tradeoffs, constraints, and consequences.
- Roadmaps, sequencing, phase gates, readiness checks, and verification criteria.

Do not use it for pure current-state discovery, architecture review, or PR-level impact unless those are inputs to the change plan.

## Git Change Evidence

Use git when the evolution plan is grounded in a branch, commit sequence, migration PR, ADR implementation, or target-state documentation update.

PR or branch against a base branch:

Replace `origin/main` with the actual PR base branch when needed, such as `origin/master`.

```bash
base=$(git merge-base HEAD origin/main)
git log --oneline --decorate --first-parent "$base"..HEAD
git diff --name-status --find-renames "$base"...HEAD
git diff --stat --find-renames "$base"...HEAD
```

Decision and target-state evidence:

```bash
git diff --find-renames "$base"...HEAD -- "docs/adr/**" "adr/**" "docs/architecture/**" "architecture/**"
git diff --find-renames "$base"...HEAD -- "roadmap/**" "migration/**" "migrations/**" "db/**"
git diff --find-renames "$base"...HEAD -- "infra/**" "deploy/**" ".github/workflows/**"
```

Migration slice by commit:

```bash
git diff-tree --no-commit-id --name-status -r <commit>
git show --name-status --find-renames --stat <commit>
git show --find-renames <commit> -- <path-or-slice>
```

Use the commit sequence to infer proposed migration slices only when the changed files, ADRs, or user-provided plan support that interpretation. Label anything else as an assumption or validation gap.

## Workflow

1. Separate current state, target state, proposed assumptions, and runtime observations.
2. Gather current evidence and target evidence: code/config/docs/ADRs/roadmaps/proposals/user-provided design notes.
3. Identify decisions: constraints, options, chosen direction, rejected alternatives, risks, and reversibility.
4. Map gaps between current and target nodes/edges/capabilities, then group them into migration slices. For business applications, bind each slice to business entities, workflows, permissions, data lifecycle states, tenant/workspace boundaries, and regression paths.
5. Sequence slices by dependency, risk, value, reversibility, and validation cost.
6. Produce a roadmap with explicit checkpoints and evidence needed to retire assumptions.

## View Recipes

- Current/target architecture variants: C4/Structurizr DSL.
- Gap map: Graphviz DOT.
- Decision tree and tradeoff relationships: Graphviz DOT or Markdown matrix.
- ADR timeline and migration roadmap: Markdown checklist plus Graphviz DOT when dependencies matter; Mermaid only for lightweight Markdown-native timelines.

Read these only when needed:

- `references/target-state-gap-recipes.md`
- `references/architecture-decision-recipes.md`

## Quality Gates

- Target-state nodes must be labeled proposed/target unless implemented.
- Do not present desired architecture as current evidence.
- Every migration slice should include a validation signal.
- Decision diagrams must keep constraints, assumptions, tradeoffs, and outcomes distinct.
- Target-state and migration claims must cite ADRs, proposals, user notes, implementation evidence, tests, or explicit assumptions. Use structured `sourceRefs` for model artifacts; in Markdown reports, cite evidence paths in prose.
- Business-app migration slices must include the business path they protect or unlock, plus the validation signal that proves it still works.

## Artifacts

These artifacts capture the current/target gap, architecture decisions, migration slices, and roadmap evidence.

- `architecture-evolution.dot|dsl|mmd`: source diagram for the proposed architecture change path or target-state evolution.
- `current-vs-target.dsl|dot|mmd`: comparison view separating current evidence from target design assumptions.
- `migration-roadmap.md`: staged migration plan with slices, sequencing, dependencies, and acceptance checks.
- `decision-map.md`: ADR or tradeoff relationship map showing constraints, choices, conflicts, and dependencies.
- `evolution-summary.md`: narrative summary of why the change is needed, what changes first, and what remains risky.

## Summary

Write the evolution summary as a decision-oriented narrative. Connect the
current-state evidence to the target state, explain the key decisions and
migration slices, and call out risks or unresolved decision points. Reference
artifact paths and next actions when they clarify what should happen next.
