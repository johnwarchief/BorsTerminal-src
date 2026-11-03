# Design Debt Guide

Use this guide to identify and prioritize visual implementation debt.

## Definition

Design debt is visual or structural implementation that increases drift, inconsistency, or maintenance cost. It may look acceptable today but makes future UI changes less predictable.

## Signals

- hard-coded hex/rgb/hsl colors
- arbitrary Tailwind values like `w-[437px]`, `text-[13px]`, `bg-[#123456]`
- inline styles in feature code
- hard-coded px spacing outside primitives
- custom shadows, gradients, radii, opacity, or transitions outside tokens
- typography values outside the scale
- repeated button/card/input/table implementations
- component variants hidden inside pages
- non-token CSS variables
- duplicated semantic colors
- local dark-mode or theme overrides inconsistent with system rules

## Context classification

Raw values may be acceptable in:

- token/theme definition files
- component primitive implementation
- CSS reset/base styles
- chart/map/canvas/media geometry
- third-party integration wrappers
- documented exceptions

Raw values are suspicious in:

- feature pages
- generated UI
- duplicated local components
- business-flow forms
- release-critical routes

## Categories

Use consistent categories:

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

## Severity

### Blocker

Debt creates immediate user-facing breakage, theming failure, or accessibility failure in a critical path.

### Major

Repeated drift across files, visible token violation, dark-mode/theming risk, or duplicated component pattern likely to spread.

### Minor

Isolated one-off value with clear local impact and easy fix.

### Debt

Maintainability concern where current UI may pass visually but future changes are risky.

### Info

Acceptable exception or cleanup candidate.

## Fix pattern

1. Identify whether an existing token/component should be used.
2. Replace the one-off value or implementation.
3. If no token exists, add a semantic token only when intentional and reusable.
4. If no component variant exists, add the variant centrally.
5. Document necessary exceptions.
6. Add lint/test/codemod protection for recurring patterns.

## Anti-patterns

Do not:

- create token aliases for accidental one-off values
- flatten meaningful product-specific variation into generic tokens
- replace local code with a shared component that lacks required accessibility/state behavior
- ignore source-of-truth conflicts between Figma, `DESIGN.md`, and implementation
- report raw values in token files as debt without context

## Batch cleanup strategy

Prioritize by:

1. critical path visibility
2. spread across files/components
3. risk to theming/accessibility/responsive behavior
4. ease of mapping to existing token/component
5. likelihood of recurring in generated UI
