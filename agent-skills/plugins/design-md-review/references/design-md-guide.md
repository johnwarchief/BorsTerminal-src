# DESIGN.md Guide

Use this guide to review or author `DESIGN.md` as a design contract for humans and coding agents.

## Purpose

`DESIGN.md` should describe reusable design intent, not just a screenshot. It should include machine-readable tokens and human-readable rationale that helps agents implement UI without inventing local rules.

## Quality bar

A good `DESIGN.md` answers:

- What does this product feel like?
- What are the semantic color roles and state colors?
- What typography hierarchy should agents use?
- What layout rhythm and density are expected?
- What shapes, shadows, and elevation patterns are allowed?
- Which components exist?
- What variants and states are allowed?
- What must agents avoid?
- How do design tokens map to code?

## Structure checklist

Recommended sections:

1. Overview
2. Colors
3. Typography
4. Layout
5. Elevation & Depth
6. Shapes
7. Components
8. Do’s and Don’ts

Use this section order when authoring unless the project has a strong reason to differ. Additional sections such as Responsive Behavior, Iteration Guide, Known Gaps, or Open Design Decisions are fine after Do’s and Don’ts.

## Frontmatter schema

Author mode should use the public DESIGN.md schema as the primary machine-readable contract:

```yaml
version: alpha
name: <project-design-analysis>
description: <product feel, source coverage, key tokens, component families, and constraints>
colors:
  <token-name>: <css-color>
typography:
  <level-name>:
    fontFamily: <font stack>
    fontSize: <dimension>
    fontWeight: <number>
    lineHeight: <number|dimension>
    letterSpacing: <dimension|number>
rounded:
  <scale-name>: <dimension>
spacing:
  <scale-name>: <dimension|number>
components:
  <component-or-state-name>:
    backgroundColor: "{colors.*}"
    textColor: "{colors.*}"
    typography: "{typography.*}"
    rounded: "{rounded.*}"
    padding: <dimension-list|token-reference>
    height: <dimension>
```

Do not make a nested `tokens:` object the primary schema. Do not rely on `schemaVersion`, `layout`, `options`, `states`, `rules`, or `openDecisions` as substitutes for the standard token groups.

For official lint compatibility:

- Include literal `primary` and `on-primary` color tokens. If the product has no brand hue, alias `primary` to the main action or primary text color and explain that in prose.
- Use valid dimensions for zero values: `letterSpacing: 0px` and `rounded.none: 0px`, not bare `0`.
- Component frontmatter may use only the official sub-tokens: `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, and `width`.
- Put extra implementation details such as border, shadow, gap, cursor, outline, row dividers, overflow, or descriptions in markdown prose, not in component frontmatter.

## Authoring depth

For a small app, a useful generated `DESIGN.md` usually has:

- 8-16 color tokens
- 6-12 structured typography levels
- 4-8 rounded tokens
- 6-10 spacing tokens
- 8-20 component token entries

For larger apps, add more entries when there is evidence. Avoid padding the frontmatter with invented roles.

Component states should be represented as related component keys, for example:

- `button-primary`
- `button-primary-hover`
- `button-primary-disabled`
- `text-input`
- `text-input-focused`
- `table-row-selected`
- `badge-error`

Each component entry should map to token references and concrete implementation values. A list of component names is not enough for Canvas, lint, or coding-agent use.

## Token checklist

Review tokens for:

- semantic names, not only raw scale names
- foreground/background pairs
- state colors: success, warning, danger, info, focus
- typography size, line height, weight, family, usage
- spacing scale and layout rhythm
- radii and elevation values
- motion duration/easing when relevant
- component token references
- token references that resolve correctly
- no orphaned or contradictory token values

In author mode, prefer token references in component entries (`{colors.primary}`, `{typography.button-md}`, `{rounded.md}`) over repeating raw values. Repeat raw values only when no stable token role exists yet, and mark the gap in Known Gaps.

## Rationale checklist

Each important token or rule should explain:

- when to use it
- when not to use it
- why it exists
- what common AI implementation mistake it prevents

Avoid vague guidance such as “make it clean” unless it is translated into implementation constraints.

## Component guidance

Document:

- component purpose
- variants and sizes
- required states
- accessibility expectations
- allowed composition patterns
- examples of what not to do
- implementation import path or token mapping when known

## Accessibility contract

Include:

- contrast expectations
- focus-visible rules
- color-not-alone rule
- reduced-motion expectations
- form label and error-state expectations
- keyboard expectations for overlays and complex components

## Implementation alignment

Compare with:

- Tailwind config
- CSS variables
- design token files
- component props and variants
- Storybook stories
- design-debt reports

Report drift both ways:

- token in `DESIGN.md` not implemented
- implementation token not documented
- raw value should become a token
- component behavior not covered by the design contract

## Open decisions

Use `needs-design-decision` instead of inventing rules when:

- Figma and code disagree
- token role is ambiguous
- component variant appears once but may not be reusable
- design state is missing from docs
- accessibility policy is not defined

## Patch style

When proposing edits, provide concrete Markdown/YAML snippets rather than generic advice. Keep agent-readable labels stable and semantic.
