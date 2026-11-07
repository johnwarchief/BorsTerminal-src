# FTS P0 — شاخص ۴ و تم واحد — پلن اجرا

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** شاخص ۴ را به «پتانسیل سود تا آخر سال» با تیتر درصد نهایی تبدیل کن و سطح دادهٔ paper/ink را حذف کن تا کل بنیادی از تم برنامه پیروی کند.

**Architecture:** محور ۴ از `profit_potential_pct` و `profit_potential_min` استفاده می‌کند؛ `sales_to_mcap` به شاهد دوم و مسیر OR تبدیل می‌شود. توکن‌های `--fd-*` به متغیرهای تم برنامه alias می‌شوند و `surface` از prefs/UI حذف می‌شود؛ هیچ بک‌اندی تغییر نمی‌کند.

**Tech Stack:** React/TS/Vite/Tailwind 4/Zustand/Vitest؛ همان frontend-v2.

**Spec:** `_audit/rebuild/fts-critic/2026-11-04/report.md` (F-01، F-05) + `docs/جزوه FTS.pdf` ص ۵–۶ + `docs/fts-notes/OWNER_RULINGS.md` #4 + رأی مالک ۲۰۲۶-۱۱-۰۴ (تم تابع برنامه).

## Global Constraints

- هیچ فرمول/آستانهٔ تازه: پتانسیل از `profit_potential_min` (۴۰) و فروش/ارزش از `v10_sales_to_mcap_min` (۰٫۳۳) خوانده می‌شود؛ کف/هدف ۱الف همان S4b است.
- S4b حفظ شود: `FtsSettingsTrigger`، P/NAV `HoldingNavPanel`، فیلتر حذف، CSV، تقویم/کدال، `panel-sales` testid و وضعیت ترکیبی محور ۴.
- **Only app themes**: هیچ surface جدا، هیچ `data-fund-surface`، هیچ دکمهٔ کاغذی/تیره. تم‌های برنامه (brass/warm/terminal/cool) منبع‌اند.
- RTL و فارسی؛ ارقام با `toFaDigits`/`formatAxisValue`؛ رنگ تنها حامل وضعیت نیست.
- `1366×768` و `1920×1080`؛ بدون وابستگی جدید؛ `tsc` صفر خطا؛ همهٔ تست‌ها سبز.
- کامیت محلی با `-c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com"`؛ بدون push.
- بعد از هر تسک: `npm run typecheck` + تست‌های همان تسک؛ شواهد بصری فقط با اسکرین‌شات.

---

### Task 1: شاخص ۴ — پتانسیل سود تا آخر سال

**Files:**
- Modify: `frontend-v2/src/features/fundamental/lib/axisMeta.ts`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalAxisCell.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/Quintet.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/panels/SalesPanel.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-axis-meta.spec.ts`
- Test: `frontend-v2/src/__tests__/fundamental-table-visual.spec.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-page-visual.spec.tsx`

**Interfaces:**
- Consumes: `ScreenerCoreRow.profit_potential_pct`, `ScreenerCoreRow.sales_to_mcap`, `AxisThresholds.profit_potential_min`, `AxisThresholds.v10_sales_to_mcap_min`, card `indicators['4'].potential_pct/potential_threshold/sales_to_mcap/sales_threshold`.
- Produces: `PotentialPath = 'potential'|'sales'|null`; `potentialPath(row, thresholds)`; `potentialStatusOf(row, thresholds)`; labels «پتانسیل سود تا آخر سال»/«پتانسیل»; `formatAxisValue(..., 'sales')` returns signed percent; `thresholdOf(thresholds, 'sales')` returns `profit_potential_min`.

- [ ] **Step 1: تست متادیتا و مسیر OR را بنویس**

در `fundamental-axis-meta.spec.ts` اضافه/به‌روزرسانی کن:

```ts
it('reads potential profit as axis 4 and keeps the sales path as evidence', () => {
  expect(AXES.find((axis) => axis.key === 'sales')?.label).toBe('پتانسیل سود تا آخر سال');
  expect(valueOf({ ...row, profit_potential_pct: 13.2, sales_to_mcap: 1.15 }, 'sales')).toBe(13.2);
  expect(thresholdOf(thresholds, 'sales')).toBe(40);
  expect(formatAxisValue(13.2, 'sales')).toBe('+۱۳٫۲٪');
  expect(potentialPath({ ...row, profit_potential_pct: 45, sales_to_mcap: 0.1 }, thresholds)).toBe('potential');
  expect(potentialPath({ ...row, profit_potential_pct: 13.2, sales_to_mcap: 1.15 }, thresholds)).toBe('sales');
  expect(potentialPath({ ...row, profit_potential_pct: 13.2, sales_to_mcap: 0.1 }, thresholds)).toBeNull();
  expect(potentialStatusOf({ ...row, profit_potential_pct: 13.2 }, thresholds)).toBe('fail');
});
```

`thresholds` در این فایل باید `profit_potential_min: 40` و `v10_sales_to_mcap_min: 0.33` داشته باشد.

- [ ] **Step 2: تست جدول و CSV را بنویس**

در `fundamental-table-visual.spec.tsx`:

```tsx
it('shows potential profit as the axis-4 headline with the sales path', () => {
  render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
  expect(screen.getByText('پتانسیل سود تا آخر سال')).toBeTruthy();
  const cell = screen.getByTestId('fundamental-cell-رنيك-sales');
  expect(cell.textContent).toContain('+۱۳٫۲٪');
  expect(cell.textContent).toContain('۱٫۱۵');
  expect(cell.getAttribute('data-path')).toBe('sales');
  expect(cell.textContent).toContain('مسیر فروش/ارزش');
});

it('sorts axis 4 by the potential percentage', () => {
  const onSelect = vi.fn();
  render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={onSelect} asOf={null} />);
  fireEvent.click(screen.getByRole('button', { name: /مرتب‌سازی پتانسیل سود/ }));
  const order = [...document.querySelectorAll('[data-testid^="fundamental-row-"]')].map((el) => el.getAttribute('data-testid'));
  // کلیکِ اول روی ستونِ جدید، نزولی است: پتانسیل ۱۳٫۲ (رنيك) بالاتر از ۰ (وبملت) است.
  expect(order[0]).toBe('fundamental-row-رنيك');
});
```

Fixture ردیف‌ها را طوری تنظیم کن که پتانسیل و نسبت فروش هر دو موجود باشند؛ رنيك: `profit_potential_pct: 13.2، sales_to_mcap: 1.15`، وبملت: `profit_potential_pct: 0، sales_to_mcap: null`.

در `fundamental-page-visual.spec.tsx` تست CSV را به‌روزرسانی کن:

```ts
expect(table.columns).toEqual(expect.arrayContaining([
  'نماد', 'رشد', 'سودآوری', 'حاشیه', 'پتانسیل سود', 'فروش/ارزش (شاهد)', 'صنعت', 'امتیاز', 'وضعیت',
]));
expect(meta).toEqual(expect.arrayContaining([
  ['آستانه پتانسیل', '40'],
  ['آستانه فروش/ارزش', '0.33'],
]));
```

- [ ] **Step 3: اجرا و دیدن شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-axis-meta.spec.ts src/__tests__/fundamental-table-visual.spec.tsx src/__tests__/fundamental-page-visual.spec.tsx`
Expected: FAIL — `potentialPath`/`potentialStatusOf` وجود ندارند و جدول هنوز نسبت فروش را تیتر می‌کند.

- [ ] **Step 4: axisMeta را تغییر بده**

در `axisMeta.ts`:

```ts
export type PotentialPath = 'potential' | 'sales' | null;

// AXES:
{ key: 'sales', num: '۴', label: 'پتانسیل سود تا آخر سال', short: 'پتانسیل', thresholdKey: 'profit_potential_min' },

export function valueOf(row: ScreenerRowLike, axis: AxisKey): number | string | null {
  switch (axis) {
    // ...
    case 'sales': return row.profit_potential_pct ?? null;
    // ...
  }
}

export function thresholdOf(thresholds: AxisThresholds | null | undefined, axis: AxisKey): number | null {
  if (!thresholds) return null;
  switch (axis) {
    // ...
    case 'sales': return thresholds.profit_potential_min ?? null;
    // ...
  }
}

export function potentialStatusOf(
  row: Pick<ScreenerRowLike, 'profit_potential_pct'>,
  thresholds: AxisThresholds | null | undefined,
): AxisStatus {
  const value = row.profit_potential_pct;
  const threshold = thresholds?.profit_potential_min;
  if (value == null || threshold == null || !Number.isFinite(value) || !Number.isFinite(threshold)) return 'unknown';
  return value >= threshold ? 'pass' : 'fail';
}

export function potentialPath(
  row: Pick<ScreenerRowLike, 'profit_potential_pct' | 'sales_to_mcap'>,
  thresholds: AxisThresholds | null | undefined,
): PotentialPath {
  if (potentialStatusOf(row, thresholds) === 'pass') return 'potential';
  const ratio = row.sales_to_mcap;
  const floor = thresholds?.v10_sales_to_mcap_min;
  if (ratio != null && floor != null && Number.isFinite(ratio) && Number.isFinite(floor) && ratio >= floor) return 'sales';
  return null;
}

export function formatAxisValue(value: number | string | null, axis: AxisKey): string {
  if (value == null) return '—';
  if (axis === 'industry') return regimeFa(String(value));
  if (axis === 'eps') return toFaDigits(Math.round(Number(value)));
  const n = Number(value);
  const prefix = (axis === 'growth' || axis === 'sales') && n > 0 ? '+' : n < 0 ? '−' : '';
  return `${prefix}${toFaDigits(Math.abs(n).toFixed(1)).replace('.', '٫')}٪`;
}
```

`thresholdKey` فقط متادیتاست؛ `thresholdOf` مرجع است.

- [ ] **Step 5: AxisCell را تغییر بده**

در `FundamentalAxisCell.tsx` importهای `potentialPath`, `potentialStatusOf` را اضافه کن. برای `axis === 'sales'`:

```tsx
const potential = axis === 'sales' ? potentialStatusOf(row, thresholds) : null;
const path = axis === 'sales' ? potentialPath(row, thresholds) : null;
const salesRatio = axis === 'sales'
  ? (row.sales_to_mcap == null ? '—' : toFaDigits(row.sales_to_mcap.toFixed(2)).replace('.', '٫'))
  : null;

// value row:
{axis === 'sales' ? (
  <span
    data-path={path ?? 'none'}
    className="rounded border border-[var(--fd-line-strong)] px-1 text-[8.5px] text-[var(--fd-text-3)]"
    title={path === 'potential' ? 'قبول از مسیر پتانسیل سود' : path === 'sales' ? 'قبول از مسیر فروش/ارزش' : 'مسیر قبولی مشخص نیست'}
  >
    {path === 'potential' ? '۴ب' : path === 'sales' ? '۴الف' : '—'}
  </span>
) : null}

// chart:
{axis === 'sales' ? (
  <Bullet value={row.profit_potential_pct ?? null} max={100} threshold={threshold} status={potential ?? 'unknown'} label={`پتانسیل سود ${value}`} />
) : null}

// threshold line (comfortable):
{axis === 'sales'
  ? `≥ ${toFaDigits(threshold ?? '—')}٪ · فروش/ارزش ${salesRatio}`
  : subtitle}
```

`data-path` باید روی خودِ `fundamental-cell-...-sales` باشد (برای تست)؛ می‌توانی روی div ریشه بگذاری:

```tsx
data-path={axis === 'sales' ? path ?? 'none' : undefined}
```

- [ ] **Step 6: جدول را تغییر بده**

`sortValue`:

```ts
case 'sales': return row.profit_potential_pct ?? null;
```

`axisThresholdLabel`:

```ts
if (axis === 'sales') return `≥ ${toFaDigits(threshold ?? '—')}٪ · ۰٫۳۳`;
```

CSV:

```ts
const columns = ['نماد', 'نام', 'صنعت شرکت', 'رشد', 'سودآوری', 'حاشیه', 'پتانسیل سود', 'فروش/ارزش (شاهد)', 'صنعت', 'امتیاز', 'وضعیت'];
// row:
formatAxisValue(row.profit_potential_pct ?? null, 'sales'),
formatAxisValue(row.sales_to_mcap ?? null, 'sales_ratio_evidence') // نمی‌توان از axis 'sales' استفاده کرد؛
```

برای شاهد از فرمت نسبت استفاده کن (نه محور):

```ts
const formatRatio = (value: number | null) => value == null ? '—' : toFaDigits(value.toFixed(2)).replace('.', '٫');
```

meta:

```ts
['آستانه پتانسیل', String(thresholds?.profit_potential_min ?? '—')],
['آستانه فروش/ارزش', String(thresholds?.v10_sales_to_mcap_min ?? '—')],
```

- [ ] **Step 7: Quintet و SalesPanel را تغییر بده**

`Quintet` شاخص sales:

```tsx
value: formatAxisValue(sales?.potential_pct ?? null, 'sales'),
threshold: `کف ${thresholdLabel(sales?.potential_threshold, '٪')}`,
status: cardStatus(card, 'sales'),
chart: (
  <Bullet
    value={sales?.potential_pct ?? null}
    max={100}
    threshold={sales?.potential_threshold ?? null}
    status={sales?.potential_pct != null && sales?.potential_threshold != null
      ? sales.potential_pct >= sales.potential_threshold ? 'pass' : 'fail'
      : 'unknown'}
    label="پتانسیل سود"
  />
),
```

`SalesPanel`:

```tsx
title="پتانسیل سود تا آخر سال"
subtitle="درصد نهایی پتانسیل سود؛ مسیر OR: فروش/ارزش ≥ ۰٫۳۳ یا پتانسیل ≥ آستانه"
value={faFixed(sales?.potential_pct, 1, '٪')}
threshold={`کف ${faThreshold(sales?.potential_threshold, '٪')}`}
chart={<Bullet value={sales?.potential_pct ?? null} max={100} threshold={sales?.potential_threshold ?? null} status={potentialStatus} label="پتانسیل سود" />}
rows={[
  ['فروش/ارزش (شاهد)', faFixed(sales?.sales_to_mcap, 2)],
  ['آستانهٔ فروش/ارزش', faThreshold(sales?.sales_threshold, '')],
  ['فروش سالانه', faFixed(sales?.annual_sales_bt, 1)],
  ['ماه‌های سالانه‌سازی', ...],
  ['آستانهٔ پتانسیل', faThreshold(sales?.potential_threshold, '٪')],
  ['معافیت', ...],
]}
```

`potentialStatus` را در پنل از `potential_pct/potential_threshold` بساز (نه `cardStatus` ترکیبی)؛ وضعیت هدر ترکیبی می‌ماند. مسیر را از `passes['4b_profit_potential']`/`passes['4a_sales_to_mcap']` یا مقادیر نشان بده.

- [ ] **Step 8: تست/کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-axis-meta.spec.ts src/__tests__/fundamental-table-visual.spec.tsx src/__tests__/fundamental-cockpit.spec.tsx src/__tests__/fundamental-page-visual.spec.tsx`
Expected: PASS.

```bash
git add frontend-v2/src/features/fundamental/lib/axisMeta.ts frontend-v2/src/features/fundamental/ui/FundamentalAxisCell.tsx frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx frontend-v2/src/features/fundamental/ui/Quintet.tsx frontend-v2/src/features/fundamental/ui/panels/SalesPanel.tsx frontend-v2/src/__tests__/fundamental-axis-meta.spec.ts frontend-v2/src/__tests__/fundamental-table-visual.spec.tsx frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx frontend-v2/src/__tests__/fundamental-page-visual.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): شاخص ۴ با تیتر پتانسیل سود تا آخر سال"
```

---

### Task 2: تم واحد — حذف paper/ink و تبعیت از تم برنامه

**Files:**
- Modify: `frontend-v2/src/app/styles.css`
- Modify: `frontend-v2/src/features/fundamental/stores/prefs.ts`
- Modify: `frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalSummary.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-prefs.spec.ts`
- Test: `frontend-v2/src/__tests__/fundamental-page-visual.spec.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-consumers.spec.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-a11y.spec.tsx`

**Interfaces:**
- Consumes: app theme vars `--bg/--panel/--panel-2/--panel-3/--line/--line-strong/--text/--text-2/--text-3/--accent/--up/--down/--warn/--flat`.
- Produces: `.fundamental-surface` token aliases; no `data-fund-surface`; no `Surface`/`setSurface`; no paper/ink buttons.

- [ ] **Step 1: تست prefs و نبود سطح را بنویس**

`fundamental-prefs.spec.ts` را به‌روزرسانی کن:

```ts
beforeEach(() => {
  useFundamentalPrefs.setState({ density: 'comfortable', sortKey: 'score', sortDir: 'desc' });
});

it('updates density and sort without a surface', () => {
  useFundamentalPrefs.getState().setDensity('compact');
  useFundamentalPrefs.getState().setSort('margin', 'asc');
  const state = useFundamentalPrefs.getState();
  expect([state.density, state.sortKey, state.sortDir]).toEqual(['compact', 'margin', 'asc']);
  expect('surface' in state).toBe(false);
});
```

در `fundamental-page-visual.spec.tsx` تست سطح را حذف و این را اضافه کن:

```ts
it('uses the app theme and has no separate data-surface control', () => {
  render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
  const page = screen.getByTestId('fundamental-page');
  expect(page.getAttribute('data-fund-surface')).toBeNull();
  expect(screen.queryByTestId('fundamental-surface-paper')).toBeNull();
  expect(screen.queryByTestId('fundamental-surface-ink')).toBeNull();
  expect(page.className).toContain('fundamental-surface');
});
```

تست‌های `data-fund-surface` در cockpit/consumers/a11y را به `queryBy...`/`toBeNull()` تغییر بده و به‌جای `ink`، وجود کلاس `fundamental-surface` را بسنج.

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-prefs.spec.ts src/__tests__/fundamental-page-visual.spec.tsx`
Expected: FAIL — `Surface`/`setSurface` و دکمه‌های سطح هنوز هستند.

- [ ] **Step 3: CSS را alias کن**

در `styles.css` دو بلوک `[data-fund-surface='paper'|'ink']` را حذف و جای آن‌ها:

```css
/* سطح داده از تم برنامه ارث می‌برد؛ هیچ تم مستقل/سوییچی وجود ندارد. */
.fundamental-surface {
  --fd-bg: var(--bg); --fd-panel: var(--panel); --fd-panel-2: var(--panel-2); --fd-panel-3: var(--panel-3);
  --fd-line: var(--line); --fd-line-strong: var(--line-strong);
  --fd-text: var(--text); --fd-text-2: var(--text-2); --fd-text-3: var(--text-3);
  --fd-accent: var(--accent); --fd-up: var(--up); --fd-down: var(--down);
  --fd-warn: var(--warn); --fd-flat: var(--flat);
  --fd-grid: color-mix(in srgb, var(--text-3) 16%, transparent);
}
```

همهٔ قواعد `.fundamental-surface .fd-*` را دست‌نخورده نگه دار.

- [ ] **Step 4: prefs را ساده کن**

```ts
export type Density = 'compact' | 'comfortable';
export type SortKey = 'score' | 'symbol' | 'growth' | 'eps' | 'margin' | 'sales' | 'industry';
export type SortDir = 'asc' | 'desc';

interface FundamentalPrefs {
  density: Density; sortKey: SortKey; sortDir: SortDir;
  setDensity: (density: Density) => void;
  setSort: (sortKey: SortKey, sortDir: SortDir) => void;
}

export const useFundamentalPrefs = create<FundamentalPrefs>()(
  persist(
    (set) => ({
      density: 'comfortable', sortKey: 'score', sortDir: 'desc',
      setDensity: (density) => set({ density }),
      setSort: (sortKey, sortDir) => set({ sortKey, sortDir }),
    }),
    { name: 'bors-fundamental-v1' },
  ),
);
```

سطح ذخیره‌شدهٔ قدیمی در persist نادیده گرفته می‌شود؛ کلید storage عوض نشود.

- [ ] **Step 5: Page/Detail/Cards/Summary/Table را از surface پاک کن**

- `FundamentalPage`: import/selector `surface` و `setSurface`، `data-fund-surface` و `div[role=group aria-label="سطح داده"]` و دو دکمه را حذف کن. `scanLabel` و `ms-auto` بماند.
- `FundamentalDetail`: `useFundamentalPrefs` فقط برای density لازم نیست؛ `surface` را از state/DetailFrame props و هر سه فراخوانی حذف کن. `data-fund-surface` از DetailFrame و success root بردار؛ `fundamental-surface` و `bg-[var(--fd-bg)]` بماند.
- `FundamentalCards`/`FundamentalSummary`: `useFundamentalPrefs`/`surface`/`data-fund-surface` را حذف کن؛ `fundamental-surface` بماند.
- `FundamentalScreenTable`: `surface` را از selector/`appearanceRef` و effect حذف کن؛ fade فقط با `[density]` اجرا شود. `Surface` import حذف.
- هیچ `data-fund-surface` در `frontend-v2/src` نماند: `grep -rn "data-fund-surface\|setSurface\|surface-paper\|surface-ink" frontend-v2/src` باید خالی باشد (به‌جز شاید نام `fundamental-surface`).

- [ ] **Step 6: تست/کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-prefs.spec.ts src/__tests__/fundamental-page-visual.spec.tsx src/__tests__/fundamental-cockpit.spec.tsx src/__tests__/fundamental-consumers.spec.tsx src/__tests__/fundamental-a11y.spec.tsx`
Expected: PASS.

```bash
git add frontend-v2/src/app/styles.css frontend-v2/src/features/fundamental/stores/prefs.ts frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx frontend-v2/src/features/fundamental/ui/FundamentalSummary.tsx frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx frontend-v2/src/__tests__/fundamental-prefs.spec.ts frontend-v2/src/__tests__/fundamental-page-visual.spec.tsx frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx frontend-v2/src/__tests__/fundamental-consumers.spec.tsx frontend-v2/src/__tests__/fundamental-a11y.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): پیروی کامل از تم برنامه و حذف سطح داده جدا"
```

---

### Task 3: پذیرش زنده و شواهد P0

**Files:** فقط شواهد untracked در `_audit/rebuild/fts-p0/`.

- [ ] **Step 1: full suite و typecheck**

Run: `cd frontend-v2 && npm run typecheck && npm test`
Expected: PASS؛ صفر خطای TS؛ همهٔ تست‌ها سبز.

- [ ] **Step 2: سرورها**

Python: `BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data BORS_NO_FETCH_LOOPS=1 python -m uvicorn app:app --host 127.0.0.1 --port 8110`
Vite: `BORS_BACKEND=http://127.0.0.1:8110 npx vite --port <free> --strictPort` (پورت آزاد؛ ۷۰۹۱ را دست نزن).

- [ ] **Step 3: اسکرین‌شات‌های دو تم برنامه**

- جدول comfortable/compact در **brass** (تیره) و **warm** (روشن)، ۱۳۶۶ و ۱۹۲۰.
- نمای رنيك و فولاد در هر دو تم؛ شاخص ۴ باید تیتر پتانسیل و مسیر OR را نشان دهد.
- هیچ سوییچ «کاغذی/تیره» نباید وجود داشته باشد؛ تغییر تم از پوستهٔ برنامه.
- P/NAV هلدینگ/بانک و CSV حفظ شود.
- Console errors = 0.

- [ ] **Step 4: اندازه‌گیری و رأی مالک**

- کنتراست متن/وضعیت در هر دو تم ≥ ۴٫۵ (حداقل برای متن ۱۱px+).
- TBT اسکرول واقعی ۱۹۲۰ (۲۰۰۰px/۳.۲s) و fling ثبت شود.
- شواهد را در `_audit/rebuild/fts-p0/` بگذار؛ تا رأی مالک PASS اعلام نکن و کامیت/پوش نهایی نساز.

---

## Self-review

- **Spec coverage:** F-01 (نام/تیتر/درصد نهایی) → Task 1؛ F-05 (تم واحد) → Task 2؛ شواهد/رأی → Task 3.
- **No placeholders:** همهٔ مسیرها/فیلدها/تست‌ها مشخص‌اند؛ fixtureها در Task 1 گام ۲ تعریف شده‌اند.
- **Type consistency:** `PotentialPath`/`potentialStatusOf`/`potentialPath` در axisMeta تعریف و در AxisCell/Panel استفاده می‌شوند؛ `Surface` حذف و ارجاعی نمی‌ماند.
- **Conflict note:** کلید داخلی `sales` برای سازگاری sortKey ذخیره‌شده حفظ می‌شود؛ برچسب/TESTID `panel-sales` حفظ می‌شود تا S4b نشکند؛ نام کاربری «پتانسیل سود تا آخر سال» است.
