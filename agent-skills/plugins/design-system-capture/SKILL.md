---
name: design-system-capture
description: Captures or updates a design system from existing UI, Figma Variables, Tailwind config, CSS variables, component library files, screenshots, Storybook, and DOM/computed styles. Use to generate or refine DESIGN.md, reconcile source-of-truth conflicts, identify token/component drift, and turn product evidence into reusable design rules.
---

# Design System Capture

## Skill contract

This Skill extracts a reusable design system from evidence. It is for discovery, reconciliation, and documentation—not for inventing arbitrary visual style.

**Read-only by default.** Do NOT create or modify any files (including `DESIGN.md`) unless the user explicitly asks to "write", "create", "generate", or "update the file". When the user says "capture", "extract", or "analyze", produce only the report output below. If you are unsure, output the report and ask before writing.

**Write mode is mandatory when requested.** If the user explicitly asks to "generate DESIGN.md", "create DESIGN.md", "write DESIGN.md", "update DESIGN.md", or "save the file", you MUST write or update the target `DESIGN.md` on disk. Do not stop at "proposed content" in that mode. After writing, report the path, source evidence, and any parser/viewer risks.

The output should clearly separate:

- confirmed design rules
- inferred patterns
- conflicts between sources
- open design decisions
- proposed `DESIGN.md` content (as inline markdown in the report, not written to disk)
- drift-prevention automation

## Use when

Use this Skill when the user asks to:

- create or update `DESIGN.md` from existing product UI
- infer design tokens from Tailwind config, CSS variables, Figma Variables, components, screenshots, or Storybook
- reconcile Figma tokens with code tokens
- identify drift between design source of truth and implementation
- document a legacy UI before refactoring
- prepare a product for Design QA automation

## Do not use when

Do not use this Skill as the primary Skill when:

- the user already has a `DESIGN.md` and wants it reviewed; use `design-md-review`
- the user asks for implementation approval; use `design-qa`
- the user asks only for screenshot diff; use `visual-regression-review`
- the user asks only for hard-coded code cleanup; use `design-debt-review`

## Inputs

Look for:

- existing `DESIGN.md`
- Figma Variables, Figma file/frame references, or exported token files
- Tailwind config
- CSS variables and global styles
- component library source
- Storybook stories
- screenshots and DOM/computed-style exports
- `.design-qa/reports/design-debt.json`
- `.design-qa/reports/component-alignment.json`
- product/brand notes from README, docs, or user-provided context

## Source priority

Use this priority unless the user states a different source of truth:

1. Explicit current design-system docs and designer-approved tokens
2. Figma Variables or token exports from the design system
3. Shared component library and theme implementation
4. Repeated patterns in production screens
5. One-off page styles
6. Screenshots without source metadata

When sources conflict, do not silently merge. Report the conflict and propose a decision.

## Capture workflow

1. **Inventory sources**
   - List available design docs, token files, CSS variables, Tailwind theme, components, stories, screenshots, and reports.
   - Mark each source as authoritative, supporting, inferred, or stale.

2. **Extract candidate tokens**
   - Colors: surfaces, text, border, brand, semantic states, chart/data colors.
   - Typography: font families, sizes, line heights, weights, letter spacing, use cases.
   - Spacing/layout: scale, containers, grids, gutters, page density, section rhythm.
   - Shape: radii by component size and hierarchy.
   - Elevation: shadows, overlays, borders, blur, stacking.
   - Motion: duration, easing, reduced-motion expectations.

3. **Extract component patterns**
   - Button, input, select, checkbox, radio, switch, card, dialog, popover, table, list, tabs, menu, alert, toast, badge, avatar, nav.
   - For each, capture variants, sizes, states, accessibility expectations, and implementation entry point.

4. **Deduplicate raw values**
   - Cluster near-identical colors and sizes.
   - Prefer existing token names over invented names.
   - Convert raw values into semantic roles only when the role is supported by repeated usage or docs.

5. **Score confidence**
   - `confirmed`: supported by authoritative docs/tokens or repeated component primitive usage.
   - `likely`: repeated across product surfaces but not formally documented.
   - `tentative`: observed once or ambiguous.
   - `conflict`: sources disagree.

6. **Draft or update `DESIGN.md`**
   - Include tokens and rationale.
   - State what is confirmed vs inferred.
   - Include Do/Don't rules that prevent likely AI implementation mistakes.
   - Add open decisions instead of inventing missing policy.
   - In read-only capture mode, output the proposed `DESIGN.md` content inline in the report.
   - In write mode, write the complete `DESIGN.md` file to disk and include a short summary in the report.

7. **Create drift-prevention rules**
   - Suggest lint rules, component alignment checks, design debt scans, Storybook coverage, visual baselines, or token export sync.

## Core review criteria

Capture design-system evidence with these rules:

- **Source authority**: Prefer approved docs/tokens over screenshots and one-off code.
- **Semantic naming**: Convert raw values into semantic roles only when usage evidence supports the role.
- **Confidence labels**: Mark rules as `confirmed`, `likely`, `tentative`, or `conflict`.
- **Conflict visibility**: Do not silently merge Figma/code/component differences.
- **Agent safety**: Output rules that prevent future AI-generated drift.
- **QA readiness**: Capture enough tokens, components, states, and source mappings to power Design QA automation.

Read `references/capture-guide.md` for source priority, confidence labels, naming, and conflict handling.

## DESIGN.md frontmatter target

When writing or drafting `DESIGN.md`, follow the public `DESIGN.md` token schema used by the reference corpus in `awesome-design-md`. The frontmatter is the machine-readable design system, not a short summary. Prefer the standard top-level keys:

- `version`
- `name`
- `description`
- `colors`
- `typography`
- `rounded`
- `spacing`
- `components`

Use `version: alpha` unless the project already uses another explicit version. Do not use a nested `tokens:` object as the primary schema. Do not substitute shallow `layout`, `options`, `states`, or `openDecisions` frontmatter for the standard token groups. Put rules, state explanations, conflicts, and decisions in markdown sections unless the project already has a compatible extension schema.

Minimum useful frontmatter for a small app:

- `colors`: 8-16 semantic roles when evidence exists, including literal `primary` and `on-primary` tokens, text/ink, canvas/surface, border/hairline, muted text, and semantic error/success/warning roles when present. If the product has no brand hue, alias `primary` to the main action or primary text color and explain that choice in prose.
- `typography`: 6-12 named levels such as `display-lg`, `heading-md`, `body-md`, `body-sm`, `caption`, `button-md`, and `code-md` when code surfaces exist. Each level should be an object with `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, and `letterSpacing` when evidence supports it. `letterSpacing` must be a dimension such as `0px`, not bare `0`.
- `rounded`: 4-8 scale entries such as `none`, `xs`, `sm`, `md`, `lg`, `xl`, `full`. Use `none: 0px`, not `none: 0`.
- `spacing`: 6-10 scale entries such as `xxs`, `xs`, `sm`, `md`, `lg`, `xl`, `xxl`, `section`.
- `components`: 8-20 entries for the real component surface. Include state variants as separate related keys such as `button-primary`, `button-primary-hover`, `button-primary-disabled`, `text-input`, `text-input-focused`, `table-row-selected`, or `badge-error`.

Component entries should reference tokens with `{path.to.token}` and use only the official DESIGN.md component sub-tokens in frontmatter: `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, and `width`. Put extra implementation details such as border, shadow, gap, cursor, outline, overflow, or descriptions in the markdown `## Components` section instead of frontmatter.

```yaml
---
version: alpha
name: Product-design-analysis
description: A concise design-system summary covering product feel, source coverage, key tokens, component families, and known constraints.
colors:
  primary: "#000000"
  on-primary: "#ffffff"
  ink: "#111827"
  muted: "#6b7280"
  canvas: "#ffffff"
  surface-card: "#f9fafb"
  hairline: "#e5e7eb"
  danger: "#dc2626"
typography:
  display-lg:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 48px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: -0.02em
  body-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  button-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: 0px
rounded:
  none: 0px
  sm: 6px
  md: 8px
  lg: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  section: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
    height: 40px
  button-primary-disabled:
    backgroundColor: "{colors.muted}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
  text-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
---
```

Markdown body requirements:

- Use stable `##` sections in this order when applicable: Overview, Colors, Typography, Layout, Elevation & Depth, Shapes, Components, Do's and Don'ts, Responsive Behavior, Known Gaps.
- Explain state requirements in `## Components` using component-token names from frontmatter.
- Put unresolved issues in `## Known Gaps` or `## Open Decisions`; mark them `needs-design-decision` instead of inventing policy.
- Keep all token references in prose as `{colors.primary}`, `{typography.body-md}`, `{rounded.md}`, or `{components.button-primary}` so readers and tooling can connect prose back to frontmatter.

## Automation path discovery

Use this Skill's local evidence collector first, then use sibling audits when deeper confirmation is needed:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
node "$DESIGN_PLUGIN_ROOT/skills/design-system-capture/scripts/collect-design-system-evidence.mjs" --config design.qa.yaml
node "$DESIGN_PLUGIN_ROOT/skills/design-debt-review/scripts/audit-design-debt.mjs" --config design.qa.yaml
node "$DESIGN_PLUGIN_ROOT/skills/component-library-alignment/scripts/audit-components.mjs" --config design.qa.yaml
node "$DESIGN_PLUGIN_ROOT/skills/design-md-review/scripts/audit-design-md.mjs" --config design.qa.yaml
```

Use Figma/token exports when the project provides them. If not, capture from code and screenshots with lower confidence.

## Naming guidance

Prefer semantic token names:

- Good: `primary`, `primaryForeground`, `surface`, `surfaceElevated`, `mutedForeground`, `borderSubtle`, `danger`, `success`
- Weak: `blue500`, `gray100`, `color1`, `buttonColor`

Use raw scale names only when they are part of an implementation scale, and map them to semantic roles when documenting design intent.

## Conflict handling

Report conflicts like this:

```markdown
### Conflict: primary button radius
- Figma variable: 12px
- Tailwind theme: 8px
- Button component: 10px hard-coded
- Production screenshots: mostly 8px
- Recommendation: choose 8px if implementation is source of truth, or update Button/theme to 12px if Figma is authoritative.
- Decision needed from: design owner
```

## Output format

```markdown
# Design System Capture Summary

## Sources Inspected
| Source | Status | Confidence | Notes |
|---|---|---:|---|

## Confirmed Design Rules

## Inferred Patterns

## Token Candidates

## Component Candidates

## Conflicts and Open Decisions

## Proposed DESIGN.md Changes

## Drift Prevention Rules

## Next Design QA Setup
- [ ] Update DESIGN.md
- [ ] Update design.qa.yaml screens
- [ ] Add component stories/snapshots
- [ ] Add token/debt scans to CI
```

## Trigger tests

This Skill should trigger for:

- “从现有 UI 反推一个 DESIGN.md。”
- “把 Tailwind / CSS variables / 组件库整理成设计系统。”
- “Figma token 和代码 token 有没有漂移？”
- “老项目没有设计系统，先帮我 capture 一版。”

It should hand off to `design-md-review` after drafting `DESIGN.md`, and to `design-qa` after a usable contract exists.

## Detailed reference

Read `references/capture-guide.md` when you need detailed source priority, capture outputs, confidence labels, semantic naming, deduplication, component capture, conflicts, and drift prevention guidance.

## Version history

- v0.4.0: Added Skill-local `collect-design-system-evidence.mjs` and updated supporting audit paths.
- v0.3.0: Moved detailed review guides into Skill-local `references/*-guide.md` files and added an inline core review criteria for progressive disclosure.
- v0.2.0: Added source priority, confidence scoring, conflict handling, semantic naming, and drift-prevention guidance.
- v0.1.0: Initial design system capture workflow.
