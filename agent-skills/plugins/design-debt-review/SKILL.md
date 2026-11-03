---
name: design-debt-review
description: Finds frontend design debt such as hard-coded colors, arbitrary Tailwind values, inline styles, px magic numbers, duplicated component patterns, non-token shadows, non-semantic variants, typography drift, and design-system drift. Use when auditing visual maintainability, cleaning AI-generated UI code, or preventing token/component erosion.
---

# Design Debt Review

## Skill contract

Design debt is visual or structural implementation that may look acceptable today but makes the design system harder to maintain tomorrow. This Skill finds, explains, and prioritizes that debt.

Do not treat every raw value as automatically wrong. Classify whether it is intentional, tokenizable, component-local, layout-specific, or accidental drift.

## Use when

Use this Skill when the user asks to:

- find hard-coded colors, spacing, shadows, radii, font sizes, or inline styles
- clean AI-generated Tailwind/CSS/UI code
- detect arbitrary Tailwind values such as `w-[437px]`, `text-[13px]`, or `bg-[#123456]`
- identify repeated button/card/form/table patterns that should become components or variants
- measure design-system drift or token adoption
- propose stylelint/eslint/codemod rules to prevent recurring visual debt

## Do not use when

Do not use this Skill as the primary Skill when:

- the user asks for full Design QA verdict; use `design-qa`
- the user asks for component usage only; use `component-library-alignment`
- the user asks for visual diff only; use `visual-regression-review`
- the user asks to author a design system from product evidence; use `design-system-capture`

## Inputs

Look for:

- `DESIGN.md`
- `design.qa.yaml`, especially `code.include`, `code.exclude`, and token/debt settings
- Tailwind config, CSS variables, theme files, style dictionary, design token files
- component library source
- app/page/feature source files
- `.design-qa/reports/design-debt.json`
- `.design-qa/reports/component-alignment.json`

## Automation path discovery

Locate this Skill's automation script in this order:

1. `$DESIGN_PLUGIN_ROOT/skills/design-debt-review/scripts`
2. `.qoder/design-plugin/skills/design-debt-review/scripts`
3. `skills/design-debt-review/scripts` in the current plugin checkout

Run:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
node "$DESIGN_PLUGIN_ROOT/skills/design-debt-review/scripts/audit-design-debt.mjs" --config design.qa.yaml
```

Then inspect:

```text
.design-qa/reports/design-debt.json
```

If automation is unavailable, manually scan representative files and report coverage limits.

## Review workflow

1. **Establish token contract**
   - Read `DESIGN.md`, Tailwind/theme config, CSS variables, and component primitives.
   - Identify semantic tokens for color, typography, spacing, radius, elevation, z-index, and motion.

2. **Scan raw values**
   - Hard-coded hex/rgb/hsl colors.
   - Arbitrary Tailwind values.
   - Inline styles in feature code.
   - `px` magic numbers for spacing, sizes, line heights, and border radius.
   - Custom shadows, gradients, opacity, or transitions outside tokens.

3. **Classify context**
   - Component primitive implementation may legitimately contain raw token definitions.
   - Theme/token files may legitimately contain raw values.
   - Feature/page code should usually reference tokens or component variants.
   - One-off geometry can be acceptable for canvas, charts, maps, or media crops if documented.

4. **Detect semantic drift**
   - Similar colors used for the same semantic role.
   - Different border radii for same component type.
   - Multiple button styles with same purpose.
   - Typography values not in the scale.
   - Repeated spacing combinations that imply missing layout component or variant.

5. **Prioritize debt**
   - Spread: how many files/components use it?
   - Visibility: does it affect primary UI or internal/admin-only UI?
   - Risk: could it bypass accessibility, theming, dark mode, responsive behavior, or brand consistency?
   - Fixability: can it map cleanly to an existing token/component?

6. **Recommend prevention**
   - Lint rule, stylelint/eslint rule, Tailwind theme configuration, codemod, snapshot, Storybook story, or component variant.

## Core review criteria

Classify design debt by context before recommending cleanup:

- **Location**: token/theme/component primitive vs feature/page/generated UI.
- **Value type**: color, spacing, typography, radius, shadow, motion, layout, component clone, or variant.
- **Visibility**: primary user path, secondary screen, internal/admin-only, or hidden implementation.
- **Spread**: isolated, repeated in one area, repeated across system, or likely to be copied.
- **Fixability**: existing token/component exists, new variant needed, new token needed, or documented exception.

Do not turn every raw value into a token. Read `references/design-debt-guide.md` for categories, exceptions, and batch cleanup strategy.

## Debt categories

Use these categories consistently:

- `hard-coded-color`
- `arbitrary-tailwind`
- `inline-style`
- `magic-number`
- `non-token-shadow`
- `non-token-radius`
- `typography-drift`
- `duplicate-component-pattern`
- `mixed-library-style`
- `undocumented-exception`

## Severity rules

- `blocker`: debt creates immediate user-facing breakage, theming failure, or accessibility failure in a critical path.
- `major`: repeated drift across files, visible token violation, dark-mode/theming risk, or duplicated component pattern.
- `minor`: isolated one-off value with clear local impact and easy fix.
- `debt`: maintainability concern where current UI may pass visually but future changes are risky.
- `info`: acceptable exception or candidate for future cleanup.

## Fix strategy

Prefer this order:

1. Replace with existing semantic token.
2. Replace with existing component prop/variant.
3. Add missing variant to shared component.
4. Add a new token only when the value is intentional, reusable, and named semantically.
5. Document an exception when raw value is necessary.
6. Add lint/test/codemod protection for recurring patterns.

Avoid creating token aliases for accidental values. Do not normalize every value if it would erase meaningful product-specific variation.

## Output format

```markdown
# Design Debt Review

## Summary
- Hard-coded colors:
- Arbitrary Tailwind values:
- Inline styles:
- Non-token typography/radius/shadow:
- Duplicate component patterns:
- Highest-risk files/components:

## Findings

### [severity] <debt category>: <title>
- Evidence:
- Affected files/components:
- Observed:
- Expected token/component:
- Risk:
- Recommended fix:
- Prevention:
- Verification:

## Suggested Batch Fixes

## Acceptable Exceptions
```

## Trigger tests

This Skill should trigger for:

- “查一下设计债。”
- “AI 生成的 Tailwind 里有没有 hard-coded 样式？”
- “把这些 arbitrary values 变成 tokens/variants。”
- “找重复的按钮/卡片/表单样式。”

It should hand off to `component-library-alignment` for component bypass analysis and `design-qa` for full verdict reporting.

## Detailed reference

Read `references/design-debt-guide.md` when you need detailed debt signals, context classification, categories, severity examples, exceptions, and batch cleanup strategy.

## Version history

- v0.4.0: Moved `audit-design-debt.mjs` into Skill-local `scripts/` and updated automation paths.
- v0.3.0: Moved detailed review guides into Skill-local `references/*-guide.md` files and added an inline core review criteria for progressive disclosure.
- v0.2.0: Added debt classification, context rules, prioritization, prevention strategy, and severity policy.
- v0.1.0: Initial design debt workflow.
