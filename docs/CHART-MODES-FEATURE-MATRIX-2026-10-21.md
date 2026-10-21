# Chart Modes & Price Adjustment — Feature Preservation Matrix (Round 8)

Date: 2026-10-21
Scope: every chart surface in the BorsTerminal frontend, the two price-series
bases, the three axis scales, and the effect of mode changes on candles,
indicators and drawings.
Status: research only. No chart/redesign code was changed in this round. Live
UI combinations are marked BLOCKED because the local app requires a login and
this mission must not ask for or use account credentials.

Evidence legend:
- CODE: proven from the current source (file:line).
- TEST: proven by an existing automated test.
- BLOCKED: requires the owner to log in to the local app; no credential is
  requested or stored by the agent.
- UNVERIFIED: implemented but not yet measured end-to-end.

## 1. Surfaces and engines

| # | Surface / route | Engine | Price-basis control | Scale control | Data source | Evidence |
|---|---|---|---|---|---|---|
| 1 | Technical page `/technical/:symbol?` — main chart | KLineCharts (klinecharts v10) | Two options: `combined` (functional) and `none` (raw) | normal / logarithm / percentage | `/api/chart/{symbol}` raw OHLC + server `factors`; basis applied client-side | CODE: `frontend/src/features/technical/nahayatnegar/lib/adjustments.ts:38`, `FtsToolbar.tsx:113`, `KLineChartWrapper.tsx:555` |
| 2 | Technical page — second engine | FFC (FastFinancialCharts) | Fixed `combined`; no dropdown (deliberate) | normal / logarithm via shared `priceScale` | same `/api/chart` bars, already in the `combined` basis | CODE: `adjustments.ts:80`, `FtsEngineChart.tsx:200`, `FtsEngineChart.tsx:227` |
| 3 | Market status page — advanced chart | same KLineChartWrapper | same two options | same three scales | same `/api/chart` | CODE: `MarketChartSection.tsx:28`, `:103` |
| 4 | Engine lab `/engine-lab` | KLineCharts + FFC side by side | feed used as-is (combined); no basis toggle | log capability compared in the capability matrix | one `/api/chart` fetch shared by both panes | CODE: `EngineLabPage.tsx:43`; TEST: capability matrix row |
| 5 | Market compare chart | custom SVG | none (series normalized to 100 at first common date) | percentage / logarithmic (`pct` / `log`) | `/api/chart` candles, normalized per series | CODE: `MarketCompareSection.tsx:88`, `:178`, `:259` |
| 6 | Portfolio watch mini charts | custom SVG | none | none | `/api/chart/{symbol}` candles, plotted directly | CODE: `WatchMiniChart.tsx:29-32`, `useWatchCandles.ts:51` |
| 7 | Master strategy canvas | custom SVG canvas | none | free zoom/pan only | strategy shapes, not a price series | CODE: `StrategyChartCanvas.tsx:24`, `:43` |
| 8 | Sparklines / micro charts | custom SVG | none | none | small trend lines | CODE: `Sparkline.tsx`, `MicroChartsDrawer.tsx` |

Notes:
- Surfaces 5–8 are not full OHLC charts; their missing basis control is a
  scope limitation, not a silently removed feature. Surface 6 must not be
  described as `combined` while plotting raw candles; that claim needs live
  verification.
- Surface 2 deliberately hides the basis dropdown because its data contract
  does not expose a raw series; the on-canvas label states the basis
  (`FFC_ADJUSTMENT_BASIS_LABEL`). Do not add a fake control there.

## 2. Independent dimensions (do not conflate)

| Dimension | Values | What it changes | What it must not change |
|---|---|---|---|
| Price basis | `none` = raw table prices; `combined` = raw × server cumulative factor | Historical OHLC before each event, and every price-based indicator | Volumes (already proven equal for raw/type7 in the reference corpus), timestamps, event markers |
| Axis scale | `normal` (linear), `logarithm`, `percentage` | Only the y-axis projection; no series values | Candle values, indicators, drawings' stored coordinates |
| Display aggregation | daily / weekly / monthly | Aggregation after basis is applied | Basis or scale semantics |

`logarithmic` is **not** a price basis and must never be counted as an
adjustment mode. `percentage` is a third axis scale (display), not a third
basis.

## 3. Combination matrix (main chart)

| Basis | Scale | Supported? | Behaviour | Evidence |
|---|---|---|---|---|
| `none` | linear | YES | raw OHLC, raw prices on axis | CODE: `applyAdjustmentToCandles` returns a copy for `none` (`adjustments.ts:334-336`); scale `normal` (`KLineChartWrapper.tsx:1468-1471`) |
| `none` | logarithmic | YES | same raw series, log projection | CODE: same basis path; `applyAxisOverride(chart, 'logarithm')` (`KLineChartWrapper.tsx:1474`) |
| `combined` | linear | YES (default) | raw × factor; default opening mode | CODE: `DEFAULT_ADJUSTMENT_MODE='combined'` (`adjustments.ts:72`); default scale `normal` (`ftsConfigStore.ts:194`) |
| `combined` | logarithmic | YES | same adjusted series, log projection | CODE: same two independent paths |
| `combined` | percentage | YES | adjusted series projected as percentage from the first visible value | CODE: `priceScale` union and `percentage` branch (`KLineChartWrapper.tsx:1468-1471`) |
| FFC `combined` | linear / log | YES | no basis control; scale shared with main chart | CODE: `FtsEngineChart.tsx:200`, `:227` |
| Compare `normalized` | pct / log | YES | normalized compare series; no OHLC basis | CODE: `MarketCompareSection.tsx:88` |

Not supported, by design:
- A separate DPS-only or capital-only basis. The server provides one combined
  ratio per event; splitting it needs event-type data the bank does not have
  (`adjustments.ts:3-12`).
- A true reinvested-performance basis in the browser. `functionalAvailable`
  and `functionalBlockers` come from the server; the UI shows the blocker note
  instead of claiming a mode it cannot render (`KLineChartWrapper.tsx:496-502`).
- Arbitrary basis × engine combinations on the FFC panel; the FFC contract has
  no raw series.

## 4. Tool impact

| Tool | Series it uses | On basis change | On scale change | Evidence |
|---|---|---|---|---|
| Candles / OHLC | `renderCandles` = adjusted `displayCandles`, aggregated after basis | Recomputed from raw × factor; volume unchanged | No value change, only y projection | CODE: `KLineChartWrapper.tsx:555-567`, `:1525-1528`; TEST: adjusted-series test (`technical-settings-effectiveness.spec.tsx:209-237`) |
| Standard indicators (MA, EMA, BOLL, RSI, MACD, VOL…) | Injected candle series (`renderCandles`) | Recompute on the selected basis (they follow the chart series) | No recomputation; projection only | CODE: `chart.createIndicator({name, paneId:'candle_pane'})` (`KLineChartWrapper.tsx:2520-2528`) |
| FTS layers (levels, patterns, structure) | Server analysis values in raw rials, mapped to chart price space with `refClose`/factor | Mapping keeps the layer anchored; the raw analysis is not recomputed | No value change | CODE: `engineFtsLayers.ts:21`, `ftsOverlays.ts:558`, `KLineChartWrapper.tsx:1618-1718` |
| Drawings (lines, channels, Fib, markers) | Stored overlay points `{timestamp, value}` | **No basis conversion**: restored values are used as-is; a drawing made in `combined` will sit at a different raw price after switching to `none` | Points unchanged; only projection changes (expected) | CODE: `applySnapshot` (`KLineChartWrapper.tsx:864-874`), storage keyed by symbol only (`drawStore.ts:26-62`) |
| Fib retracement special case | Chart drawings | Same as drawings | A separate `fibLogarithmic` render setting exists; it is not the chart scale | CODE: `ChartSettingsDialog.tsx:416-418` |
| Compare chart series | Normalized closes | Not applicable (no basis control) | Recomputed normalization/projection | CODE: `MarketCompareSection.tsx:178-225` |

## 5. State, persistence, and stale data

| Item | Current behaviour | Evidence |
|---|---|---|
| Basis selection visibility | Toolbar shows the active label (`عملکردی…` / `خام…`) and the description | CODE: `FtsToolbar.tsx:113-131` |
| Basis persistence across reload | Not persisted directly: `activeAdjustment` is component state initialized to `combined`; only a chart template can carry an `adjustment` value | CODE: `KLineChartWrapper.tsx:414`, `chartTemplateStore.ts:15`, `:112`, `:2136` |
| Scale persistence | Persisted in `fts.chart.settings.v1` via `setPriceScale` | CODE: `ftsConfigStore.ts:315-319` |
| Symbol / timeframe / basis change | Data reloads; scale lock is released; indicators are reattached | CODE: `useEffect` deps (`KLineChartWrapper.tsx:1495-1501`) |
| Drawing restore after symbol/timeframe change | Restored from symbol/keyed store; no adjustment key | CODE: `KLineChartWrapper.tsx:884-899` |
| Drawing restore after basis change | Same store; no conversion | CODE: as above; **risk** |
| Functional capability note | Server-driven note and blocker counts are displayed under the chart | CODE: `KLineChartWrapper.tsx:496-502`; TEST: `technical-settings-effectiveness.spec.tsx:240-252` |

## 6. Findings / gaps (not fixed in this round)

1. **Drawings do not carry a basis.** The store key is `fts.drawings.v1.{symbol}`
   and the overlay points are raw price values. Switching `combined ↔ none`
   changes the visual position/meaning of a drawing. Needs live confirmation
   and, before any redesign, an explicit decision: either store drawings in a
   basis-neutral space (e.g., factor-relative) or convert on switch.
2. **Basis selection is not persisted outside a template.** The scale is
   persisted, the basis is not. The mandate asks for a clear and (if needed)
   retained selection; the current UI is clear but not retained on reload.
3. **Standard indicators follow the selected basis; FTS layers stay raw.**
   This is internally consistent (price indicators on price series; FTS values
   mapped to the display), but the UI must state it. A redesign must not
   compute both on the same series silently.
4. **Mini charts plot raw candles with no basis label.** The main chart
   defaults to `combined`; the watch mini chart calls `/api/chart` and draws
   `candles` directly. Either label them as raw or apply the same factor.
   Code-level finding; live visual check pending.
5. **Log scale is independent, but a `fibLogarithmic` setting also exists.**
   A redesign must not merge the chart scale with the Fib tool's own
   logarithmic rendering setting; they are different controls.
6. **FFC has no basis dropdown by design.** Do not add a control that cannot
   change the series; keep the on-canvas basis label.

## 7. Live test plan (blocked on local login)

Once the owner logs in to the local app in the provided browser tab, the
following must be measured and recorded (no credentials in chat/files):

1. Load one symbol with a known DPS/capital event (e.g., فولاد or حخزر) in
   `combined` / linear; record the OHLC at the event date and the axis range.
2. Switch to `none` / linear; record the same OHLC; verify the raw series and
   that volume/timestamps did not change.
3. Switch to `combined` / log and `none` / log; verify the axis projection and
   that OHLC values are unchanged by the scale.
4. Draw a horizontal line and a channel in `combined`; switch to `none`;
   verify whether the drawing remains at the same price/time or shifts.
5. Add MA(20) and RSI; switch basis; verify whether the indicator recomputes
   on the new series and whether the legend announces the basis.
6. Switch symbol/timeframe and back; verify the mode and scale state, stale
   data, and drawing restore.
7. Repeat on the market-status advanced chart (same engine) and the FFC panel
   (no basis control; scale only).

Until this plan is executed, the live status of items 1–7 is **BLOCKED** /
**UNVERIFIED**, not "passing".

## 8. Design constraints for a future proposal

- Keep both bases visible as two explicit choices; never hide `none` behind a
  menu that looks like a scale control.
- Keep linear/log as a separate control with its own label; never use log as
  a proxy for adjustment.
- Show the active basis and scale together in a persistent status line.
- If drawings are basis-sensitive, either convert them or warn the user
  before switching; do not move user drawings silently.
- Preserve the server-driven `functionalAvailable` / blocker note; do not
  replace it with a generic "adjusted" badge.
- If a chart surface cannot support a mode, state the limitation on that
  surface rather than removing the mode globally.
