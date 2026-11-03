---
name: dependency-impact-analyzer
description: "Dependency and change-impact analysis. Use when the user needs to understand dependencies, coupling, cycles, layer violations, ownership edges, dependency risk, or what modules, services, tests, data stores, and deployments a proposed or actual change may affect."
---

# Dependency Impact Analyzer

Use this skill when the architectural question is: **What depends on what, and what will this change affect?**

It combines static dependency mapping with impact traversal. A dependency map is an input and output, but the scenario is dependency reasoning.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../graphviz/SKILL.md` for dense dependency, cycle, and impact graphs.

## Scene Boundary

Use `dependency-impact-analyzer` for:

- Package/module/service/database/third-party dependency analysis.
- Cycles, layering violations, unstable abstractions, shared library overuse, or ownership boundary problems.
- PR/change impact: affected modules, services, contracts, tests, data stores, deployments, docs, and release risk.
- Refactoring candidates and dependency governance rules.
- Business application change impact: affected domain entities, workflows, permissions, tenant/workspace/organization boundaries, data lifecycle states, and regression paths.

Do not use it for request/data/business flow sequencing unless traversal order matters more than dependency structure.

For business applications, map changed paths to business entities, workflows, permissions, and data/state ownership before graph traversal. The blast radius should explain what business behavior may be affected, not only which files or packages changed.

## Git Change Evidence

For PR/change-impact questions, treat git output as the change-set input, then map changed paths to architecture nodes before traversal.

Local working tree:

```bash
git status --short
git diff --name-status --find-renames
git diff --stat --find-renames
git diff --find-renames -- <path-or-module>
```

PR or branch against a base branch:

Replace `origin/main` with the actual PR base branch when needed, such as `origin/master`.

```bash
base=$(git merge-base HEAD origin/main)
git diff --name-only --diff-filter=AMRT --find-renames "$base"...HEAD
git diff --name-status --find-renames "$base"...HEAD
git diff --stat --find-renames "$base"...HEAD
git diff --find-renames "$base"...HEAD -- <path-or-module>
```

Single commit or commit range:

```bash
git show --name-status --find-renames --stat <commit>
git diff --name-status --find-renames <before>..<after>
git diff --stat --find-renames <before>..<after>
```

Use `name-status` to seed changed nodes, `stat` to size the review, and the full diff only for architecture-relevant files such as public APIs, package/build manifests, schemas, migrations, IaC, routing, service contracts, test boundaries, and generated architecture models.

## Workflow

1. Define the dependency grain: file, package, module, service, contract, table, topic, deployment unit, or team-owned domain.
2. Collect dependency evidence from imports, build/package manifests, route/config files, service contracts, schema references, IaC, tests, and runtime registry where available. Use the target project's own build, language server, dependency tooling, or small ad hoc queries when they fit the repository; do not assume a bundled extractor exists.
3. Normalize edge types: compile-time, runtime-call, data-access, event, config, ownership, test, deployment, or documentation.
4. Build the directed graph and calculate cycles, fan-in/fan-out, layer violations, unstable nodes, and bridge/shared nodes.
5. For impact questions, start from changed nodes and traverse direct and indirect edges; separate confirmed impact from plausible impact.
6. Output prioritized findings with evidence paths and concrete validation steps.

## Architecture Analysis Quality

When using dependency evidence to explain architecture, keep the analysis anchored in project structure instead of generic graph facts:

- Treat project-owned files, modules, workspace packages, service directories, contracts, and generated artifacts as primary architecture nodes. Built-in platform modules and third-party packages are context unless the question is specifically about external dependency risk.
- Use fan-in, fan-out, shared imports, cycles, and unresolved nodes as signals, then explain why they matter for boundaries, coupling, or change impact.
- Identify module boundaries from multiple evidence cues where possible: path grouping, package manifests, public exports, entry points, tests, build scripts, and evidence references.
- Do not infer deployment topology, databases, queues, runtime traffic, team ownership, or business flows from static imports alone.
- Every risk or impact claim should name the node(s), traversal direction or graph signal, evidence paths or `sourceRefs` in structured model artifacts, confidence, and a concrete validation step.
- Record unknowns when the graph cannot answer runtime behavior, ownership, production traffic, or release blast radius.

## View Recipes

- Dependency graph, cycle graph, layer violation graph: Graphviz.
- Change blast radius: Graphviz DOT with impacted/unknown/excluded states; use Mermaid only for small Markdown-native sketches.
- Rule report: Markdown plus optional CSV.

Read these only when needed:

- `references/dependency-map-recipes.md`
- `references/change-impact-recipes.md`

## Quality Gates

- Static import edges, runtime calls, data access, events, and deployment coupling must not be mixed without labels.
- Third-party dependencies and business module dependencies should use distinct groups.
- Impact claims must include traversal direction and stopping criteria.
- Large graphs need filters by layer, domain, team, or risk level.
- Business-app impact claims must name the affected entity, workflow, permission, data lifecycle state, tenant/workspace boundary, or regression path when evidence supports it.

## Artifacts

These artifacts capture the dependency graph, impacted nodes, rule violations, and evidence-backed findings for a change or dependency question.

- `dependency-map.dot`: maintainable graph source for dependency relationships at the chosen grain.
- `impact-map.dot|mmd`: focused blast-radius view from the changed or queried nodes to affected areas.
- `violations.csv`: machine-readable list of cycles, layer violations, forbidden edges, or ownership breaches.
- `dependency-impact-findings.md`: prioritized findings with evidence, confidence, affected tests, and validation steps.

## Summary

Write the impact summary around the user's change or dependency question. Name
the analysis grain, the most affected areas, why those areas are affected, and
which claims are confirmed versus inferred. Include artifact paths and targeted
validation steps where uncertainty remains.
