---
name: design-md-review
description: Reviews, authors, or improves DESIGN.md as a machine-readable and human-readable design system contract. Use for design.md linting, token frontmatter, section completeness, design rationale, token references, component rules, Do/Don't guidance, design-token export readiness, and implementation alignment.
---

# DESIGN.md Review

## Skill contract

`DESIGN.md` is the project's design contract for humans and coding agents. It should define both machine-readable tokens and human-readable design rationale.

This Skill reviews or authors `DESIGN.md` so that agents can reliably implement, review, and refactor UI without inventing local design rules.

**Mode selection rule:**

- **Review mode (default when `DESIGN.md` exists):** Audit the existing file against the quality bar below. Output findings, severity, and concrete patches. Do NOT regenerate or replace the entire file.
- **Author mode (only when `DESIGN.md` does not exist OR the user explicitly asks to "create", "write", or "generate" a new one):** Produce a complete `DESIGN.md` using the public DESIGN.md schema. If the user explicitly asks to create, write, generate, update, or save the file, write it to disk at the requested path or `./DESIGN.md`.

When the user says "review", "audit", "check", or "lint", always use Review mode regardless of file quality.

## Use when

Use this Skill when the user asks to:

- create, review, or improve `DESIGN.md`
- check whether the design system contract is complete enough for coding agents
- validate design tokens, token references, or design.md linter output
- document colors, typography, layout, elevation, shapes, components, states, and Do/Don’t rules
- compare `DESIGN.md` with Tailwind/CSS/theme implementation
- prepare design tokens for export into Tailwind, CSS variables, or DTCG-style token formats

## Do not use when

Do not use this Skill as the primary Skill when:

- the user asks for full implementation QA; use `design-qa`
- the user asks to derive a design system from screenshots, CSS, Figma, or code; use `design-system-capture` first
- the user only asks for screenshot comparison; use `visual-regression-review`
- the user only asks for design debt in code; use `design-debt-review`

## Inputs

Look for:

- `DESIGN.md`
- Tailwind config and CSS variable files
- design token JSON/YAML files
- Figma Variables exports or references
- component library docs and Storybook stories
- `SCREEN_SPEC.md` for page-level patterns
- `.design-qa/reports/design-md-audit.json`
- design.md linter output, if available

## Automation path discovery

Locate this Skill's automation script in this order:

1. `$DESIGN_PLUGIN_ROOT/skills/design-md-review/scripts`
2. `.qoder/design-plugin/skills/design-md-review/scripts`
3. `skills/design-md-review/scripts` in the current plugin checkout

Run the local audit:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
node "$DESIGN_PLUGIN_ROOT/skills/design-md-review/scripts/audit-design-md.mjs" --config design.qa.yaml
```

If the official design.md CLI is available, also run:

```bash
npx @google/design.md lint DESIGN.md
```

Inspect:

```text
.design-qa/reports/design-md-audit.json
```

## Review workflow

1. **Check file existence and structure**
   - `DESIGN.md` exists in the expected location.
   - YAML frontmatter exists and is valid.
   - Markdown body is readable by humans.
   - Sections are stable and easy for agents to scan.

2. **Check token quality**
   - Frontmatter should follow the public `DESIGN.md` schema: `version`, `name`, `description`, `colors`, `typography`, `rounded`, `spacing`, and `components`.
   - Do not treat a small nested `tokens:` object, `layout/options` metadata, or prose-only tables as equivalent to the standard schema.
   - Tokens use semantic roles rather than only raw names.
   - Token references are valid and not orphaned.
   - Color tokens include foreground/background relationships where relevant.
   - Typography tokens include size, line height, weight, and use cases.
   - Spacing, radius, elevation, and motion tokens are documented when they shape UI consistency.
   - Component frontmatter is a token map, not a list of component names. Prefer entries like `button-primary`, `button-primary-hover`, `text-input`, `text-input-focused`, `table-row-selected`, and `badge-error` with `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `height`, or similar evidenced properties.

3. **Check required design areas**
   - Overview
   - Colors
   - Typography
   - Layout
   - Elevation & Depth
   - Shapes
   - Components
   - Do’s and Don’ts

4. **Check design rationale**
   - Explain what the product should feel like.
   - Explain why tokens exist and where they should be used.
   - Explain what not to do.
   - Avoid vague words without implementation consequences.

5. **Check component guidance**
   - Buttons, inputs, cards, navigation, dialogs, tables, lists, alerts/toasts, tabs, and menus should have usage rules if present in the product.
   - States should be explicit: default, hover, focus-visible, active, disabled, loading, selected, error, success, warning, empty.
   - Component guidance should mention when to use variants and when not to create new variants.

6. **Check accessibility contract**
   - Contrast expectations.
   - Focus-visible rules.
   - Color-not-alone rule for semantic states.
   - Motion/reduced-motion expectations.
   - Form and error-state expectations.

7. **Check implementation alignment**
   - Map tokens to Tailwind theme, CSS variables, style dictionary, or component props.
   - Identify tokens defined in design but not implemented.
   - Identify implementation tokens with no design rationale.
   - Identify direct hard-coded values that should reference tokens.

8. **Produce concrete edits**
   - Prefer exact Markdown/YAML additions over generic suggestions.
   - When uncertain, mark items as `needs-design-decision` instead of inventing rules.

## Author workflow

Use this workflow when `DESIGN.md` is missing or the user explicitly asks to create/write/generate it:

1. **Inspect evidence first**
   - Read `package.json`, global styles, CSS variables, Tailwind/theme config, component files, route/page files, Storybook stories, screenshots, and existing token files when present.
   - If design evidence is only code, label derived rules as inferred in prose. Do not invent brand policy that is not visible in code or docs.

2. **Write standard frontmatter**
   - Use the public DESIGN.md schema as the primary machine-readable contract:
     - `version`
     - `name`
     - `description`
     - `colors`
     - `typography`
     - `rounded`
     - `spacing`
     - `components`
   - Use `version: alpha` unless the project already declares a different DESIGN.md version.
   - Do not use a nested `tokens:` object as the primary schema.
   - Do not substitute `schemaVersion`, `layout`, `options`, `states`, `rules`, or `openDecisions` for the standard token groups. Those may appear only as project-specific extensions when the project already uses them.

3. **Make frontmatter substantial**
   - `colors`: target 8-16 semantic tokens for small projects and more when evidenced. Include literal `primary` and `on-primary` tokens; if the product has no brand hue, alias `primary` to the main action or primary text color and explain that choice in prose. Also include ink/text, body/muted text, canvas/surface, hairline/border, and semantic status roles when present.
   - `typography`: target 6-12 structured levels such as `display-lg`, `heading-md`, `body-md`, `body-sm`, `caption`, `button-md`, and `code-md` when code/data surfaces exist. Each level should include `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, and `letterSpacing` when evidenced. `letterSpacing` is a dimension: write `0px`, not bare `0`.
   - `rounded`: target 4-8 scale entries such as `none`, `xs`, `sm`, `md`, `lg`, `xl`, `full`. `rounded.none` must be `0px`, not bare `0`.
   - `spacing`: target 6-10 scale entries such as `xxs`, `xs`, `sm`, `md`, `lg`, `xl`, `xxl`, `section`.
   - `components`: target 8-20 entries for real component surfaces. Model states as related component token names, for example `button-primary`, `button-primary-hover`, `button-primary-disabled`, `text-input`, `text-input-focused`, `table-row-selected`, `badge-error`.

4. **Use component token maps**
   - Component entries should be objects, not strings or simple lists.
   - Use only official DESIGN.md component sub-tokens in frontmatter: `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, and `width`.
   - Put extra implementation details such as border, shadow, gap, cursor, outline, description, overflow, row dividers, or text transform in the markdown `## Components` section, not in frontmatter.
   - Reference tokens with `{colors.*}`, `{typography.*}`, `{rounded.*}`, and `{spacing.*}` wherever possible.

5. **Write standard markdown sections**
   - Use stable `##` sections in this order when applicable: Overview, Colors, Typography, Layout, Elevation & Depth, Shapes, Components, Do's and Don'ts, Responsive Behavior, Known Gaps.
   - Explain component states in `## Components` using the same token names from frontmatter.
   - Put unresolved issues in `## Known Gaps` or `## Open Design Decisions`; mark them `needs-design-decision`.

6. **Verify the output**
   - Confirm frontmatter parses as YAML.
   - Confirm token references in prose and component entries point at existing frontmatter paths.
   - If the local `design-md` Canvas parser is available, run it or report why it could not be run.
   - If `npx @google/design.md lint DESIGN.md` is available and appropriate, run it or report why it was skipped.

## Core review criteria

Review `DESIGN.md` against these criteria:

- **Readable contract**: Humans and agents can quickly understand the product feel and rules.
- **Machine-readable tokens**: Frontmatter tokens are semantic, valid, and implementation-ready.
- **Reference schema alignment**: Frontmatter uses the standard `DESIGN.md` token groups (`colors`, `typography`, `rounded`, `spacing`, `components`) rather than a plugin-specific substitute.
- **Design rationale**: Markdown explains when, why, and how to use tokens and components.
- **Coverage**: Colors, typography, layout, elevation, shapes, components, states, accessibility, and Do/Don't rules are covered.
- **Alignment**: Tokens and component rules map to Tailwind/CSS/theme/component implementation.
- **Decision safety**: Missing or conflicting rules are marked as open decisions, not invented silently.

Read `references/design-md-guide.md` for detailed section, token, component, accessibility, and patch guidance.

## Quality bar

A good `DESIGN.md` should answer:

- What does this product feel like?
- What are the semantic color roles and state colors?
- What typography hierarchy should agents use?
- What layout rhythm and density are expected?
- What shapes, shadows, and elevation patterns are allowed?
- Which components exist, what variants are allowed, and what states must be implemented?
- What must agents avoid?
- How do design tokens map to code?

## Common weaknesses

- Token names are raw (`blue500`) but never semantic (`primary`, `surface`, `danger`).
- Typography section lists fonts but not hierarchy or use cases.
- Component section lists components but omits states.
- Do/Don’t rules are vague, such as “make it clean.”
- Accessibility expectations are absent.
- Tokens in the body do not match frontmatter.
- Implementation theme and design contract drift apart.
- The file describes a screenshot but not reusable system rules.

## Output format

### Review mode (default when file exists)

~~~markdown
# DESIGN.md Review

## Summary
<Completeness, implementation readiness, and biggest risks.>

## Findings

### [severity] <issue title>
- Evidence:
- Observed:
- Expected:
- Impact on agents/implementation:
- Recommended edit:
- Verification:

## Proposed DESIGN.md Patch

```markdown
<concrete patch or section text>
```

## Open Design Decisions
- [ ] <decision needed>
~~~

### Author mode (only when no DESIGN.md exists or user explicitly asks to create)

Write or output a complete `DESIGN.md` document with:

- standard frontmatter (`version`, `name`, `description`, `colors`, `typography`, `rounded`, `spacing`, `components`)
- substantial token entries, not a tiny summary
- component token maps with state variants as related component keys
- standard markdown sections in the expected order
- `Known Gaps` for unresolved or low-confidence design decisions

When the user asked to write/generate/create/save the file, write it to disk and report the path plus verification results.

## Trigger tests

This Skill should trigger for:

- “帮我检查 DESIGN.md 写得够不够。”
- “给这个项目补一个 DESIGN.md。”
- “DESIGN.md token 和 Tailwind 有没有对齐？”
- “用 design.md lint 结果给我修复建议。”

It should hand off to `design-system-capture` when the design contract must be inferred from existing UI evidence.

## Detailed reference

Read `references/design-md-guide.md` when you need detailed `DESIGN.md` section checks, token quality rules, rationale guidance, accessibility contract guidance, implementation alignment checks, and patch style.

## Version history

- v0.4.0: Moved `audit-design-md.mjs` into Skill-local `scripts/` and updated automation paths.
- v0.3.0: Moved detailed review guides into Skill-local `references/*-guide.md` files and added an inline core review criteria for progressive disclosure.
- v0.2.0: Added design contract quality bar, implementation alignment workflow, concrete patch guidance, and trigger boundaries.
- v0.1.0: Initial DESIGN.md review workflow.
