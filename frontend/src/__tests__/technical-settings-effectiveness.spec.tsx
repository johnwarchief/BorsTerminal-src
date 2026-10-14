// گاردمانِ قدمِ ۵/۷ — «کنترلِ زنده باید اثر داشته باشد»
// قدمِ صفر پنج ردیفِ تنظیمات را مرده شمرد (D-1): مقدار درِ localStorage می‌نشست و
// هیچ‌جای کدِ چارت خوانده نمی‌شد. این پرونده همان پنج را با جاسوسی از API واقعیِ
// `klinecharts` v10 می‌سنجد: نه اینکه state عوض شد، بلکه اینکه **به کتابخانه رسید**.
// توجه: این‌ها تستِ jsdom با stub هستند، نه آزمونِ مرورگر واقعی؛ راستی‌آزماییِ
// پیکسلیِ نهایی درِ `_audit/ra365_job_phase7_ui.js` با Edge انجام می‌شود.
import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';
import { FtsEngineChart } from '@features/technical/components/FtsEngineChart';
import { FFC_ADJUSTMENT_BASIS_LABEL, FFC_ADJUSTMENT_MODE } from '@features/technical/nahayatnegar/lib/adjustments';

let lastChartInstance: ReturnType<typeof chartStub> | null = null;

function chart() {
  if (!lastChartInstance) throw new Error('chart stub هنوز ساخته نشده');
  return lastChartInstance;
}

const DAY = 86400000;
const T0 = Date.parse('2026-01-08T00:00:00Z');
const ISO = ['2026-01-08', '2026-01-09', '2026-01-12'];

/** پاسخِ `/api/chart` با ضریبِ تجمعیِ سرور: دو کندلِ نخست ۰٫۵، آخری ۱ */
const CHART_PAYLOAD = {
  status: 'success',
  candles: ISO.map((time, i) => ({ time, open: 100, high: 110, low: 90, close: 100 + i })),
  volumes: ISO.map((time) => ({ time, value: 1000 })),
  adjustEvents: [{ date: '2026-01-10', ratio: 0.5 }],
  factors: [
    { time: ISO[0], factor: 0.5 },
    { time: ISO[1], factor: 0.5 },
    { time: ISO[2], factor: 1 },
  ],
  corporateEvents: [],
  adjustCapability: {
    source: 'ledger+base-price-discontinuity', combined_available: true,
    functional_available: false, functional_reason: 'r',
    functional_blockers: ['event-type-unresolved:2'], chain_complete: true,
  },
};

const chartStub = () => {
  const instance = {
    setDataLoader: vi.fn(),
    setSymbol: vi.fn(),
    setPeriod: vi.fn(),
    setFormatter: vi.fn(),
    createIndicator: vi.fn(),
    removeIndicator: vi.fn(),
    setPaneOptions: vi.fn(),
    setStyles: vi.fn(),
    overrideYAxis: vi.fn(),
    overrideXAxis: vi.fn(),
    overrideOverlay: vi.fn(),
    removeOverlay: vi.fn(),
    createOverlay: vi.fn(() => 'ov-1'),
    resetData: vi.fn(),
    resize: vi.fn(),
    getConvertPictureUrl: vi.fn(() => ''),
    subscribeAction: vi.fn(),
    scrollToRealTime: vi.fn(),
    getDataList: vi.fn(() => []),
    getVisibleRange: vi.fn(() => ({ from: 0, to: 2 })),
    setScrollEnabled: vi.fn(),
    setZoomEnabled: vi.fn(),
    getOverlays: vi.fn(() => [] as Record<string, unknown>[]),
  };
  lastChartInstance = instance;
  return instance;
};

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(),
  registerOverlay: vi.fn(),
  registerIndicator: vi.fn(),
  getSupportedOverlays: vi.fn(() => []),
}));

vi.mock('@shared/api/http', () => ({
  // پیش‌فرض: شبکه نیست (همان شرایطِ سوئییتِ همسایهٔ technical-nn-chart.spec.tsx)؛
  // تست‌هایی که سریِ داده لازم دارند با `mockResolvedValueOnce` پاسخِ واقعیِ
  // `/api/chart` را تزریق می‌کنند. بی‌این، هر تست سه لایۀ فال‌بک را طی می‌کند و
  // React هشدارِ «not wrapped in act» می‌دهد.
  http: vi.fn(async () => { throw new Error('no network in this test'); }),
}));

const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');

/** آخرین باری که چارت از دیتا لودر می‌خواهد — همان سریِ کاننیکالِ تعدیل‌شده */
function loaderBars(): { timestamp: number; close: number; volume?: number }[] {
  const calls = chart().setDataLoader.mock.calls;
  const last = calls[calls.length - 1]?.[0] as
    { getBars: (a: { callback: (bars: unknown[], e: unknown) => void }) => void } | undefined;
  if (!last?.getBars) throw new Error('دیتا لودر ثبت نشده');
  let out: { timestamp: number; close: number; volume?: number }[] = [];
  last.getBars({ callback: (bars) => { out = bars as never; } });
  return out;
}

/** حلقۀ میکروتسک‌ها را زهکش می‌کند (نه تایمرِ ۲ ثانیه‌ایِ خودِ چارت، که وگرنه
 *  تیکِ ساعتِش درِ میانهٔ سوئیت می‌افتد و هشدارِ act می‌دهد). */
const flush = async () => {
  // سه لایۀ فال‌بکِ `fetchCandleData` هر کدام یک await دارند؛ هشت حلقه کافی است
  // تا همه‌شان درِ همین act زهکش شوند و بعد از پایانِ تست به‌روزرسانیِ بی‌act نروند.
  for (let i = 0; i < 8; i += 1) await act(async () => { await Promise.resolve(); });
};

const lastStyles = () => {
  const c = chart().setStyles.mock.calls;
  return c[c.length - 1]?.[0] as Record<string, any>;
};

const lastYAxisOverride = () => {
  const c = chart().overrideYAxis.mock.calls;
  return c[c.length - 1]?.[0] as Record<string, unknown>;
};

describe('کنترل‌هایِ تنظیمات باید به موتورِ چارت برسند (D-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastChartInstance = null;
    useFtsConfigStore.getState().setPriceScale('normal');
    useFtsConfigStore.getState().setView({
      axisDragLock: false, axisTickMargin: 3, wickGray: false,
      showWatermark: true, watermarkOpacity: 20, showBorders: true, showWicks: true,
      candleUp: '#089981', candleDown: '#f23645', wickUp: null, wickDown: null,
    } as never);
  });

  // ── ۱) قفلِ درگِ محور ──────────────────────────────────────────────────
  it('پیش‌فرض: درگِ محور آزاد است ⇒ scrollZoomEnabled:true روی هر دو محور', async () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    expect(lastYAxisOverride().scrollZoomEnabled).toBe(true);
    const xc = chart().overrideXAxis.mock.calls;
    expect(xc[xc.length - 1]?.[0]).toEqual({ scrollZoomEnabled: true });
  });

  it('روشن‌کردنِ «قفل درگ محور» ⇒ همان پرچم به کتابخانه می‌رسد', async () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    act(() => { useFtsConfigStore.getState().setView({ axisDragLock: true }); });
    expect(lastYAxisOverride().scrollZoomEnabled).toBe(false);
  });

  it('با عوض‌شدنِ مقیاس، قفلِ درگ نمی‌میرد (overrideYAxis درِ v10 ادغام نمی‌کند)', async () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    act(() => { useFtsConfigStore.getState().setView({ axisDragLock: true }); });
    act(() => { screen.getByTitle('مقیاس لگاریتمی').click(); });
    const o = lastYAxisOverride();
    expect(o.name).toBe('logarithm');
    expect(o.scrollZoomEnabled).toBe(false);   // ← نقصِ D-1/D-6: نام می‌رفت و قفل می‌ماند
  });

  // ── ۲) حاشیۀ برچسبِ محورها ────────────────────────────────────────────
  it('حاشیۀ انتخابیِ کاربر درِ tickText هر دو محور می‌نشیند', async () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    act(() => { useFtsConfigStore.getState().setView({ axisTickMargin: 10 }); });
    const s = lastStyles();
    expect(s.xAxis.tickText.marginStart).toBe(10);
    expect(s.xAxis.tickText.marginEnd).toBe(10);
    expect(s.yAxis.tickText.marginStart).toBe(10);
    expect(s.yAxis.tickText.marginEnd).toBe(10);
  });

  // ── ۳) سایۀ خاکستری ───────────────────────────────────────────────────
  it('«سایۀ خاکستری» رنگِ سایه را عوض می‌کند و خاموش‌شدنش به بدنه برمی‌گرداند', async () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    act(() => { useFtsConfigStore.getState().setView({ wickGray: true }); });
    const bar = lastStyles().candle.bar;
    expect(bar.upWickColor).toBe('#787b86');
    expect(bar.downWickColor).toBe('#787b86');
    act(() => { useFtsConfigStore.getState().setView({ wickGray: false }); });
    expect(lastStyles().candle.bar.upWickColor).toBe('#089981');
  });

  // ── ۴) واترمارک ────────────────────────────────────────────────────────
  it('واترمارک با شفافیتِ انتخابی رسم می‌شود و با خاموش‌کردنش از DOM می‌رود', async () => {
    const { container } = render(<KLineChartWrapper initialSymbol="فولاد" />);
    const wm = container.querySelector('[data-testid="chart-watermark"]') as HTMLElement;
    expect(wm).toBeTruthy();
    expect(wm.style.opacity).toBe('0.2');
    expect(wm.textContent).toContain('فولاد');
    act(() => { useFtsConfigStore.getState().setView({ showWatermark: false }); });
    expect(container.querySelector('[data-testid="chart-watermark"]')).toBeNull();
    act(() => { useFtsConfigStore.getState().setView({ showWatermark: true, watermarkOpacity: 5 }); });
    expect((container.querySelector('[data-testid="chart-watermark"]') as HTMLElement).style.opacity).toBe('0.05');
  });

  // ── ۵) ضریبِ سرور، نه زنجیرۀِ مرورگر ──────────────────────────────────
  it('سریِ رسم‌شدنه از ضریبِ سرور می‌آید: حجم ÷factor می‌شود (قیمت نیست که ایندکس شود)', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce(CHART_PAYLOAD);
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    const bars = loaderBars();
    expect(bars.length).toBe(3);
    // دو کندلِ پیشِ رویداد: ۱۰۰۰ ÷ ۰٫۵ = ۲۰۰۰؛ کندلِ آخر دست‌نخورده
    expect(bars[0].volume).toBe(2000);
    expect(bars[1].volume).toBe(2000);
    expect(bars[2].volume).toBe(1000);
    // نسبتِ(first÷last) با ضریب عوض می‌شود: خام ≈ ۱۰۰/۱۰۲، تعدیل‌شده ≠ آن
    expect(bars[0].timestamp).toBe(T0);
    expect(bars[2].timestamp).toBe(T0 + 4 * DAY);
  });

  it('بی‌ضریب از سرور (سریِ محلی) همان کندلِ خام رسم می‌شود، نه صفر', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...CHART_PAYLOAD, factors: [],
      adjustCapability: { source: 'local-db-unseen', combined_available: false },
    });
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    const bars = loaderBars();
    expect(bars.map((b) => b.volume)).toEqual([1000, 1000, 1000]);
  });

  it('مانعِ تعدیلِ عملکردی رویِ چارت خوانده می‌شود (UI صادق، قدمِ ۵)', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce(CHART_PAYLOAD);
    const { container } = render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    const note = container.querySelector('[data-testid="chart-functional-note"]');
    expect(note).toBeTruthy();
    expect(note?.textContent).toContain('event-type-unresolved:2');
  });
});

// موتورِ دوم کرکرۀ «نوع تعدیل قیمت» را ندارد (آن کرکره درِ نوارِ ابزارِ KLineCharts
// است). پس دو چیز باید ثابت شود: سریِ آن از همان ضریبِ سرور می‌آید (سایرِ تست‌ها)،
// و مبنایِ سری رویِ صحنه اعلام می‌شود — نه اینکه کاربر سوییچِ موتور را بی‌تغییرِ
// عددی و بی‌اعلام ببیند. برچسب از همان ثابتِ مبناست، پس اعلام و داده نمی‌توانند
// از هم جدا بیفتند.
describe('موتورِ دوم: مبنایِ سریِ رسم‌شده خوانا اعلام می‌شود (مرحلۀ ۵)', () => {
  const ROOT = path.resolve(__dirname, '..', 'features', 'technical');

  it('مبنا همان «عملکردی» است و میزبان آن را از ثابتِ یکسان می‌خواند (بی‌ادعایِ جدا از داده)', () => {
    const page = fs.readFileSync(path.join(ROOT, 'routes', 'TechnicalPage.tsx'), 'utf8');
    const host = fs.readFileSync(path.join(ROOT, 'components', 'FtsEngineChart.tsx'), 'utf8');
    expect(FFC_ADJUSTMENT_MODE).toBe('combined');
    expect(page).toMatch(/applyAdjustmentToCandles\([^)]*FFC_ADJUSTMENT_MODE/);
    expect(page).not.toMatch(/applyAdjustmentToCandles\([^)]*'combined'/);
    expect(host).toMatch(/data-testid="ffc-adjust-basis"[^\n]*\{FFC_ADJUSTMENT_BASIS_LABEL\}/);
  });

  it('خطِ وضعیتِ موتورِ دوم مبنایِ سری را رویِ صحنه می‌آورد', () => {
    render(
      <FtsEngineChart
        engineId="ffc"
        bars={[]}
        fts={null}
        dark={false}
        logScale={false}
        candleStyle="candles"
      />,
    );
    const line = screen.getByTestId('ffc-adjust-basis');
    expect(line.textContent).toContain(FFC_ADJUSTMENT_BASIS_LABEL);
  });
});
