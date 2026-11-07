# FTS P1 — جزئیات شاخص ۱/۲/۳ و نمودارها — پلن اجرا

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** شاخص ۱ را با کف/هدف و ۱الف/۱ب و فروش دورهٔ جاری/قبل، شاخص ۲ را با رشد دوره‌به‌دورهٔ EPS و نمودار، و شاخص ۳ را با نام دقیق و نمودار کامل کن؛ هر شاخصی که داده دارد نمودار داشته باشد.

**Architecture:** `GrowthPanel` دو ریزنمودار ۱ب و فروش جاری/قبل می‌گیرد؛ `EpsPanel` یک ریزنمودار `DeltaBars` برای رشد دوره‌ای؛ همه داده‌ها از کارت/اسکرینر موجودند. هیچ بک‌اندی تغییر نمی‌کند.

**Tech Stack:** React/TS/Vite/Tailwind 4/Vitest؛ SVG درون‌خطی.

**Spec:** `_audit/rebuild/fts-critic/2026-11-04/report.md` (F-02/F-03/F-04) + جزوه ص ۳–۴ + `OWNER_RULINGS.md` #2/#3 + رأی مالک «نمودار هرجا ممکن است».

## Global Constraints

- هیچ فرمول/آستانهٔ تازه؛ کف رشد ۴۰، هدف ۶۰ (رأی #3)؛ حاشیه ناخالص کف ۲۰/استاندارد ۳۰ (رأی #2)؛ EPS فقط از سری موجود.
- ۱الف و ۱ب جدا؛ ۱ب فقط برای تولیدی‌ها applicable؛ شکاف داده = نامشخص نه رد.
- تم واحد برنامه؛ S4b حفظ؛ فارسی/RTL؛ بدون وابستگی؛ `tsc` صفر؛ تست‌ها سبز؛ کامیت محلی/بدون push.
- رنگ تنها حامل وضعیت نیست؛ نمودارها `role="img"` + label فارسی.

---

### Task 1: شاخص ۱ — کف/هدف، ۱الف/۱ب و فروش دورهٔ قبل

**Files:**
- Modify: `frontend-v2/src/features/fundamental/api/useFtsCard.ts`
- Modify: `frontend-v2/src/features/fundamental/lib/axisMeta.ts`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalAxisCell.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/panels/GrowthPanel.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/panels/MarginPanel.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx` (freshness label only)
- Test: `frontend-v2/src/__tests__/fundamental-schema.spec.ts`
- Test: `frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-table-visual.spec.tsx`

**Interfaces:**
- Consumes: `monetary.ytd_now_bt/ytd_prev_bt/threshold/target_threshold`, `volume.real_pct/volume_pct/threshold/pass/data_gap/applicable`, screener `i1a_pass/i1b_pass/i1b_applicable/i1b_data_gap`.
- Produces: `growthSubStatuses(row)` returning `{a: AxisStatus; b: AxisStatus}`; GrowthPanel threshold `کف ۴۰٪ · هدف ۶۰٪`, current/prior sales rows, 1b Bullet, sales-pair HistoryBars; margin label exact.

- [ ] **Step 1: تست‌ها را بنویس**

`fundamental-schema.spec.ts`:

```ts
it('parses current and previous sales and 1b evidence', () => {
  const parsed = FtsCardSchema.parse({
    status: 'success', symbol: 'فولاد',
    indicators: {
      '1': {
        monetary: { monetary_pct: 56, threshold: 40, target_threshold: 60, pass: true, ytd_now_bt: 250942.2, ytd_prev_bt: 160873.4 },
        volume: { applicable: true, real_pct: -2.5, pass: false, threshold: 0, reason: 'رشد واقعی منفی' },
      },
    },
  });
  expect(parsed.indicators?.['1']?.monetary?.ytd_now_bt).toBe(250942.2);
  expect(parsed.indicators?.['1']?.volume?.reason).toBe('رشد واقعی منفی');
});
```

`fundamental-cockpit.spec.tsx`:

```tsx
it('shows the growth floor/target, 1a/1b, and both sales periods with charts', () => {
  render(<FundamentalDetail symbol="فولاد" onBack={vi.fn()} />);
  const panel = screen.getByTestId('panel-growth');
  expect(panel.textContent).toContain('کف ۴۰٪');
  expect(panel.textContent).toContain('هدف ۶۰٪');
  expect(panel.textContent).toContain('۲۵۰٬۹۴۲');
  expect(panel.textContent).toContain('۱۶۰٬۸۷۳');
  expect(panel.textContent).toContain('−۲٫۵٪');
  expect(panel.querySelectorAll('svg[role="img"]').length).toBeGreaterThanOrEqual(2);
  expect(panel.querySelector('[data-testid="growth-sales-pair"]')).toBeTruthy();
});
```

`fundamental-table-visual.spec.tsx`:

```tsx
it('shows 1a/1b sub-statuses in the growth column', () => {
  render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
  const cell = screen.getByTestId('fundamental-cell-رنيك-growth');
  expect(cell.textContent).toContain('۱الف');
  expect(cell.textContent).toContain('۱ب');
});
```

Margin name:

```tsx
expect(screen.getByText('حاشیه سود ناخالص')).toBeTruthy();
```

- [ ] **Step 2: RED**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-schema.spec.ts src/__tests__/fundamental-cockpit.spec.tsx src/__tests__/fundamental-table-visual.spec.tsx`
Expected: FAIL — ytd/1b fields, sub-statuses, charts, exact margin name missing.

- [ ] **Step 3: schema و axisMeta**

- `Axis1Schema.monetary`: add `ytd_now_bt: Num, ytd_prev_bt: Num`.
- `ScreenerRowLike` Pick: add `i1a_pass`, `i1b_pass`, `i1b_applicable`, `i1b_data_gap`.
- In `axisMeta.ts`:

```ts
export function growthSubStatuses(row: Pick<ScreenerRowLike, 'i1a_pass' | 'i1b_pass' | 'i1b_applicable' | 'i1b_data_gap'>): { a: AxisStatus; b: AxisStatus } {
  const a: AxisStatus = row.i1a_pass === true ? 'pass' : row.i1a_pass === false ? 'fail' : 'unknown';
  const b: AxisStatus = row.i1b_applicable === false ? 'na'
    : row.i1b_pass === true ? 'pass'
      : row.i1b_pass === false ? 'fail'
        : row.i1b_data_gap ? 'unknown' : 'unknown';
  return { a, b };
}
```

`AXES` margin label → `'حاشیه سود ناخالص'`.

- [ ] **Step 4: AxisCell subclass**

In `FundamentalAxisCell` for growth, append to subtitle:

```tsx
const subs = axis === 'growth' ? growthSubStatuses(row) : null;
const growthSubtitle = subs
  ? `${thresholdLabel(thresholds, 'growth')} · ۱الف ${statusFa(subs.a)} · ۱ب ${statusFa(subs.b)}`
  : null;
```

Use `growthSubtitle` for the `subtitle` when axis growth; keep chart Bullet with combined status.

- [ ] **Step 5: GrowthPanel**

```tsx
const floor = monetary?.threshold ?? null;
const target = monetary?.target_threshold ?? null;
const volume = card.indicators?.['1']?.volume;
const volumeStatus = metricStatus(volume);
const money = (value: number | null | undefined) => value == null ? '—' : `${faNum(value, 0)} میلیارد تومان`;
// threshold label:
`کف ${faThreshold(floor, '٪')}${target == null ? '' : ` · هدف ${faThreshold(target, '٪')}`}`
// chart threshold={floor}
// rows:
['۱الف — رشد ریالی', pct],
['۱ب — رشد واقعی/تناژ', `${volumeValue(card)} · ${statusFa(volumeStatus)}`],
['فروش دورهٔ جاری', money(monetary?.ytd_now_bt)],
['فروش دورهٔ قبل', money(monetary?.ytd_prev_bt)],
// children:
<div className="grid grid-cols-2 gap-2">
  <div>
    <span className="text-[9px] ...">۱ب — رشد واقعی</span>
    <div className="h-[24px]"><Bullet value={volume?.applicable === false ? null : volume?.real_pct ?? null} max={100} threshold={volume?.threshold ?? null} status={volumeStatus} label="رشد واقعی ۱ب" /></div>
  </div>
  <div data-testid="growth-sales-pair">
    <span className="text-[9px] ...">فروش جاری / دورهٔ قبل</span>
    <div className="h-[24px]"><HistoryBars values={[monetary?.ytd_prev_bt ?? null, monetary?.ytd_now_bt ?? null]} labels={['دوره قبل', 'دوره جاری']} status="pass" /></div>
  </div>
</div>
```

Import `faNum` from `@shared/lib/fa`, `HistoryBars`, `faThreshold`. Keep reason row.

- [ ] **Step 6: MarginPanel exact name**

`title="حاشیه سود ناخالص"`; `subtitle="سود ناخالص ÷ درآمد عملیاتی × ۱۰۰؛ کف ۲۰٪ · استاندارد ۳۰٪"`; `details` unchanged. `FundamentalDetail` freshness label `'3_gross_margin': 'حاشیه سود ناخالص'`.

- [ ] **Step 7: GREEN + commit**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-schema.spec.ts src/__tests__/fundamental-cockpit.spec.tsx src/__tests__/fundamental-table-visual.spec.tsx src/__tests__/fundamental-holding.spec.tsx`
then `npm test`.
Commit:
`git add ... && git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): جزئیات و نمودارهای ۱الف/۱ب و فروش دوره‌ای"`

---

### Task 2: شاخص ۲ — رشد دوره‌به‌دورهٔ EPS + نمودار DeltaBars

**Files:**
- Modify: `frontend-v2/src/features/fundamental/api/useFtsCard.ts` (eps_yoy_pct)
- Modify: `frontend-v2/src/features/fundamental/lib/axisMeta.ts` (epsChanges/epsChangeText/epsDeltaText)
- Create: `frontend-v2/src/features/fundamental/ui/mini/DeltaBars.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/panels/EpsPanel.tsx`
- Modify: `frontend-v2/src/app/styles.css` (delta bar colors)
- Test: `frontend-v2/src/__tests__/fundamental-axis-meta.spec.ts`
- Test: `frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-mini.spec.tsx`

**Interfaces:**
- Consumes: `indicators['2'].eps_series/period_ends/eps_yoy_pct`.
- Produces: `epsChanges(series, fromBackend?)`, `epsChangeText(pct)`, `epsDeltaText(prev, cur)`, `DeltaBars({ values, labels })`.

- [ ] **Step 1: تست‌ها**

axis-meta:

```ts
it('computes EPS period deltas and growth percentages', () => {
  const changes = epsChanges([1119, 1615, 1672]);
  expect(changes).toEqual([null, 44.325, 3.529]);
  expect(epsChangeText(changes[1])).toBe('+۴۴٫۳٪');
  expect(epsDeltaText(1119, 1615)).toBe('+۴۹۶');
  expect(epsDeltaText(1615, 1672)).toBe('+۵۷');
});
```

cockpit:

```tsx
it('shows each EPS period delta and growth with a chart', () => {
  render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
  const panel = screen.getByTestId('panel-eps');
  expect(screen.getByTestId('eps-period-1').textContent).toContain('+۴۹۶');
  expect(screen.getByTestId('eps-period-1').textContent).toContain('+۴۴٫۳٪');
  expect(screen.getByTestId('eps-period-2').textContent).toContain('+۵۷');
  expect(panel.querySelector('[data-testid="eps-growth-chart"]')).toBeTruthy();
});
```

mini:

```tsx
it('renders delta bars with direction classes', () => {
  render(<DeltaBars values={[null, 44.3, 3.5]} labels={['۱۴۰۳', '۱۴۰۴', '۱۴۰۵']} />);
  expect(screen.getByRole('img', { name: /رشد دوره‌ای/ })).toBeTruthy();
  expect(document.querySelectorAll('.fd-delta-bar.is-up').length).toBe(2);
});
```

- [ ] **Step 2: RED** with the same focused specs.

- [ ] **Step 3: axisMeta helpers + schema**

```ts
export function epsChanges(series: readonly (number | null | undefined)[] | null | undefined, fromBackend?: readonly (number | null | undefined)[] | null | undefined): (number | null)[] {
  if (!Array.isArray(series)) return [];
  if (Array.isArray(fromBackend) && fromBackend.length === series.length) {
    return fromBackend.map((value) => value == null || !Number.isFinite(Number(value)) ? null : Number(value));
  }
  return series.map((value, index) => {
    if (index === 0) return null;
    const prev = series[index - 1];
    if (prev == null || value == null || !Number.isFinite(Number(prev)) || !Number.isFinite(Number(value)) || Number(prev) <= 0) return null;
    return ((Number(value) - Number(prev)) / Number(prev)) * 100;
  });
}

export function epsChangeText(pct: number | null | undefined): string {
  if (pct == null || !Number.isFinite(pct)) return '—';
  return fmtPct(pct, 1);
}

export function epsDeltaText(prev: number | null | undefined, cur: number | null | undefined): string {
  if (prev == null || cur == null || !Number.isFinite(prev) || !Number.isFinite(cur)) return '—';
  const delta = cur - prev;
  const sign = delta > 0 ? '+' : delta < 0 ? '−' : '';
  return `${sign}${toFaDigits(Math.abs(Math.round(delta)))}`;
}
```

Add `eps_yoy_pct: z.array(z.number().nullable()).nullish()` to Axis2Schema. Import `fmtPct` from `@shared/lib/fa`.

- [ ] **Step 4: DeltaBars**

```tsx
export function DeltaBars({ values, labels, height = 30 }: { values: Array<number | null>; labels: string[]; height?: number }) {
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  return (
    <div className="flex h-full items-end gap-1" role="img" aria-label="رشد دوره‌ای EPS">
      {values.map((v, i) => {
        const pct = v == null ? 0 : (Math.abs(v) / max) * 48;
        return (
          <div key={i} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end" title={`${labels[i]} — ${v ?? '—'}٪`}>
            <div className="flex h-full w-full flex-col justify-center">
              <span className={`fd-delta-bar ${v != null && v < 0 ? 'is-down' : 'is-up'}`} style={{ height: `${Math.max(v == null ? 0 : 3, pct)}%` }} />
            </div>
            <span className="truncate text-[8px] text-[var(--fd-text-3)]">{labels[i]}</span>
          </div>
        );
      })}
    </div>
  );
}
```

CSS:

```css
.fundamental-surface .fd-delta-bar.is-up { background: var(--fd-up); }
.fundamental-surface .fd-delta-bar.is-down { background: var(--fd-down); }
```

- [ ] **Step 5: EpsPanel**

```tsx
const changes = epsChanges(series, eps?.eps_yoy_pct);
const labels = eps?.period_ends ?? series.map((_, index) => `دوره ${toFaDigits(index + 1)}`);
// children:
<div className="flex flex-col gap-1">
  <div className="h-[30px]" data-testid="eps-growth-chart">
    <DeltaBars values={changes} labels={labels} />
  </div>
  <div className="grid grid-cols-1 gap-0.5">
    {series.map((value, index) => (
      <div key={index} data-testid={`eps-period-${index}`} className="flex items-center justify-between gap-2 border-b border-[var(--fd-line)] py-0.5 text-[9.5px]">
        <span className="text-[var(--fd-text-3)]">{labels[index]}</span>
        <b className="text-[var(--fd-text)]">{faInt(value)}</b>
        <span className="text-[var(--fd-text-2)]">{index === 0 ? '—' : epsDeltaText(series[index - 1], value)}</span>
        <span className={changes[index] != null && changes[index]! < 0 ? 'text-[var(--fd-down)]' : 'text-[var(--fd-up)]'}>{epsChangeText(changes[index])}</span>
      </div>
    ))}
  </div>
</div>
```

Import `DeltaBars`, `epsChangeText`, `epsDeltaText`, `epsChanges`, `faInt` already.

- [ ] **Step 6: GREEN + commit**

Run all focused + full suite; commit:
`git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): رشد دوره‌به‌دورهٔ EPS و نمودار DeltaBars"`

---

### Task 3: پذیرش زنده P1

- [ ] `npm run typecheck && npm test` سبز.
- [ ] build + اسکرین‌شات‌های brass/warm، ۱۳۶۶/۱۹۲۰: پنل رشد (۱ب + فروش جاری/قبل + کف/هدف)، پنل EPS (دلتا/درصد/DeltaBars)، نام شاخص ۳، همهٔ پنج شاخص نمودار دارند.
- [ ] کنسول صفر؛ P/NAV و CSV حفظ؛ کنتراست ≥۴٫۵؛ TBT واقعی.
- [ ] رأی مالک؛ بدون push.

## Self-review

- Spec coverage: F-02 (رشد دوره‌ای EPS) → Task 2؛ F-03 (نام/فرمول/نمودار) → Task 1؛ F-04 (کف/هدف و ۱الف/۱ب و فروش دوره‌ای) → Task 1؛ «نمودار هرجا ممکن» → Task 1/2.
- No placeholders: فیلدها/تست‌ها/مسیرها مشخص.
- Type consistency: `growthSubStatuses` از `ScreenerRowLike` توسعه‌یافته؛ `epsChanges/epsChangeText/epsDeltaText` در axisMeta و مصرف در EpsPanel.
- کلید `sales` و `panel-sales` دست‌نخورده؛ تم واحد P0 حفظ.
