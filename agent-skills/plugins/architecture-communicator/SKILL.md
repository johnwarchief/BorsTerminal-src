---
name: architecture-communicator
description: "Architecture communication and stakeholder view design. Use when the user needs to explain architecture to executives, product, business, engineering, operations, security, or delivery teams by tailoring scope, language, diagram detail, and delivery artifacts to the audience."
---

# Architecture Communicator

Use this skill when the architectural question is: **How do we explain this architecture clearly to a specific audience?**

This scene does not invent a new architecture model. It selects and adapts views from evidence-backed models so each audience sees the right level of detail.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../../references/diagram-delivery-recipes.md` when the output must be Markdown, Mermaid, Structurizr, Graphviz, Excalidraw, Draw.io, SVG, slides, or Canvas.

## Scene Boundary

Use `architecture-communicator` for:

- Explaining architecture to executives, product, business, engineering, operations, security, or customers.
- Turning a system model, flow, deployment map, risk review, or migration plan into audience-specific views.
- Preparing architecture review materials, design walkthroughs, onboarding docs, or slide-ready diagram notes.
- Choosing what to hide, simplify, annotate, or split for communication without losing traceability.

Do not use it as a substitute for missing evidence. If the source architecture is unknown, start with `system-modeler`.

## Workflow

1. Identify audience, decision they need to make, and time/detail constraints.
2. Select the source model or scenario artifact to communicate.
3. Choose 1-3 views that answer the audience’s question; remove unrelated detail rather than shrinking an overloaded diagram.
4. Translate technical labels into audience language while preserving stable IDs and evidence notes in supporting material.
5. Prepare the delivery surface: Markdown, wiki, diagram source, Canvas, Excalidraw, Draw.io, SVG, or slide notes.
6. Include reading order, caveats, assumptions, and follow-up questions.

## View Recipes

- Executive/business: capability/context view, risk/roadmap summary, one decision per visual.
- Engineering: container/module/flow/dependency view with evidence paths.
- Operations/security: deployment/runtime/data/trust-boundary view.
- Onboarding: progressive map from context to key flows and ownership.

Read `references/stakeholder-view-recipes.md` only when needed.

## Quality Gates

- Do not simplify away material risks or assumptions.
- Do not put all audiences into one diagram unless the question is truly shared.
- Preserve source model IDs and evidence references in supporting material even when the visual is simplified. Keep `sourceRefs` when the source is a structured model.
- The output should tell the reader what decision or action the view supports.
- For business-application models, translate labels into the audience's business language while preserving critical domain rules, permissions, lifecycle states, assumptions, and evidence notes.

## Artifacts

These artifacts capture the audience-specific communication plan, selected views, reading notes, and delivery-ready explanation for the architecture model.

- `architecture-communication-plan.md`: audience, decision context, message hierarchy, and chosen explanation depth.
- `stakeholder-view.dsl|dot|mmd|excalidraw`: audience-specific diagram source or editable view derived from the architecture model.
- `diagram-reading-notes.md`: plain-language guide for how to read the view, including scope, assumptions, and caveats.
- `delivery-summary.md`: final delivery notes that explain what was produced, who it is for, and how it should be used.

## Summary

Write a natural reader-facing summary shaped for the audience. Emphasize the
message they need to take away, the view or artifact that supports it, any
caveats that change interpretation, and the concrete artifact paths. Add next
actions only when they are useful for the audience's decision.
