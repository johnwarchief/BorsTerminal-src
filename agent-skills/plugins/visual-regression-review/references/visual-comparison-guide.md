# Visual Comparison Guide

Use this guide for screenshot regression, Figma/reference conformance, diff interpretation, masks, thresholds, and capture protocol.

## Modes

### Regression mode

Expected image is a previously approved UI baseline.

Use for:

- PR visual regression
- preventing accidental CSS/layout changes
- tracking approved UI over time

Approval is stricter because both images should come from the same app rendering pipeline.

### Conformance mode

Expected image is a designer-owned reference such as Figma export, prototype image, or handoff screenshot.

Use for:

- UI implementation vs Figma
- prototype handoff QA
- validating AI-generated UI against a visual target

Approval needs interpretation because design tools and browsers render differently.

## Required setup

Before comparing:

- match viewport to the design frame
- set `deviceScaleFactor` intentionally
- use a stable browser and OS in CI
- install production fonts or document fallback differences
- disable animations and hide carets
- freeze date/time and random data
- use deterministic seed data
- wait for UI stability before capture
- mask dynamic regions
- compare images at known dimensions

## Figma-to-UI conformance

When comparing to Figma:

1. Confirm Figma file/frame is current and approved.
2. Export the exact frame/state/node.
3. Match viewport dimensions to the Figma frame.
4. Set browser zoom/device scale factor consistently.
5. Use the same content or consciously accept content differences.
6. Mask regions with live data or generated media.
7. Use diff output as evidence, then inspect impacted regions.

## Dynamic content masking

Usually mask:

- avatars and user-uploaded media
- timestamps, dates, counters, and live metrics
- ads, maps, random illustrations, charts with live data
- cursor/caret and text selection
- skeleton shimmer or loading animation
- personalized names when the reference uses fake data

Do not mask:

- primary CTA alignment
- content that should match fixed design copy
- layout containers causing overflow
- state indicators that should be implemented
- broken images or missing icons

## Threshold guidance

Raw diff ratio is a triage signal:

- `0–0.5%`: likely acceptable, inspect high-impact areas.
- `0.5–2%`: inspect layout, typography, color, and asset regions.
- `2–5%`: likely major unless explained by known dynamic content.
- `>5%`: likely blocker for stable regression; for Figma conformance, inspect whether data/content mismatch dominates.

Never use raw percentage alone. A tiny diff on a destructive CTA or price value may be more important than a large diff in a decorative image.

## Common false positives

- subpixel anti-aliasing
- OS/browser/font rendering differences
- font fallback or missing font weights
- Figma shadow/blur/gradient/blend-mode differences
- scrollbars present in one environment
- line wrapping from real content vs mock data
- image compression or CDN transforms
- dynamic content not masked
- sticky headers captured at different scroll positions

## Meaningful failure patterns

Report findings for:

- missing or extra visible element
- wrong page hierarchy or CTA emphasis
- wrong semantic color or status state
- layout shift, overflow, clipping, or broken wrapping
- typography scale or line-height mismatch affecting readability
- spacing/density mismatch changing grouping
- wrong asset, icon size, crop, or aspect ratio
- state missing from screenshot or interaction flow
- responsive layout diverging from design intent

## Diff explanation template

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

## Baseline policy

Update baselines only when:

- the visual change is intentional
- design owner or reviewer has approved it
- the new baseline is generated in the same deterministic environment
- the report explains what changed and why

Do not update a baseline to hide a regression.
