---
name: accessibility-review
description: Reviews frontend accessibility using automated axe/Playwright reports plus manual design QA heuristics. Use for a11y checks, WCAG-oriented review, contrast, keyboard navigation, focus-visible state, ARIA, form labels, alt text, heading structure, touch targets, motion, and accessible component states.
---

# Accessibility Review

## Skill contract

Use automated accessibility evidence plus manual design review to identify barriers. Automation is a starting point, not a complete accessibility approval.

The goal is to produce actionable, user-impact-focused findings that can be fixed in the right component or page layer.

## Use when

Use this Skill when the user asks to:

- review accessibility, a11y, WCAG, contrast, keyboard navigation, focus state, ARIA, labels, alt text, or heading structure
- interpret axe, Storybook a11y, Playwright a11y, Lighthouse, or browser accessibility findings
- check whether UI states remain accessible: hover, focus-visible, disabled, loading, error, empty, selected, expanded, collapsed
- review design or implementation for keyboard-only, screen-reader, low-vision, reduced-motion, or touch users
- fix accessibility issues in frontend components

## Do not use when

Do not use this Skill as the primary Skill when:

- the user asks for full Design QA across visual, components, debt, and screenshots; use `design-qa`
- the user only asks for screenshot diff interpretation; use `visual-regression-review`
- the user asks to create the design system; use `design-system-capture`

## Inputs

Look for:

- `design.qa.yaml`
- `.design-qa/reports/a11y.json`
- Storybook a11y reports
- Playwright tests and page routes
- component source files
- form, modal, nav, menu, table, tooltip, toast, and dialog components
- screenshots showing focus/error/disabled/loading states
- `DESIGN.md` accessibility and color rules

## Automation path discovery

Locate this Skill's automation script in this order:

1. `$DESIGN_PLUGIN_ROOT/skills/accessibility-review/scripts`
2. `.qoder/design-plugin/skills/accessibility-review/scripts`
3. `skills/accessibility-review/scripts` in the current plugin checkout

Run automated checks when a route or config is available:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
node "$DESIGN_PLUGIN_ROOT/skills/accessibility-review/scripts/audit-a11y.mjs" --config design.qa.yaml
```

Then inspect:

```text
.design-qa/reports/a11y.json
```

If automation is unavailable, perform a source-and-screenshot accessibility review and explicitly label it as manual.

## Review workflow

1. **Identify user paths**
   - Prioritize primary flows: sign in, checkout, onboarding, create/edit forms, search, navigation, destructive actions, and error recovery.

2. **Read automated findings**
   - Group repeated violations by component.
   - Prioritize violations with direct user impact over raw count.
   - Do not duplicate identical findings for every instance unless spread matters.

3. **Check semantic structure**
   - Landmarks, headings, lists, tables, forms, buttons, links, dialogs, menus, and tabs should use appropriate semantic roles.
   - Prefer native HTML semantics before adding ARIA.

4. **Check keyboard behavior**
   - All interactive controls are reachable.
   - Focus order follows visual and logical order.
   - Focus is trapped in modals and restored after close.
   - Escape closes dismissible overlays where expected.
   - Disabled controls are not focus traps.

5. **Check visual focus and state clarity**
   - Focus-visible state is visible and consistent with `DESIGN.md`.
   - Hover-only information is also available by focus or click.
   - Error, success, warning, selected, disabled, and loading states do not rely only on color.

6. **Check names and descriptions**
   - Icon-only buttons have accessible names.
   - Form controls have labels and helpful error text.
   - Complex controls expose state such as expanded, selected, checked, invalid, busy, or disabled.

7. **Check contrast and readability**
   - Text, icons conveying meaning, focus rings, borders that convey state, and disabled text should meet project/WCAG expectations.
   - Watch muted text on tinted surfaces and white text on gradient or image backgrounds.

8. **Check motion and responsive/touch access**
   - Reduced motion is respected for disruptive animation.
   - Touch targets are large enough and not too close together.
   - Zoom or narrow viewport does not hide essential controls.

9. **Choose the fix layer**
   - If repeated, fix the component primitive.
   - If page-specific, fix the page composition.
   - If token-driven, update semantic tokens or state tokens.

## Core review criteria

Review accessibility through four lenses:

- **Operable**: Can keyboard and touch users reach and use every critical control?
- **Perceivable**: Are text, icons, focus rings, and state indicators visible and not color-only?
- **Understandable**: Are labels, names, instructions, errors, and headings clear?
- **Robust**: Do semantics, ARIA, focus management, and component states work across assistive technologies?

Automated scans are evidence, not approval. Read `references/accessibility-review-guide.md` when you need detailed manual checks or severity examples.

## Severity rules

- `blocker`: primary flow inaccessible; keyboard trap; missing accessible name on critical action; critical form cannot be submitted or corrected; severe contrast failure in essential content.
- `major`: repeated component-level violation; important state not announced; focus order confusing; error recovery unclear; contrast failure in common content.
- `minor`: localized issue with workaround; non-critical alt text issue; small focus polish issue.
- `manual-review`: automated tools cannot determine correctness, such as screen-reader phrasing or complex workflow logic.

## Common issue patterns

- Button or link has no accessible name.
- Form field uses placeholder as label.
- Modal opens without focus management.
- Toast announces visually but not programmatically.
- Error text appears visually but is not associated with the input.
- Custom select/menu/tab lacks keyboard support or ARIA state.
- Focus ring is removed or too low contrast.
- Color-only status indicators.
- `div` or `span` used as interactive control.
- Heading levels skip because of visual styling rather than document structure.

## Fix guidance

- Prefer native elements over ARIA when possible.
- Do not add ARIA to hide semantic problems; fix the underlying element first.
- Fix accessibility in shared components when the issue repeats.
- Preserve visual design while improving semantics and focus behavior.
- Add tests for critical keyboard and a11y behavior.
- Include manual verification steps for keyboard and screen reader paths.

## Output format

```markdown
# Accessibility Review

## Summary
<Automation coverage, primary risks, and confidence.>

## Findings

### [severity] <issue title>
- Evidence:
- Affected screen/component:
- User impact:
- Expected behavior:
- Recommended fix:
- Verification:

## Component-Level Fixes

## Manual Review Required
- [ ] Keyboard-only primary path
- [ ] Screen reader check for primary path
- [ ] Error recovery path
- [ ] Reduced motion behavior
- [ ] Touch target and zoom behavior
```

## Trigger tests

This Skill should trigger for:

- “检查这个页面的 a11y / WCAG。”
- “这个弹窗键盘和 screen reader 有没有问题？”
- “解释 axe 报告并给修复建议。”
- “看一下 focus ring、contrast、form labels。”

It should hand off to `design-qa` when the user asks for full design acceptance.

## Detailed reference

Read `references/accessibility-review-guide.md` when you need detailed automated/manual checks, path prioritization, severity examples, fix-layer guidance, or verification steps.

## Version history

- v0.4.0: Moved `audit-a11y.mjs` into Skill-local `scripts/` and updated automation paths.
- v0.3.0: Moved detailed review guides into Skill-local `references/*-guide.md` files and added an inline core review criteria for progressive disclosure.
- v0.2.0: Added trigger boundaries, user-impact workflow, severity rules, common patterns, and fix-layer guidance.
- v0.1.0: Initial accessibility workflow.
