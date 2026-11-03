---
name: c4model
description: "C4/Structurizr DSL foundation. Use to turn architecture evidence into maintainable C4 system landscape, context, container, and component source artifacts."
---

# C4 Model

C4/Structurizr DSL foundation.

Use this skill when the user needs C4 modeling, Structurizr-compatible architecture models, system landscape/context/container/component views, or Qoder viewer instructions.

The goal is to turn architecture evidence into maintainable C4 semantic sources and, when requested, provide those sources for Qoder viewer inspection.

Read `../../references/architecture-contract.md` before producing user-facing architecture artifacts.

Read `../../references/architecture-evidence-model.md` before claiming that a node, edge, risk, or decision is supported by code, configuration, runtime data, or documentation.

Read `../../references/diagram-output-formats.md` before choosing Mermaid, PlantUML, Graphviz, Structurizr DSL, Excalidraw, Draw.io, SVG, Markdown, or slide-oriented output.

Read `../../references/structurizr-canvas-pipeline.md` before writing Structurizr DSL or explaining Qoder viewer instructions.

Read `references/c4model-examples.md` when the user asks for examples, when choosing between system context/container/component views, or when the generated model needs a concrete standard Structurizr DSL pattern.

## Use Cases

- The user explicitly asks for C4, Structurizr, system context, container, component, or Qoder viewer instructions.
- A `*.structurizr.dsl` workspace needs to be authored, reviewed, or explained.
- System landscape modeling, reverse architecture modeling, architecture review, or living architecture needs a stable C4 semantic source.
- The evidence model must remain the source of truth while rendered previews remain derived artifacts.

## Inputs

- `<name>.structurizr.dsl` or inline DSL written by the agent.
- Optional workspace name, workspace description, and output directory.

## Recommended Views

- C4 System Landscape.
- C4 System Context.
- C4 Container.
- C4 Component, only when each component has evidenced parent container boundaries.
- Qoder Structurizr DSL preview.

## Example Entry Points

- System Context: one system, direct users, and direct external systems; useful for explaining boundaries to technical and non-technical stakeholders.
- Container: applications, data stores, and major technology choices inside one system; useful for development, architecture, and operations review.
- Component: use only inside one container when responsibilities are evidenced in code; otherwise use a container view plus a Graphviz dependency map.
- See `references/c4model-examples.md` for concrete evidence models and standard Structurizr DSL examples.

## Workflow

1. Confirm that the requested view fits C4; send dense dependency graphs that do not fit C4 to `graphviz`.
2. Write or confirm the `<name>.structurizr.dsl` workspace with the needed views.
3. Write a Markdown explanation that names purpose, audience, scope, assumptions, evidence, and reading order.
4. If visual inspection is needed, open the DSL file with Qoder's Structurizr DSL viewer.
5. After changing examples or viewer resources, run `npm run validate:examples`.

## Quality Gates

- `.structurizr.dsl` is the source of truth. Rendered previews are derived artifacts.
- Low-confidence, unknown, target, and proposed nodes must keep their labels and must not be presented as verified current state.
- Generate component views only when parent containers are clear.
- If a preview cannot render the view, fix the DSL source before asking the user to manually adjust a derived artifact.

## Avoid

- Do not force every diagram into C4; flowcharts, risk heatmaps, and dense dependency graphs often do not fit.
- Do not manually edit derived preview output to fix model facts.
- Do not copy `../structurizr4js` source into this plugin.

## Artifacts

These artifacts are the maintainable C4 sources and companion notes that explain scope, evidence, assumptions, and reading order.

- `<name>.dsl` / `<name>.structurizr.dsl`: Structurizr DSL workspace source containing the model, relationships, views, and layout intent.
- `<name>.architecture-understanding.md`: purpose, evidence, assumptions, and reading order.
- `<name>.evidence.md`: optional detailed evidence index.

## Exit Criteria

- C4 levels, system boundaries, main nodes, and relationships are traceable to the evidence model.
- Standard Structurizr DSL examples can be used in official Structurizr tools or Playground.
- The DSL can be parsed by a Structurizr-compatible tool when one is available.
- The summary explains how to open the DSL with Qoder's format viewer when visual inspection is needed.

## Summary

Summarize the C4 model in the form that best fits the request. Explain the
scope, view level, evidence, important assumptions, and any risks or gaps in
plain language. Reference the DSL and companion notes by path, and mention how
to open the DSL in Qoder when visual inspection is useful.

## Files

- `../../references/architecture-contract.md`: shared architecture principles, view levels, evidence rules, and delivery contract.
- `../../references/architecture-evidence-model.md`: node, edge, evidence, confidence, and traceability model.
- `../../references/diagram-output-formats.md`: format selection rules and export constraints.
- `../../references/structurizr-canvas-pipeline.md`: Structurizr DSL artifact and viewer guidance.
- `references/c4model-examples.md`: C4 view selection, standard Structurizr DSL examples, evidence model examples, and architect scenarios.
