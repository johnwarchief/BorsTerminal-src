---
name: legacy-system-visualizer
description: "Legacy system understanding and modernization visual modeling. Use when the user needs to understand, map, stabilize, or migrate a poorly documented legacy system with sparse evidence, unknown ownership, hidden dependencies, batch jobs, data coupling, or strangler-style modernization needs."
---

# Legacy System Visualizer

Use this skill when the architectural question is: **How do we understand and safely change this legacy system despite incomplete evidence?**

Legacy work stays separate from ordinary system modeling because low-confidence evidence, undocumented runtime behavior, old data coupling, and human knowledge dependencies are part of the method.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../system-modeler/SKILL.md` for confirmed current-state structure, `../dependency-impact-analyzer/SKILL.md` for hidden coupling, `../flow-visualizer/SKILL.md` for key business/data/batch paths, and `../evolution-planner/SKILL.md` for modernization sequencing.

Read `../../references/business-application-fitness.md` when the legacy system contains domain entities, workflows, permissions, billing, tenant/workspace boundaries, data lifecycle rules, or business validation paths.

## Scene Boundary

Use `legacy-system-visualizer` for:

- Taking over old systems with missing docs, unclear boundaries, or unknown owners.
- Mapping modules, data tables, scripts, batch jobs, manual operations, and external interfaces.
- Finding hidden dependencies, high-risk data paths, unsupported code, and knowledge silos.
- Planning strangler, database split, service extraction, stabilization, or replacement slices.

Do not start with a big rewrite recommendation. The first job is to make unknowns explicit and reduce change risk.

## Workflow

1. Build an observable-facts inventory: code, configs, schemas, jobs, logs, runbooks, docs, incidents, and user-provided tribal knowledge.
2. Label each fact by confidence and evidence type; keep rumors and inferred relationships visible as low-confidence assumptions.
3. Map business capabilities to code areas, data stores, batch jobs, interfaces, and manual operations.
4. Identify risk clusters: critical flows, data ownership conflicts, no-test areas, fragile scripts, high-coupling modules, and human-only knowledge.
5. Choose 2-4 views: legacy module map, capability-to-code map, data/batch flow, unknowns map, or migration slice map.
6. Propose stabilization and modernization slices with validation signals and rollback boundaries.

## View Recipes

- Legacy module/dependency map: Graphviz DOT written to `legacy-map.dot`.
- Capability-to-code/data map: Markdown table plus Graphviz DOT written to `capability-map.dot`.
- Batch/data flow: `flow-visualizer` style Graphviz DOT written to `batch-data-flow.dot`.
- Strangler/migration slice map: `evolution-planner` style roadmap.

Read `references/legacy-discovery-recipes.md` only when needed.

## File Output Rules

**Never output raw DOT source inline in the conversation.** Always write diagram files to disk using the file-writing tool.

- Output directory: use the workspace root of the target system, or a subdirectory named `architecture/` if the workspace root is not writable.
- Write each `.dot` file with the file-writing tool before describing the diagram in the conversation.

## Quality Gates

- Unknown areas are first-class output, not omissions.
- Migration slices must bind business capability, data boundary, risk, and validation signal.
- Batch jobs, scripts, cron tasks, manual operations, and data exports must be checked explicitly.
- Do not treat folder structure as business domain boundaries without evidence.
- Every confirmed fact must cite evidence. Use structured `sourceRefs` for model artifacts; in Markdown reports, cite evidence paths in prose. Low-confidence facts, inferred relationships, and tribal-knowledge claims must be labeled with confidence and a concrete validation step.
- In legacy MVC applications, distinguish views/forms/templates from controllers/models/jobs. A view that posts to `send_invoice` confirms the UI route and payload, not that the mail was sent, logged, retried, or that invoice status changed.
- Legacy diagrams should use labels such as `UI: send invoice form` or `Form posts to mailer/send_invoice` when only view evidence exists, then draw `mail dispatched`, `invoice closed`, or `payment recorded` as unknown until controller/model evidence is present.
- For legacy business applications, map business capabilities and critical workflows before proposing modernization slices.

## Artifacts

These artifacts capture low-confidence legacy discovery, unknown areas, risk clusters, and modernization slices.

All diagram artifacts must be **written to disk**, not printed in the conversation.

| File | Notes |
|------|-------|
| `legacy-map.dot` | Primary legacy module/dependency graph (Graphviz DOT source) |
| `capability-map.dot` | Capability-to-code/data map (Graphviz DOT source) |
| `batch-data-flow.dot` | Batch jobs and data flow graph (Graphviz DOT source) |
| `capability-to-code-map.md` | Capability → code area table with evidence |
| `legacy-unknowns-and-risks.md` | Unknown areas, risk clusters, and validation steps |
| `migration-slices.md` | Stabilization and modernization slices |

After writing each file, report its path and a one-line next action in the conversation.

## Summary

Write the legacy-system summary as an evidence-weighted narrative. Separate
confirmed structure from assumptions, name critical capabilities and unknowns,
and describe the safest stabilization or migration slices. Include artifact
paths and render commands only when files were written and the user can run them.
