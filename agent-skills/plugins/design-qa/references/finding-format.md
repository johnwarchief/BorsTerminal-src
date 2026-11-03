# Design QA Finding Format

Use this guide to keep findings consistent, actionable, and easy to convert into tickets or patches.

## Finding fields

Each finding should include:

```markdown
### [<severity>] <category>: <short title>
- ID: <stable id if available, e.g. DQA-001>
- Screen/route:
- Component/selector:
- Evidence:
- Observed:
- Expected:
- Impact:
- Recommended fix:
- Verification:
- Owner: <design | frontend | design-system | content | unknown>
```

## Field guidance

### Evidence

Prefer concrete evidence:

- file path and line reference
- selector or component name
- expected/actual/diff image path
- JSON report path and finding id
- design token or component rule
- Figma node/frame name

Weak evidence like “looks off” is not enough unless no stronger evidence exists, and then it must be labeled as subjective/manual.

### Observed

Describe what exists now, without mixing in the fix.

Good:

```text
Primary CTA uses `bg-[#1d4ed8]` and 6px radius in `src/app/checkout/CheckoutActions.tsx`.
```

Weak:

```text
Button is bad.
```

### Expected

Tie expected behavior to the strongest available design source.

Good:

```text
`DESIGN.md` defines primary buttons as `{colors.primary}` with `{radii.md}` and focus-visible outline using `{colors.focus}`.
```

### Impact

Explain why the issue matters:

- design approval risk
- user task failure
- accessibility barrier
- component-system drift
- future maintenance cost
- mismatch with approved design reference

### Recommended fix

Make it implementable:

- use a specific token
- switch to a shared component
- add a component variant
- update a state story/test
- adjust layout rule
- update approved baseline only after design sign-off

### Verification

Describe how to confirm the fix:

- re-run a script
- inspect a screenshot/diff
- test keyboard path
- check Storybook state
- confirm `DESIGN.md` lint passes
- ask design owner to approve an intentional change

## Report shape

Use this structure for a full Design QA report:

```markdown
# Design QA Verdict: <Pass | Pass with warnings | Fail | Inconclusive>

## Summary

## Evidence Reviewed

## Blockers

## Major Issues

## Minor Issues

## Design Debt

## Acceptable Differences

## Needs Design Decision

## Automation Artifacts

## Verification Checklist
```

## Verdict rules

- `Fail`: at least one blocker, or multiple major issues that undermine the design intent.
- `Pass with warnings`: no blockers, but minor/major/debt findings remain and are acceptable for this release.
- `Pass`: no blocking or material issues and evidence quality is strong.
- `Inconclusive`: reference, route, screenshots, or implementation evidence is insufficient.

## Ticket-friendly labels

When turning findings into tickets, use labels like:

- `design-qa:blocker`
- `design-qa:visual`
- `design-qa:a11y`
- `design-qa:components`
- `design-qa:debt`
- `design-qa:responsive`
- `needs-design-decision`
