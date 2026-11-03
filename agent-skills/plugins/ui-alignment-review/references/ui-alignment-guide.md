# UI Alignment Guide

## Purpose

UI alignment review answers one practical question:

> Does the implemented UI match the approved design closely enough that a designer and frontend engineer can accept, fix, or intentionally document the differences?

It is narrower than full Design QA and richer than raw visual regression. It combines screenshot comparison, design reference mapping, component usage, token checks, DOM/computed-style evidence, and implementation recommendations.

## Terms

- **Reference**: the approved Figma frame, prototype image, baseline screenshot, or design owner screenshot.
- **Actual**: screenshot captured from the running app, Storybook story, preview deployment, or local route.
- **Conformance mode**: actual UI vs design reference.
- **Regression mode**: actual UI vs last approved implementation baseline.
- **Alignment target**: a specific selector or component that should be measured or checked, such as hero title, primary CTA, card, nav, or form field.
- **Acceptable difference**: a documented difference that is intentional, dynamic, data-driven, or approved by the design owner.

## Review protocol

### 1. Confirm the same state

Before comparing, confirm:

- same route or Storybook story
- same viewport width/height
- same device scale factor
- same theme/mode
- same locale
- same app state
- same data fixture
- same loading/error/empty state
- same authentication state
- same scroll position when not using full-page capture

A mismatch here is a setup issue before it is a design issue.

### 2. Normalize screenshot capture

Use this capture protocol where possible:

- run browser and baseline generation in the same environment
- freeze time and seed data
- disable animations/transitions
- hide caret
- use reduced motion
- set deterministic viewport and device scale factor
- wait for stable network/UI state
- mask only dynamic regions such as avatar photos, timestamps, ads, random charts, live metrics, and generated content
- avoid full-page screenshots when sticky headers/footers or lazy loading make the comparison noisy

### 3. Compare visual evidence

Start with expected/actual/diff images, then interpret by category:

- layout geometry
- spacing rhythm
- typography
- color/tokens
- image/icon/asset
- borders/radius/shadow/elevation
- component variants
- state behavior
- responsive behavior
- content/data differences
- screenshot setup issues
- browser/rendering noise

Do not use diff percentage alone. A 0.5% diff on a primary button color can be more important than a 5% diff inside a masked carousel image.

### 4. Use DOM and source evidence to explain causes

When a screenshot shows a mismatch, inspect:

- bounding boxes for key elements
- computed `font-size`, `line-height`, `font-weight`, `letter-spacing`, color, background, border radius, shadow, padding, margin, gap
- component imports and variants
- Tailwind arbitrary values
- inline styles
- CSS variables and token usage
- layout containers and breakpoint rules

The best finding says both what changed visually and where a developer can fix it.

## Alignment categories

### Layout geometry

Check:

- frame size and viewport parity
- max-width and container alignment
- grid columns and gutters
- card and section positions
- vertical rhythm
- sticky/fixed elements
- scroll and fold position
- grouping and visual hierarchy

Common causes:

- wrong container max-width
- missing wrapper
- unexpected padding/margin
- CSS reset differences
- image aspect ratio mismatch
- hidden/extra content
- full-page vs viewport capture mismatch

### Typography

Check:

- font family and fallback
- size
- weight
- line height
- letter spacing
- text transform
- wrapping
- truncation
- line clamp
- content density

Common causes:

- web font not loaded
- browser fallback font
- token mismatch
- component default differs from design
- translated or real content differs from design fixture

### Color and visual tokens

Check:

- semantic role, not just exact hex
- theme mode
- opacity
- border color
- background layers
- gradient direction/stops
- elevation/shadow
- radius
- disabled/hover/focus states

Common causes:

- raw hex values
- old token alias
- theme mode mismatch
- local override
- non-token arbitrary Tailwind value

### Component and variant alignment

Check:

- shared Button/Input/Card/Dialog/Table/Navigation primitives
- approved variants
- hover/focus/active/disabled/loading/error states
- icon placement and size
- label/help/error text slots
- spacing inside compound components

Common causes:

- raw HTML bypass
- local duplicate component
- missing variant in design system
- prop mapping mismatch from Figma to code
- Storybook story missing a state

### Responsive alignment

Check:

- content priority and order
- navigation collapse behavior
- form field stacking
- touch target size
- table/card transformation
- primary action visibility
- overflow and clipping
- safe area and sticky CTA behavior

Common causes:

- design frame only covers desktop
- route lacks mobile spec
- breakpoint mismatch
- dynamic content longer than design placeholder

## Severity guide

### Must fix / blocker

Use when:

- primary action missing, misplaced, or visually wrong
- required content/state missing
- layout breaks the primary flow
- navigation or form cannot be understood
- screenshot setup reveals actual implementation mismatch, not noise
- repeated mismatch indicates design system variant is wrong
- design owner could not reasonably approve the screen

### Should fix / major

Use when:

- visible spacing, typography, color, or layout mismatch affects perceived quality
- element hierarchy differs from the design
- component variant differs but the flow still works
- mobile/tablet layout is noticeably worse than design intent
- there is repeated token/component drift

### Polish / minor

Use when:

- small optical alignment issue
- slight icon or label positioning issue
- small text wrapping difference with low impact
- small spacing mismatch that does not affect hierarchy

### Acceptable difference / info

Use when:

- dynamic data differs and is intentionally masked or documented
- design used placeholder copy but implementation uses real content
- browser font rendering creates small antialiasing differences
- implementation has a documented technical constraint accepted by design
- screenshot capture cannot validate the issue

### Needs design decision

Use when:

- design reference and `DESIGN.md` disagree
- implementation has a reasonable alternative but no approval
- real content breaks the design placeholder and requires layout policy
- a component variant is needed but not defined
- baseline should potentially be updated after review

## Anti-patterns

Avoid:

- increasing `maxDiffPixelRatio` until the test passes
- masking whole sections to hide real mismatches
- updating baselines before design approval
- treating all browser-rendering differences as bugs
- treating diff percentage as design priority
- fixing feature code with one-off values when the design-system component is wrong
- ignoring mobile because the desktop diff passed
- reviewing a screen against the wrong Figma frame or state

## Good finding example

```markdown
### [major] Hero title line-height is too tight on desktop
- Category: typography
- Evidence: `.design-qa/diff/home-desktop.png`; selector `[data-testid="hero-title"]`
- Observed: computed `font-size: 48px`, `line-height: 52px`; title wraps 8px higher than reference.
- Expected: DESIGN.md display heading uses 48px / 56px.
- Likely cause: page-level class `leading-[52px]` overrides heading token.
- Recommended frontend fix: replace the arbitrary line-height with the display heading token or the shared `Heading` component variant.
- Verification: re-run `audit-ui-alignment.mjs` and inspect home-desktop diff.
```

## Bad finding example

```markdown
This page does not look the same.
```

The bad example is not actionable because it lacks category, evidence, expected value, likely cause, and verification.
