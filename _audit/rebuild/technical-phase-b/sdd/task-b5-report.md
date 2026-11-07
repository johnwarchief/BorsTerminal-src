# Task B5 report — unslop pass on the new chrome + visual acceptance

**Status:** complete (local only, no push)
**SHA:** `71479436` — `feat(technical): پاس unslop و پذیرش بصری میزکار`
**Branch:** `integration/4axes-main-2026-11-03`
**Parent:** `fbd6f30e`
**Brief:** `.superpowers/sdd/2026-11-05-technical-workspace-phase-b/task-b5-brief.md`

## What changed

### 12px floor (chrome + feed + panels)

- `workspace/ActiveEventCard.tsx` — tier-2 pill: `text-[11px]` → `text-xs`, `px-1.5 py-0.5` → `px-2 leading-5`, `rounded-full` → `rounded-[var(--radius-md)]`, `shrink-0` + wrap-safe header so the pill cannot be squeezed in the 240px rail. `<b>` headings replaced with size/medium hierarchy. Card is now the Tab stop for the rail (`tabIndex={0}`, `aria-label`, `focus-visible` outline).
- `workspace/ActivityBar.tsx` — 4px radius, explicit `focus-visible` outline. (The reported `gap-1.5` was already `gap-2` at HEAD; the test now enforces no half-step utilities.)
- `workspace/WorkspaceTopbar.tsx` — all four controls unified on `h-9` (36px) with `h-7` (28px) inner controls; removed the `h-9`/`h-10` mix, `px-1.5`, `h-6`; `font-semibold` → `font-medium`; focus-visible on submit/timeframe/select; 4px radii.
- `workspace/EventFeed.tsx` — feed tabs/toggle/portal trigger have focus-visible + 4px radii; portal header `py-2.5` → `py-2`, `font-bold t-12` → `text-xs font-medium`; text «✕» replaced with an SVG close icon; dialog radius 12px; feed body `h-80` → `h-[min(20rem,40vh)]` (the B1 comment assigned responsive feed height to B5).
- `workspace/InspectorRail.tsx` — toggle badge off-grid padding fixed, focus-visible, 4px radii.
- `ScannerFeed.tsx` — tier badge `text-[11px] px-1` → `text-xs px-2 leading-5` + 4px radius + `shrink-0`; `<b>` headings → size/medium; row buttons get focus-visible.
- Panels (`Top50Panel`, `IndicatorsPanel`, `TelegramCatalogList`, `CandleEdgeCard` via `EdgePanel`) — all sub-12px `t-8/t-85/t-9/t-95/t-10/t-11` and `text-[10px]/[11px]` raised to `text-xs` (≈92 tokens). This is the census scope the brief asked for; panel spacing/A11y beyond the text floor was left untouched.

### Responsive chart share (1366 ≥ 60%)

With the app sidebar expanded (208px), the spec grid `40 | 1fr | 280` gave a **796px** chart at 1366 → 58.3%, below the acceptance floor. `WorkspaceShell` now reads columns from `--ws-grid-columns` (fallback = the §3 string) and `styles.css` narrows the rail to **240px below 1441px**. At 1920 the spec 280px rail is unchanged. Formula at 1366: `1366 − 208 sidebar − 40 activity − 40 drawing toolbar − 240 rail = 838` stage / **836px wrapper = 61.2%**.

### New test — `ui/workspace/__tests__/WorkspaceVisual.test.tsx` (8 cases)

1. DOM census (class-derived effective font size, inherited): every own-text node under `workspace-topbar|activity|rail|feed` on **all four tabs** ≥ 12px, including the tier-2 pill.
2. Portal census ≥ 12px.
3. No `font-bold`/`font-extrabold` in `ui/workspace/**` non-test sources.
4. No half-step spacing utilities (`gap-1.5`, `px-1.5`, `py-0.5`, `p-2.5`, …) in workspace sources + `ScannerFeed`.
5. Topbar controls all `h-9`, inner timeframe buttons `h-7`.
6. Activity buttons, feed tabs and the rail card carry `focus-visible:`.
7. Exactly one `aria-current="true"` activity section, following clicks.
8. Tab-order model: activity bar → rail card → feed tabs, all tabbable (`tabIndex ≤ 0`), no positive tabindex. *jsdom cannot move focus on Tab; this asserts tabbability + DOM order. Real Tab was verified in Edge (below).*

## Verification

| Check | Result |
|---|---|
| `npx tsc --noEmit` | clean |
| `npm run build` | success (only the pre-existing >500 kB chunk warning) |
| Full suite `npx vitest run` | **777 passed / 777** (93 files); baseline 769 + 8 new |
| Live acceptance script | `D:/BorsTerminal-tmp/s4b-browser/b5-workspace-acceptance.js` |

Servers: backend `BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data python -m uvicorn app:app --host 127.0.0.1 --port 8110`; dist `cd D:/BorsTerminal-tmp/s4b-browser && PORT=7093 node serve-dist.js`; Edge headless via playwright-core. Both started by this task and stopped only after evidence was written.

Acceptance route: `#/technical/وبملت` (نماد فولاد had no forming pattern at capture time; وبملت gives a populated rail card and 20 scanner rows).

### Measurements (`acceptance.json`)

| Viewport / theme | chart wrapper | ratio | rail | feed body | horizontal scroll |
|---|---|---|---|---|---|
| 1366×768 brass | 836px | **0.6120** | 240px | 307px | 1366 = 1366 ✅ |
| 1366×768 warm | 836px | **0.6120** | 240px | 307px | 1366 = 1366 ✅ |
| 1920×1080 brass | 1350px | **0.7031** | 280px | 320px | 1920 = 1920 ✅ |
| 1920×1080 warm | 1350px | **0.7031** | 280px | 320px | 1920 = 1920 ✅ |

`document.documentElement.scrollWidth <= clientWidth` held after every tab on every viewport/theme (16 checks + 4 shell checks).

### Live 12px census (computed `font-size` in Edge)

| Combo | events | top50 | indicators | edge | portal |
|---|---|---|---|---|---|
| 1366 brass | 137 nodes / min 12 / 0 off | 392 / 12 / 0 | 321 / 12 / 0 | 57 / 12 / 0 | min 12 / 0 |
| 1366 warm | 137 / 12 / 0 | 392 / 12 / 0 | 321 / 12 / 0 | 57 / 12 / 0 | min 12 / 0 |
| 1920 brass | 137 / 12 / 0 | 392 / 12 / 0 | 321 / 12 / 0 | 57 / 12 / 0 | min 12 / 0 |
| 1920 warm | 137 / 12 / 0 | 392 / 12 / 0 | 321 / 12 / 0 | 57 / 12 / 0 | min 12 / 0 |

### Feature-preservation checklist

- [x] events tab opened (`scanner-panel`, 20 `pattern-row-*`, `pattern-rules`)
- [x] top50 tab opened (`top50-panel`)
- [x] indicators tab opened (`indicators-panel`)
- [x] edge tab opened (`edge-tab-panel`)
- [x] portal opened (`portal-modal-backdrop`, selected edge panel inside, closed by button; Escape covered by unit test)
- [x] drawing toolbar visible (`drawing-toolbar` 40×627)
- [x] forecast controls visible (`forecast-controls` 1158×36)
- [x] scanner rows present (20)
- [x] rail card present and populated (`pattern-card`: «سر و شانه … کیفیت ساختار ۹۰ …»)
- [ ] scanner pullback/CHoCH events: **0** in this data snapshot (no rows to show; panel/rules still render)

### Keyboard (real Edge Tab, 140 presses, 1366 brass)

- Activity bar reached at stop **25** (all four: chart/scanner/indicators/settings), `:focus-visible` true.
- Rail card (`pattern-card`, section, `aria-label`) at stop **54**, `:focus-visible` true.
- Feed tabs at stop **55** (all four), `:focus-visible` true.
- No positive tabindex; order is DOM order (activity → rail card → feed tabs).

### Console / network errors

- Console: exactly one unique message — `Failed to load resource: the server responded with a status of 404 (Not Found)`.
- Page errors: none.
- HTTP 404s (known, pre-existing, reported not hidden), 6 responses across the run:
  - `/api/chart/وبملت/forecast` ×2
  - `/api/chart/وبملت/edge` ×2
  - `/api/chart/وبملت/indicators` ×2

### Evidence

Directory: `_audit/rebuild/technical-phase-b/2026-11-06/` (untracked, not committed)

- `acceptance.json` — full measurements, per-tab census, keyboard stops, checklist, errors
- 4 shells: `shell-{1366x768,1920x1080}-{brass,warm}.png`
- 16 tabs: `tab-{events,top50,indicators,edge}-{1366x768,1920x1080}-{brass,warm}.png`
- 4 portals: `portal-{1366x768,1920x1080}-{brass,warm}.png`
- 1 extra card close-up: `rail-card-1366-brass.png`

## Concerns / untested

- **Rail narrows to 240px below 1441px** — intentional to satisfy the ≥60% chart floor at 1366 with the expanded app sidebar. At 1920 the §3 280px rail is unchanged. If the product insists on 280 everywhere at 1366, either the app sidebar must default collapsed or the 60% floor must be relaxed.
- **`ForecastControls` and `DrawingToolbar` still carry sub-12px typography** (e.g. `t-8`/`t-9`). They are pre-existing chart chrome inside the chart stage, outside the agreed census scope; changing them would be a separate chart-scale pass.
- **App sidebar / topbar / market surfaces** also still use <12px type; out of the workspace scope.
- **Tier-2 pill live state is detection-dependent**: at capture time وبملت's forming pattern was tier 1, so the card's pill is covered by the unit census with a tier-2 pattern and visually by the scanner rows' «کم‌بسامد» badges; no dedicated live screenshot of the rail pill.
- **No Firefox/Safari run**; Edge (Chromium) only.
- **No pixel-diff baseline**; acceptance is measurement/screenshot/manual review.
- The 404s mean forecast/edge/indicators panels fall back to empty/derived states by design (pre-existing); the edge card still renders its explanation/empty data from the store.
