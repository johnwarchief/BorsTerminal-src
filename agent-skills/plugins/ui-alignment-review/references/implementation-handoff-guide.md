# Implementation Handoff Guide

## Goal

Make UI alignment review repeatable for designers and frontend engineers. The best handoff gives the agent or reviewer a clear mapping from design reference to implementation route, stable data, expected viewport, and acceptance criteria.

## Designer handoff checklist

Provide:

- Figma frame URL or exported PNG for each target screen
- screen name and state name, for example `checkout-error-mobile`
- intended viewport size and device scale
- theme/mode: light, dark, high contrast, compact, dense, etc.
- required content state: default, loading, empty, error, success, permission denied
- placeholder vs real data expectations
- dynamic regions that should be ignored or masked
- components that must be reused
- known intentional deviations
- design owner or reviewer for final signoff

## Frontend handoff checklist

Provide:

- app URL or local route
- app startup command if automation should launch it
- readiness URL and wait selector
- deterministic data fixture or seed
- auth state setup when needed
- stable selectors for important alignment targets, preferably `data-testid`
- component source files and Storybook stories
- changed files or PR notes
- known implementation constraints

## Recommended `design.qa.yaml` mapping

```yaml
screens:
  - name: checkout-error-mobile
    mode: conformance
    expected:
      type: figma
      figma:
        url: https://www.figma.com/design/FILE_KEY/name?node-id=12-345
        format: png
        scale: 1
    app:
      url: /checkout?fixture=error
      viewport:
        width: 390
        height: 844
      deviceScaleFactor: 1
      fullPage: true
      waitUntil: networkidle
      waitForSelector: '[data-testid="checkout-page"]'
      freezeDate: "2026-01-01T00:00:00Z"
    compare:
      maxDiffPixelRatio: 0.02
      maxDiffPixels: 5000
      threshold: 0.2
      masks:
        - selector: '[data-testid="user-avatar"]'
      ignoreSelectors:
        - '[data-testid="timestamp"]'
    uiAlignment:
      anchors:
        - name: primary cta
          selector: '[data-testid="submit-order"]'
          expected:
            minHeight: 44
            height:
              value: 48
              tolerance: 1
            css:
              borderRadius: 12px
              fontWeight: "600"
```

## Global UI alignment config

```yaml
uiAlignment:
  runVisualComparison: true
  runComponentAudit: true
  runDebtAudit: true
  runA11yAudit: false
  defaultTolerancePx: 6
  anchors:
    - name: main heading
      selector: '[data-testid="page-heading"]'
      expected:
        css:
          fontSize: 48px
          lineHeight: 56px
```

Use global anchors for repeated app shell targets. Use screen-level anchors for page-specific targets.

## Stable selector guidance

Prefer:

```html
<h1 data-testid="page-heading">...</h1>
<button data-testid="primary-cta">...</button>
<section data-testid="pricing-card">...</section>
```

Avoid relying on brittle selectors such as:

```text
body > div:nth-child(2) > div > div:nth-child(4)
```

## Acceptance workflow

1. Frontend implements using design-system components and tokens.
2. Automation exports reference and captures actual UI.
3. UI alignment review creates must-fix, should-fix, polish, acceptable-difference, and needs-design-decision items.
4. Frontend fixes must-fix and high-value should-fix items.
5. Designer reviews acceptable differences and decides whether design or implementation should change.
6. Baseline/reference is updated only after design approval.
7. Visual tests are kept in CI for regression protection.

## Common team agreements

Agree on:

- which diffs block release
- max diff thresholds by screen criticality
- which dynamic regions are allowed to be masked
- whether full-page or viewport screenshot is canonical
- how to handle real content longer than Figma placeholder text
- how to handle Figma/browser font rendering differences
- how to record design decisions
- who can approve baseline updates

## Ticket-ready finding fields

Use these fields when creating tasks:

```yaml
title:
category:
severity:
screen:
route:
reference:
selector:
files:
evidence:
observed:
expected:
likelyCause:
frontendFix:
designerDecisionNeeded:
verification:
```

## Definition of done

A UI alignment task is done when:

- visual comparison passes or remaining differences are documented
- important alignment targets match expected computed styles or approved tolerance
- components use approved primitives and variants
- no new hard-coded visual values are introduced
- responsive viewports are checked
- design owner accepts intentional differences
- baseline is updated only when the implemented state is now the approved reference
