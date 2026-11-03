---
name: explore
description: "Architecture router. Use for broad architecture requests and route by user scenario: model current architecture, analyze flows, dependency impact, deployment/runtime topology, evolution planning, risk/quality review, legacy understanding, communication, or architecture health."
---

# Architecture Explore

Use this skill first when the user asks broadly for architecture understanding, architecture diagrams, architecture review, runtime maps, migration plans, dependency analysis, data/call/business flows, or artifact validation.

The router chooses **the architecture job first** and **diagram/view formats second**. Do not route by artifact type alone.

## Mandatory Shared Gate

Before producing user-facing architecture artifacts, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Read `../../references/structurizr-canvas-pipeline.md` only when writing C4/Structurizr DSL artifacts or explaining Qoder viewer instructions.

Read `../../references/business-application-fitness.md` when the target is a business application, SaaS product, workflow-heavy product, CRM, ERP, ecommerce, marketplace, project management, invoicing, ledger, LMS, CMS, property-management system, or when the user asks whether an agent/skill understands the business domain.

## Routing Principles

- Separate current state, target state, runtime observations, and design assumptions.
- Do not claim a node, edge, risk, or decision is evidence-backed unless it cites code, config, runtime data, documentation, or user-provided source material.
- Prefer small readable views over one overloaded diagram.
- Pick the smallest scenario skill set that answers the user’s question.
- Use `c4model` and `graphviz` as artifact-source foundations, not as primary user scenarios.
- Use `drawio` only for explicit Draw.io, `.drawio`, diagrams.net, editable delivery, or local Draw.io MCP requests.

## Git Change Routing

When the user mentions a PR, branch, commit range, git diff, working tree, "this change", or "recent changes", gather a minimal change summary before choosing the scenario:

```bash
git status --short
git diff --name-status --find-renames
git diff --stat --find-renames
git log --oneline --decorate --max-count=8
```

For PR-style branch analysis, replace `origin/main` with the actual base branch when needed:

```bash
base=$(git merge-base HEAD origin/main)
git diff --name-status --find-renames "$base"...HEAD
git diff --stat --find-renames "$base"...HEAD
```

Route from the architectural job exposed by the change:

- Changed dependencies, contracts, modules, tests, data stores, or deployment units → `dependency-impact-analyzer`.
- Changed diagrams, evidence models, sourceRefs, architecture docs, or living-architecture checks → `architecture-health`.
- Changed ADRs, risk controls, quality gates, release-critical paths, or review evidence → `risk-quality-reviewer`.
- Changed migration slices, target-state docs, platform adoption work, or decision implementation → `evolution-planner`.

## Business Application Routing

For real business applications, the first question is not "can it build?" but "does the model explain the business safely enough to change it?" Gather business evidence before settling on diagrams:

- Agent instructions: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, MCP or AI coding notes.
- Business model: domain entities, actors, roles, permissions, organization/tenant/workspace concepts.
- Data/state: migrations, schemas, lifecycle states, audit/event history, soft delete, transactional boundaries.
- End-to-end paths: create/order/pay, create/project/task/status, create/invoice/send/collect, create/ledger/transaction/post, or the equivalent product workflow.
- Business validation: unit/integration/E2E tests, fixtures, seeds, API contracts, migration tests, CI paths.

Routing defaults:

- Broad "understand this business system" request → `system-modeler` primary, with `flow-visualizer` for at least one critical business path.
- "Can an AI agent safely work in this app?" or "agent readiness" → `risk-quality-reviewer` supported by `system-modeler`.
- Git/PR change in business code → `dependency-impact-analyzer`, but include affected business entities, workflows, permissions, data lifecycle, and regression paths.
- Legacy or low-evidence business system signals such as old frameworks, procedural code, missing ORM/migrations, monolithic deployment, hidden batch jobs, unknown owners, or sparse docs → `legacy-system-visualizer` supported by `system-modeler` or `risk-quality-reviewer`.

The answer must not stop at framework, package, or build-command inventory. Include a human-readable architecture understanding, business-language diagrams where they help, evidence-backed domain claims, unknowns, and Business Application Fitness findings when agent readiness is part of the question.

## Scene Router

| User question | Primary skill | Supporting foundation or skill |
| --- | --- | --- |
| “What is this system/repo/platform architecture?” | `system-modeler` | `c4model`, `graphviz` |
| “How do business steps, service calls, events, or data move?” | `flow-visualizer` | `graphviz`, PlantUML/Mermaid only when sequence or Markdown-native output is needed |
| “What depends on what?” or “What will this change affect?” | `dependency-impact-analyzer` | `graphviz`, `architecture-health` |
| “Where does it run and how is it released/operated?” | `deployment-topology-analyzer` | `graphviz`, `c4model` for small runtime-to-logical views |
| “How should the architecture evolve and why?” | `evolution-planner` | `c4model`, `dependency-impact-analyzer` |
| “Is this architecture risky or good enough?” | `risk-quality-reviewer` | `system-modeler`, `architecture-health` |
| “How do we understand or migrate this legacy system?” | `legacy-system-visualizer` | `system-modeler`, `evolution-planner` |
| “How do we explain this architecture to this audience?” | `architecture-communicator` | `c4model`, diagram delivery references |
| “Is this diagram/model/report current and traceable to evidence?” | `architecture-health` | scenario artifacts, project-local validation |

## Foundation Router

| Need | Use |
| --- | --- |
| C4 system landscape/context/container/component, Structurizr DSL, Qoder viewer instructions | `c4model` |
| Dense relationships, dependency networks, call/data/risk/impact graphs, DOT/SVG | `graphviz` |
| Draw.io, `.drawio`, diagrams.net, editable diagram delivery, or local Draw.io MCP setup | `drawio` |
| Output format choice, Structurizr/Graphviz/Mermaid/PlantUML/Excalidraw/Draw.io/SVG/slides delivery | `../../references/diagram-output-formats.md` and `../../references/diagram-delivery-recipes.md` |

## Workflow

1. Identify the user’s architecture job, audience, decision, and scope.
2. Decide whether the request is current-state, target-state, runtime observation, design assumption, or mixed.
3. If the target is a business application, apply the Business Application Fitness reference before choosing final views.
4. Select one primary scenario skill. Add at most two supporting skills unless the task is explicitly a full architecture review.
5. Gather enough evidence to avoid unsupported artifacts; if evidence is thin, produce a low-confidence map with validation gaps.
6. Choose output format after the scenario is clear. Prefer Structurizr for C4 views and Graphviz for relationship/flow/risk/deployment views; use Mermaid mainly for lightweight Markdown-native sketches.
7. If the output is Draw.io, keep the evidence model or text diagram source canonical and treat Draw.io as editable delivery.
8. Summarize the result with evidence, assumptions, gaps, and artifact paths.

## Quality Gates

- Route by the architecture job, not by the diagram format the user happens to mention.
- Pick the smallest skill set that answers the request and explain why each selected skill is needed.
- Do not claim the route is correct unless the selected scene matches the user's decision, scope, and evidence needs.
- Business-application requests must produce business-language output: actors, domain entities, workflows, permissions, tenant/workspace boundaries, lifecycle states, regression paths, unknowns, and evidence-backed findings. Cite evidence in text; reserve structured `sourceRefs` requirements for evidence models, traceability checks, and living-architecture validation.

## MECE Boundaries

- `system-modeler`: structure and boundaries.
- `flow-visualizer`: movement through the system.
- `dependency-impact-analyzer`: dependency graph reasoning and change blast radius.
- `deployment-topology-analyzer`: runtime placement, network, environment, and release topology.
- `evolution-planner`: target state, decisions, and migration sequence.
- `risk-quality-reviewer`: architecture review, quality attributes, technical debt, and remediation.
- `legacy-system-visualizer`: low-evidence legacy discovery and modernization slicing.
- `architecture-communicator`: audience-specific explanation of an existing model.
- `architecture-health`: freshness, traceability, validation, and living architecture checks.

## Avoid

- Do not route directly to a view because the user said “diagram.”
- Do not keep separate skills for every diagram type when the workflow is the same.
- Do not merge runtime deployment topology into logical system structure.
- Do not route AI/tool-process mapping into this software architecture package.
- Do not treat export format as the user’s real architecture question.
- Do not use `drawio` as the source of truth for architecture facts.

## Artifacts

These artifacts capture the selected architecture route, evidence plan, scope, and concrete files produced by the routed workflow.

- `architecture-plan.md`: scoped plan for the architecture question, audience, evidence needs, and expected outputs.
- `scenario-route.md`: concise record of the selected workflow and why it fits the user's architecture job.
- `architecture-evidence-plan.md`: checklist of code, docs, configs, runtime data, and assumptions to inspect.
- `artifact-summary.md`: inventory of produced artifacts, what each one answers, and where to find it.

## Summary

Summarize the route and result in the shape that fits the user's request. Make
clear which architecture question was answered, which workflow or artifact was
used, what evidence was available, what remains uncertain, and where the
produced artifacts live. Avoid exposing routing mechanics unless they help the
user understand the result.

## Files

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`
- `../../references/diagram-delivery-recipes.md`
- `../../references/structurizr-canvas-pipeline.md`
- `../../references/architecture-tooling-assessment.md`
- `../../references/business-application-fitness.md`
