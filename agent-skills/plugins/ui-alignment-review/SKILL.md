---
name: ui-alignment-review
description: Reviews whether frontend UI implementation is aligned with an approved Figma frame, prototype screenshot, baseline image, DESIGN.md contract, and component system. Use for designer/frontend handoff, UI-to-design alignment, pixel-level evidence interpretation, spacing/typography/layout fixes, implementation acceptance, and ticket-ready alignment feedback.
---

# UI Alignment Review

## Skill contract

This Skill helps designers and frontend engineers align an implemented UI with an approved design reference. It sits between raw screenshot comparison and full Design QA:

- `visual-regression-review` produces screenshot diff evidence.
- `ui-alignment-review` turns that evidence into designer/frontend alignment findings and implementation tasks.
- `design-qa` combines UI alignment with accessibility, token, debt, and release approval signals.

Do not treat UI alignment as “0 changed pixels.” Treat it as an evidence-based acceptance workflow: match the intended layout, hierarchy, tokens, components, states, and responsive behavior while filtering expected noise.

An alignment verdict requires both an approved visual/reference target and a rendered implementation for the same viewport, state, theme, and content. Do not write alignment findings from code, paths, or memory alone. If either artifact is missing or cannot be captured, report an evidence issue instead of inventing a visual verdict.

## Use when

Use this Skill when the user asks to:

- compare a frontend route with a Figma frame, prototype image, mockup, or approved screenshot
- help a frontend developer make the UI look like the design
- produce designer-facing alignment feedback after implementation
- explain why a UI screenshot does not match the design image
- classify visual diffs into layout, spacing, typography, color, asset, component, responsive, state, or data differences
- create ticket-ready fixes for a designer/frontend handoff
- tune masks, viewport settings, screenshot protocol, or acceptance thresholds for UI conformance
- review whether a change is an acceptable implementation difference or needs designer approval

## Do not use when

Do not use this Skill as the primary Skill when:

- the user only wants raw pixel diff output; use `visual-regression-review`
- the user wants full release Design QA across a11y, debt, components, states, and docs; use `design-qa`
- the user only wants to check raw component-library adoption; use `component-library-alignment`
- the user only wants to find hard-coded token/style debt; use `design-debt-review`
- the user is exploring a new visual direction with no implementation to compare; use `design-system-capture` or `design-md-review`

## Evidence hierarchy

Use the strongest available evidence first:

1. Approved design reference: Figma frame, prototype image, approved baseline screenshot, or design owner screenshot
2. `DESIGN.md`, `SCREEN_SPEC.md`, design tokens, component docs, and Storybook stories
3. `design.qa.yaml` alignment protocol: route, viewport, device scale, masks, thresholds, expected reference, dynamic data policy
4. `.design-qa/reports/ui-alignment.json`, `visual-comparison.json`, `component-alignment.json`, and `design-debt.json`
5. `.design-qa/expected/*.png`, `.design-qa/actual/*.png`, `.design-qa/diff/*.png`
6. Source files, CSS/Tailwind/theme config, DOM/computed-style measurements, and component imports
7. User comments or inferred intent, clearly labeled as inference

Never claim a UI is design-approved from visual intuition alone.

## Inputs

Look for:

- `design.qa.yaml`
- `DESIGN.md`
- `SCREEN_SPEC.md`
- Figma file key/node ID or Figma frame URL
- reference screenshots under `.design-qa/expected/`
- actual screenshots under `.design-qa/actual/`
- diff images under `.design-qa/diff/`
- `.design-qa/reports/ui-alignment.json`
- `.design-qa/reports/visual-comparison.json`
- `.design-qa/reports/component-alignment.json`
- `.design-qa/reports/design-debt.json`
- app routes, preview URLs, Storybook URLs, or local app command
- changed files or PR context

If inputs are missing, continue with partial evidence and state the confidence level.

## Automation path discovery

Locate this Skill's automation script in this order:

1. `$DESIGN_PLUGIN_ROOT/skills/ui-alignment-review/scripts`
2. `.qoder/design-plugin/skills/ui-alignment-review/scripts`
3. `skills/ui-alignment-review/scripts` in the current plugin checkout

Run:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
node "$DESIGN_PLUGIN_ROOT/skills/ui-alignment-review/scripts/run-ui-alignment.mjs" --config design.qa.yaml
```

Then inspect:

```text
.design-qa/reports/ui-alignment.json
.design-qa/UI_ALIGNMENT_REPORT.md
.design-qa/reports/visual-comparison.json
.design-qa/diff/*.png
```

The full runner calls `audit-ui-alignment.mjs`, which can call sibling scripts for Figma export, Playwright screenshot capture, image comparison, component alignment, and design-debt scanning. If automation is unavailable, manually follow the same review protocol.

## Core review criteria

Apply these criteria before reading detailed references:

- **Reference mapping**: Is each implemented screen matched to the correct Figma frame, mockup, or approved baseline for the same state, viewport, and content?
- **Capture protocol**: Are viewport, device scale, full-page mode, font availability, frozen time/data, reduced motion, masks, and ignored dynamic regions configured consistently?
- **Layout geometry**: Do container width, grid, grouping, element positions, alignment, spacing rhythm, hierarchy, and scroll behavior match the reference?
- **Typography**: Do font family, size, weight, line-height, letter spacing, wrapping, truncation, and content density match the design intent?
- **Visual tokens**: Do colors, opacity, border radius, borders, shadows, gradients, icons, images, and elevation use approved tokens or documented exceptions?
- **Components and states**: Are shared components and variants used, and are default, hover, focus-visible, active, disabled, loading, empty, error, selected, and expanded states aligned?
- **Responsive behavior**: Do configured breakpoints preserve layout priority, tap targets, readability, and primary actions?
- **Acceptable differences**: Are differences due to real data, localization, font rendering, browser rendering, dynamic content, or approved implementation constraints documented rather than hidden?
- **Fixability**: Can each finding point to a likely file/component/token/selector and a concrete verification step?

Always make a specific pass over typography, spacing/layout rhythm, colors/tokens, image/icon/asset fidelity, and copy/content. If the full screenshot does not make those details readable, inspect focused regions before producing final findings.

## Main workflow

1. **Identify alignment mode**
   - Use `conformance` when comparing current UI to Figma, a prototype image, or a design reference.
   - Use `regression` when comparing current UI to the last approved implementation baseline.
   - Use `component` when comparing Storybook or component examples against design components.

2. **Normalize the reference**
   - Confirm the design frame, app route, viewport, device scale factor, screenshot mode, state, theme, language, and sample data are meant to match.
   - Prefer fixed seed data, frozen time, disabled animations, hidden caret, and reduced motion.
   - Mask only dynamic or irrelevant regions; do not mask real layout or token defects.
   - If the design and implementation are not comparable, call out the mismatch before judging fidelity.

3. **Run automation when possible**
   - Export Figma/reference image if configured.
   - Capture the actual UI screenshot.
   - Compare expected and actual images.
   - Run optional component and design-debt scans to explain why the visual result drifted.
   - Collect configured DOM/computed-style measurements when selectors are provided.

4. **Interpret diffs by design meaning**
   - Translate pixel differences into design categories: missing element, layout shift, spacing mismatch, typography mismatch, token mismatch, image/icon mismatch, state mismatch, responsive issue, dynamic data, or rendering noise.
   - Do not rely only on diff percentage. A small diff on a primary CTA may matter more than a large diff in an approved dynamic image area.
   - Treat handmade SVG/CSS replacements, generic placeholder imagery, mismatched icons, and prompt-like copy as alignment issues when the reference specifies real assets or product-specific text.

5. **Classify alignment findings**
   - `must-fix`: prevents design acceptance, breaks hierarchy, misses required content/state, or affects a primary path.
   - `should-fix`: visible mismatch likely to be noticed by users or designers, but not a release stopper.
   - `polish`: small spacing, optical alignment, icon alignment, or copy density issue.
   - `acceptable-difference`: intentional or technically unavoidable difference documented for design signoff.
   - `needs-design-decision`: implementation and design contract conflict, or design reference is ambiguous/outdated.

6. **Recommend implementation changes**
   - Prefer tokens, component variants, and layout primitives over one-off CSS.
   - Fix shared components when the issue appears in multiple places.
   - Do not “fix” by widening thresholds or adding broad masks before investigating real diffs.
   - Update baselines only after the design owner accepts the implemented result.

7. **Produce a designer/frontend alignment report**
   - Include the target reference, actual route, viewport, evidence quality, blocking deltas, likely implementation cause, recommended fix, and verification step.
   - Separate actual product differences from screenshot setup problems.

## Severity mapping

Use Design QA severities when reporting into the larger pipeline:

- `blocker`: same as `must-fix`; design acceptance should fail.
- `major`: same as high-impact `should-fix`; visible issue or repeated mismatch.
- `minor`: same as `polish`; small visual issue with low user-flow impact.
- `info`: acceptable difference, setup note, or evidence limitation.
- `needs-design-decision`: use this label when the team must decide whether to update the design, implementation, or acceptance criteria.

## Output format

Use this format unless the user requests another one:

```markdown
# UI Alignment Review: <Pass | Needs fixes | Inconclusive>

## Summary
<2-5 sentences explaining alignment status and evidence quality.>

## Reference Mapping
- Screen/route:
- Reference:
- Implementation:
- Viewport/device scale:
- Mode:
- Dynamic regions/masks:

## Must Fix

### <finding title>
- Category: layout | spacing | typography | token | asset | component | state | responsive | data | setup
- Evidence:
- Observed:
- Expected:
- Likely cause:
- Recommended frontend fix:
- Designer decision needed:
- Verification:

## Should Fix

## Polish

## Acceptable Differences

## Setup / Evidence Issues

## Artifacts
- Expected:
- Actual:
- Diff:
- JSON reports:

## Verification Checklist
- [ ] Re-run UI alignment automation
- [ ] Inspect diff images at target viewports
- [ ] Inspect typography, spacing/layout, colors/tokens, image/assets, and copy/content
- [ ] Confirm dynamic content masks are justified
- [ ] Confirm fixes use tokens/components rather than one-off CSS
- [ ] Confirm design owner accepts intentional differences
```

## Patch policy

When asked to patch code:

- inspect existing layout and component primitives before editing feature code
- prefer semantic tokens and component variants
- avoid broad threshold/mask changes as a substitute for UI fixes
- keep data/state fixtures stable so diffs remain repeatable
- update reference screenshots only after approval
- preserve accessibility states while adjusting visual alignment

## Trigger tests

This Skill should trigger for:

- “帮我把这个页面和 Figma 对齐。”
- “设计师说这里不像稿子，帮我找差异并改。”
- “前端实现和 UI 图做一下 alignment review。”
- “这个 diff 是不是必须修？”
- “用截图和原型图生成对齐问题清单。”
- “UI 对齐不要只看像素，帮我按布局/字体/颜色/组件拆问题。”

It should hand off to:

- `visual-regression-review` for raw image diff protocol
- `component-library-alignment` for component adoption and variant governance
- `design-debt-review` for token/style debt
- `accessibility-review` for accessibility release risk
- `design-qa` for final release verdict

## Detailed references

Read local references only when deeper detail is needed:

- `references/ui-alignment-guide.md` for alignment categories, review protocol, severity, and anti-patterns.
- `references/implementation-handoff-guide.md` for designer/frontend handoff, reference mapping, data fixtures, and acceptance workflow.
- `references/automation-guide.md` for pipeline commands, artifacts, config examples, and selector-anchor configuration.

## Version history

- v0.5.0: Added dedicated UI alignment workflow for designer/frontend design-to-implementation conformance.
