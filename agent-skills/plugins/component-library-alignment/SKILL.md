---
name: component-library-alignment
description: Checks whether frontend implementation uses the intended design-system component library instead of raw HTML, local one-off components, arbitrary Tailwind variants, or mixed UI libraries. Use for component consistency, design-system adoption, UI primitive governance, variant review, Storybook coverage, and implementation review.
---

# Component Library Alignment

## Skill contract

This Skill checks whether UI implementation respects the project’s component system. The goal is not to ban raw HTML everywhere; the goal is to prevent feature code from bypassing shared accessibility, visual, interaction, and token rules.

Use evidence from imports, component names, JSX/HTML elements, styles, Storybook stories, and `DESIGN.md` component rules.

## Use when

Use this Skill when the user asks to:

- review whether UI uses design-system components correctly
- detect raw `<button>`, `<input>`, `<dialog>`, custom modals, duplicate cards, or local component clones
- check whether AI-generated UI bypassed component primitives
- review component variants, state coverage, or Storybook coverage
- identify mixed UI libraries or inconsistent component sources
- propose refactors from one-off UI to shared components

## Do not use when

Do not use this Skill as the primary Skill when:

- the user asks for full Design QA; use `design-qa`
- the user asks whether implementation matches a Figma/reference design overall; use `ui-alignment-review`
- the user only wants visual screenshot comparison; use `visual-regression-review`
- the user wants design/reference image conformance for designers and frontend engineers; use `ui-alignment-review`
- the user only wants hard-coded style and token drift; use `design-debt-review`
- the user asks to define the component library from scratch; use `design-system-capture`

## Inputs

Look for:

- `design.qa.yaml`, especially `components.libraryImportPatterns` and `components.rawElementPolicy`
- `DESIGN.md` component rules
- component library directories such as `src/components/ui`, `src/design-system`, `packages/ui`, or equivalent
- UI source files in app/routes/features/pages
- Storybook stories
- existing component docs
- `.design-qa/reports/component-alignment.json`

## Automation path discovery

Locate this Skill's automation script in this order:

1. `$DESIGN_PLUGIN_ROOT/skills/component-library-alignment/scripts`
2. `.qoder/design-plugin/skills/component-library-alignment/scripts`
3. `skills/component-library-alignment/scripts` in the current plugin checkout

Run:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
node "$DESIGN_PLUGIN_ROOT/skills/component-library-alignment/scripts/audit-components.mjs" --config design.qa.yaml
```

Then inspect:

```text
.design-qa/reports/component-alignment.json
```

If automation is unavailable, inspect imports and JSX/HTML manually.

## Review workflow

1. **Identify the intended component system**
   - Read `components.libraryImportPatterns` in `design.qa.yaml`.
   - Search for shared primitives: Button, Input, Select, Checkbox, Radio, Switch, Dialog, Popover, Tooltip, Card, Table, Tabs, Toast, Alert, Badge, Avatar, Menu, Navigation.
   - Read `DESIGN.md` component rules and state expectations.

2. **Define allowed raw zones**
   - Raw elements may be acceptable inside component primitive implementation files.
   - Raw elements are usually suspicious inside page, route, feature, or generated UI files when a shared primitive exists.

3. **Scan for bypasses**
   - Raw interactive elements: `<button>`, `<input>`, `<select>`, `<textarea>`, `<a role="button">`, clickable `<div>`/`<span>`.
   - Local duplicate components: `PrimaryButton`, `CustomButton`, `MyModal`, `FeatureCard`, `FormInput`, `UserTable` when shared equivalents exist.
   - Direct imports from multiple UI libraries without an adapter layer.
   - Feature-local variants implemented with arbitrary class strings instead of component props.

4. **Check variant governance**
   - Variants should live in component primitives, tokens, or design-system docs.
   - Feature code should not invent semantic variants such as `danger`, `premium`, `ghost`, `subtle`, or `compact` without central definition.
   - Required states should be covered: default, hover, focus-visible, active, disabled, loading, selected, error, success, empty.

5. **Check Storybook/test coverage**
   - Important components and variants should have stories or screenshots.
   - Missing states should be reported when they affect current screens or future drift risk.

6. **Classify and prioritize**
   - Prioritize shared component bypasses in critical flows.
   - Prioritize duplicated implementations with accessibility or token differences.
   - Treat isolated raw markup as minor only when no shared component exists and the semantics are correct.

## Core review criteria

Check component alignment with these quick review criteria:

- **Source**: Is common UI imported from the intended design-system package or directory?
- **Bypass**: Are raw interactive elements or local clones used where shared primitives exist?
- **Variants**: Are visual variants represented by component props or central styles rather than page-level class strings?
- **States**: Do shared components cover hover, focus-visible, active, disabled, loading, error, empty, selected, and expanded states where relevant?
- **Governance**: Are new patterns documented in Storybook, component docs, or `DESIGN.md`?
- **Risk**: Would this pattern spread if copied by an AI coding agent?

Read `references/component-alignment-guide.md` for allowed raw zones, severity examples, and refactor policy.

## Severity rules

- `blocker`: critical flow bypasses a shared component and loses accessibility, state handling, or design-critical behavior.
- `major`: repeated feature-level bypass, duplicated component pattern, mixed UI libraries creating inconsistent UX, or missing central variant for a visible state.
- `minor`: isolated local implementation with low spread risk.
- `debt`: maintainability risk or future design-system drift without immediate visible defect.

## Preferred fixes

- Replace raw feature markup with existing design-system components.
- If a needed variant is missing, add it to the shared component rather than duplicating local styles.
- Add or update Storybook stories for new variants and states.
- Preserve behavior, accessibility props, and test coverage during refactors.
- Avoid introducing a second UI library unless there is an explicit migration/adapter plan.

## Evidence examples

Good evidence:

```text
src/app/settings/ProfileForm.tsx uses raw <button className="..."> while src/components/ui/Button.tsx provides variant="primary" and loading/disabled behavior.
```

Weak evidence:

```text
This looks inconsistent.
```

Always include file path, component name, import pattern, and observed bypass.

## Output format

```markdown
# Component Library Alignment Review

## Summary
<Component adoption status, spread risk, and highest priority fixes.>

## Findings

### [severity] <component/library issue>
- Evidence:
- Affected files:
- Observed:
- Expected component/variant:
- Design/accessibility impact:
- Recommended fix:
- Verification:

## Suggested Refactors

## Missing Component Variants or Stories
```

## Trigger tests

This Skill should trigger for:

- “这个页面是不是绕过了组件库？”
- “AI 写的 UI 有没有重复实现 Button / Dialog / Card？”
- “检查组件 variant 是否应该抽到 design system。”
- “看一下 Storybook 状态覆盖够不够。”

It should hand off to `ui-alignment-review` for designer/frontend design-to-code alignment, `design-debt-review` for hard-coded value cleanup, and `design-qa` for full approval reporting.

## Detailed reference

Read `references/component-alignment-guide.md` when you need detailed allowed raw zones, common bypass patterns, severity examples, preferred refactors, and evidence standards.

## Version history

- v0.5.0: Clarified boundary with `ui-alignment-review`; component alignment is only one layer of UI alignment.
- v0.5.0: Clarified boundary with `ui-alignment-review`.
- v0.4.0: Moved `audit-components.mjs` into Skill-local `scripts/` and updated automation paths.
- v0.3.0: Moved detailed review guides into Skill-local `references/*-guide.md` files and added an inline core review criteria for progressive disclosure.
- v0.2.0: Added boundaries, allowed raw zones, variant governance, severity rules, and evidence standards.
- v0.1.0: Initial component alignment workflow.
