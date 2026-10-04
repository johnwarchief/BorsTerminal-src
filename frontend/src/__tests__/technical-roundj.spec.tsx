// دورِ J — سه آزمونِ پایانیِ مسیرِ تکنیکال:
//  ۹) چارت، سایدبار و `/api/fts` یک رأی واحد می‌دهند (نه سه رأیِ هم‌خانواده)
//  ۱۰) KLineCharts و موتورِ دوم همان payload و همان کندل‌ها را مصرف می‌کنند
//  ۱۱) چند سیگنالِ هم‌کندل در یک برچسب ادغام می‌شوند و قیمتشان جابه‌جا نمی‌شود
import { act, fireEvent, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';
import { engineFtsLayers } from '@features/technical/lib/engineFtsLayers';
import { patternInputsFromFts } from '@features/technical/lib/patternOverlays';
import { jetBadges } from '@features/technical/components/FtsBadgeStrip';
import { resolveFtsStatusView } from '@features/technical/components/FtsStatusCard';
import { technicalSignal } from '@features/technical/signals/technicalSignals';

type OverlayCfg = { name?: string; groupId?: string; points?: { timestamp: number; value: number }[];
  extendData?: unknown; [key: string]: unknown };
let overlays: OverlayCfg[] = [];
const chartStub = () => ({
  setDataLoader: vi.fn(), setSymbol: vi.fn<(o: unknown) => void>(), setPeriod: vi.fn(),
  setFormatter: vi.fn(), createIndicator: vi.fn(), removeIndicator: vi.fn(),
  setPaneOptions: vi.fn(), setStyles: vi.fn(), overrideYAxis: vi.fn(), overrideOverlay: vi.fn(),
  removeOverlay: vi.fn((q?: { groupId?: string }) => {
    if (q?.groupId === 'fts_strategy_overlays') overlays = [];
  }),
  createOverlay: vi.fn((cfg: OverlayCfg) => {
    if (cfg.groupId === 'fts_strategy_overlays') overlays.push(cfg);
    return 'ov';
  }),
  resetData: vi.fn(), resize: vi.fn(), getConvertPictureUrl: vi.fn(() => ''),
  subscribeAction: vi.fn(), scrollToRealTime: vi.fn(), getDataList: vi.fn(() => []),
  setScrollEnabled: vi.fn(), getOverlays: vi.fn(() => [] as unknown[]),
});
vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()), dispose: vi.fn(), registerOverlay: vi.fn(),
  registerIndicator: vi.fn(), getSupportedOverlays: vi.fn(() => []),
}));
const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');

const CANDLES = ['2025-01-06', '2025-01-07', '2025-01-08', '2025-01-09', '2025-01-10']
  .map((time, i) => ({ time, open: 100 + i, high: 102 + i, low: 99 + i, close: 101 + i, volume: 10 }));
const dayUtc = (s: string) => Date.parse(`${s}T00:00:00Z`);

/** یک payloadِ واحد — همان چیزی که `/api/fts` می‌فرستد (جتِ امروز + دو رویدادِ هم‌کندل) */
const FTS = {
  jet: { active: true, resistance: 210, ceiling: 205, static_broke: true, tier: 'strong',
         resistance_date: '2025-01-08', reason: null },
  choch: { bearish: false, bullish: false, level: null },
  point_hunt: { active: false, floor_price: null, touches: 2, floor_date: '2025-01-06' },
  double_bottom: { active: false }, range_box: { active: false },
  fib: { zone_33_40: { lo: 150, hi: 160, in_zone: true }, zone_618_70: { lo: 120, hi: 130, in_zone: false },
         levels: [{ ratio: 0.5, price: 140 }], leg: { direction: 'up', start: '2025-01-06' } },
  trend: { D: { trend: 'up' }, W: { trend: 'up' }, M: { trend: 'up' }, alignment: 'up',
           matrix: { decision: 'PERMITTED', setup: 'JET_OR_PULLBACK_HOLD' } },
  hourglass: { active: false, ma52: null },
  exit_engine: { verdict: 'hold', signals: [], unmeasured: [],
                 l1: { ma14_exit: false, hard_stop: 190, stop_hit: false },
                 l3: { third_peak: false, double_top: false, hs_break: false } },
  status: { code: 'entry_trigger', text: 'تریگرِ فعال رویِ کندلِ امروز: جت',
            trigger: { kind: 'jet', label: 'جت', price: 210, date: '2025-01-10', role: 'entry' },
            exits: [], warnings: [], unknown: [], vetoed: false },
  roles: { jet: 'entry', fib_zone: 'context', third_peak: 'warning', ma14_exit: 'exit' },
  // دو رویدادِ تاریخی رویِ یک کندل و یک رویدادِ هم‌قیمتِ نزدیک
  setups: [
    { date: '2025-01-09', kind: 'choch', label: 'CHoCH', price: 105, side: 'below' },
    { date: '2025-01-09', kind: 'dbl', label: 'دابل‌باتم', price: 105.4, side: 'above' },
    { date: '2025-01-06', kind: 'choch', label: 'CHoCH', price: 150, side: 'above' },
  ],
} as unknown as FtsAnalysisData;

async function renderWith(fts: FtsAnalysisData) {
  overlays = [];
  vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
    const u = String(url);
    if (u.startsWith('/api/chart/')) {
      return { ok: true, json: async () => ({ status: 'success', candles: CANDLES, volumes: [],
        factors: CANDLES.map((c) => ({ time: c.time, factor: 1 })), adjustEvents: [] }) } as never;
    }
    if (u.startsWith('/api/fts/')) {
      return { ok: true, json: async () => ({ status: 'success', fts }) } as never;
    }
    return { ok: false, json: async () => ({}) } as never;
  }));
  render(<KLineChartWrapper initialSymbol="فولاد" fts={fts} />);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  // «بدون تعدیل» تا عددِ محور همان ریالِ سرور باشد (وگرنه kِ نمایش اعداد را عوض می‌کند)
  await act(async () => { fireEvent.click(document.querySelector('[title="نوع تعدیل قیمت"]') as HTMLElement); });
  const none = Array.from(document.querySelectorAll('.nn-dropdown-item'))
    .find((e) => (e.textContent ?? '').includes('بدون تعدیل')) as HTMLElement;
  await act(async () => { fireEvent.click(none); });
  await act(async () => { await Promise.resolve(); });
  const ftsBtn = document.querySelector('[data-testid="nn-fts-layer-toggle"]') as HTMLElement;
  if (ftsBtn?.getAttribute('aria-pressed') !== 'true') {
    await act(async () => { fireEvent.click(ftsBtn); });
  }
  const histBtn = document.querySelector('[data-testid="nn-history-events-toggle"]') as HTMLElement;
  await act(async () => { fireEvent.click(histBtn); });
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

const drawn = (name: string) => overlays.filter((o) => o.name === name);

/** ورودیِ کاملِ سیگنال (۶۰ کندلِ معتبر ⇒ داوری «کوتاه» نیست) */
function mkSignal(fts: FtsAnalysisData, ts = 1_700_000_000_000) {
  const n = 60;
  const closes = Array.from({ length: n }, (_, i) => 100 + i);
  return technicalSignal({
    symbol: 'فولاد',
    opens: closes.map((c) => c - 1),
    closes,
    highs: closes.map((c) => c + 2),
    lows: closes.map((c) => c - 2),
    volumes: Array.from({ length: n }, () => 10),
    riskGatePass: true,
    enforceRiskGates: true,
    fts,
  }, ts);
}

describe('یک رأی در سه جا (#224)', () => {
  it('چارت، بج‌ها، کارتِ وضعیت و سیگنالِ مستر همه از همان payload ONE رأی می‌دهند', () => {
    const sig = mkSignal(FTS);
    // ۱) سیگنال: جتِ فعال ⇒ breakout و عنوانِ «پرواز»
    expect(sig.payload.setups).toContain('breakout');
    expect(sig.direction).toBe('bullish');
    // ۲) کارتِ وضعیت: همان entry_trigger از موتور، نه متنِ ثابت
    const view = resolveFtsStatusView(sig, false);
    const st = FTS.status!;
    expect(view.code).toBe(st.code);
    expect(view.text).toBe(st.text);
    // ۳) بج‌ها: یک بجِ جت (نه دو)، و زمینه‌ها بجِ ستاپ نمی‌گیرند
    const badges = jetBadges(FTS);
    expect(badges.length).toBe(1);
    expect(badges[0].label).toBe('جت فعال');
    // ۴) فیبو درِ هیچ‌کدام از سه‌جا «ستاپ» نیست
    expect(sig.payload.setups).not.toContain('fibonacci');
    expect(sig.payload.context).toContain('fib_zone_33_40');
  });

  it('با وتوی هفتگی، هیچ‌کدام «پرواز فعال» نمی‌نویسند', () => {
    const vetoed = {
      ...FTS,
      trend: { ...FTS.trend, W: { trend: 'down' }, alignment: 'na',
               matrix: { decision: 'REJECT', setup: 'NONE' } },
      status: { ...FTS.status, code: 'weekly_veto', text: 'وتوی تایم هفتگی — فرصت ورود نمی‌دهد',
                trigger: null, vetoed: true },
    } as unknown as FtsAnalysisData;
    const sig = mkSignal(vetoed);
    expect(resolveFtsStatusView(sig, false).code).toBe('weekly_veto');
    expect(sig.title).not.toContain('پرواز');
    expect(jetBadges(vetoed as never as FtsAnalysisData)[0].label).toBe('جت (وتوی هفتگی)');
  });
});

describe('دو موتور، یک منبع (#224)', () => {
  const plain = { toDisp: (p: number) => p, tsForDate: (d: string) => dayUtc(d) };

  it('نگاشتِ kline و موتورِ دوم همان سطحِ جت و همان کندل را می‌خوانند', () => {
    const k = patternInputsFromFts(FTS, plain);
    const f = engineFtsLayers({ fts: FTS, anchorTs: dayUtc('2025-01-10'),
                                startTs: dayUtc('2025-01-06'), toDisp: plain.toDisp,
                                tsForDate: plain.tsForDate });
    expect(k.jet.level).toBe(210);
    const jetLayer = f.find((l) => l.id === 'jet')!;
    expect(jetLayer.points.map((p) => p.value)).toEqual([210, 210]);
    expect(jetLayer.points[0].timestamp).toBe(dayUtc('2025-01-08'));
    expect(jetLayer.points[1].timestamp).toBe(dayUtc('2025-01-10'));
    // تریگرِ فعلی درِ هر دو هست و از همان عدد/تاریخ می‌آید
    const trig = f.find((l) => l.id === 'current-trigger')!;
    expect(trig.points[0].timestamp).toBe(dayUtc('2025-01-10'));
    expect(trig.points[0].value).toBe(210);
  });

  it('موتورِ دوم سطح فیبو را پیش‌فرض نمی‌کشد، درست مثلِ kline', () => {
    const off = engineFtsLayers({ fts: FTS, anchorTs: dayUtc('2025-01-10'), startTs: dayUtc('2025-01-06'),
                                  toDisp: plain.toDisp, tsForDate: plain.tsForDate });
    expect(off.filter((l) => l.id.startsWith('fib-level-'))).toEqual([]);
    const on = engineFtsLayers({ fts: FTS, anchorTs: dayUtc('2025-01-10'), startTs: dayUtc('2025-01-06'),
                                 toDisp: plain.toDisp, tsForDate: plain.tsForDate, showFibLevels: true });
    expect(on.map((l) => l.id)).toContain('fib-level-0.5');
  });
});

describe('چند سیگنال روی یک کندل (#224)', () => {
  beforeEach(() => { vi.clearAllMocks(); overlays = []; });

  it('رویدادهای هم‌کندل در یک برچسب ادغام می‌شوند و هیچ قیمتی جابه‌جا نمی‌شود', async () => {
    await renderWith(FTS);
    const marks = drawn('simpleAnnotation');
    // دو رویدادِ ۲۰۲۵-۰۱-۰۹ در یک برچسب، رویدادِ ۰۱-۰۸ جدا، و تریگرِ فعلی جدا
    const labels = marks.map((m) => String(m.extendData));
    expect(labels.some((l) => l.includes('CHoCH') && l.includes('دابل‌باتم'))).toBe(true);
    expect(labels.filter((l) => l === 'CHoCH • دابل‌باتم').length).toBe(1);
    // هیچ مارکری قیمتش درصدی جابه‌جا شده نباشد: هر مقدار باید عینِ عددِ سرور باشد
    const allowed = new Set([105, 105.4, 150, 210]);
    for (const m of marks) {
      const v = m.points?.[0]?.value as number;
      expect(allowed.has(Math.round(v * 10) / 10), `برچسب ${m.extendData} روی ${v}`).toBe(true);
    }
    // تریگرِ فعلی برجسته و رویِ کندلِ آخر است
    const trig = marks.find((m) => String(m.extendData).startsWith('▲'));
    expect(trig?.points?.[0]?.timestamp).toBe(dayUtc('2025-01-10'));
    expect(trig?.points?.[0]?.value).toBe(210);
  });
});

