# Design QA Automation Guide

This guide explains how the plugin automation supports Design QA.

## Required project files

At minimum:

```text
DESIGN.md
design.qa.yaml
```

Optional but recommended:

```text
SCREEN_SPEC.md
.design-qa/expected/*.png
```

## Script discovery

Scripts are Skill-local. Locate the plugin runtime root in this order:

1. `$DESIGN_PLUGIN_ROOT`
2. `.qoder/design-plugin`
3. the current plugin checkout root

Then run the corresponding Skill script under:

```text
$DESIGN_PLUGIN_ROOT/skills/<skill-name>/scripts/<script>.mjs
```

Recommended environment:

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin}
```

## Full pipeline

```bash
DESIGN_PLUGIN_ROOT=${DESIGN_PLUGIN_ROOT:-.qoder/design-plugin} \
node "$DESIGN_PLUGIN_ROOT/skills/design-qa/scripts/run-design-qa.mjs" --config design.qa.yaml
```

The full pipeline runs:

- `audit-design-md.mjs`
- `export-figma-frame.mjs`
- `capture-ui-screenshot.mjs`
- `compare-images.mjs`
- `audit-ui-alignment.mjs`
- `audit-a11y.mjs`
- `audit-components.mjs`
- `audit-design-debt.mjs`
- `generate-design-qa-report.mjs`

Design-system capture is a supporting workflow and can run separately with `collect-design-system-evidence.mjs`.

## Individual commands

### Initialize config

```bash
node "$DESIGN_PLUGIN_ROOT/skills/design-qa/scripts/init-design-qa.mjs"
```

### Export Figma references

```bash
FIGMA_TOKEN=figd_xxx \
node "$DESIGN_PLUGIN_ROOT/skills/visual-regression-review/scripts/export-figma-frame.mjs" --config design.qa.yaml
```

### Capture actual UI screenshots

```bash
node "$DESIGN_PLUGIN_ROOT/skills/visual-regression-review/scripts/capture-ui-screenshot.mjs" --config design.qa.yaml
```

### Compare screenshots

```bash
node "$DESIGN_PLUGIN_ROOT/skills/visual-regression-review/scripts/compare-images.mjs" --config design.qa.yaml
```

### UI alignment

```bash
node "$DESIGN_PLUGIN_ROOT/skills/ui-alignment-review/scripts/audit-ui-alignment.mjs" --config design.qa.yaml
```

### Accessibility

```bash
node "$DESIGN_PLUGIN_ROOT/skills/accessibility-review/scripts/audit-a11y.mjs" --config design.qa.yaml
```

### Component alignment

```bash
node "$DESIGN_PLUGIN_ROOT/skills/component-library-alignment/scripts/audit-components.mjs" --config design.qa.yaml
```

### Design debt

```bash
node "$DESIGN_PLUGIN_ROOT/skills/design-debt-review/scripts/audit-design-debt.mjs" --config design.qa.yaml
```

### DESIGN.md contract

```bash
node "$DESIGN_PLUGIN_ROOT/skills/design-md-review/scripts/audit-design-md.mjs" --config design.qa.yaml
```

### Design-system capture evidence

```bash
node "$DESIGN_PLUGIN_ROOT/skills/design-system-capture/scripts/collect-design-system-evidence.mjs" --config design.qa.yaml
```

## Output artifacts

Default output:

```text
.design-qa/
  expected/
  actual/
  diff/
  reports/
    visual-comparison.json
    ui-alignment.json
    a11y.json
    component-alignment.json
    design-debt.json
    design-md-audit.json
  DESIGN_QA_REPORT.md
```

## CI guidance

Use deterministic environments for visual checks:

- same OS image
- same browser version
- installed fonts
- stable viewport and device scale factor
- fixed test data
- frozen time where possible
- animations disabled
- masked dynamic content

Do not approve baseline updates automatically. Baseline updates should require design owner or reviewer sign-off.

## Interpreting automation

Automation tells you where to inspect. It does not replace design judgment.

- Visual diff finds pixel changes, not root causes.
- UI alignment checks connect visual evidence to DOM anchors/selectors, computed styles, and likely fix paths.
- axe finds many a11y issues, not all accessibility issues.
- component audits find obvious bypasses, not all design-system misuse.
- debt scans flag likely raw-value drift, not every intentional exception.

Always turn raw findings into user-impact findings before reporting a final verdict.
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

## Handoff rules

Use sibling guides when depth is needed:

- `../ui-alignment-review/references/ui-alignment-guide.md`
- `../ui-alignment-review/references/implementation-handoff-guide.md`
- `../visual-regression-review/references/visual-comparison-guide.md`
- `../accessibility-review/references/accessibility-review-guide.md`
- `../component-library-alignment/references/component-alignment-guide.md`
- `../design-debt-review/references/design-debt-guide.md`
- `../design-md-review/references/design-md-guide.md`
- `../design-system-capture/references/capture-guide.md`
