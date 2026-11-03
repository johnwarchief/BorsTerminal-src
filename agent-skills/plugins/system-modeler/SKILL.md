---
name: system-modeler
description: "Current architecture modeling. Use when the user wants to understand what a system, repository, platform, or product architecture is today by building an evidence-backed system model from code, docs, configs, and service boundaries."
---

# System Modeler

Use this skill when the architectural question is: **What is this system and what are its main parts, boundaries, owners, and upstream/downstream relationships?**

This is a scene skill, not a diagram-type skill. It may produce C4, dependency, module, context, or stakeholder-ready views, but the source of truth is one current-state architecture model.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../c4model/SKILL.md` for C4/Structurizr/Canvas outputs and `../graphviz/SKILL.md` for dense module or relationship graphs.

Read `../../references/business-application-fitness.md` when the system is a business application or when the user asks whether the skill/agent understands the product domain.

## Scene Boundary

Use `system-modeler` for:

- Understanding a repository, system, product area, or platform.
- Reverse-modeling architecture from code, manifests, configs, service catalogs, or docs.
- Creating system landscape, system context, container, component, module, or ownership views.
- Choosing the right abstraction level before deeper flow, dependency, risk, deployment, or evolution work.
- Modeling business applications by capabilities, domain entities, permissions/tenant/workspace boundaries, data/state ownership, and critical workflows before drilling into technical containers.

Do not use it as the primary skill when the user already asks for runtime deployment, migration planning, architecture review, data/call/business flow, or diagram freshness. Route those to their scenario skills.

**NOT in scope for this skill — do NOT include these in the output:**

- Quality gate findings, risk registers, or technical debt items → route to `risk-quality-reviewer`
- DSL/diagram syntax issues or linting errors → route to `architecture-health`
- Remediation recommendations or fix suggestions → route to `evolution-planner`
- Architecture health checks or stale diagram detection → route to `architecture-health`
- Deployment or runtime issues → route to `deployment-topology-analyzer`

The output of this skill is a **current-state architecture model** (evidence nodes, edges, views) plus a summary block. It is NOT a review report.

## Workflow

1. Define scope: product/system/repo, current-state only unless the user explicitly asks for target or proposed architecture.
2. Discover evidence: README, package/build files, service boundaries, routing, APIs, databases, IaC references, docs, ADRs, and code entry points.
3. For business applications, also inspect agent instructions, domain models, schema/migrations, routes/controllers, policies/roles, tenant/workspace/organization boundaries, lifecycle state, tests, fixtures, and seed data.
4. Build the evidence model with stable node/edge IDs, confidence, state, owner, and `sourceRefs` when the requested output includes a structured evidence model.
5. Choose the smallest useful views: usually business capability or system context first, then container/module drill-down only where evidence supports it.
6. Keep diagram certainty aligned with the text: label inferred actors, tenant/workspace boundaries, partner/customer visibility, permissions, and integrations as `assumed`, `inferred`, or `unknown` when they are not directly evidenced.
7. Separate confirmed architecture from inferred structure and list unknowns as validation tasks.
8. Route to `flow-visualizer`, `dependency-impact-analyzer`, `deployment-topology-analyzer`, or `risk-quality-reviewer` when the next question is more specific.

## Business Application Modeling

When the target is a business application, the model should make the product domain legible before it explains the implementation stack:

- Name core business actors, entities, capabilities, and workflows in business language.
- Show permission, tenancy, organization, workspace, role, or membership boundaries when evidenced.
- Do not draw workspace, tenant, permission, partner, customer, or role boundaries as confirmed architecture from folder names or instruction-file paths alone. Use low-confidence labels and validation steps until schema, policy, controller, test, or product documentation confirms them.
- Identify data stores, schema ownership, lifecycle states, audit history, soft delete, imports/exports, and transactional boundaries when evidenced.
- Include at least one end-to-end business path candidate and route it to `flow-visualizer` when a diagram is needed.
- Review agent instruction files for business context and regression guidance; missing domain rules are a finding, not an omission to hide.
- Summarize Business Application Fitness findings when the user is evaluating whether agents can work safely in the repo.

## View Recipes

- System context or landscape: use `c4model`.
- Container/component view: use `c4model` only when parent boundaries are evidenced.
- Module/package map: use `graphviz` when relationships are dense.
- Audience-specific summary: route to `architecture-communicator`.

Read these only when needed:

- `references/system-landscape-recipes.md`
- `references/code-to-architecture-recipes.md`

## Model Integrity Rules

> These are **internal accuracy constraints** for building the model. They are NOT sections to output, NOT findings to report, and NOT a review checklist. Do not produce a "Quality Gate Findings" section.

- Current-state nodes and edges must cite code, config, docs, or runtime sources. Use structured `sourceRefs` for evidence model artifacts; for narrative business reports, cite filenames in the text and mark unsupported claims as assumptions or unknowns.
- Avoid making folder structure look like runtime architecture unless calls/configs confirm it.
- Keep external systems, internal containers, modules, and data stores at distinct semantic levels.
- Record low-confidence areas instead of smoothing them into the diagram.
- Business-application outputs must not be only a framework, package, or build-command summary.
- Business entities, workflows, permissions, and lifecycle claims need evidence citations or explicit low-confidence validation tasks.
- If a scenario-critical entity, package, handler, integration, or lifecycle mechanism is missing from the evidence pack, elevate it near the Architecture Summary or model overview. Do not leave it only as a late validation gap. Make clear which parts of the requested business model are structurally incomplete.
- Separate structural evidence from behavioral evidence. A field, table, enum, counter, or relation confirms the shape of the model; it does not confirm the mutation, lifecycle transition, callback, job, permission enforcement, or business rule that uses it. Avoid confirmed action verbs such as creates, increments, assigns, enforces, sends, moves, completes, deletes, posts, reserves, charges, or persists unless the action path is evidenced.
- Separate UI evidence from backend behavior. Forms, views, templates, client routes, and page objects confirm available interactions and payloads; they do not confirm persistence, integration delivery, permission enforcement, or state transitions without handler, model, job, test, trace, or callback evidence.
- Separate fixture evidence from production behavior. Factories, fixtures, seeders, and demo data confirm sample shape/defaults; they do not prove runtime creation paths, lifecycle defaults, validations, or side effects without production handler/service or integration-test evidence. Phrase factory values as "Factory sample default..." rather than production defaults unless runtime code confirms the default. In diagrams, use `Factory:` or `Data shape:` as the main label for factory-only evidence instead of action-completion labels.
- Context and capability diagrams must not be more confident than the narrative. If the report calls an actor, entity, boundary, or integration unknown, the diagram must label it as unknown/inferred or leave it out of the confirmed path.

## Artifacts

These artifacts capture the current-state system model, supporting evidence, and architecture understanding for the inspected project.

Write all diagram source files to disk — do NOT inline the full content in the chat. Reference file paths in the response.

- `system-model.dsl|dot|mmd`: canonical source for the current-state system structure at the selected view level.
- `system-context.dsl|dot|mmd`: boundary-focused view showing actors, external systems, and major relationships.
- `system-model.evidence.md`: evidence index for nodes, relationships, assumptions, confidence, and unknowns.
- `system-model.summary.md`: readable explanation of the model, scope, important relationships, and validation gaps.
- `architecture-understanding.md` or `business-architecture.md`: domain-oriented architecture explanation when Business Application Fitness applies.

## Summary

Write the system summary as a compact architecture explanation, not a fixed
form. Cover the system boundary, important actors or containers, key
relationships, evidence strength, and unknowns. Reference artifact paths and
validation steps when they make the model easier to inspect or improve.
