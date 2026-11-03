---
name: drawio
description: "Optional Draw.io / diagrams.net delivery foundation. Use only when the user explicitly asks for Draw.io, .drawio, diagrams.net, editable diagram delivery, or local Draw.io MCP usage. Preserve the architecture evidence model as source of truth; use Draw.io only as a derived editable delivery format."
---

# Draw.io

Optional Draw.io / diagrams.net delivery foundation.

Use this skill when the user explicitly asks for Draw.io, `.drawio`, diagrams.net, editable diagram delivery, or local Draw.io MCP setup. Do not use this skill just because the user asks for an architecture diagram.

This skill helps an agent decide whether to recommend or use a local Draw.io MCP server. It does not add Draw.io to the plugin's deterministic generation pipeline.

Read `../../references/architecture-contract.md` before producing user-facing architecture artifacts.

Read `../../references/architecture-evidence-model.md` before claiming that a node, edge, risk, or decision is supported by code, configuration, runtime data, or documentation.

Read `../../references/diagram-output-formats.md` before choosing Mermaid, PlantUML, Graphviz, Structurizr DSL, Excalidraw, Draw.io, SVG, Markdown, Canvas, or slide-oriented output.

## Use Cases

- The user asks for an editable `.drawio` or diagrams.net delivery.
- The user already has a Draw.io MCP server installed and asks the agent to open or update a diagram through it.
- A stakeholder wants to continue manual editing in Draw.io after the architecture model has been generated.
- A small Mermaid or XML diagram should be opened in Draw.io for workshop editing.
- The user asks how to install or configure Draw.io MCP locally.

## Boundaries

- Keep the Structurizr DSL, DOT, or Mermaid source as the source of truth.
- Treat Draw.io as a derived editable delivery artifact, not the canonical architecture model.
- Do not add Draw.io as a dependency of this plugin.
- Do not invent Draw.io MCP tools that are not available in the current agent environment.
- Do not replace C4/Structurizr, Graphviz, or Mermaid generation with Draw.io.
- Do not route broad architecture requests directly to `drawio`; route by scenario first through `explore`.

## Recommended Local MCP

Prefer the official Draw.io MCP package when the user wants a simple local install for opening Mermaid, XML, or CSV diagrams in Draw.io.

Codex-style MCP config:

```toml
[mcp_servers.drawio]
command = "npx"
args = ["-y", "@drawio/mcp"]
```

Use this path when the agent needs tools such as:

- `open_drawio_mermaid`
- `open_drawio_xml`
- `open_drawio_csv`

The hosted endpoint can be convenient for non-sensitive diagrams, but local or self-hosted setup is safer for private architecture content.

## Advanced Live Editor MCP

If the user specifically wants an agent to inspect or edit an already-open Draw.io document, a live-editor MCP such as `drawio-mcp-server` may be useful.

Codex-style MCP config:

```toml
[mcp_servers.drawio]
command = "npx"
args = ["-y", "drawio-mcp-server", "--editor"]
```

Use this only when the user understands that the MCP interacts with a running Draw.io editor session. It is useful for interactive edits, pages, layers, selections, and exports, but it is less suitable for deterministic CI-style architecture generation.

## Workflow

1. Route the architecture request through the appropriate scenario skill first.
2. Generate or validate the source artifact: Structurizr DSL, Mermaid, DOT, or SVG.
3. If Draw.io MCP tools are available, open the derived source in Draw.io:
   - Use Mermaid for small flowcharts and readable documentation diagrams.
   - Use XML when precise Draw.io layout, pages, layers, or vendor shapes matter.
   - Use CSV only for simple structured shape imports.
4. Tell the user which artifact remains canonical and which Draw.io artifact is editable delivery.
5. If Draw.io MCP tools are not available, provide install steps and keep delivering the normal source artifacts.

## Quality Rules

- Preserve stable node and edge IDs when converting into Draw.io XML.
- Preserve labels, state, confidence, and `sourceRefs` where the target format allows it.
- Mark low-confidence or assumed relationships visibly.
- Include a short README or summary note explaining how the Draw.io file was derived.
- Avoid manual Draw.io edits that change architecture facts without updating the evidence model.

## Artifacts

These artifacts separate the canonical architecture source from any derived editable Draw.io delivery file.

- `<name>.mmd|dot|dsl|svg`: canonical or intermediate diagram source used for delivery.
- `<name>.drawio`: optional derived editable Draw.io XML when generated.
- `drawio-summary.md`: source-of-truth note, editable delivery status, MCP availability, and regeneration steps.

## Summary

Summarize the Draw.io delivery without turning it into the source of truth.
State which artifact remains canonical, which Draw.io file is editable, how it
was derived, and any MCP or usage notes the user needs. Include paths and next
steps only when they help the user open or maintain the editable diagram.

## Files

- `../../references/architecture-contract.md`: shared architecture contract, evidence rules, and artifact shape.
- `../../references/architecture-evidence-model.md`: node, edge, evidence, confidence, and traceability model.
- `../../references/diagram-output-formats.md`: format selection rules, including editable delivery formats.
- `../../references/diagram-delivery-recipes.md`: delivery/export recipes and degradation notes.
