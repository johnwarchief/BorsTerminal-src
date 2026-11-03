# Design System Capture Guide

Use this guide when extracting design-system rules from existing product evidence.

## Goal

Capture a reusable design system from evidence without inventing arbitrary style. Separate confirmed rules from inferred patterns and unresolved conflicts.

## Source priority

Default priority:

1. Current design-system docs and designer-approved tokens
2. Figma Variables or token exports
3. Shared component library and theme implementation
4. Repeated patterns in production screens
5. One-off page styles
6. Screenshots without source metadata

When sources conflict, report the conflict and request or propose a design decision.

## Capture sources

- Figma Variables and Styles
- `tailwind.config.*`
- CSS variables
- token JSON/YAML files
- component props and variants
- Storybook stories
- screenshots and DOM/computed styles
- existing `DESIGN.md`
- product/brand documentation

## Capture outputs

- token inventory
- typography scale
- spacing and layout scale
- radius and elevation scale
- semantic color roles
- component catalog
- state matrix
- accessibility expectations
- Do/Don't rules
- known exceptions
- source confidence labels
- proposed `DESIGN.md` updates

## DESIGN.md frontmatter shape

When the output is a `DESIGN.md`, use the standard public schema as the primary frontmatter:

- `version`
- `name`
- `description`
- `colors`
- `typography`
- `rounded`
- `spacing`
- `components`

Do not emit a tiny nested `tokens:` block as the main machine-readable contract. Do not rely on `layout`, `options`, `states`, `rules`, or `openDecisions` top-level keys as substitutes for the standard token groups.

Target enough concrete tokens for implementation:

- Colors: semantic roles for primary action, foreground/ink, canvas/surface, muted text, borders/hairlines, and semantic statuses when present. Include literal `primary` and `on-primary`; if needed, alias `primary` to the main action or primary text color and explain the alias in prose.
- Typography: named levels such as `display-lg`, `heading-md`, `body-md`, `body-sm`, `caption`, `button-md`, and `code-md`, each with font family, size, weight, line height, and letter spacing when evidenced. Use `letterSpacing: 0px`, not bare `0`.
- Rounded and spacing: explicit scales, not prose-only descriptions. Use `rounded.none: 0px`, not bare `0`.
- Components: a map of component tokens. Model variants and states as related entries such as `button-primary`, `button-primary-hover`, `button-primary-disabled`, `text-input`, `text-input-focused`, and `table-row-selected`.

Component token properties should reference other tokens with `{colors.*}`, `{typography.*}`, and `{rounded.*}` where possible. Use only official frontmatter properties (`backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, `width`). Put project-specific details like borders, shadows, gaps, cursor, overflow, or descriptions in markdown prose instead.

## Confidence labels

Use these labels:

- `confirmed`: supported by authoritative docs/tokens or repeated component primitive usage.
- `likely`: repeated across product surfaces but not formally documented.
- `tentative`: observed once or ambiguous.
- `conflict`: sources disagree.

## Semantic naming

Prefer semantic token names:

- `primary`
- `primaryForeground`
- `surface`
- `surfaceElevated`
- `mutedForeground`
- `borderSubtle`
- `danger`
- `success`
- `focus`

Weak names:

- `blue500`
- `gray100`
- `color1`
- `buttonColor`

Raw scale names can exist in implementation, but `DESIGN.md` should map them to semantic roles when possible.

## Deduplication

When clustering values:

- keep semantic differences even if raw values are close
- do not collapse all near-grays into one token without role evidence
- identify aliases and source conflicts
- preserve component-specific tokens when they reflect real design intent

## Component capture

For each component, capture:

- purpose
- variants
- sizes
- states
- accessibility expectations
- import path or implementation entry point
- token dependencies
- examples and anti-examples
- confidence level

## Conflict format

```markdown
### Conflict: <topic>
- Figma:
- Code/theme:
- Component:
- Production evidence:
- Impact:
- Recommendation:
- Decision needed from:
```

## Quality bar

A captured system should be:

- semantic rather than merely visual
- deduplicated
- mapped to implementation tokens
- explicit about uncertainty
- safe for coding agents to consume
- actionable for Design QA automation

## Drift prevention

Suggest:

- `DESIGN.md` linting
- stylelint/eslint rules
- component alignment scan
- design debt scan
- Storybook state coverage
- visual baselines
- token export/sync checks
