# RA365 Parity Contract — version 1.0 (Round 26)

**Date:** 2026-10-24  
**Scope:** BorsTerminal raw OHLCV and performance-adjusted candles vs Rahavard365.  
**Rule:** thresholds, denominators, cohort membership and comparison rules are frozen here; they may not be changed to improve a percentage.

## 1. Sources and snapshots

| Side | Artifact | Timestamp | SHA-256 | Coverage |
|---|---|---|---|---|
| Reference | `ref_bars_v2.jsonl` | 2026-10-20 | `4b1ecb4c1effc4d5770c…` | 2,595 assets × {type0,type7} × {D,W} = 10,388 series |
| Product (frozen) | `product_live_final_v4.jsonl` | 2026-10-20 | `893b6d6aa1059d51a83b…` | 3,344 product lines (2,595 cohort symbols + aliases/variants) |
| Manifest | `cohort.jsonl` (Round 18) | 2026-10-22 | 277,500,847 bytes | 2,595 assets: `ra_asset_id`, `symbol`, `ins_code`, `basis`, `adjust_source` |
| Product (current, 50) | `product_rows2/` (Round 24 frozen) | 2026-10-24 03:54 | `artifacts/ra365/r25/evidence-sha256.txt` | 50 symbols × D/W/M reference (`r23_ref_50`) |
| Monthly reference | `ra365_r23_ref_50.json` | 2026-10-23 20:19Z | `52d94284…` | 50 assets, D/W/M |

Snapshots are never mixed inside a comparison. The 2026-10-23 50-symbol reference is a **revision sample** used only for the current-code 50-symbol cohort; the 2026-10-20 full-universe corpus is the full-universe baseline.

## 2. Instrument identity

- Stable key: `ra_asset_id` ↔ `symbol` ↔ `ins_code` from the cohort manifest.
- Symbol normalization for joining: strip whitespace, Arabic `ك/ي/ى` → Persian `ک/ی`.
- Unmatched assets are counted, never silently dropped. Full-universe adjusted: 1,964/2,595 paired; 631 reference assets have no matching product line (alias/coverage) and are reported separately.

## 3. Raw comparison (two distinct metrics)

### 3-1. Exact raw-field equality (literal)
Product field equals reference field with `|d| ≤ 1e-9` for prices and volume. No widen, no basis substitution, no tolerance.

### 3-2. Tolerance raw equality
Price `|d| ≤ max(0.5, 1e-6·|ref|)`; volume `|d| ≤ 1`.

### 3-3. Contractual raw equality (the historical R18/R19 contract)
- Product `open` = FIRST trade of the session (clamped into `[low,high]` when FIRST is zero/out of range); fallback to adjusted base then close.
- Product `high/low` = `widen(open_eff, parser_high, parser_low, close)` so the body is contained; displayed variants use `high_raw/low_raw` only for diagnostics.
- `close_official` = official closing (`closing`); `close_last` = last trade (`last`, when positive); `close_display` = the cohort's price basis (`last` or `closing`).
- Reference `type0.close` is compared to **both** `close_last` and `close_closing`; the contract row requires the documented field set: `open_eff`, `high_contract`, `low_contract`, `close_official` (+ `volume` non-null).
- Weekly: Saturday buckets (`(day-2)//7`); open = first, high = max, low = min, close = last, volume = sum, stamp = last trading day.
- Monthly: Jalali month buckets (`jy*12+(jm-1)`); same OHLCV aggregation; product stamp = last trading day; reference monthly stamp is the first day of the Jalali month; pairing is by month key, not stamp.
- Literal raw metrics are reported separately and never substituted for the contractual ones.

## 4. Performance-adjusted comparison

- Factor definition: `factor(t) = ∏ ratio_e` over events with `effective_date > t`; anchor: last candle factor = 1. Ratios ≤ 1 for downward adjustments.
- Product adjusted price = product displayed raw price × factor(t).
- Factor exact: `|d| ≤ 1e-9`; factor tolerance: relative `1e-6`.
- Adjusted exact/tolerance: same price rules as §3-1/3-2, applied to adjusted OHLC.
- Event identity: `(asset, effective_date, source, kind)`; same-date multi-row official PA rows are grouped into one combined event by product of ratios; DPS base = the effective candle's official close; combined share+DPS and share-leg dedupe follow the Round 25 rules.
- Factor-chain parity, adjusted OHLC parity and raw parity are reported separately; none is inferred from another.

## 5. Denominator, coverage and missing bars

- Denominator = common paired dates per series, plus explicitly counted reference-only and product-only bars.
- Reference-only / product-only bars are never deleted to raise a percentage.
- Missing categories: product no-trade bars (reference has a bar, product marks no trade), product missing (reference bar absent from product), reference missing (product bar absent from reference), outside reference history.
- Coverage is reported per timeframe and per asset class; a series with <10 paired rows is listed as NOT_COMPARABLE, not excluded silently.
- Current 50-symbol cohort denominators: 126,961 D and 29,668 W paired rows (50); 38,463 / 8,893 (14); 87,293 / 20,484 (31); 39,668 / 9,182 (holdout); monthly 7,316 (50).

## 6. Revisions and incomplete feeds

- Both sides carry snapshot timestamps; comparisons never mix revisions.
- The TSETMC live CSV may flip between revisions per request (measured Round 24/25: 1577↔1576 rows). A shorter response is treated as a partial feed; new unproven base gaps are `provisional:partial-feed` and are not applied or cached.
- A revision that is real and stable is reported as `HISTORICAL_REVISION`, not as a product defect.
- Reference-only events are never imported into production without independent evidence.

## 7. Explicit non-goals

- Literal 100% raw equality is **not** assumed achievable while the product's raw history comes from TSETMC and the reference from Rahavard. The contract measures the gap; it does not hide it.
- Changing the production raw source, tolerances, denominators or cohort membership requires the owner's explicit approval.
