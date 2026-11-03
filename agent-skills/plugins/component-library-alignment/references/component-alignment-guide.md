# Component Alignment Guide

Use this guide to decide whether implementation respects the design-system component library.

## Goal

Prevent feature code from bypassing shared visual, accessibility, state, and token rules. Raw HTML is not always wrong; ungoverned raw UI in feature surfaces is the risk.

## What to check

- common components imported from the intended library
- raw elements limited to component primitive files or justified contexts
- variants expressed via component props or central styles
- states covered in shared components
- Storybook/tests cover important component states
- UI libraries are not mixed without adapter/migration plan
- local class overrides do not erase design-system behavior

## Component inventory

Look for primitives such as:

- Button
- Input, Textarea, Select, Checkbox, Radio, Switch
- Dialog, Popover, Tooltip, Toast
- Card, Alert, Badge, Avatar
- Table, List, Tabs, Menu, Navigation
- Form and Field components

## Allowed raw zones

Raw elements may be acceptable in:

- component primitive implementations
- low-level adapter files
- content/article rendering
- semantic wrappers where no shared component exists
- canvas, chart, map, media, or third-party integration zones

Raw interactive elements are suspicious in:

- pages/routes
- generated UI
- feature components
- business-flow forms
- modals and navigation surfaces

## Common findings

- raw `<button>` where `<Button>` exists
- raw `<input>` where `<Input>` or `<Field>` exists
- feature-specific modal where `<Dialog>` exists
- one-off table styling where `<DataTable>` exists
- button variant encoded as Tailwind classes instead of `variant` prop
- local disabled/loading/focus styles that differ from shared primitive
- direct imports from two UI libraries in the same feature
- duplicated card/list/form patterns that should become variants

## Severity

### Blocker

Critical flow bypasses shared component and loses accessibility, state, or design-critical behavior.

### Major

Repeated bypass, duplicated pattern, visible inconsistent UX, mixed UI libraries, or missing central variant for common state.

### Minor

Isolated local implementation with low spread risk and correct semantics.

### Debt

Maintenance or governance risk without immediate visual failure.

## Preferred fix

1. Replace feature-local markup with shared component.
2. Use existing variant/size/state props.
3. If missing, add variant to shared component instead of local classes.
4. Document new variant in component docs or `DESIGN.md`.
5. Add Storybook story or snapshot for important states.
6. Add lint/codemod guard for repeated bypasses.

## Evidence standard

Good finding:

```text
src/app/settings/ProfileForm.tsx uses raw <button className="..."> while src/components/ui/Button.tsx provides variant="primary" plus loading/disabled/focus-visible behavior.
```

Weak finding:

```text
This button looks custom.
```

Always include file path, component name, import source, and the expected shared component or variant.
