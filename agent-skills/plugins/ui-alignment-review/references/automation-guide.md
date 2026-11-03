# UI Alignment Automation Guide

Use this guide when running the designer/frontend UI alignment workflow from `design.qa.yaml`.

## Scripts

Full UI alignment pipeline:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin} \
node "$DESIGN_PLUGIN_ROOT/skills/ui-alignment-review/scripts/run-ui-alignment.mjs" --config design.qa.yaml
```

Selector/anchor audit pipeline:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin} \
node "$DESIGN_PLUGIN_ROOT/skills/ui-alignment-review/scripts/audit-ui-alignment.mjs" --config design.qa.yaml
```

Markdown report generation only:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin} \
node "$DESIGN_PLUGIN_ROOT/skills/ui-alignment-review/scripts/generate-ui-alignment-report.mjs" --config design.qa.yaml
```

## Artifacts

The full pipeline may produce:

```text
.design-qa/expected/*.png
.design-qa/actual/*.png
.design-qa/diff/*.png
.design-qa/reports/figma-export.json
.design-qa/reports/screenshots.json
.design-qa/reports/visual-comparison.json
.design-qa/reports/ui-alignment.json
.design-qa/reports/run-ui-alignment.json
.design-qa/UI_ALIGNMENT_REPORT.md
```

## Configuration

Use `uiAlignment.anchors` for global targets inspected on every configured screen. Use `screens[].uiAlignment.anchors` for page-specific targets. Older `inspectSelectors` keys are still accepted for backward compatibility, but new configs should use `anchors`.

```yaml
uiAlignment:
  runVisualComparison: true
  runComponentAudit: true
  runDebtAudit: true
  runA11yAudit: false
  measurementTolerancePx: 1
  anchors:
    - name: global nav
      selector: '[data-testid="global-nav"]'
      expected:
        height:
          value: 64
          tolerance: 2
        css:
          position: sticky

screens:
  - name: checkout-mobile
    app:
      url: /checkout
      viewport:
        width: 390
        height: 844
    uiAlignment:
      anchors:
        - name: primary cta
          selector: '[data-testid="primary-cta"]'
          severity: major
          expected:
            minHeight: 44
            height:
              value: 48
              tolerance: 1
            css:
              borderRadius: 12px
              fontWeight: "600"
```

## Interpretation

- Use pixel diff to locate suspicious regions.
- Use anchor-level DOM and computed CSS checks to explain concrete implementation gaps.
- Do not broaden masks or thresholds to hide real design mismatches.
- Prefer adding 5–12 high-value anchors per critical screen over trying to automate every element.
