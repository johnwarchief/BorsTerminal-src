# Design QA Review Guide

Use this guide when a Design QA task needs more detail than the core rules in `SKILL.md`.

## Scope

Design QA answers one release question: **does this implementation respect the approved design intent well enough for designer acceptance?**

It combines seven dimensions:

1. `DESIGN.md` conformance
2. Visual conformance or regression
3. Component-library consistency
4. Responsive behavior
5. Interaction state coverage
6. Accessibility
7. Design debt and drift risk

Do not score visual taste in isolation. Tie each finding to an approved contract, reference image, component rule, accessibility expectation, code evidence, or clearly labeled inference.

Do not complete a QA verdict from implementation code, file paths, or memory alone. A release-facing QA verdict needs a source truth and a rendered implementation for the same state, viewport, theme, and content. If those cannot be matched, report the blocker before interpreting visual differences.

## Evidence priority

Use this order when evidence conflicts:

1. Current designer-approved system documentation: `DESIGN.md`, component docs, Figma variables, token files.
2. Current screen-level specification: `SCREEN_SPEC.md`, product acceptance criteria, user-provided design notes.
3. Approved reference image: Figma export, prototype screenshot, approved baseline.
4. Deterministic automation: screenshot diff JSON, axe report, component audit, design-debt audit.
5. Implementation source: component imports, CSS/Tailwind/theme config, Storybook stories, tests.
6. Rendered screenshot or user screenshot.
7. Inference from product conventions, marked as inference.

When the reference image is older than the code or product spec, do not assume it is authoritative. Mark the issue as `needs-design-decision`.

## Seven review dimensions

### 1. DESIGN.md conformance

Check whether the implementation follows the design contract:

- semantic color tokens instead of arbitrary raw values
- typography hierarchy and use cases
- spacing rhythm and density
- approved radii, shadows, elevation, and surfaces
- component usage rules
- state color and semantic color rules
- Do/Don't constraints

Report a `major` or `blocker` when a deviation changes hierarchy, brand expression, accessibility, or a critical component state.

### 2. Visual conformance or regression

Check whether the rendered UI matches the approved design evidence:

- major layout position and size
- page hierarchy and CTA emphasis
- grouping, alignment, spacing, density, and anchor-level UI alignment
- font size, weight, line-height, and wrapping
- color, contrast, surface, border, and shadow
- image crop, icon size, and asset choice
- responsive layout at configured viewports

Use pixel diff as a detector, not as the final verdict. A tiny diff on a primary CTA can be more important than a large diff in a masked decorative image.

Every visual conformance pass must explicitly inspect:

- typography and fonts
- spacing and layout rhythm
- colors and token mapping
- image, icon, logo, and asset fidelity
- copy and app-specific content

Use focused region inspection when the full-view screenshot is not readable enough to judge these surfaces.

### 3. Component-library consistency

Check whether the implementation uses shared components and variants:

- common UI primitives imported from the project design system
- raw elements limited to primitive implementation zones or justified exceptions
- variants defined centrally, not encoded ad hoc in feature code
- states supported by components, not patched locally
- Storybook/tests cover important variants and states

### 4. Responsive behavior

Check configured viewport sizes:

- mobile
- tablet
- desktop
- wide desktop, when relevant

Look for overflow, clipped content, hidden CTAs, awkward wrapping, excessive density, lost hierarchy, broken fixed positioning, and scroll traps.

### 5. Interaction state coverage

Check at least:

- default
- hover
- focus-visible
- active/pressed
- disabled
- loading
- empty
- error
- success/warning, where relevant
- selected/expanded/collapsed, where relevant

Missing focus-visible, disabled, loading, and error states are often design QA issues even when the default screenshot looks correct.

### 6. Accessibility

Review automated violations and manual risks:

- contrast
- visible focus
- keyboard reachability
- accessible names
- form labels and error associations
- semantic headings and landmarks
- alt text and non-text content
- reduced motion
- touch target size and spacing

Accessibility issues in the primary path are design approval issues, not just engineering bugs.

### 7. Design debt

Check maintainability risks:

- hard-coded colors
- arbitrary Tailwind values
- inline styles in feature code
- non-token CSS variables
- custom shadows/radii/typography outside tokens
- component bypasses
- repeated visual patterns
- unapproved variants

Treat debt as `major` when it is repeated, visible, or likely to spread through generated UI.

## Severity guide

### Blocker

Use `blocker` when the issue prevents design approval or safe release:

- primary flow visually or functionally broken
- required element/state missing in a critical path
- large visual conformance failure in the approved reference area
- accessibility barrier in the primary path
- responsive layout hides or breaks a primary action
- design-system bypass causes inconsistent behavior or state failure in a release-critical surface

### Major

Use `major` when the issue is visible, repeated, or undermines the system:

- obvious spacing, typography, color, component, or hierarchy mismatch
- repeated token/component bypass
- missing important state
- a11y issue affecting common use
- responsive issue with workaround but real user impact
- drift that will likely spread

### Minor

Use `minor` for localized polish issues:

- small alignment or spacing mismatch
- slight typography or icon positioning issue
- localized copy or truncation concern with low flow impact
- single non-critical state polish issue

### Debt

Use `debt` when the current UI may look acceptable, but implementation increases drift risk:

- hard-coded value that should become a token
- local variant that should be centralized
- repeated classes suggesting a missing primitive
- inconsistent token names or duplicated semantic colors

### Info / Needs Design Decision

Use `info` for context, limitations, or acceptable differences.

Use `needs-design-decision` when evidence conflicts or the design contract does not define the expected behavior.

## Avoiding overreach

Do not:

- fail a screen only because the raw diff percentage is high
- pass a screen only because the raw diff percentage is low
- call a reference authoritative when it may be stale
- mask real layout problems to make a test pass
- invent tokens or component variants without design evidence
- turn every px value into a token without considering context
- claim screen-reader quality from axe output alone
- accept custom CSS art, handmade SVG substitutes, placeholder avatars, or fake product imagery when the source design requires real assets or a specific visual treatment
- collapse a broad product-flow audit into Design QA when no source visual target exists

## Handoff rules

Use sibling guides when depth is needed:

- `../ui-alignment-review/references/ui-alignment-guide.md`
- `../visual-regression-review/references/visual-comparison-guide.md`
- `../accessibility-review/references/accessibility-review-guide.md`
- `../component-library-alignment/references/component-alignment-guide.md`
- `../design-debt-review/references/design-debt-guide.md`
- `../design-md-review/references/design-md-guide.md`
- `../design-system-capture/references/capture-guide.md`
