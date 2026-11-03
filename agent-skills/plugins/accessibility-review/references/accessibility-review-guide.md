# Accessibility Review Guide

Use this guide for detailed accessibility review and axe/Playwright result interpretation.

## Principle

Automated accessibility tools catch important classes of issues, but they do not prove accessibility. Combine automated findings with manual review of user paths.

## Automated checks

Common automated findings:

- color contrast
- missing form labels
- missing accessible names
- duplicate IDs
- invalid ARIA
- heading order
- missing image alt text
- missing landmarks
- invalid role/state relationships

Group repeated findings by component instead of reporting every instance separately when the same fix applies.

## Manual checks

Always consider:

- keyboard-only operation
- visible focus order
- modal/popover focus management
- screen-reader clarity for primary path
- error recovery
- content readability
- reduced motion
- zoom/reflow at narrow widths
- touch target size and spacing
- complex component behavior: menus, tabs, comboboxes, dialogs, tables, toasts

## User path priority

Prioritize:

1. sign in / sign up
2. checkout / payment
3. create/edit/submit forms
4. search and filtering
5. navigation and settings
6. destructive actions
7. error recovery

## Severity

### Blocker

- keyboard trap
- inaccessible primary action
- critical button or link has no accessible name
- essential form cannot be completed or corrected
- severe contrast failure on essential text/action
- modal/dialog cannot be operated with keyboard

### Major

- repeated component-level accessibility issue
- important state not announced or visually available
- focus order confusing in common path
- error text not associated with input
- common content contrast failure

### Minor

- localized issue with workaround
- non-critical decorative alt issue
- minor focus polish issue
- heading order issue that does not block comprehension

### Manual review

Use when correctness cannot be determined automatically:

- screen-reader phrasing quality
- complex workflow logic
- intent of icon-only control
- reduced-motion acceptability
- content clarity

## Fix layer

Fix in this order:

1. Shared component primitive if repeated.
2. Component variant/state if pattern-specific.
3. Page composition if truly local.
4. Token if contrast/focus/state color is system-wide.
5. Copy/content if accessible name or instruction text is unclear.

## Common patterns and fixes

- Placeholder used as label → add persistent label and associate it with input.
- Icon-only button → provide accessible name.
- Modal opens without focus handling → focus initial meaningful element, trap focus, restore focus on close.
- Error visually present only → associate error via `aria-describedby` and mark invalid state.
- Clickable `div` → use native button/link or implement keyboard semantics only when unavoidable.
- Focus ring removed → restore visible focus-visible style using design token.
- Color-only status → add icon/text/shape or programmatic state.

## Verification checklist

- [ ] Run automated a11y scan.
- [ ] Complete primary path with keyboard only.
- [ ] Check visible focus in light/dark/high-contrast surfaces.
- [ ] Verify screen-reader names for critical controls.
- [ ] Verify form labels and error associations.
- [ ] Verify modal/menu/tab behavior.
- [ ] Verify reduced-motion behavior for disruptive animation.
- [ ] Verify touch targets and zoom/reflow where relevant.
