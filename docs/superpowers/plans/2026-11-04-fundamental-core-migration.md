# S4a — هستهٔ بنیادی در مهاجرت (Go + v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** صفحهٔ `/fundamental` و `/fundamental/:symbol` را در `frontend-v2` بسازیم و دادهٔ آن را روی Go ببریم؛ کارت بنیادی Go با اوراکل پایتون (شامل freshness) یکی شود.

**Architecture:** cutover افزایشی: Vite فقط `/api/fundamental`، `/api/screener`، `/api/market` و `/api/sync/codal` را به Go می‌فرستد؛ بقیهٔ v2 فعلاً پایتون می‌ماند. صفحه دو حالت دارد: جدول هسته (همهٔ نمادها) و نمای نماد (کارت، Drill-Down، فصلی، P/E، تازگی/سلامت). جدول از `fts_results` می‌خواند که فعلاً updater پایتون می‌نویسد — قید اعلام‌شده.

**Tech Stack:** Go 1.27 (stdlib + modernc sqlite), React 18 + TypeScript + Zod + TanStack Query/Virtual + Vitest, Vite proxy.

**Spec:** `docs/superpowers/specs/2026-11-04-fundamental-core-migration-design.md`

## Global Constraints

- شاخه: `integration/4axes-main-2026-11-03`؛ **push نکن** مگر با اجازهٔ صریح مالک.
- هر commit فقط فایل‌های همان Task؛ هویت: `git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit ...`؛ هرگز `git config`/`git add -A`.
- تغییرات uncommitted فعلی `backend-go/internal/fundamental/axis1.go`، طلایی‌ها و `backend-go/internal/prediction/prediction_test.go` بخشی از groundwork همین پلن‌اند؛ دور ریخته نشوند. فایل‌های نامرتبط را stage نکن.
- منبع حقیقت کارت/فیلدها: توابع پایتون `api/fundamental.py` و `fts_engine.py` + طلایی‌های `backend-go/internal/fundamental/testdata/golden`. هیچ فرمول/آستانهٔ تازه‌ای ساخته نمی‌شود؛ `codal_periods` و موتور FTS دست‌نخورده.
- Go env:
  ```bash
  export PATH="/d/BorsTerminal-tmp/go-toolchain/go/bin:$PATH"
  export GOPATH="D:/BorsTerminal-tmp/gopath" GOMODCACHE="D:/BorsTerminal-tmp/gopath/pkg/mod"
  export GOCACHE="D:/BorsTerminal-tmp/gocache" GOFLAGS="-mod=mod" GOPROXY="https://goproxy.cn,direct"
  ```
- تست‌های Go/Python آفلاین؛ هیچ درخواست واقعی به TSETMC/CODAL/ADB. Go روی DB کپی `D:/BorsTerminal-tmp/4axes-data-main` با `-read-only -no-loops`.
- v2: اگر `node_modules` نبود، junction موقت به `D:/BorsTerminal-worktrees/4-axes/frontend-v2/node_modules` بساز و بعد حذف کن؛ هرگز commit نکن.
- Persian/RTL، بدون emoji، بدون dependency تازه، ارقام فارسی با `faNum`/`toFaDigits`.
- جدول هسته: «قبول» سبز و «—» برای غیرقبول؛ **حکمِ رد از روی boolean نساز**. تفکیک رد/بی‌نظر فقط در کارت. `excluded` نشان «خارج از پنج‌شاخص» می‌گیرد.
- `GET /api/fundamental/freshness` باید پیش از `GET /api/fundamental/{symbol}` ثبت شود.
- `as_of` اسکرینر = روز نشست (`MAX(d_even)`)، نه `time.Now()`.

---

## File Structure

| فایل | مسئولیت |
|---|---|
| `backend-go/internal/fundamental/axis1.go` | شکل axis1 (حذف extra، reason در کارت) |
| `backend-go/internal/fundamental/card.go` | مونتاژ کارت، profile/thresholds/freshness |
| `backend-go/internal/fundamental/insights.go` | details/subchecks |
| `backend-go/internal/fundamental/axis2.go`، `axis3.go`، `axis45.go` | فیلدهای محورها |
| `backend-go/internal/fundamental/config.go` | thresholds پیش‌فرض/ادغام |
| `backend-go/internal/fundamental/freshness.go` (جدید) | سرویس freshness |
| `backend-go/internal/fundamental/handlers.go`/`routes.go` | route دسته‌ای freshness |
| `backend-go/internal/httpapi/server.go`، `routes.json` | ثبت route/ترتیب |
| `backend-go/internal/screener/screener.go` | `as_of` روز نشست |
| `tools/parity/compare_fundamental_10.py` (جدید) | پاریتی ۱۰ نماد Python/Go |
| `frontend-v2/vite.config.ts` | proxy مسیرمحور + پورت env |
| `frontend-v2/src/app/App.tsx`، `Sidebar.tsx` | مسیر/ناوبری |
| `frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx` (جدید) | صفحه جدول/نماد |
| `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx` (جدید) | جدول هسته |
| `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx` (جدید) | نمای نماد |
| `frontend-v2/src/features/fundamental/ui/AxisDrilldown.tsx` (جدید) | پنل هر محور |
| `frontend-v2/src/features/fundamental/ui/QuarterlyTrend.tsx` (جدید) | روند فصلی |
| `frontend-v2/src/features/fundamental/ui/CodalHealthStrip.tsx` (جدید) | سلامت کدال |
| `frontend-v2/src/features/fundamental/api/useScreenerCore.ts` (جدید) | اسکرینر هسته |
| `frontend-v2/src/features/fundamental/api/useQuarters.ts` (جدید) | quarters |
| `frontend-v2/src/features/fundamental/api/useSectorPe.ts` (جدید) | P/E/میانه |
| `frontend-v2/src/features/fundamental/api/useCodalHealth.ts` (جدید) | سلامت |
| `frontend-v2/src/__tests__/fundamental-page.spec.tsx` (جدید) | تست صفحه/جدول |
| `frontend-v2/src/__tests__/fundamental-detail.spec.tsx` (جدید) | تست جزئیات/Drill-Down |

---

### Task 1: شکل axis1 و groundwork Go

**Files:**
- Modify: `backend-go/internal/fundamental/axis1.go`
- Modify (already dirty): `backend-go/internal/fundamental/testdata/golden/**`، `backend-go/internal/prediction/prediction_test.go`
- Test: `backend-go/internal/fundamental/axis1_test.go` (existing)

**Interfaces:**
- Consumes: oracle `api/fundamental.py:ind1a_monetary_growth` (593-663) and `_nodata` (605-623)
- Produces: axis1 success without `basis`/`series`; nodata with `basis` but without `series`; all `TestAx1*` green.

- [ ] **Step 1: RED — run the two shape tests**

```bash
cd backend-go
export PATH="/d/BorsTerminal-tmp/go-toolchain/go/bin:$PATH" GOPATH="D:/BorsTerminal-tmp/gopath" GOMODCACHE="D:/BorsTerminal-tmp/gopath/pkg/mod" GOCACHE="D:/BorsTerminal-tmp/gocache" GOFLAGS="-mod=mod" GOPROXY="https://goproxy.cn,direct"
go test ./internal/fundamental -run 'TestAx1Ind1aMatchesOracle|TestAx1NoSeriesNodataShape' -v
```

Expected: `TestAx1Ind1aMatchesOracle` fails with `basis: کلیدِ اضافه`; `TestAx1NoSeriesNodataShape` fails `12 کلید دارد want 11`.

- [ ] **Step 2: Remove the extra success key**

In `axis1.go`, inside the final success `return map[string]any{...}` of `Ind1aMonetaryGrowth`, remove:
```go
"basis": nil,
```
Keep `"basis": nil` in the `nodata` map (the oracle `_nodata` has it).

- [ ] **Step 3: Remove the extra nodata series key**

In the `nodata` map, remove:
```go
"series": ax1MsSeries(series),
```
The oracle `_nodata` has no `series`; `ax1AsSlice(nil)` still satisfies the test's empty-series assertion.

- [ ] **Step 4: GREEN**

```bash
go test ./internal/fundamental -run 'TestAx1' -v
```
Expected: all `TestAx1*` PASS.

- [ ] **Step 5: Commit the groundwork**

```bash
cd ..
git add backend-go/internal/fundamental/axis1.go \
        backend-go/internal/fundamental/testdata/golden \
        backend-go/internal/prediction/prediction_test.go
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "fix(go-fundamental): شکلِ axis1 و طلایی‌های تازهٔ کارت"
```

---

### Task 2: پاریتی کارت — محورهای ۱ تا ۳، profile، thresholds

**Files:**
- Modify: `backend-go/internal/fundamental/card.go`
- Modify: `backend-go/internal/fundamental/axis2.go`
- Modify: `backend-go/internal/fundamental/axis3.go`
- Modify: `backend-go/internal/fundamental/config.go`
- Test: `backend-go/internal/fundamental/card_test.go` (existing goldens)

**Interfaces:**
- Consumes: Python `api/fundamental.py:evaluate_v10` (1412-1558)، `ind2_eps_track` (948-1024)، `ind3_gross_margin` (1064-1126)، `fts_engine.eps_evidence_label`، `margin_tier`، `margin_class_na`
- Produces: `TestCardGoldens/card_up`، `card_up_score5`، `card_down`، `card_thin` با صفر diff.

- [ ] **Step 1: RED — capture the exact diff for one case**

```bash
cd backend-go
export PATH="/d/BorsTerminal-tmp/go-toolchain/go/bin:$PATH" GOPATH="D:/BorsTerminal-tmp/gopath" GOMODCACHE="D:/BorsTerminal-tmp/gopath/pkg/mod" GOCACHE="D:/BorsTerminal-tmp/gocache" GOFLAGS="-mod=mod" GOPROXY="https://goproxy.cn,direct"
go test ./internal/fundamental -run 'TestCardGoldens/card_up$' -v
```

Expected: the field list in the spec §4.1 (`monetary.series` extra، `monetary.reason` missing، `evidence_label`، `margin_tier`، `na_kind`، `acceptance_path`، `annualize_*`، `profile.margin_class`، `thresholds.*`).

- [ ] **Step 2: Fix indicator 1 shape**

In `card.go`, ensure the `indicators["1"]` map is exactly:
```go
map[string]any{
    "monetary": growth,
    "volume":   volume,
    "pass":     axis1,
    "reason":   axis1Reason,
}
```
Remove `series` from the `monetary` map if the axis1 function still adds it; add `reason` from the existing axis1 state calculation. The golden `card_up` is the oracle.

- [ ] **Step 3: Add indicator 2/3 and profile/threshold fields**

Port these fields from the Python oracle (do not invent values):

- `indicators.2.evidence_label` ← `fts_engine.eps_evidence_label(tier)` (`api/fundamental.py:972-973`).
- `indicators.3.margin_tier` ← `fts_engine.margin_tier(margin_pct)` (`fts_engine.py:1797`).
- `indicators.3.na_kind`، `margin_class`، `data_gap`، `ideal`، `na`، `reason`، `remediation` ← `api/fundamental.py:1064-1126` (especially the N/A branch at 1092-1099 and `fts_engine.margin_class_na` at 1849).
- `indicators.3.net_margin_pct` / `net_margin_period` ← `api/fundamental.py:1457-1458`.
- `profile.margin_class` ← `fts_engine.margin_class_na`/the profile map; the golden `card_up.profile` shows the exact key.
- `thresholds.mandatory_sectors` must be the 6 defaults (`config.go:54` already has 6; find the merge path that returns 3 — likely a golden fixture config) and `thresholds.reject_insurance` must be present. The card's `thresholds` object must match the golden byte-for-byte.

Remove Go-only extra fields the oracle does not emit under `indicators.3` (the diff lists `basis`، `fiscal_year`، `formula`، `gross_profit_bt`، `optimal_threshold`، `period_end`، `ref_company`، `ref_tracing_no`، `revenue_bt`، `source`، `unit`، `unit_label`، `unit_valid`) **unless the Python function puts them in `indicators.3`**; move display-only data to `details` if the oracle keeps it there.

- [ ] **Step 4: GREEN for the four cases**

```bash
go test ./internal/fundamental -run 'TestCardGoldens/(card_up|card_up_score5|card_down|card_thin)$' -v
```
Expected: all four PASS. If `card_fund` remains red, that is Task 3.

- [ ] **Step 5: Commit**

```bash
git add backend-go/internal/fundamental/card.go backend-go/internal/fundamental/axis2.go backend-go/internal/fundamental/axis3.go backend-go/internal/fundamental/config.go
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "fix(go-fundamental): فیلدهای کارت محور ۱-۳ و profile/thresholds"
```

---

### Task 3: پاریتی کارت — محورهای ۴/۵، details، صندوق

**Files:**
- Modify: `backend-go/internal/fundamental/axis45.go`
- Modify: `backend-go/internal/fundamental/insights.go`
- Modify: `backend-go/internal/fundamental/card.go`
- Test: `backend-go/internal/fundamental/card_test.go`

**Interfaces:**
- Consumes: Python `ind4_valuation` (1143-1256)، `ind5_industry` (1257-1278)، `build_insights` (1642-2042)، `v10_data_gaps` (2043-2110)، `margin_gap_detail` (1025-1063)
- Produces: all `TestCardGoldens` subtests green except freshness (Task 4).

- [ ] **Step 1: RED — capture fund diffs**

```bash
cd backend-go
export PATH="/d/BorsTerminal-tmp/go-toolchain/go/bin:$PATH" GOPATH="D:/BorsTerminal-tmp/gopath" GOMODCACHE="D:/BorsTerminal-tmp/gopath/pkg/mod" GOCACHE="D:/BorsTerminal-tmp/gocache" GOFLAGS="-mod=mod" GOPROXY="https://goproxy.cn,direct"
go test ./internal/fundamental -run 'TestCardGoldens/(card_fund|card_mixed|card_holding|card_no_sales)$' -v
```

Expected diffs include: `indicators.4.acceptance_path/annualize_label/annualize_months/reason`، `details.۳.calc/source/subchecks`، `data_gaps` length، `indicators.3` fund branch.

- [ ] **Step 2: Port indicator 4 fields**

In `axis45.go`, add/align:
```go
"acceptance_path":  acceptancePath,          // fts_engine.i4_acceptance_path
"annualize_months": annualizeMonths,         // months_used
"annualize_label":  annualizeLabel,          // fts_engine.annualize_label
"reason":           reason,                  // exact Python ind4 reason
```
Use the same `sales_pass`/`potential_pass` inputs as the oracle; do not compute a second acceptance rule.

- [ ] **Step 3: Port fund axis3/details**

For `card_fund` (صندوق), the oracle marks indicator 3 `na=true` with `na_kind`, `margin_class`, `reason` and `remediation`; the Go fund path currently emits a different N/A reason and extra fields. Port `ind3_gross_margin`'s fund branch (`api/fundamental.py:1064-1126`) and `margin_gap_detail`; make `details.۳.calc/source/subchecks` match the golden. `data_gaps` must be length 1 for `card_fund`.

- [ ] **Step 4: Port details/subchecks**

In `insights.go`, align `details["۱".."۵"]` with `api/fundamental.py:build_insights` and the golden. Each detail has `title`, `formula`, `source`, `calc`, `what`, `subchecks`; each subcheck carries `key`, `label`, `state`, `value`, `threshold`, `detail` (plus optional `verified`/`confidence`/`periods`). Do not invent labels; copy from the oracle.

- [ ] **Step 5: GREEN all card goldens (pre-freshness)**

```bash
go test ./internal/fundamental -run 'TestCardGoldens' -v
```
Expected: all pass **if** goldens do not yet include freshness (they currently don't). If any freshness-related diff appears, stop and carry it to Task 4.

- [ ] **Step 6: Commit**

```bash
git add backend-go/internal/fundamental/axis45.go backend-go/internal/fundamental/insights.go backend-go/internal/fundamental/card.go
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "fix(go-fundamental): محور ۴/۵، details و مسیر صندوق"
```

---

### Task 4: Freshness در Go + کلید کارت + route

**Files:**
- Create: `backend-go/internal/fundamental/freshness.go`
- Modify: `backend-go/internal/fundamental/card.go`
- Modify: `backend-go/internal/fundamental/handlers.go`
- Modify: `backend-go/internal/fundamental/routes.go`
- Modify: `backend-go/internal/httpapi/server.go`
- Modify: `backend-go/internal/httpapi/routes.json`
- Test: `backend-go/internal/fundamental/freshness_test.go` (new)، `backend-go/internal/httpapi/fundamental_routes_test.go`

**Interfaces:**
- Consumes: Python `api/fundamental.py:freshness_of` (2279-2439)، `_asof_iso` (2253-2265)؛ Go `Service`/`symbolid`/`period`.
- Produces:
  - `func (s *Service) FreshnessBody(ctx context.Context, symbols []string) (map[string]any, error)` (service)
  - `func (s *Service) Freshness(w http.ResponseWriter, r *http.Request)` (HTTP handler; no name collision)
  - `GET /api/fundamental/freshness?symbols=a,b`
  - card key `"freshness": ...`
  - route registered before `/{symbol}`.

- [ ] **Step 1: Write the failing service test**

Create `freshness_test.go` with an in-memory fixture (schema from `db.Open` or the existing card test helper). Insert:
- `instruments` row `(ins_code='1', l_val18='فولاد', ...)`؛
- `market_watch` row `d_even=20261103`؛
- `monthly_sales` + `codal_notices` publish `1405/06/31 09:00:00`؛
- `financial_statements` audited nonconsolidated `period_end=1404/12/29` publish `1405/05/10 09:00:00`؛
- `pipeline_dirty` axis `1_growth`؛
- a quarantined MS notice older than the latest monthly.

Assert:
```go
fr := out["axes"].(map[string]any)
// 1_growth state == "stale", as_of == "2026-09-22T09:00:00+03:30"
// 2_eps_trend state == "fresh", period_end == "1404/12/29"
// 5_industry as_of == "2026-11-03"
// out["as_of"] == oldest of 1/2/3 ("2026-09-22T09:00:00+03:30")
```
Use the same query/semantics as Python: latest monthly + latest FS reference + board day + dirty + latest quarantine per kind; precedence quarantined > stale > missing > fresh.

- [ ] **Step 2: RED**

```bash
go test ./internal/fundamental -run 'TestFreshness' -v
```
Expected: compile failure `s.FreshnessBody undefined` / test failure.

- [ ] **Step 3: Implement the service**

Create `freshness.go` with:
- `type freshnessAxis struct` or `map[string]any` matching the Python contract;
- queries using `symbolid.Pred` variants and `period.DatedSQL`/`period` helpers;
- `asOfISO` helper: date-only stays; timestamp `"YYYY-MM-DD HH:MM:SS"` → `"YYYY-MM-DDTHH:MM:SS+03:30"`;
- `freshnessOf(ctx, symbol)` and `FreshnessBody(ctx, symbols)`; if `symbols` empty, default first 200 `paper_type=1` instruments (or `instruments` rows) as Python does;
- no writes.

- [ ] **Step 4: Add the card key and route**

- In `card.go`, add `"freshness": freshness` to the card response; compute it with the same connection/context via `FreshnessBody` (or `freshnessOf`). If the service method needs a context, thread it from the handler.
- In `handlers.go`, add `Freshness` HTTP handler parsing `symbols` (comma-separated, max 200); return `{"status":"success","count":N,"items":[...]}`.
- In `httpapi/server.go`, register:
  ```go
  mux.HandleFunc("GET /api/fundamental/freshness", srv.Fundamental.Freshness)
  ```
  **before** `GET /api/fundamental/{symbol}`.
- Add the route to `routes.json` in sorted order.

- [ ] **Step 5: Regenerate card goldens from the Python oracle**

From repo root:
```bash
PYTHONIOENCODING=utf-8 python tools/parity/gen_fundamental_card_golden.py
```
This now includes the `freshness` key in all 12 goldens. Then:
```bash
cd backend-go
go test ./internal/fundamental -run 'TestCardGoldens|TestFreshness' -v
```
Expected: PASS. If the golden freshness differs, fix Go to the oracle, not the golden.

- [ ] **Step 6: Route-order test**

Add to `fundamental_routes_test.go`:
```go
func TestFreshnessRoutePrecedesSymbol(t *testing.T) {
    // call /api/fundamental/freshness with a fake service and assert 200/not 404
}
```
Also assert the route appears in `Routes()` and before `GET /api/fundamental/{symbol}`.

- [ ] **Step 7: Commit**

```bash
git add backend-go/internal/fundamental/freshness.go backend-go/internal/fundamental/card.go \
        backend-go/internal/fundamental/handlers.go backend-go/internal/fundamental/routes.go \
        backend-go/internal/httpapi/server.go backend-go/internal/httpapi/routes.json \
        backend-go/internal/fundamental/freshness_test.go backend-go/internal/httpapi/fundamental_routes_test.go \
        backend-go/internal/fundamental/testdata/golden
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(go-fundamental): freshness، route و کلید کارت"
```

---

### Task 5: `as_of` اسکرینر = روز نشست

**Files:**
- Modify: `backend-go/internal/screener/screener.go`
- Test: `backend-go/internal/screener/screener_test.go`

**Interfaces:**
- Consumes: `market_watch.d_even` (maximum board day)
- Produces: `as_of` in `GetScreener` payload = `YYYY-MM-DD` or `nil` if unavailable; no `time.Now()`.

- [ ] **Step 1: RED test**

Add to `screener_test.go` a fixture with `market_watch(ins_code, d_even)` rows `20261102`, `20261103`; assert `res["as_of"] == "2026-11-03"`.
Run:
```bash
go test ./internal/screener -run 'TestGetScreenerAsOf' -v
```
Expected: current `time.Now()` date, FAIL.

- [ ] **Step 2: Implement**

In `loadScreenerData` (or `GetScreener`), query:
```sql
SELECT MAX(d_even) FROM market_watch
```
Convert `YYYYMMDD` to `YYYY-MM-DD`; if NULL, omit/null. Do not use the system clock.

- [ ] **Step 3: GREEN and commit**

```bash
go test ./internal/screener -v
git add backend-go/internal/screener/screener.go backend-go/internal/screener/screener_test.go
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "fix(go-screener): as_of از روز نشست تابلو"
```

---

### Task 6: v2 — proxy، مسیرها، جدول هسته و نمای پایهٔ نماد

**Files:**
- Modify: `frontend-v2/vite.config.ts`
- Modify: `frontend-v2/src/app/App.tsx`
- Modify: `frontend-v2/src/app/shell/Sidebar.tsx`
- Create: `frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx`
- Create: `frontend-v2/src/features/fundamental/api/useScreenerCore.ts`
- Test: `frontend-v2/src/__tests__/fundamental-page.spec.tsx`

**Interfaces:**
- Consumes: Go `/api/screener` (subset: `symbol`, `symbol_norm`, `name`, `sector_name`, `score`, `verdict`, `excluded`, `i1_pass`..`i5_pass`, `as_of`); existing `useFtsCard`, `FundamentalSummary`, `FundamentalCards`.
- Produces:
  - `useScreenerCore(): UseQueryResult<ScreenerPayload>`
  - `FundamentalScreenTable({rows,onSelect})`
  - `FundamentalPage` routes `/fundamental` and `/fundamental/:symbol`
  - Sidebar `/fundamental` live.

- [ ] **Step 1: Proxy + port env**

In `vite.config.ts`:
```ts
const python = process.env.BORS_BACKEND || 'http://127.0.0.1:8101';
const go = process.env.BORS_BACKEND_GO;
const goProxy = go ? {
  '/api/fundamental': { target: go, changeOrigin: false },
  '/api/screener': { target: go, changeOrigin: false },
  '/api/market': { target: go, changeOrigin: false },
  '/api/sync/codal': { target: go, changeOrigin: false },
} : {};
```
Use `server.port = Number(process.env.BORS_VITE_PORT) || 5180`, and proxy `{ ...goProxy, '/api': { target: python, changeOrigin: false }, '/vendor': { target: python, changeOrigin: false } }`. Specific keys must precede `/api`.

- [ ] **Step 2: Failing page test**

Create `fundamental-page.spec.tsx`:
- mock `useScreenerCore` with 2 rows (`فولاد` score 5, `خساپا` score 2, one `excluded`);
- render `<FundamentalPage />` inside a `MemoryRouter` at `/fundamental`;
- assert table exists, 2 rows, `فولاد` has 5 pass chips, `excluded` badge on the excluded row;
- click `فولاد` → assert navigate called with `/fundamental/فولاد` (mock `useNavigate`).
Run:
```bash
cd frontend-v2 && npx vitest run src/__tests__/fundamental-page.spec.tsx
```
Expected: FAIL (component missing).

- [ ] **Step 3: Implement hook/table/page shell**

`useScreenerCore.ts`:
```ts
const Str = z.string().nullish();
const Bool = z.boolean().nullish();
const Row = z.looseObject({
  symbol: z.string(), symbol_norm: Str, name: Str, sector_name: Str,
  score: z.number(), verdict: Str, excluded: Bool,
  i1_pass: Bool, i2_pass: Bool, i3_pass: Bool, i4_pass: Bool, i5_pass: Bool,
});
const Payload = z.looseObject({ status: z.string(), count: z.number(),
  data: z.array(Row), as_of: Str });
```
Query `/api/screener` with `staleTime: 60_000`.

`FundamentalScreenTable`:
- columns: نماد، صنعت، ۵ نشان (سبز برای `true`، «—» برای غیر)، امتیاز، وضعیت (`excluded` → «خارج از پنج‌شاخص»).
- search on symbol/name; sector select from distinct rows; sort by score desc default; virtualize only if >200 rows (use `@tanstack/react-virtual`, existing dependency).
- row `onClick`/`onKeyDown` Enter → `onSelect(symbol)`.

`FundamentalPage`:
- `useParams` for `symbol`; if no symbol render header + table + freshness note; if symbol render `FundamentalDetail` with `card` and a back link.
- `FundamentalDetail` in this task: header + `FundamentalSummary` + `FundamentalCards` + freshness badge; Task 7 adds drilldown/quarters/PE/health. This task's page is usable for table→card review and is not a dead-end placeholder.
- Enable sidebar item.

- [ ] **Step 4: GREEN + typecheck**

```bash
cd frontend-v2
npx vitest run src/__tests__/fundamental-page.spec.tsx
npm run typecheck
```
Expected: PASS/0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/vite.config.ts frontend-v2/src/app/App.tsx frontend-v2/src/app/shell/Sidebar.tsx \
        frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx \
        frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx \
        frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx \
        frontend-v2/src/features/fundamental/api/useScreenerCore.ts \
        frontend-v2/src/__tests__/fundamental-page.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(v2): مسیر بنیادی، جدول هسته و نمای پایهٔ نماد"
```

---

### Task 7: v2 — Drill-Down، فصلی، P/E صنعت، سلامت کدال

**Files:**
- Create: `frontend-v2/src/features/fundamental/ui/AxisDrilldown.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/QuarterlyTrend.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/CodalHealthStrip.tsx`
- Create: `frontend-v2/src/features/fundamental/api/useQuarters.ts`
- Create: `frontend-v2/src/features/fundamental/api/useSectorPe.ts`
- Create: `frontend-v2/src/features/fundamental/api/useCodalHealth.ts`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-detail.spec.tsx`

**Interfaces:**
- Consumes: card `details` (keys `۱`..`۵`; each `{title,formula,source,calc,what,subchecks}`); `/api/fundamental/{s}/quarters`؛ `/api/market`؛ `/api/sync/codal/pipeline`.
- Produces:
  - `AxisDrilldown({card, axis, onChange})` with five tabs; shows formula/source/calc/what/subchecks; subcheck state badge.
  - `QuarterlyTrend({quarters})` with Persian labels; no invented values.
  - `CodalHealthStrip({health})` with last success, queue, quarantined, gap flag.
  - `useSectorPe(symbol)` returning `{pe, median, sector}`.

- [ ] **Step 1: Failing detail test**

Mock `useFtsCard` with a card containing `details["۳"]` and `freshness`; mock `useQuarters`, `useSectorPe`, `useCodalHealth`; render detail; assert:
- 5 drilldown tabs;
- clicking tab `۳` shows `details.۳.calc` and `subchecks[0].label`;
- quarterly rows render periods;
- sector PE/median render;
- health strip shows queue count.
Run focused vitest; expect FAIL.

- [ ] **Step 2: Implement hooks/components**

- `useQuarters`: GET `/api/fundamental/${symbol}/quarters`, schema `quarters: array of looseObject`; no client recomputation unless the old `deCumulateQuarters` helper is ported (for trend, display raw period values; do not invent YoY).
- `useSectorPe`: GET `/api/market`, find row by symbol, sector median of finite `pe` values; return nulls honestly.
- `useCodalHealth`: GET `/api/sync/codal/pipeline`; schema loose; display `queue.queued`, `queue.quarantined`, `gap_flag`, `last_successful_sync.at`.
- `AxisDrilldown`: options `[{key:'1_growth',digit:'۱',label:'رشد فروش'}, ...]`; render `details[digit]`; for each subcheck show `label`, `value`, `threshold`, `detail`, state chip; unknown fields ignored.
- `QuarterlyTrend`: a compact table/list of `period_end`, revenue, net_profit, eps; Persian numbers.
- `CodalHealthStrip`: compact status chips; if health missing, show "وضعیت سلامت در دسترس نیست".
- Integrate into `FundamentalDetail` below cards.

- [ ] **Step 3: GREEN + typecheck**

```bash
cd frontend-v2
npx vitest run src/__tests__/fundamental-detail.spec.tsx src/__tests__/fundamental-page.spec.tsx
npm run typecheck
```
Expected: PASS/0.

- [ ] **Step 4: Commit**

```bash
git add frontend-v2/src/features/fundamental/ui/AxisDrilldown.tsx \
        frontend-v2/src/features/fundamental/ui/QuarterlyTrend.tsx \
        frontend-v2/src/features/fundamental/ui/CodalHealthStrip.tsx \
        frontend-v2/src/features/fundamental/api/useQuarters.ts \
        frontend-v2/src/features/fundamental/api/useSectorPe.ts \
        frontend-v2/src/features/fundamental/api/useCodalHealth.ts \
        frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx \
        frontend-v2/src/__tests__/fundamental-detail.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(v2): Drill-Down، فصلی، P/E صنعت و سلامت کدال"
```

---

### Task 8: پاریتی ۱۰ نماد + گیت زنده/بصری

**Files:**
- Create: `tools/parity/compare_fundamental_10.py`
- Test: manual gate (not CI)
- Maybe create `_audit/fundamental-s4a/` screenshots (gitignored or docs? Use D:/BorsTerminal-tmp).

**Interfaces:**
- Consumes: Python API on 8101، Go on 8103، symbols list.
- Produces: report JSON/markdown with per-symbol diffs; exit 1 on mismatch.

- [ ] **Step 1: Write the parity script**

Create `tools/parity/compare_fundamental_10.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مقایسهٔ ۱۰ نماد بنیادی بین FastAPI پایتون و Go (فقط خواندن)."""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT = ["فولاد", "خساپا", "وبصادر", "شپنا", "همراه",
           "فارس", "کگل", "خودرو", "شبندر", "تاپیکو"]


def get(base, path):
    url = base.rstrip("/") + path
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None


def diff(a, b, path="", out=None):
    out = [] if out is None else out
    if type(a) is not type(b):
        out.append("%s: type %s != %s" % (path, type(a).__name__, type(b).__name__))
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append("%s.%s: missing in python" % (path, k))
            elif k not in b:
                out.append("%s.%s: missing in go" % (path, k))
            else:
                diff(a[k], b[k], "%s.%s" % (path, k), out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s: length %d != %d" % (path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            diff(a[i], b[i], "%s[%d]" % (path, i), out)
    elif a != b:
        out.append("%s: %r != %r" % (path, a, b))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default="http://127.0.0.1:8101")
    ap.add_argument("--go", default="http://127.0.0.1:8103")
    ap.add_argument("--symbols", default=",".join(DEFAULT))
    args = ap.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    failed = 0
    checked = 0
    for sym in symbols:
        for path in ("/api/fundamental/%s" % urllib.parse.quote(sym),
                     "/api/fundamental/%s/quarters" % urllib.parse.quote(sym)):
            py_status, py = get(args.python, path)
            go_status, go = get(args.go, path)
            if py_status == 404 and go_status == 404:
                continue
            if py_status != go_status or py is None or go is None:
                print("FAIL %s status python=%s go=%s" % (path, py_status, go_status))
                failed += 1
                continue
            d = diff(py, go)
            checked += 1
            if d:
                failed += 1
                print("FAIL %s (%d diff)" % (path, len(d)))
                for line in d[:20]:
                    print("  " + line)
            else:
                print("PASS %s" % path)
    print("%d checked, %d failed" % (checked, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

Expected: with both servers running on the same DB copy, `PASS` for every existing symbol and `0 failed`. If a field differs, fix Go to the Python oracle; do not normalize it away unless it is a declared timestamp (none in the card contract).

- [ ] **Step 2: Start Go and Vite**

```bash
cd backend-go
go run ./cmd/borsd -port 8103 -db-dir D:/BorsTerminal-tmp/4axes-data-main -read-only -no-loops > D:/BorsTerminal-tmp/borsd-s4a.log 2>&1 &
cd ../frontend-v2
BORS_BACKEND=http://127.0.0.1:8101 BORS_BACKEND_GO=http://127.0.0.1:8103 BORS_VITE_PORT=5181 npm run dev > D:/BorsTerminal-tmp/vite-s4a.log 2>&1 &
```

- [ ] **Step 3: Run parity**

```bash
PYTHONIOENCODING=utf-8 python tools/parity/compare_fundamental_10.py \
  --python http://127.0.0.1:8101 --go http://127.0.0.1:8103
```
Expected: exit 0; all 10 symbols card+quarters equal. If a difference is a real oracle gap, fix Go in the relevant Task; do not normalize it away.

- [ ] **Step 4: Browser gate**

Use Browser Use/Computer Use or Playwright-core with Edge/Brave:
- open `http://localhost:5181/#/fundamental`;
- verify table rows > 0, search `فولاد`, click row, detail loads;
- open each of 5 drilldown tabs; verify formula/calc text present;
- verify quarterly rows, P/E/median, health strip;
- screenshots at 1366×768 and 1920×1080;
- console errors zero; no overflow at 1366.
- Verify network: `/api/fundamental`, `/api/screener`, `/api/market`, `/api/sync/codal` hit Go (check `borsd-s4a.log`), not Python.

- [ ] **Step 5: Commit the script and report**

```bash
git add tools/parity/compare_fundamental_10.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "test(parity): مقایسهٔ ۱۰ نماد بنیادی Python/Go"
```

---

## Self-Review

- **Spec coverage:** Go card parity → Tasks 1-3؛ freshness/route/card key → Task 4؛ screener as_of → Task 5؛ proxy/routes/table → Task 6؛ drilldown/quarters/PE/health → Task 7؛ 10-symbol + visual/Go gate → Task 8.
- **Out of scope recorded:** settings/calendar/DPS/export/P/NAV and `/api/fundamental/screen` are not tasks, matching the spec §1/§8.
- **Placeholder scan:** no TBD/TODO; every verification has a command and expected result. Parity tasks use the golden diff as the exact checklist and the Python functions as the oracle; no invented fields.
- **Type consistency:** `useScreenerCore`, `FundamentalScreenTable`, `AxisDrilldown`, `useQuarters`, `useSectorPe`, `useCodalHealth`, `Service.Freshness` names are used consistently across tasks.
- **Known dependency:** `fts_results` remains Python-fed; table rows are Go-served but not independently materialized. Stated in spec and plan; not claimed as full Go independence.
