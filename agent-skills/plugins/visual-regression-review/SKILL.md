---
name: visual-regression-review
description: Compares UI screenshots against approved baselines, Figma exports, prototype images, or reference screenshots. Use for visual regression testing, design conformance review, screenshot diff analysis, UI-to-design comparison, PR visual review, threshold tuning, masks, and explaining meaningful visual differences.
---

# Visual Regression Review

## Skill contract

Use screenshot evidence to find meaningful visual differences. This Skill supports two related but different workflows:

- **Regression mode**: current UI screenshot vs previously approved UI baseline.
- **Conformance mode**: current UI screenshot vs Figma export, prototype image, or design reference.

Do not equate “1:1 comparison” with “0 changed pixels.” The goal is design confidence: detect meaningful differences, filter expected noise, and explain what should be fixed.

For conformance mode, a useful comparison needs both an approved source image and a rendered implementation image for the same state. If either side is missing, stale, cropped incorrectly, loading, blocked, or captured at the wrong viewport, report that setup problem before interpreting visual differences.

## Use when

Use this Skill when the user asks to:

- compare current UI screenshots with baseline screenshots
- compare implementation with Figma, prototype, or reference images
- review visual changes in a PR
- decide whether screenshot diffs are acceptable
- create or tune masks, thresholds, viewport settings, or screenshot capture protocol
- provide raw visual evidence for `ui-alignment-review`

## Do not use when

Do not use this Skill as the primary Skill when:

- the user asks for designer/frontend UI alignment findings and owners; use `ui-alignment-review`
- the user asks for overall Design QA across code, a11y, components, and debt; use `design-qa`
- the user asks to author the design system; use `design-md-review` or `design-system-capture`
- the user asks only for accessibility; use `accessibility-review`
- the user wants subjective visual exploration without an implementation screenshot or reference image

## Inputs

Look for:

- `design.qa.yaml`
- `.design-qa/reports/visual-comparison.json`
- `.design-qa/expected/*.png`
- `.design-qa/actual/*.png`
- `.design-qa/diff/*.png`
- Figma file key and node ID, or a Figma URL that can be parsed
- app route, preview URL, or local base URL
- viewport width/height and device scale factor
- masks for dynamic content
- threshold settings
- notes about frozen data/time, fonts, animations, and environment

## Mode selection

Choose mode from `design.qa.yaml` when present.

Use **regression mode** when the expected image is a previously approved app screenshot.

Use **conformance mode** when the expected image comes from a designer-owned source such as Figma, exported prototype, mockup, or handoff screenshot.

If the expected image source is unclear, mark the mode as `unknown` and state that approval confidence is limited.

## Automation path discovery

Locate this Skill's automation script in this order:

1. `$DESIGN_PLUGIN_ROOT/skills/visual-regression-review/scripts`
2. `.qoder/design-plugin/skills/visual-regression-review/scripts`
3. `skills/visual-regression-review/scripts` in the current plugin checkout

Typical commands:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
node "$DESIGN_PLUGIN_ROOT/skills/visual-regression-review/scripts/export-figma-frame.mjs" --config design.qa.yaml
node "$DESIGN_PLUGIN_ROOT/skills/visual-regression-review/scripts/capture-ui-screenshot.mjs" --config design.qa.yaml
node "$DESIGN_PLUGIN_ROOT/skills/visual-regression-review/scripts/compare-images.mjs" --config design.qa.yaml
```

If Figma export is unavailable, allow manually supplied expected images under `.design-qa/expected/`.

## Comparison protocol

1. **Validate reference authority**
   - Confirm expected image is approved and current.
   - Confirm the Figma node or reference screenshot matches the target screen state.
   - Confirm the reference is not an obsolete mockup or stale baseline.

2. **Normalize environment**
   - Use consistent viewport and device scale factor.
   - Load the same fonts or document font fallback differences.
   - Disable animations and hide carets.
   - Freeze time and deterministic test data where possible.
   - Wait for network idle or stable UI before capture.
   - Confirm the source and implementation represent the same route, content, state, theme, and responsive breakpoint.

3. **Mask dynamic regions**
   - Avatars, personalized names, timestamps, live metrics, ads, randomized illustrations, maps, charts with live data, and skeleton shimmer should usually be masked.
   - Do not mask layout-critical regions just to pass a comparison.

4. **Compare images**
   - Use pixel diff as a detector, not the final verdict.
   - Record diff pixels, diff ratio, image dimensions, threshold, and masks.
   - Save expected, actual, and diff images.

5. **Interpret by region**
   - Identify whether differences are layout, typography, color, spacing, asset, state, or data differences.
   - Explain the likely cause only when supported by code, DOM, or visual evidence.
   - Make focused checks for typography, spacing/layout rhythm, colors/tokens, image/icon/asset fidelity, and app-specific copy when those details are too small in the full-view diff.

6. **Decide severity**
   - Consider visual impact, affected user path, design contract, and whether the difference repeats across components or screens.

## Common false positives

Treat these carefully before filing a design bug:

- subpixel anti-aliasing or OS/browser font rendering differences
- minor line-wrapping caused by different real data length
- image compression differences
- dynamic content not masked
- scrollbars appearing in one environment but not another
- Figma effects that browsers render differently, especially blur, shadows, gradients, and blend modes
- real content exceeding mock data length

Document false positives as “acceptable difference” or “environment limitation,” not as passing evidence.

## Failure patterns to report

Report as findings when evidence shows:

- missing or extra visible element
- wrong hierarchy or CTA emphasis
- wrong color role or semantic state color
- layout shift, alignment error, overflow, or clipped content
- typography scale mismatch affecting readability
- spacing/density mismatch that changes perceived grouping
- incorrect asset, icon size, image crop, or aspect ratio
- custom CSS/SVG/art substitutes where the approved reference requires specific imagery, logos, icons, or generated/real visual assets
- app-specific copy drift, prompt leakage, placeholder text, or text wrapping/truncation that changes hierarchy
- unimplemented hover/focus/disabled/loading/error/empty state
- responsive layout that diverges at configured viewport

## Threshold guidance

Thresholds are guardrails, not design truth.

- Keep stricter thresholds for stable app-baseline regression.
- Allow more tolerance for Figma conformance when fonts, effects, or data differ.
- Prefer masks and deterministic data over simply raising thresholds.
- Any threshold change should explain what noise it addresses and why it does not hide a real issue.

## Core review criteria

Classify every visual difference before assigning severity:

- **Reference authority**: Is the expected image current and approved?
- **Mode**: Is this app-baseline regression or Figma/reference conformance?
- **Region impact**: Does the diff affect primary CTA, navigation, form, content, or only decorative/dynamic regions?
- **Difference type**: Layout, spacing, typography, color, asset, state, data, or rendering noise?
- **Mask/threshold quality**: Are dynamic regions masked without hiding real layout problems?
- **Fidelity surfaces**: Have typography, spacing/layout, colors/tokens, image/assets, and copy/content been inspected beyond the raw pixel ratio?
- **User/design impact**: Does the difference change comprehension, hierarchy, task completion, or brand consistency?

Use pixel diff as a detector, not the final verdict. Read `references/visual-comparison-guide.md` for detailed threshold, mask, and baseline policy.

## Finding format

```markdown
### [severity] <screen>: <visual issue>
- Mode: <regression | conformance>
- Expected image:
- Actual image:
- Diff image:
- Diff metric:
- Affected region:
- Observed:
- Expected:
- Likely cause:
- Recommended fix:
- Verification:
```

## Patch guidance

When fixing visual differences:

- prefer token and component fixes over local CSS overrides
- check responsive behavior after layout fixes
- preserve accessibility states and hit targets
- update baselines only when the new UI is intentionally approved
- never hide a real mismatch by adding broad masks or high thresholds

## Trigger tests

This Skill should trigger for:

- “把当前页面截图和 Figma 原型图做 1:1 比对。”
- “这个 diff.png 是不是视觉回归？”
- “帮我调 visual regression 的 masks 和 threshold。”
- “PR 改了 CSS，跑截图回归并解释差异。”

It should hand off to `ui-alignment-review` when the user asks for designer/frontend conformance against a Figma/reference image with actionable layout/style feedback, and to `design-qa` when the user asks for a full approval verdict across visual, a11y, component, and debt dimensions.

## Detailed reference

Read `references/visual-comparison-guide.md` when you need detailed guidance on screenshot modes, Figma conformance, masks, thresholds, false positives, diff interpretation, or baseline update policy.

## Version history

- v0.5.0: Clarified that raw screenshot evidence should be interpreted by `ui-alignment-review` for designer/frontend action items.
- v0.5.0: Clarified handoff to `ui-alignment-review` for designer/frontend design conformance.
- v0.4.0: Moved Figma export, screenshot capture, and image comparison scripts into Skill-local `scripts/`.
- v0.3.0: Moved detailed review guides into Skill-local `references/*-guide.md` files and added an inline core review criteria for progressive disclosure.
- v0.2.0: Added explicit regression/conformance modes, protocol, false-positive handling, threshold guidance, and finding format.
- v0.1.0: Initial screenshot comparison workflow.
