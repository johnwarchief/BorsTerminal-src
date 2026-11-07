# Owner expectations — explicit test cases

These are the owner's stated expectations for the FTS experience. Use them as
test cases in every critique. If one conflicts with the booklet, report both and
mark the conflict; never silently drop either.

## From the owner's critique brief (2026-11-04)

1. **EPS per-period growth:** for each period, show how much EPS grew and by what
   percentage. A single 3-year trend arrow or a `3/3` count is not enough.
2. **Indicator 1 correctness:** 1a and 1b must each be checked and shown
   separately and correctly; the combined verdict must be explainable.
3. **Indicator 1 period detail:** show this period's sales/revenue and the
   previous comparable period, in addition to the growth percentage.
4. **Theme:** light/dark must follow the app theme. Do not maintain a separate
   data-surface theme (the owner rejected the split paper/ink surface for this
   product).
5. **Indicator 4 naming:** «پتانسیل سود تا آخر سال». The headline number must be
   the final potential-profit percentage produced by the formula, not merely the
   sales/market-cap ratio.
6. **Indicator 3 naming:** «حاشیه سود ناخالص» (gross profit margin), not a
   shortened «حاشیهٔ ناخالص» where the screen is supposed to name the indicator.

## Booklet / owner-ruling anchors to verify (do not treat this summary as a substitute)

### F-01 — sales/revenue growth
- Booklet page 3: growth versus the same period last year; owner ruling #3:
  **floor 40%**, **target 60%** (inflation coverage).
- 1a = monetary sales growth; 1b = real/volume growth is an implementation
  addition (owner ruling #9 discusses the tonnage/real effect). 1b is applicable
  to goods producers; banks/services/holdings are N/A for physical tonnage.
- Show current and previous cumulative sales amounts and the percentage.
- Do not use a fabricated 1b threshold; use the configured/source value and mark
  ambiguity.

### F-02 — 3-year EPS trend
- Booklet page 4: `EPS(t-2) < EPS(t-1) < EPS(t)` and all positive; audited
  year-end statements, non-consolidated preferred. Consolidated-only history is
  a data gap/N/A, not a rejection.
- Owner expectation: per-period EPS and period-over-period growth percentages.
- Show years available/required and the evidence (audited/consolidated/interim).

### F-03 — gross profit margin
- Name: **«حاشیه سود ناخالص»**.
- Formula: `Gross_Profit / Operating_Revenue × 100`.
- Owner ruling #2: floor **20%**, standard **30%**; booklet page 4 also says
  above 30% is required and above 50% is good. Net margin is explicitly not the
  target.
- Show the gross profit and revenue inputs.

### F-04 — profit potential to year-end
- Name: **«پتانسیل سود تا آخر سال»**.
- Headline: the final potential-profit percentage from the booklet page 5
  formula (annualized sales × gross margin ÷ market cap); show the sales,
  annualization months, gross margin and market-cap inputs.
- Owner ruling #4: annualize `YTD × 12 / months`; sales/market-cap floor
  **0.33**, ideal **1.0**. The configured potential threshold (currently 40%)
  must come from config/source; do not invent it.
- The sales/market-cap ratio is secondary evidence, not the headline.

### F-05 — industry pricing regime
- Booklet page 6: four axes (company type, pricing type, rial/dollar, outlook).
- Mandatory-pricing sectors per booklet: **خودرو و قطعات، نیروگاه، لاستیک**.
  Insurance is a separate hard veto. دارو and غذا are allowed, not mandatory.
- Do not present an implementation addition as a booklet rule.

## User-experience expectations

- Every axis answers: rule, threshold, inputs, computed value, distance to
  threshold, status, and **why**.
- Unknown/data-gap is visually and verbally distinct from fail; never zero-fill.
- The screen is understandable without the booklet; the booklet is the audit
  reference, not required reading for the user.
- Numbers are Persian and formatted consistently; no raw English enums or
  Latin-digit timestamps in the Persian surface.
- Both app themes are readable; status is not carried by color alone.

## How to use these expectations

For each item, record `PASS`, `FAIL`, or `NOT TESTED` with evidence. A failure
here is at least **Major**; a wrong formula/threshold/number or a missing 1a/1b
is **Blocker**. A pure wording preference is **Minor** unless the owner named it
explicitly (names #5/#6 are explicit).
