---
name: design-qa
description: Orchestrates frontend Design QA against DESIGN.md, SCREEN_SPEC.md, Figma/reference images, screenshots, component-library rules, accessibility expectations, and design-debt reports. Use when the user asks whether a UI implementation matches design intent, design system, prototype, visual QA requirements, or design acceptance criteria.
---

# Design QA

## Skill contract

Design QA turns design intent into verifiable implementation evidence. Use it to decide whether a frontend screen, PR, or generated UI is ready for designer approval.

This Skill coordinates the other design Skills rather than replacing them:

- `design-md-review` checks the global design contract.
- `visual-regression-review` checks screenshot regression or conformance evidence.
- `ui-alignment-review` turns image diff, DOM anchors/selectors, computed styles, and component evidence into designer/frontend alignment findings.
- `accessibility-review` checks accessibility evidence and manual a11y risks.
- `component-library-alignment` checks whether implementation uses the intended components.
- `design-debt-review` checks maintainability and token drift.
- `design-system-capture` creates or updates the design system when no reliable contract exists.

Treat every conclusion as evidence-based. Prefer concrete screenshots, JSON reports, selectors, source files, token names, and component names over generic visual opinions.

A Design QA verdict requires both sides of the comparison:

- **Source truth**: `DESIGN.md`, `SCREEN_SPEC.md`, approved Figma frame, baseline screenshot, prototype image, design-system docs, or another named design target.
- **Rendered implementation**: local/deployed URL, browser screenshot, Storybook screenshot, component render, or implementation screenshot for the same state.

If either side cannot be opened, rendered, captured, or matched to the same viewport/state/content, report `Inconclusive` or `Fail` with the blocker. Do not pass QA from code paths, memory, or prose alone.

## Use when

Use this Skill when the user asks to:

- review a UI, page, component, PR, or generated frontend against a design
- compare implementation with `DESIGN.md`, `SCREEN_SPEC.md`, a Figma frame, a prototype image, or a reference screenshot
- produce designer-facing QA feedback with severity and fixes
- decide whether visual differences are acceptable or blocking
- combine visual diff, accessibility, component, token, and design-debt signals into one verdict
- turn design feedback into implementation tasks or patches

## Do not use when

Do not use this Skill as the primary Skill when:

- the user only wants to create or update `DESIGN.md`; use `design-md-review` or `design-system-capture`
- the user wants designer/frontend UI alignment for a specific screen; use `ui-alignment-review`
- the user only wants raw screenshot comparison; use `visual-regression-review`
- the user only wants WCAG/a11y review; use `accessibility-review`
- the user only wants style debt cleanup; use `design-debt-review`
- the user wants a broad UX/product-flow audit without a source visual target and rendered implementation; keep that out of Design QA or first capture the missing evidence
- there is no implementation evidence and the request is purely exploratory design direction; first ask for or infer design context, then use `design-system-capture` if needed

## Evidence hierarchy

Use the strongest available evidence first:

1. Product-approved `DESIGN.md`, design tokens, component-library docs, and `SCREEN_SPEC.md`
2. Approved Figma frame, exported prototype image, or approved baseline screenshot
3. Deterministic automation reports in `.design-qa/reports/*.json`
4. Actual screenshots in `.design-qa/actual/` and diff images in `.design-qa/diff/`
5. Source code, Storybook stories, CSS/Tailwind/theme configuration, and DOM/computed-style evidence
6. Human screenshots or textual feedback from the user
7. Inference from conventions, clearly labeled as inference

Do not claim design approval from visual intuition alone.

## Core review criteria

Before reading detailed guides, apply these lightweight review criteria:

- **Contract**: Does the UI follow `DESIGN.md`, `SCREEN_SPEC.md`, and approved token/component rules?
- **Visual**: Does the screenshot match the approved reference closely enough for design acceptance after masking expected dynamic content?
- **Alignment**: Are mismatches classified as implementation deviation, design ambiguity, spec mismatch, fixture noise, or intentional change?
- **Components**: Does implementation reuse shared components and variants instead of one-off feature styles?
- **Responsive**: Do configured viewports preserve hierarchy, grouping, readability, and primary actions?
- **States**: Are default, hover, focus-visible, active, disabled, loading, empty, error, and success/warning states covered where relevant?
- **Accessibility**: Can keyboard, screen-reader, low-vision, reduced-motion, and touch users complete the primary path?
- **Debt**: Are hard-coded values, arbitrary Tailwind classes, inline styles, duplicated patterns, or token drift likely to spread?

Use `blocker`, `major`, `minor`, `debt`, `info`, and `needs-design-decision` consistently. Read `references/review-guide.md` only when deeper scoring detail is needed.

## Required fidelity surfaces

Every Design QA report must explicitly check these surfaces, even when the user only asks for a general verdict:

- **Fonts and typography**: family/fallback, weight, size, line height, wrapping, truncation, hierarchy, display/body balance, and text density.
- **Spacing and layout rhythm**: viewport/frame match, crop, alignment, margins, padding, section gaps, component gaps, radii, shadows, surfaces, and vertical rhythm.
- **Colors and tokens**: palette, semantic roles, contrast, opacity, shadows, gradients, state colors, and whether implementation values map to approved tokens.
- **Image and asset fidelity**: source asset presence, subject match, crop, scale, sharpness, aspect ratio, icon style, logo treatment, transparency, masking, and whether real assets were replaced with CSS/SVG approximations.
- **Copy and content**: app-specific text, labels, CTAs, state copy, truncation, and whether placeholder or prompt-like text leaks into the UI.

When the full screenshot is too small to judge one of these surfaces, capture or inspect a focused region. If focused inspection is unnecessary, say why.

## Required inputs

Look for these files in the project root first:

- `DESIGN.md`
- `SCREEN_SPEC.md`
- `design.qa.yaml`
- `.design-qa/DESIGN_QA_REPORT.md`
- `.design-qa/reports/*.json`
- `.design-qa/expected/*.png`
- `.design-qa/actual/*.png`
- `.design-qa/diff/*.png`
- component library files and theme files
- app routes, preview URL, or local app start command

If key inputs are missing, continue with partial evidence and state exactly what is missing.

## Automation path discovery

When deterministic automation is useful, locate the plugin runtime root in this order:

1. `$DESIGN_PLUGIN_ROOT`
2. `.qoder/design-plugin`
3. the current plugin checkout root

The orchestrator script lives in `skills/design-qa/scripts/` and calls sibling Skill scripts from their own `scripts/` directories.

Preferred full pipeline:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin} \
node "$DESIGN_PLUGIN_ROOT/skills/design-qa/scripts/run-design-qa.mjs" --config design.qa.yaml
```

If automation is unavailable, perform a manual Design QA using the same evidence model and output format.

## Main workflow

1. **Clarify scope without blocking**
   - Determine whether the review targets a screen, route, component, PR, screenshot pair, or entire app.
   - Infer the target from changed files, `design.qa.yaml`, or user-provided artifacts when possible.
   - Avoid delaying the review for missing optional inputs; report gaps instead.

2. **Read the design contract**
   - Extract brand/product personality, semantic color roles, typography scale, spacing rhythm, elevation, shapes, component rules, and Do/Don't constraints from `DESIGN.md`.
   - Extract page-level layout, state, empty/error/loading behavior, copy constraints, and responsive expectations from `SCREEN_SPEC.md`.

3. **Collect implementation evidence**
   - Read app source, component usage, styles, theme config, Storybook stories, and prior reports.
   - Prefer existing `.design-qa` artifacts before rerunning expensive checks.
   - Open or capture the rendered implementation before making a visual verdict.
   - Put source visual evidence and implementation evidence into the same comparison context when judging visual fidelity; separate image views are not enough for a final QA verdict.

4. **Run deterministic checks when appropriate**
   - `run-design-qa.mjs` for the whole pipeline.
   - `audit-design-md.mjs` for `DESIGN.md` and token contract checks.
   - `export-figma-frame.mjs`, `capture-ui-screenshot.mjs`, and `compare-images.mjs` for raw visual evidence.
   - `audit-ui-alignment.mjs` for designer/frontend UI-to-design alignment evidence.
   - `audit-a11y.mjs` for accessibility evidence.
   - `audit-components.mjs` for component alignment.
   - `audit-design-debt.mjs` for hard-coded style and token drift evidence.

5. **Interpret evidence by design impact**
   - Group raw findings into user-visible design problems.
   - Explain likely cause only when evidence supports it.
   - Separate true design failures from acceptable noise such as masked dynamic content, browser font rendering, or intentional product-data differences.
   - Classify gaps across the required fidelity surfaces: typography, spacing/layout, colors/tokens, image/assets, copy/content, responsiveness, states, and accessibility.

6. **Assign severity**
   - `blocker`: prevents design approval, breaks the primary flow, violates accessibility in a high-impact path, misses a required element/state, or creates a large visual conformance failure.
   - `major`: visible deviation, token violation, component-system bypass, responsive breakage, or missing important state.
   - `minor`: small polish issue that does not undermine comprehension or flow completion.
   - `debt`: maintainability or consistency risk, even if current UI looks acceptable.
   - `info`: limitation, acceptable difference, or useful context.

7. **Recommend fixes**
   - Prefer existing tokens and component variants.
   - Prefer fixing primitives over page-level overrides.
   - Do not introduce one-off colors, spacing, shadows, or typography values unless explicitly required by the design contract.
   - Preserve keyboard, focus, loading, disabled, empty, and error states.
   - Add or update visual snapshots, Storybook stories, or regression tests for important changes.

8. **Produce a designer-facing report**
   - Include verdict, evidence, affected screens/files, impact, fix, and verification.
   - Keep screenshots/diff artifacts linked or listed.
   - Call out what automation could not verify.

## Patch policy

When the user asks you to modify code:

- inspect the existing component system before changing feature code
- replace raw or local UI with design-system components when available
- map hard-coded values to semantic tokens
- preserve existing behavior and tests
- update snapshots only after explaining why the visual change is intentional
- do not “fix” by widening thresholds or masking real deviations

## Output format

Use this format unless the user requests another one:

```markdown
# Design QA Verdict: <Pass | Pass with warnings | Fail | Inconclusive>

## Summary
<2-5 sentences explaining the decision and evidence quality.>

## Evidence Reviewed
- Design contract:
- Source visual truth:
- Rendered implementation:
- Viewport/state/content match:
- Screens/routes:
- Automation reports:
- Screenshots/diffs:
- Source files/components:

## Blockers

### <finding title>
- Severity: blocker
- Evidence:
- Observed:
- Expected:
- User/design impact:
- Recommended fix:
- Verification:

## Major Issues

## Minor Issues

## Design Debt

## Acceptable Differences

## Automation Artifacts
- Expected screenshots:
- Actual screenshots:
- Diff screenshots:
- JSON reports:

## Verification Checklist
- [ ] Re-run visual comparison at configured viewports
- [ ] Re-run accessibility scan
- [ ] Confirm typography, spacing/layout, colors/tokens, image/assets, and copy/content were checked
- [ ] Confirm component states: default, hover, focus-visible, active, disabled, loading, error, empty
- [ ] Confirm no new hard-coded styles or arbitrary token bypasses
- [ ] Confirm design owner accepts intentional differences
```

## Trigger tests

A well-written installation of this Skill should trigger for prompts like:

- “帮我 review 这个页面有没有按设计稿实现。”
- “用 Figma 图和当前 UI 做 Design QA。”
- “这个 PR 会不会破坏设计系统？”
- “跑一下视觉比对、a11y、组件和设计债，然后给我结论。”

It should not be the only Skill triggered for prompts like:

- “帮我写一个新的 DESIGN.md。” Use `design-md-review` or `design-system-capture`.
- “只比较两张截图。” Use `visual-regression-review`.

## Detailed references

Read local references only when deeper detail is needed:

- `references/review-guide.md` for seven-dimension Design QA scoring, evidence priority, severity, and handoff rules.
- `references/finding-format.md` for designer-facing report and ticket-ready finding structure.
- `references/automation-guide.md` for script usage, artifacts, CI guidance, and interpretation limits.

For specialized review depth, read sibling Skill guides:

- `../ui-alignment-review/references/ui-alignment-guide.md`
- `../ui-alignment-review/references/implementation-handoff-guide.md`
- `../visual-regression-review/references/visual-comparison-guide.md`
- `../accessibility-review/references/accessibility-review-guide.md`
- `../component-library-alignment/references/component-alignment-guide.md`
- `../design-debt-review/references/design-debt-guide.md`
- `../design-md-review/references/design-md-guide.md`
- `../design-system-capture/references/capture-guide.md`

## Version history

- v0.5.0: Added `ui-alignment-review` as the designer/frontend alignment layer and included UI alignment evidence in the full pipeline.
- v0.4.0: Moved orchestration/report scripts into Skill-local `scripts/` and updated the pipeline to call sibling Skill scripts.
- v0.3.0: Moved detailed review guides into Skill-local `references/*-guide.md` files and added an inline core review criteria for progressive disclosure.
- v0.2.0: Expanded trigger rules, evidence hierarchy, automation discovery, severity policy, patch policy, and output contract.
- v0.1.0: Initial Design QA workflow.
