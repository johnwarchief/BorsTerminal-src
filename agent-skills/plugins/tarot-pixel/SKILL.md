---
name: tarot-pixel
description: >-
  Recreate production UI from locally imported Figma, or Sketch designs with Tarot Pixel MCP. Use for design-to-code work, implementing pages or components from visual designs, restoring layout and styling, generating raster assets, choosing rasterization boundaries, and deciding which visual elements should be implemented with code. Trigger when the user provides a local /design/{designId} URL, a designId, a module or node reference, or asks to implement or verify UI from an imported design.
description_zh: >-
  使用 Tarot Pixel MCP，根据本地导入的 Figma 或 Sketch 设计稿还原生产级界面。适用于设计转代码、页面或组件实现、布局与样式还原、栅格资源生成、栅格化边界选择，以及判断视觉元素应由代码还是图片实现；当用户提供本地 /design/{designId} URL、designId、模块或节点引用，或要求按设计稿实现、验证界面时触发。
---

# Tarot Pixel

## Required quick flow

Read this flow for every task.

```text
Step 0  Check the environment -> call server_status, resolve designId, then call design_get_overview
Step 1  Locate manually -> use node map for visual location, search by name, and module context for structure
Step 2  Gather evidence -> use D2C context, batch D2C context, and targeted screenshots for exact facts
Step 3  Decide and implement -> combine design evidence with the repository context and choose CSS, assets, and component structure
```

## Core principles

- Derive every visual value from exact MCP evidence such as `design_get_d2c_context` and `design_get_node_relative_offset`. Never eyeball dimensions, spacing, alignment, or position from screenshots.
- Prefer raster assets for decoration and code for content.
- Organize code by visual and product semantics. Do not translate the design layer tree one layer at a time.
- Do not expect a Chat API. Perform node location, component decomposition, and implementation planning yourself; use subagents or other coding workflows when useful.
- Fetch context on demand. Do not preload every node or the complete raw design.
- Generate implementation raster assets only with `design_get_composite` or `design_get_multi_composite`. Screenshots and node maps are evidence, not production assets.

## Environment and tool usage

The design must already have been synced from the relevant MasterGo, Figma, or Sketch plugin. Design ingestion uses the local HTTP service outside this Skill; do not call import endpoints from the coding workflow.

1. Call `server_status`.
2. Extract `designId` from a local URL such as `http://127.0.0.1:18276/design/<designId>` or `http://localhost:18276/design/<designId>`, or use the ID supplied by the user.
3. If no ID is supplied, call `design_list`. Continue automatically only when one design is a clear match; otherwise ask the user which local design to use.
4. Call `design_get_overview` before locating nodes.
5. If no local design exists, ask the user to sync it from the design tool, then call `design_list` again.

Tarot Pixel normally generates a stable eight-character `designId`, but always use the exact ID returned by the tools.

Use only identifiers returned by Tarot Pixel. MCP arguments use arrays rather than comma-separated query strings.

When a tool returns a `resourceUri`, read the content through MCP. When it returns a local `url` or `path`, use it for inspection or copying only; do not write Tarot Pixel runtime URLs or internal filesystem paths into production code.

Error handling:

- `DESIGN_NOT_FOUND`, `MODULE_NOT_FOUND`, or `NODE_NOT_FOUND`: verify the IDs with `design_list`, `design_get_overview`, or `design_list_modules`.
- Module preview failure: use `design_get_node_map` or `design_get_module_screenshot`.
- Rendering failure: confirm that the View is ready in `server_status`, then retry only the required render.

## Standard workflow

### Step 1: Locate manually

Goal: locate the target nodes through visual layout, search, and structure.

Use this combination:

1. `design_get_node_map` — map visible regions to node IDs.
2. `design_search_nodes` — search names or text when the map is dense.
3. `design_get_module_context` — browse the module tree and surrounding structure.

Do not use the node map as a source of dimensions or style values.

Example sequence:

```text
design_get_node_map       { designId, moduleId }
design_search_nodes       { designId, q: "My group buys", module: moduleId }
design_get_module_context { designId, moduleId }
```

### Step 2: Gather evidence independently

Goal: collect exact facts required for implementation.

- Call `design_get_d2c_context` after locating a critical node.
- Call `design_get_d2c_context_batch` when 3-8 critical nodes are already known.
- Call `design_get_node_screenshot` only when a boundary is unclear or the context marks the node for review.
- Use `design_get_node_css`, `design_get_node_layout`, or `design_get_node_spacing` only when the layered D2C context needs targeted clarification.

### Step 3: Decide and implement

Goal: combine design evidence with the existing codebase and choose the implementation.

Decision checklist:

- CSS or raster asset? Base the choice on style complexity in D2C context.
- How should components be split? Base the split on product behavior and the repository architecture.
- How should overlap be implemented? Use `design_get_node_overlap` and `design_get_node_relative_offset`.
- Which decorative layers should be merged? Follow the rasterization rules below.
- Which existing assets should remain content images? Use `design_get_node_assets` or `design_list_assets`.

Output requirements:

- Edit the appropriate project files directly. Do not return disconnected snippets for the user to place manually.
- After generating a raster asset, inspect it, copy it into the target project's managed asset directory, and reference the project asset path.
- Never commit a `127.0.0.1` URL, `tarot-pixel://` URI, Tarot Pixel data path, or temporary render path.
- For isomorphic lists, implement one representative row and reuse the same structure. Handle genuinely different states separately.

## MCP tool reference

### Module level

| Tool                           | Purpose                                               | Use when                                                 | Avoid                                       | Output                |
| ------------------------------ | ----------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------- | --------------------- |
| `design_get_overview`          | List module summaries and design totals               | The user's target is ambiguous or at the start of a task | Skipping directly to node search            | Structured data       |
| `design_get_module`            | Return module root, direct children, and statistics   | The module is known and raw structure is needed          | Using it as the main implementation context | Structured data       |
| `design_get_module_context`    | Return a readable module tree and context             | Browsing module structure quickly                        | Replacing visual location with it           | Text context          |
| `design_get_module_preview`    | Return an imported or locally rendered module preview | Confirming the target module                             | Estimating numeric values from it           | Image metadata        |
| `design_get_node_map`          | Render a visual node map                              | Mapping a visual region to node IDs                      | Using it as a style source                  | PNG resource metadata |
| `design_get_module_similarity` | Group visually and structurally similar nodes         | Repeated structures or multiple states are suspected     | Using it as the default entry point         | Structured data       |
| `design_diff_modules`          | Compare two modules by node path                      | Consolidating multiple states or variants                | Calling it for a single-module task         | Structured data       |

Call `design_diff_modules` with `designId`, `moduleIdA`, and `moduleIdB`.

### Node level

| Tool                         | Purpose                                                       | Use when                                    | Avoid                                              | Output                |
| ---------------------------- | ------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------- | --------------------- |
| `design_get_node`            | Return raw node details, styles, bounds, children, and assets | A node is known and a raw field is required | Replacing D2C context                              | Structured data       |
| `design_get_d2c_context`     | Return implementation facts to a requested depth              | A critical node has been located            | Fetching every candidate before location           | Text context          |
| `design_get_node_screenshot` | Render one node                                               | A boundary is unclear or review is needed   | Rendering every node                               | PNG resource metadata |
| `design_get_node_subtree`    | Expand descendant structure                                   | A node tree requires deeper inspection      | Replacing D2C context                              | Structured data       |
| `design_search_nodes`        | Search by text, name, type, module, parent, or asset presence | The node map is crowded or a label is known | Searching when the map already identifies the node | Structured data       |

### Raster asset generation

| Tool                                | Purpose                                        | Use when                                                        | Avoid                                     | Output             |
| ----------------------------------- | ---------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------- | ------------------ |
| `design_get_composite`              | Generate one parent-bound raster asset         | Static decoration and dynamic content share one parent          | Rendering before deciding include/exclude | Local PNG metadata |
| `design_get_multi_composite`        | Merge arbitrary nodes in one module            | The layers are visually related but lack a useful common parent | Treating it as the default                | Local PNG metadata |
| `design_get_node_composite_hint`    | Analyze composition candidates and hidden text | It is unclear whether a node should be rasterized               | Treating the hint as the final decision   | Structured data    |
| `design_get_module_composite_nodes` | Scan a module for composition candidates       | Performing module-level discovery                               | Replacing manual location                 | Structured data    |

Key `include`, `exclude`, text, and scale behavior:

- `design_get_composite`:
  - `nodeId` defines the parent-bound crop.
  - `include` selects the child layers or child subtrees to retain.
  - `exclude` hides specified layers.
  - `excludeTextNodes` defaults to `true`; `false` technically preserves text nodes. Keep the default for normal D2C work, implement text with DOM, and never disable it for `[keep-text]` nodes.
  - `scale` defaults to 2 and accepts integers from 1 to 4.
- `design_get_multi_composite`:
  - `include` is required and accepts the nodes to merge.
  - `exclude` hides dynamic nodes among them.
  - It does not automatically hide text. Explicitly exclude text nodes so implementation text remains DOM content.
  - `padding` controls extra crop space; `scale` defaults to 2.
- A single-node composite uses one parent-bound crop. A multi-node composite uses the bounding box of arbitrary included nodes in the same module.
- Composite and node screenshot output strips CSS-only transform effects from the target and its ancestor chain so the image is exported upright. Restore intended rotation or flipping with CSS in the implementation.
- Multi-node composite removes the shared ancestor transform when producing the merged image.

Very important: inspect the generated image content after every composite. Check all of the following:

- It matches the visual design.
- The image is not broken or empty.
- It does not contain accidental overlap.
- `include` and `exclude` selected the intended layers.
- Text is excluded correctly. Because `design_get_composite` hides text by default, implement that text with DOM; `[keep-text]` must never be baked into an image.
- The merged layers form the intended visual unit.
- The asset has been copied into the target project before its path is used in code.

### Overlap and relative position

| Tool                              | Purpose                                                     | Use when                                                        | Avoid                                       | Output          |
| --------------------------------- | ----------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------- | --------------- |
| `design_get_node_overlap`         | Analyze overlap and implementation hints                    | The design visibly contains overlay, badge, or partial coverage | Ordinary flow layout                        | Structured data |
| `design_get_node_relative_offset` | Return exact relative coordinates, containment, and overlap | Overlap is confirmed and positioning must be chosen             | Calling it before the relationship is known | Structured data |

### Batch evidence

| Tool                           | Purpose                                       | Use when                             | Avoid                                 | Output        |
| ------------------------------ | --------------------------------------------- | ------------------------------------ | ------------------------------------- | ------------- |
| `design_get_d2c_context_batch` | Return layered D2C context for multiple nodes | 3-8 critical nodes are already known | Fetching every candidate at the start | Text contexts |

Pass `nodeIds` as an array and use only the depth required by the task.

### Custom font subsetting

| Tool                | Purpose                                                       | Use when                                                                            | Avoid                                                                                                         | Output                                |
| ------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `font_subset_local` | Generate a local WOFF2 subset from caller-provided font bytes | A custom font is available locally and the required characters are static and known | Unknown character sets, full-font use, remote font fetching, or restricted fonts that cannot be redistributed | Local WOFF2 metadata and resource URI |

Pass `fontBase64` and `subset`. This tool does not resolve a font by family or weight and does not download remote font URLs. Copy the generated WOFF2 into the target project before referencing it.

## Rasterization decision rules

### Decision priority

Evaluate in this order:

1. Business content images such as product images, avatars, and user uploads -> keep an `<img>` or the project's image component; do not merge them into decoration.
2. Promotional or campaign decoration such as red packets, coupons, and complex card backgrounds -> prefer one merged raster asset.
3. Small icons below 48 px -> generate an individual asset or use SVG when appropriate.
4. Interactive elements such as buttons and inputs -> implement with code; evaluate only their background with the next rule.
5. Simple shapes with solid color, simple gradients, and no texture or lighting -> implement with CSS. Rasterize complex texture, lighting, or effects.
6. Mixed containers with dynamic content -> rasterize the static background, exclude dynamic content, and overlay code.

When uncertain, prefer rasterizing static decoration, but first confirm that the node is truly static.

### Rasterization boundaries

- The unit is a visual unit, not a node subtree. Prefer one static visual region plus excluded dynamic layers. The node tree does not necessarily match the visual tree.
- Merge decorative layers that always appear together in fixed positions into one composite.
- Dynamic content must be excluded: text, prices, avatars, countdowns, and similar content must not be baked into the image.
- Export an icon separately only when it has real cross-screen reuse value.
- Handle different states separately, such as normal/completed or locked/unlocked.
- Never implement the same element twice as both a raster asset and DOM/CSS.

### Scenario guide

| Scenario                              | Strategy                                                                                                                                              |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dialog, overlay, or panel             | Generate one backplate image; exclude title, body, price, buttons, and other dynamic content                                                          |
| Red packet, coupon, or campaign card  | Generate one background composite; exclude amount, code, countdown, and stateful text; generate separate assets for distinct states                   |
| Product card or entitlement row       | Merge gradient base, fixed badge base, and divider when their positions are fixed; exclude price and title; reuse one background for isomorphic cards |
| List or feed row                      | Define one representative row and reuse it; implement state differences separately when rows differ                                                   |
| Header, tab bar, or bottom navigation | Generate one mixed-container background strip; exclude icons and labels                                                                               |
| Full-screen atmosphere background     | Use a small number of large composites; implement titles, people, and products with code or separate content assets                                   |

### Merge test

Ask: do these static decorative nodes always appear together in fixed positions?

- If yes, generate one composite to reduce render calls and DOM elements.
- If no, keep them separate according to reuse and state boundaries.

Do not merge:

- Dynamic content such as product images, text, prices, or user avatars.
- Independently reusable icon components.
- Elements representing different product states.

### Composite examples

<example>
**Scenario 1: background plus fixed decoration**

A card background, top-right fixed badge, and bottom decoration line always appear together.

```json
{
  "tool": "design_get_composite",
  "arguments": {
    "designId": "<designId>",
    "nodeId": "node_card",
    "include": ["node_bg_svg", "node_badge", "node_decoration_line"]
  }
}
```

Result: one merged asset instead of three separate assets.
</example>

<example>
**Scenario 2: complex background texture**

A gradient, texture overlay, and lighting decoration form one visual background.

```json
{
  "tool": "design_get_composite",
  "arguments": {
    "designId": "<designId>",
    "nodeId": "node_hero",
    "include": ["node_gradient_bg", "node_texture_overlay", "node_light_effect"]
  }
}
```

Result: one raster asset instead of several CSS layers that approximate the effect.
</example>

Call comparison:

```text
[BAD]  Three design_get_composite calls for node_bg, node_divider, and node_icon.

[GOOD] One design_get_composite call:
       nodeId=node_card
       include=[node_bg, node_divider, node_icon]

[GOOD] Mixed container:
       nodeId=node_promo_card
       include=[node_bg, node_decoration]
       exclude=[node_title, node_price]
```

## Overlap handling

Use overlap tools only when the screenshot visibly contains overlap, D2C context reports `overflow`, `overlap`, or `absolute`, or the positioning strategy is genuinely unclear.

1. Call `design_get_node_overlap { designId, nodeId }` to distinguish containment, partial coverage, overlays, and badges.
2. After confirming the relationship, call `design_get_node_relative_offset { designId, fromNodeId, toNodeId }` for exact positioning evidence.
3. Choose normal flow, flex/grid, relative positioning, or absolute positioning based on both the relationship and the existing code structure.

## Absolutely forbidden

- Eyeballing numeric values from screenshots.
- Prefetching large amounts of D2C context before locating target nodes.
- Writing decorative background code before obtaining and inspecting the required composite asset.
- Rasterizing text marked `[keep-text]`.
- Overusing `position: absolute` in ordinary flow layouts.
- Exporting one image per child node instead of one meaningful visual unit.
- Implementing one element both as an image and as duplicate DOM/CSS.
- Writing private object-storage URLs into code.
- Writing Tarot Pixel localhost URLs, MCP resource URIs, internal data paths, or temporary render paths into production code.

## CSS notes

- Account for global styles and resets when matching the visual design.
- When adding `padding` or `border`, also set or verify `box-sizing: border-box`.
