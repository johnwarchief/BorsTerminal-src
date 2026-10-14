// __tests__/engine-klinecharts-adapter.spec.ts -- آزمونِ مستقیمِ آداپترِ
// `engine/klinecharts` (بستۀ مرحلۀ ۷): رابطِ موتور «دو نکت = ناحیه» می‌گوید و
// `btsBand` تنها جایی است که آن نیت به هندسۀ v10 ترجمه می‌شود. اینجا دقیقاً همان
// هندسه اندازه گرفته می‌شود، نه اینکه دکمه‌ای کلیک شده باشد.
//
// stubِ klinecharts دو چیزی را مثلِ کتابخانه واقعاً رفتار می‌کند که آزمونِ سطحی
// نمی‌بیند: (۱) `createOverlay` یک `id` تولیدی می‌دهد (نه `id` ما)، پس «جایگزینیِ
// گروه» باید با همان idهایِ تولیدی کار کند؛ (۲) `rect` درِ v10 فقط *نوعِ شکل* است،
// پس کمربند تنها از اورلیِ ثبت‌شده (`btsBand`) عبور می‌کند.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChartOverlaySpec } from '@features/technical/engine/types';

type Row = { id: string; name?: string; groupId?: string; points?: { timestamp?: number; value: number }[];
  extendData?: unknown; styles?: unknown };

let rows: Row[] = [];
let seq = 0;
const created: Row[] = [];
const charts: ReturnType<typeof chartStub>[] = [];
let registeredOverlays: Record<string, unknown>[] = [];

const chartStub = () => ({
  setDataLoader: vi.fn(), setSymbol: vi.fn(), setPeriod: vi.fn(), resetData: vi.fn(),
  setOffsetRightDistance: vi.fn(), setStyles: vi.fn(), overrideYAxis: vi.fn(), overrideXAxis: vi.fn(),
  createIndicator: vi.fn(), removeIndicator: vi.fn(), setPaneOptions: vi.fn(),
  scrollToRealTime: vi.fn(), resize: vi.fn(), getConvertPictureUrl: vi.fn(() => ''),
  subscribeAction: vi.fn(), overrideOverlay: vi.fn(),
  getDataList: vi.fn(() => rows.map((r) => ({ timestamp: r.points?.[0]?.timestamp ?? 0 }))),
  getVisibleRange: vi.fn(() => ({ from: 0, to: rows.length - 1 })),
  createOverlay: vi.fn((cfg: Omit<Row, 'id'>) => {
    const row: Row = { ...cfg, id: `ov-${++seq}` };
    rows.push(row);
    created.push(row);
    return row.id;
  }),
  removeOverlay: vi.fn((q?: { id?: string; groupId?: string }) => {
    if (q?.id) rows = rows.filter((r) => r.id !== q.id);
    else if (q?.groupId) rows = rows.filter((r) => r.groupId !== q.groupId);
    else rows = [];
  }),
  getOverlays: vi.fn(() => rows),
});

vi.mock('klinecharts', () => ({
  init: vi.fn(() => {
    const chart = chartStub();
    charts.push(chart);
    return chart;
  }),
  dispose: vi.fn(),
  registerIndicator: vi.fn(),
  registerOverlay: vi.fn((def: Record<string, unknown>) => { registeredOverlays.push(def); }),
  getSupportedOverlayes: vi.fn(() => []),
}));

const { KLineChartsEngine } = await import('@features/technical/engine/klinecharts/KLineChartsEngine');

const T0 = Date.UTC(2026, 0, 5);
const DAY = 86_400_000;

const mountOpts = {
  visibleBars: 120,
  palette: { background: '#0b111c', grid: '#1b2637', up: '#16a34a', down: '#dc2626',
             axisText: '#94a3b8', lastLine: '#64748b', crosshair: '#e2e8f0' },
  candleStyle: 'candles',
  formatTime: () => '',
  formatPrice: (v: number) => String(v),
} as never;

/** باکسِ رنجِ مرحلۀ ۶ — همان شکلِ سازۀ `engineFtsLayers` (id پایدار، دو کرانۀ خودش) */
const boxBand: ChartOverlaySpec = {
  id: 'range-box', kind: 'band', group: 'fts-pattern',
  points: [{ timestamp: T0 + 2 * DAY, value: 1419 }, { timestamp: T0 + 22 * DAY, value: 1621 }],
  color: '#fbbf24', fill: 'rgba(251, 191, 36, 0.12)', label: 'جعبه رنج', width: 1, dashed: true,
};

async function mountedEngine() {
  const engine = new KLineChartsEngine();
  const host = document.createElement('div');
  await engine.mount(host, mountOpts);
  return engine;
}

/** تابعِ رسمِ اورلیِ ثبت‌شدۀ btsBand — همان چیزی که v10 با مختصاتِ پیکسل صدا می‌زند */
function bandFigures(coordinates: { x: number; y: number }[]) {
  const def = registeredOverlays.find((d) => d.name === 'btsBand') as
    { createPointFigures: (p: { coordinates: { x: number; y: number }[]; overlay: unknown }) => unknown[] } | undefined;
  expect(def, 'کمربند بی‌اورلیِ ثبت‌شده در v10 هیچ مستطیلی نمی‌سازد').toBeTruthy();
  return def!.createPointFigures({ coordinates, overlay: { extendData: { color: '#fbbf24', fill: 'rgba(251,191,36,0.12)' } } }) as
    { type: string; attrs: { x: number; y: number; width: number; height: number } }[];
}

describe('آداپترِ klinecharts — نگاشتِ kind و هندسۀ کمربند', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    rows = [];
    seq = 0;
    created.length = 0;
    charts.length = 0;
    // registeredOverlays عمداً پاک نمی‌شود: `bandOverlayRegistered` درِ خودِ آداپتر
    // وضعیتِ سطحِ ماژول است، پس «یک‌بار ثبت» درِ کلِ فایل سنجیده می‌شود.
  });

  it('هر kind به اورلیِ درستِ v10: band→btsBand، level، segment، marker', async () => {
    const engine = await mountedEngine();
    const specs: ChartOverlaySpec[] = [
      boxBand,
      { id: 'ma14', kind: 'level', group: 'fts-pattern', points: [{ timestamp: T0 + 24 * DAY, value: 1270 }], color: '#38bdf8' },
      { id: 'trendline', kind: 'segment', group: 'fts-pattern', points: [{ timestamp: T0, value: 1100 }, { timestamp: T0 + 9 * DAY, value: 1500 }], color: '#a78bfa' },
      { id: 'structure-W-2026-01-12:LL (W)', kind: 'marker', group: 'fts-structure', points: [{ timestamp: T0 + 7 * DAY, value: 1180 }], color: '#f87171', label: 'LL (W)' },
      // کمربندِ دوم درِ همان صدا: اورلی یک‌بار ثبت می‌شود، نه به‌ازایِ هر باکس
      { ...boxBand, id: 'third-peak', color: '#f472b6', points: [{ timestamp: T0, value: 1480 }, { timestamp: T0 + 20 * DAY, value: 1520 }] },
    ];
    engine.applyOverlays('fts-pattern', specs);
    expect(created.map((r) => r.name)).toEqual(['btsBand', 'horizontalStraightLine', 'segment', 'simpleAnnotation', 'btsBand']);
    expect(registeredOverlays.filter((d) => d.name === 'btsBand')).toHaveLength(1);
    // رنگِ کمربند از extendData خوانده می‌شود (styles.polygon اینجا نقشی ندارد)
    expect(created[0].extendData).toEqual({ color: '#fbbf24', fill: 'rgba(251, 191, 36, 0.12)', width: 1, dashed: true });
    expect(created[0].styles).toEqual({});
    expect(created[3].extendData).toBe('LL (W)');
    engine.destroy();
  });

  it('باکسِ کراندار با دو timestampِ خودش به موتور می‌رسد — نه از «الان»، نه تمام‌عرض', async () => {
    const engine = await mountedEngine();
    engine.applyOverlays('fts-pattern', [boxBand]);
    expect(created[0].points?.map((p) => p.timestamp)).toEqual([T0 + 2 * DAY, T0 + 22 * DAY]);
    expect(created[0].points?.map((p) => p.value)).toEqual([1419, 1621]);
    engine.destroy();
  });

  it('createPointFiguresِ btsBand مستطیل را بینِ همان دو مختصات می‌بندد (عرض = فاصلۀ دو نکت)', async () => {
    const engine = await mountedEngine();
    engine.applyOverlays('fts-pattern', [boxBand]);
    // مرتب‌سازیِ x/y و ارتفاعِ حداقلِ ۲ پیکسل (باکسِ تخت نازک هم دیده شود)
    const wide = bandFigures([{ x: 120, y: 300 }, { x: 380, y: 92 }]);
    expect(wide).toHaveLength(1);
    expect(wide[0].type).toBe('rect');
    expect(wide[0].attrs).toEqual({ x: 120, y: 92, width: 260, height: 208 });
    // جهتِ second point مهم نیست: همان جعبه از پایین به بالا
    const flipped = bandFigures([{ x: 380, y: 92 }, { x: 120, y: 300 }]);
    expect(flipped[0].attrs).toEqual({ x: 120, y: 92, width: 260, height: 208 });
    // باکسِ یک‌کندلی درِ زومِ زیاد: عرضِ منطقیِ صفر، ارتفاعِ حداقلِ دو پیکسل — باز هم کراندار
    const thin = bandFigures([{ x: 200, y: 150 }, { x: 200, y: 150.4 }]);
    expect(thin[0].attrs).toEqual({ x: 200, y: 150, width: 0, height: 2 });
    // نکتِ دومی نباشد نیم‌بند نمی‌سازیم
    expect(bandFigures([{ x: 100, y: 100 }])).toEqual([]);
    engine.destroy();
  });

  it('به‌روزرسانی «جایگزین» است نه انباشته: باکسِ حذف‌شده می‌رود و باکسِ تازه تک می‌ماند', async () => {
    const engine = await mountedEngine();
    engine.applyOverlays('fts-pattern', [boxBand]);
    expect(rows.filter((r) => r.groupId === 'fts-pattern')).toHaveLength(1);
    // نماد/TF عوض شده و لایۀ جدید باکس ندارد — idهایِ تولیدی هیچ‌وقت با idِ ما
    // یکی نیستند، پس کلِ گروهِ خودش باید برود (هیچ باکسِ کهنه‌ای رویِ نمودارِ تازه نمی‌ماند)
    engine.applyOverlays('fts-pattern', [
      { id: 'ma14', kind: 'level', group: 'fts-pattern', points: [{ timestamp: T0 + 24 * DAY, value: 1270 }], color: '#38bdf8' },
    ]);
    const live = rows.filter((r) => r.groupId === 'fts-pattern');
    expect(live).toHaveLength(1);
    expect(live[0].name).toBe('horizontalStraightLine');
    // باکس برگشت: درِ بوم فقط یک ردیفِ btsBand می‌ماند، هرچند دو بار ساخته شده
    engine.applyOverlays('fts-pattern', [boxBand]);
    expect(created.filter((r) => r.name === 'btsBand')).toHaveLength(2);
    expect(rows.filter((r) => r.name === 'btsBand')).toHaveLength(1);
    engine.destroy();
  });

  it('لایۀ بی‌نکت رسم نمی‌شود؛ خطایِ موتور درِ health می‌نشیند نه کرش', async () => {
    const engine = await mountedEngine();
    engine.applyOverlays('fts-pattern', [{ ...boxBand, points: [] }]);
    expect(created).toHaveLength(0);
    // createOverlay اگر بیفتد (اورلیِ ناشناخته/نسخۀ بی‌rect) اپ نمی‌افتد؛ شاهدش را می‌گوید
    const chart = charts[charts.length - 1];
    chart.createOverlay.mockImplementationOnce(() => { throw new Error('unknown overlay'); });
    engine.applyOverlays('fts-pattern', [boxBand]);
    const errs = engine.health().errors;
    expect(errs.some((e) => e.code === 'overlay' && e.message.includes('range-box'))).toBe(true);
    engine.destroy();
  });
});
