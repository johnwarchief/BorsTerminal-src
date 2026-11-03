---
name: graphviz
description: "Graphviz/DOT source foundation. Use to turn dense architecture evidence into maintainable DOT artifacts for dependency, flow, deployment, risk, lineage, and impact graphs that do not fit C4."
---

# Graphviz

Graphviz DOT source foundation.

Use this skill when the user needs Graphviz DOT source, dense dependency maps, large relationship graphs, risk maps, data lineage graphs, or non-C4 architecture relationship modeling.

The goal is to turn non-C4 architecture relationship models into layout-friendly, filterable, reusable Graphviz DOT.

Read `../../references/architecture-contract.md` before producing user-facing architecture artifacts.

Read `../../references/architecture-evidence-model.md` before claiming that a node, edge, risk, or decision is supported by code, configuration, runtime data, or documentation.

Read `../../references/diagram-output-formats.md` before choosing Mermaid, PlantUML, Graphviz, Structurizr DSL, Excalidraw, Draw.io, SVG, Markdown, or slide-oriented output.

Read `references/graphviz-scenarios.md` when the user asks for examples, when the view is relation-dense, or when choosing DOT patterns for dependency, lineage, risk, layer, state-machine, or blast-radius graphs.

## Use Cases

- The user explicitly asks for Graphviz, DOT, large graphs, dependency graphs, cycle detection, layer violations, risk maps, or lineage graphs.
- The view has enough nodes and edges that Mermaid or C4 would become unreadable.
- The graph needs grouping by layer, domain, team, risk, or data object.
- Dependencies, service calls, data flows, technical debt, or change impact need layout.

## Inputs

- Architecture evidence: code structure, imports, service contracts, IaC, docs, or other source material.
- Optional graph name, rank direction, output path, and grouping field.

## Layout Decision Rules

Use layout direction as a delivery decision, not a fixed style preference.

| Scenario | Preferred direction | LR exception |
| --- | --- | --- |
| Qoder Canvas or built-in `.dot` preview, especially when the graph is relation-dense | `rankdir=TB` | Only after the graph is intentionally small and width is verified. |
| Risk, technical debt, dependency, layer violation, change impact, deployment, legacy, and unknowns maps | `rankdir=TB` | Rare; split or filter the graph before using `LR`. |
| Short linear data lineage, ETL/CDC chain, traffic path, or critical service path | `rankdir=TB` for Canvas, `rankdir=LR` for compact SVG/Markdown delivery | Use `LR` when the graph has few nodes, short labels, no wide clusters, and is not expected to open first in Canvas. |
| Sequence, timeline, or migration chronology | Prefer PlantUML sequence, Mermaid timeline, or Markdown | Use DOT only for small relationship overlays, then choose direction by preview target. |

Wide horizontal DOT often renders outside the useful Canvas viewport and can appear blank or nearly blank. Add `nodesep`, `ranksep`, focused clusters, filters, or drill-down graphs before switching dense Canvas-oriented output to horizontal layout.

## Recommended Views

- Module/package/service dependency graph.
- Cycle graph, layer violation graph, reverse dependency graph.
- Data lineage graph, read/write graph, event relationship graph.
- Risk or technical-debt relationship graph.
- Change blast-radius graph.

## Example Entry Points

- Module dependencies: use `--cluster-by group|owner|type` to show layers, teams, or domains, and keep edge labels such as `compile-time-dependency`.
- Service calls: label an edge `runtime-call` only when API clients, route config, traces, or runtime evidence support it.
- Data lineage: use distinct shapes for databases, queues, jobs, and export files; keep edge labels such as `reads`, `writes`, `publishes`, and `batch-export`.
- Risk or technical debt: use diamond risk nodes, dashed low-confidence edges, and a summary that names the next validation step.
- See `references/graphviz-scenarios.md` for concrete evidence models and DOT snippets.

## Workflow

1. Confirm that the requested view is relationship-dense; send C4 system/context/container/component views to `c4model`.
2. Choose node granularity and filters so the output is not an unreadable full graph.
3. Choose the DOT layout with the decision table above. Default dense Canvas-oriented output to `rankdir=TB`; document any deliberate `rankdir=LR` exception in the summary.
4. Write `<name>.dot` to disk as an actual file using the file creation tool — do NOT inline the full DOT source in the chat. Reference the file path in the response.
5. Render SVG with Graphviz when an export is needed.
6. If an interactive Canvas preview is needed, open the DOT file with Qoder's DOT format viewer.
7. Output reading order, key clusters, abnormal relationships, and follow-up governance actions.
8. After changing examples or viewer resources, run `npm run validate:examples`.

## Quality Gates

- Edge types must distinguish compile-time dependency, runtime call, data access, event, config, and human assumption.
- Large graphs must include filtering or grouping notes; do not deliver only one unreadable full graph.
- Qoder Canvas-oriented DOT must prefer `rankdir=TB` for dense graphs and avoid a single long horizontal rank unless the graph is intentionally small and width has been considered.
- Low-confidence and unknown edges must be visible through style or labels.
- DOT is the maintainable source file. SVG/PNG are derived artifacts.

## Avoid

- Do not describe static imports as runtime calls.
- Do not use Graphviz for views that need reusable C4 system/context/container semantics.
- Do not produce a visually pleasing layout while dropping evidence, confidence, or follow-up actions.

## Artifacts

These artifacts capture the maintainable DOT source, optional render output, evidence index, and graph-reading summary.

- `<name>.dot`: Graphviz DOT source file.
- `<name>.svg`: optional rendered graph.
- `<name>-evidence.md`: node/edge evidence and confidence.
- `<name>-summary.md`: filters, key findings, and follow-up actions.

## Exit Criteria

- Readers can locate key relationships, abnormal clusters, and high-risk nodes.
- Nodes and edges are traceable to the evidence model.
- The graph source can be regenerated and filtered or grouped as needed.

## Summary

Summarize the graph in prose that helps the reader interpret it. Explain why
DOT was used, what the graph includes or filters out, the most important
clusters or edges, and any low-confidence relationships. Reference the DOT,
optional render output, and viewer/render instructions when useful.

## Files

- `../../references/architecture-contract.md`: shared architecture principles, view levels, evidence rules, and delivery contract.
- `../../references/architecture-evidence-model.md`: node, edge, evidence, confidence, and traceability model.
- `../../references/diagram-output-formats.md`: format selection rules and export constraints.
- `references/graphviz-scenarios.md`: DOT examples for dependency maps, layer violations, lineage, risk maps, and related scenarios.
