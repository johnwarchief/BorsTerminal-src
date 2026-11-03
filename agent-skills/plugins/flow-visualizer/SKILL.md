---
name: flow-visualizer
description: "Architecture flow analysis. Use when the user needs to understand how business actions, service calls, events, data, files, or state move through a system, including sync/async boundaries, ownership, latency, failure paths, and data sensitivity."
---

# Flow Visualizer

Use this skill when the architectural question is: **How does something move through the system?**

The moving thing may be a business request, API call, event, batch job, data object, file, state transition, or user journey. The workflow is shared; the view type changes by flow kind.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../graphviz/SKILL.md` for business flows, lifecycle maps, data flows, and dense flow networks. Use Mermaid/PlantUML only when the user asks for Markdown-native diagrams or when a compact sequence/state sketch is clearly the best fit.

Read `../../references/business-application-fitness.md` when the flow is a business workflow in a product such as CRM, ERP, ecommerce, project management, invoicing, ledger, LMS, CMS, or property management.

## Scene Boundary

Use `flow-visualizer` for:

- Business workflows, user journeys, state transitions, and swimlanes.
- Service/API/RPC/message call chains and failure propagation.
- Data lineage, database/cache/file/object-store movement, retention, and sensitive data paths.
- Explaining one critical path from trigger to outcome.

Do not use it for static dependency analysis, deployment topology, or broad system inventory unless those are needed as inputs.

## Workflow

1. Identify the trigger and outcome: user action, API, event, scheduled job, decision, or data production/consumption point.
2. Choose the flow kind: business, service call, event, data, batch, state, or mixed.
3. Gather evidence from code paths, API/IDL contracts, event schemas, DB schemas, migrations, configs, traces, logs, docs, or user-provided process notes. Use `sourceRefs` when emitting a structured evidence model; otherwise cite evidence filenames in the narrative.
4. For business applications, translate implementation evidence into actor/action/outcome language before adding service, API, or table names.
5. Draw the main path first, then add branches for async transfer, retries, error handling, manual steps, approvals, permission checks, and ownership boundaries.
6. When a scenario-critical step is not evidenced, draw a partial confirmed path plus an `Unknown / validate next` branch instead of completing the happy path from assumptions.
7. Label edge semantics: sync/async/batch, protocol, payload/data object, permissions, lifecycle state, latency, retry/timeout, and confidence.
8. Split overloaded flows into focused diagrams: happy path, failure path, data lifecycle, state transition, or role swimlane.

## View Recipes

- Business/process flow: Graphviz DOT by default; use Mermaid only for small Markdown-native sketches.
- Service call path: PlantUML sequence diagram for detailed temporal interaction, plus Graphviz DOT for the service network when relationships matter.
- Data lineage/lifecycle: Graphviz DOT with data stores and ownership boundaries.

Read these only when needed:

- `references/business-flow-recipes.md`
- `references/service-call-recipes.md`
- `references/data-flow-recipes.md`

## Quality Gates

- Do not draw async queues/events as synchronous RPC.
- Do not use a single trace as proof of all possible runtime paths.
- Data flows must show stores, owners, sensitivity, and retention when the evidence exists.
- Business steps and technical steps should be visually separable.
- Business flow diagrams must use business roles, domain objects, lifecycle states, and outcomes; keep controller/service/table details in a separate drill-down.
- For business applications, the primary flow should read as actor/action/outcome first. Put controller, service, job, route, and table names in annotations or a technical drill-down.
- Every flow step must cite code, config, docs, schema, tests, traces, or user-provided process notes. Steps without evidence must be labeled assumed or unknown. Use structured `sourceRefs` for model artifacts, not as a mandatory field in every narrative business report.
- Do not use common lifecycle states, sample board/list names, standard CRM stages, ecommerce checkout assumptions, or expected payment callbacks as confirmed flow steps unless repository evidence supports them.
- If the requested flow is missing a scenario-critical handler, entity, integration, or state mechanism, state that limitation before the detailed walkthrough. For example, if checkout evidence has cart factories but no order-creation service or payment callback, say the flow is behaviorally incomplete and only structurally supported before listing step-level gaps.
- Do not treat fields, enums, counters, foreign keys, or entity relations as proof that a business action happens. A lifecycle step is confirmed only when you have the action path: mutation, controller, job, callback, trigger, event handler, test, trace, or user-provided process note. Otherwise split the confirmed data structure from the inferred behavior. Avoid confirmed action verbs such as creates, increments, assigns, enforces, sends, moves, completes, deletes, posts, reserves, charges, or persists unless the action path is evidenced.
- Do not treat UI forms, templates, client routes, or page-object steps as proof of backend behavior. They confirm available interaction, submitted payload, or UI step order. Split the UI step from the server-side effect when the controller, server action, mutation, model method, job, callback, integration test, or trace is missing.
- For diagrams, make UI-only evidence visually explicit: label nodes as `UI:`, `Form:`, `Route:`, or `Test step:` and put persistence, delivery, payment, or status-change effects in separate unknown/inferred nodes until server-side evidence exists.
- Do not treat factories, fixtures, seeders, or sample data as proof of production behavior. They confirm data shape and example defaults. In narrative text, write "Factory sample default..." or "Fixture example value..." instead of production-style phrasing such as "orders default to paid" unless runtime code confirms that default. Label diagram nodes with `Factory:`, `Fixture:`, `Seed:`, or `Data shape:` as the main label, not action-completion labels such as `Cart Created` with the qualifier only in parentheses. Keep creation, payment, inventory, validation, and lifecycle effects unknown until handler/service/test evidence exists.
- When an action handler is unknown, use dashed/dotted edges and labels such as `would create`, `structure supports`, or `needs validation`; do not use solid confirmed action edges from unknown handlers to factory-only nodes.
- Mermaid flowcharts must declare every node with a stable ID and readable label before connecting it. Check that every edge endpoint matches an existing node ID, and that node-shape delimiters match (`[...]`, `(...)`, `{...}`).
- A diagram must not contradict the narrative unknowns. If the report says a payment callback, inventory reservation, opportunity entity, permission check, or workspace boundary is unknown, the diagram must label that part unknown/inferred or omit it from the confirmed path.

## Artifacts

These artifacts capture the confirmed flow source, main path, alternatives, evidence, and risks.

- `flow.dot|mmd|puml`: source diagram for the overall business, service, event, or data flow.
- `flow-main.dot|puml|mmd`: focused view of the confirmed main path, excluding optional branches when useful.
- `flow-evidence.md`: source references for triggers, handlers, calls, events, stores, and state transitions.
- `flow-risks-and-gaps.md`: unsupported steps, failure paths, unknown ownership, and validation actions.

## Summary

Write the flow summary around the actual movement being explained. Describe the
trigger, main path, outcome, important branches, evidence, and any missing
runtime or business confirmation. Include artifact paths and validation steps
only where they help the user inspect or verify the flow.
