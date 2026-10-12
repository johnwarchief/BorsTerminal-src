// اورلی‌های FTSِ چارت (#161): چارت باید همان اعدادِ سرور را رسم کند، نه چیزی که
// خودش حساب کرده باشد. اینجا هندسهٔ رسم را اندازه می‌گیریم، نه متن را.
import { act, fireEvent, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type OverlayCfg = { name?: string; groupId?: string; points?: { timestamp: number; value: number }[];
  extendData?: unknown; [key: string]: unknown };

let overlays: OverlayCfg[] = [];
/** لایۀ «الگوهای FTS» گروهٍ جدا دارد (`fts_pattern_overlays`) — جعبۀ رنج و
 *  مارکرهای ساختار آن‌جا رسم می‌شوند، نه در گروهِ سطوحِ فیبو/تریگر. */
let patternOverlays: OverlayCfg[] = [];
const chartStub = () => ({
  setDataLoader: vi.fn(), setSymbol: vi.fn<(o: unknown) => void>(), setPeriod: vi.fn(),
  setFormatter: vi.fn(), createIndicator: vi.fn(), removeIndicator: vi.fn(),
  setPaneOptions: vi.fn(), setStyles: vi.fn(), overrideYAxis: vi.fn(), overrideOverlay: vi.fn(),
  removeOverlay: vi.fn((q?: { groupId?: string }) => {
    if (q?.groupId === 'fts_strategy_overlays') overlays = [];
    if (q?.groupId === 'fts_pattern_overlays') patternOverlays = [];
  }),
  createOverlay: vi.fn((cfg: OverlayCfg) => {
    if (cfg.groupId === 'fts_strategy_overlays') overlays.push(cfg);
    if (cfg.groupId === 'fts_pattern_overlays') patternOverlays.push(cfg);
    return 'ov';
  }),
  resetData: vi.fn(), resize: vi.fn(), getConvertPictureUrl: vi.fn(() => ''),
  subscribeAction: vi.fn(), scrollToRealTime: vi.fn(), getDataList: vi.fn(() => []),
  setScrollEnabled: vi.fn(), getOverlays: vi.fn(() => [] as unknown[]),
});

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(), registerOverlay: vi.fn(), registerIndicator: vi.fn(),
  getSupportedOverlays: vi.fn(() => []),
}));

const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');

/** سه سطحِ فیبوی سرور، دو مارکرِ تاریخ‌دار و یک هشدار خروج — همه دست‌ساز */
const FTS = {
  fib: {
    retrace_base_high: 200, retrace_base_low: 100,
    zone_33_40: { lo: 155, hi: 165, in_zone: false },
    zone_618_70: { lo: 128, hi: 138, in_zone: false },
    levels: [
      { ratio: 0, price: 200 }, { ratio: 0.33, price: 165 }, { ratio: 0.4, price: 155 },
      { ratio: 0.5, price: 139 }, { ratio: 0.618, price: 128 }, { ratio: 0.7, price: 120 },
      { ratio: 1, price: 100 },
    ],
    leg: { direction: 'up', start: '2025-01-06', end: '2025-01-10', high: 200, low: 100 },
  },
  setups: [
    // ردیفِ کهنه: اگر سروری روزی جتِ تاریخی بفرستد، چارت رسمش نمی‌کند
    { date: '2025-01-07', kind: 'jet', label: 'جت', price: 210, side: 'above' },
    { date: '2025-01-09', kind: 'choch', label: 'CHoCH', price: 150, side: 'below' },
  ],
  status: {
    code: 'entry_trigger',
    text: 'تریگرِ فعال رویِ کندلِ امروز: جت',
    trigger: { kind: 'jet', label: 'جت', price: 210, date: '2025-01-10', role: 'entry' },
  },
  roles: { jet: 'entry', fib_zone: 'context' },
  exit_engine: { verdict: 'exit', l1: { ma14_exit: true } },
} as Record<string, unknown>;

const CANDLES = ['2025-01-06', '2025-01-07', '2025-01-08', '2025-01-09', '2025-01-10']
  .map((time, i) => ({ time, open: 100 + i, high: 102 + i, low: 99 + i, close: 101 + i, volume: 10 }));

const dayUtc = (s: string) => Date.parse(`${s}T00:00:00Z`);

async function renderChart(fts: unknown = FTS) {
  overlays = [];
  patternOverlays = [];
  vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
    const u = String(url);
    if (u.startsWith('/api/chart/')) {
      return { ok: true, json: async () => ({ status: 'success', candles: CANDLES, volumes: [],
        factors: CANDLES.map((c) => ({ time: c.time, factor: 1 })), adjustEvents: [] }) } as never;
    }
    return { ok: false, json: async () => ({}) } as never;
  }));
  render(<KLineChartWrapper initialSymbol="فولاد" fts={fts as never} />);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  // از «تعدیل عملکردی» (پیش‌فرض) به «بدون تعدیل» تا عددِ محور همان ریالِ سرور باشد
  await act(async () => { fireEvent.click(document.querySelector('[title="نوع تعدیل قیمت"]') as HTMLElement); });
  const none = Array.from(document.querySelectorAll('.nn-dropdown-item'))
    .find((e) => (e.textContent ?? '').includes('بدون تعدیل')) as HTMLElement;
  await act(async () => { fireEvent.click(none); });
  await act(async () => { await Promise.resolve(); });
  // لایۀ «تحلیل FTS» را روشن می‌کند. دورِ موتور تکنیکال پیش‌فرضِ محصول روشن شد
  // (سیگنال‌ها سنجشِ تاریخی گرفتند)، پس این‌جا دیگر «یک بار کلیک» کافی نیست —
  // با aria-pressed خوانده می‌شود تا تست به پیش‌فرضِ محصول گره نخورد.
  const ftsBtn = document.querySelector('[data-testid="nn-fts-layer-toggle"]') as HTMLElement;
  if (ftsBtn.getAttribute('aria-pressed') !== 'true') {
    await act(async () => { fireEvent.click(ftsBtn); });
  }
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

const drawn = (name: string) => overlays.filter((o) => o.name === name);

describe('اورلی FTS روی چارت، از دادهٔ سرور (#161)', () => {
  beforeEach(() => { vi.clearAllMocks(); overlays = []; });

  it('سطح‌های فیبو پیش‌فرض رسم نمی‌شوند (سلسله‌مراتبِ دورِ J: زمینه نباید کندل را بپوشاند)', async () => {
    await renderChart();
    expect(drawn('horizontalStraightLine')).toEqual([]);
    // کمربندها (مستطیل) همیشه می‌مانند
    expect(drawn('rect').length).toBe(2);
  });

  it('با کلیدِ «سطح‌های فیبو» هر هفت سطح با همان عددِ سرور رسم می‌شود', async () => {
    await renderChart();
    const btn = document.querySelector('[data-testid="nn-fib-levels-toggle"]') as HTMLElement;
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    await act(async () => { fireEvent.click(btn); });
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const values = drawn('horizontalStraightLine')
      .map((o) => o.points?.[0]?.value).sort((a, b) => (a ?? 0) - (b ?? 0));
    expect(values).toEqual([100, 120, 128, 139, 155, 165, 200]);
  });

  it('هیچ عددِ فیبویی که سرور نگفته روی چارت نمی‌نشیند', async () => {
    await renderChart();
    const allowed = new Set((FTS as unknown as { fib: { levels: { price: number }[] } }).fib.levels.map((l) => l.price));
    for (const o of drawn('horizontalStraightLine')) {
      expect(allowed.has(o.points?.[0]?.value as number)).toBe(true);
    }
  });

  it('نوارِ کمربند از آغازِ موج شروع می‌شود، نه از «الان»', async () => {
    await renderChart();
    const rects = drawn('rect');
    expect(rects.length).toBe(2);
    for (const r of rects) {
      expect(r.points?.[0]?.timestamp).toBe(dayUtc('2025-01-06'));
      expect(r.points?.[1]?.timestamp).toBe(dayUtc('2025-01-10'));
    }
    expect(rects.map((r) => r.points?.[1]?.value).sort((a, b) => (a ?? 0) - (b ?? 0))).toEqual([128, 155]);
    expect(rects.map((r) => r.points?.[0]?.value).sort((a, b) => (a ?? 0) - (b ?? 0))).toEqual([138, 165]);
  });

  it('مارکرهای ستاپ سرور سرِ کندلِ خودشان می‌نشینند، و جتِ تاریخی هیچ‌وقت', async () => {
    await renderChart();
    // پیش‌فرض: فقط تریگرِ فعلی (یک انوتیشن)، نه انبوه رویدادِ گذشته
    const off = drawn('simpleAnnotation');
    expect(off.map((m) => m.extendData)).toEqual(['▲ جت']);
    expect(off[0].points?.[0]?.timestamp).toBe(dayUtc('2025-01-10'));
    // رویدادهای تاریخی را با کلید روشن می‌کنیم
    const btn = document.querySelector('[data-testid="nn-history-events-toggle"]') as HTMLElement;
    await act(async () => { fireEvent.click(btn); });
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const marks = drawn('simpleAnnotation');
    // فیکسچر یک رویدادِ «جتِ ۲۰۲۵-۰۱-۰۷» دارد؛ چارت باید دورش بیندازد
    expect(marks.map((m) => String(m.extendData)).filter((s) => s.includes('جت') && !s.startsWith('▲'))).toEqual([]);
    const byLabel = Object.fromEntries(marks.map((m) => [String(m.extendData), m]));
    expect(byLabel['CHoCH']?.points?.[0]?.timestamp).toBe(dayUtc('2025-01-09'));
    expect(byLabel['▲ جت']?.points?.[0]?.timestamp).toBe(dayUtc('2025-01-10'));
  });

  it('هشدار خروج از موتورِ سرور می‌آید، نه از شرطِ تک‌کندلیِ چارت', async () => {
    await renderChart();
    expect((document.querySelector('.nn-fts-exit-alert')?.textContent ?? '')).toContain('هشدار خروج');
  });

  // مرحلۀ ۶، شکافِ ب-۳: باکسِ رنج ۲۰ کندلی است؛ رسمِ تمام‌عرضِ آن دروغ می‌گفت
  it('جعبۀ رنج درِ چارت کرانۀ بازۀ خودش را می‌گیرد و کمربندهای فیبو تمام‌عرض می‌مانند', async () => {
    // دیدِ این فیکسچر ۹۹→۱۰۶ است؛ باکسِ ۱۰۳→۱۰۴ یک‌هفتمِ پنل ⇒ مستطیلِ کراندار
    await renderChart({
      ...FTS,
      range_box: { active: true, top: 104, bottom: 103, pct_above_top: 1.4,
                   start_date: '2025-01-07', end_date: '2025-01-09' },
    });
    const rects = patternOverlays.filter((o) => o.name === 'rect');
    const box = rects.filter((r) => r.points?.[0]?.timestamp === dayUtc('2025-01-07'));
    expect(box).toHaveLength(1);
    expect(box[0].points?.map((p) => p.timestamp)).toEqual([dayUtc('2025-01-07'), dayUtc('2025-01-09')]);
    expect(box[0].points?.map((p) => p.value)).toEqual([104, 103]);
    // تنها مستطیلِ این گروه همان باکس است ⇒ باکس روی کلِ دید کشیده نشده
    expect(rects).toHaveLength(1);
  });

  it('باکسِ بلندتر از یک‌پنجمِ دید مستطیل نمی‌شود — به دو خطِ سطحِ سقف/کف تنزل می‌کند (#193)', async () => {
    // همان قاعدۀ سرور، بلندتر از دید (۱۰۱→۱۰۶ از دامنهٔ ۹۹→۱۰۶): سقفِ ارتفاعِ
    // بصری جعبه را هم می‌گیرد؛ سطوح دست‌نخورده می‌مانند، فقط شکلِ رسم عوض می‌شود.
    await renderChart({
      ...FTS,
      range_box: { active: true, top: 106, bottom: 101, pct_above_top: 1.4,
                   start_date: '2025-01-07', end_date: '2025-01-09' },
    });
    expect(patternOverlays.filter((o) => o.name === 'rect')).toHaveLength(0);
    const lines = patternOverlays
      .filter((o) => o.name === 'horizontalStraightLine')
      .map((o) => o.points?.[0]?.value);
    expect(lines).toEqual([106, 101]);
  });

  it('جعبۀ رنجِ بی‌کرانِ زمانی رویِ چارت نمی‌آید — extent حدس نیست', async () => {
    await renderChart({ ...FTS, range_box: { active: true, top: 210, bottom: 140 } });
    expect(patternOverlays.filter((o) => o.name === 'rect')).toHaveLength(0);
    expect(patternOverlays.some((o) => o.points?.some((p) => p.value === 210))).toBe(false);
  });

  // مرحلۀ ۶، شکافِ ب-۱: نسخۀ Wِ ساختار منتشر می‌شد ولی هیچ‌جا خوانده نمی‌شد
  it('پیوتِ هفتگیِ ساختار با برچسبِ (W) رویِ کندلِ خودش می‌نشیند', async () => {
    await renderChart({
      ...FTS,
      structure_points: {
        D: [{ idx: 1, time: '2025-01-07', confirm_idx: 3, confirm_time: '2025-01-09', price: 101, kind: 'low', label: 'HL' }],
        W: [{ idx: 2, time: '2025-01-08', confirm_idx: 4, confirm_time: '2025-01-10', price: 103, kind: 'high', label: 'LH' }],
      },
    });
    const marks = patternOverlays
      .filter((o) => o.name === 'simpleAnnotation')
      .map((o) => ({ label: String(o.extendData), ts: o.points?.[0]?.timestamp, v: o.points?.[0]?.value }));
    expect(marks).toEqual([
      { label: 'HL', ts: dayUtc('2025-01-07'), v: 101 },
      { label: 'LH (W)', ts: dayUtc('2025-01-08'), v: 103 },
    ]);
  });
});
