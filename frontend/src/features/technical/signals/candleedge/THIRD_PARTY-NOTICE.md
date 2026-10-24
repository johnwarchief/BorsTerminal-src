# Third-party notice — CandleEdge

This directory contains TypeScript ports of analytical functions from:

- **Project:** CandleEdge — Market Structure & Pattern Probability Scanner
- **Repository:** https://github.com/michaelsboost/CandleEdge
- **Reviewed commit:** `75761e26b23ccaf59b31365e1ec817374673d77b`
  (2026-05-25, "feat: expand CandleEdge pattern engine, validation logic, chart structures, caching, and documentation")
- **Source file:** `src/script.js` (1,547 lines)
- **License:** MIT — Copyright (c) 2026 Michael Schwartz
- **License copy:** [`LICENSE-CANDLEEDGE`](./LICENSE-CANDLEEDGE)

## Ported functions and source ranges

| BorsTerminal file | CandleEdge source | Functions |
|---|---|---|
| `candleMath.ts` | `src/script.js:115-123,149-155` | `isUptrend`, `isDowntrend`, `candleParts` |
| `candlePatterns.ts` | `src/script.js:171-174,197-207,227-233,251-257` | `isDoji`, `isBullishEngulfing`, `isBearishEngulfing`, `isHammer`, `isShootingStar` |
| `swings.ts` | `src/script.js:409-422,424-436` | `findSwingPoints`, `findLocalExtrema` |
| `structurePatterns.ts` | `src/script.js:442-446,461-525,558-576,579-638,929-947,949-965,967-1001` | `percentSlope`, five triangle/wedge detectors, pullback/bounce validators, double top/bottom, BOS, liquidity sweeps, HH/LL/HL/LH |
| `scanner.ts` | `src/script.js:1025-1143` (orchestration idea only) | event orchestration with confirmation metadata (rewritten, not copied) |

## Modifications (documented in `docs/technical-indicators/reviewed/CANDLEEDGE-REUSE-AUDIT-2026-10-25.md`)

1. JavaScript converted to strict TypeScript; presentation fields (`name`, `icon`, `status` strings) removed and replaced with detector ids, families, and biases.
2. Every swing carries `confirmedAtIndex`; the scanner emits each structure event once, at the bar where its evidence completes.
3. Bullish/bearish BOS is evaluated at the confirmation bar of the new swing. The upstream condition `recentHigh.index === idx` (lines 933/943) can never be true with its own slice (line 1077-1078), so the upstream detector never fires. The 0.5% threshold is compared as a relative change; the upstream multiply form made the exact boundary pass on one side and fail on the other because `100 * 1.005 = 100.49999999999999`.
4. Liquidity sweeps use the latest confirmed swing level. Upstream used the second-to-last (`swings.highs[length-2]`, lines 951/960), skipping the freshest level.
5. A provisional tail scan was added for swings whose right window is not complete; it is reported separately and is never an event.
6. Double top/bottom are emitted once per confirmed pair instead of repeating on each bar inside the 20-bar recency window.

## Not copied

The application shell, HTML templates, CSS/Tailwind, Alpine.js component, websocket feed,
lightweight-charts and its plugins, PapaParse, service worker, CSV fixtures, images, and the
bundled `dist/` output are not part of this directory. No npm dependency was added.

CandleEdge's descriptive statistics engine (`src/script.js:12-109`) was reviewed and **not**
transferred; the reasons are recorded in the audit report.
