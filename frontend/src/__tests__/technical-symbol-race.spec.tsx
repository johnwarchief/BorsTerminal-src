// نگهبانِ ترتیبِ واکشیِ کندل: با عوض‌شدنِ نماد، پاسخِ نمادِ قبلی نباید رویِ چارتِ
// تازه بنشیند. ریشۀ باگ: `fetchCandleData` سه لایه fallback داشت و هیچ‌گاه نمی‌پرسید
// «آیا این پاسخ هنوز مالِ نمادی است که کاربر می‌بیند؟» — `setRawCandles` بی‌شرط
// صدا زده می‌شد، پس اگر درخواستِ نمادِ اول دیرتر از نمادِ دوم می‌رسید، چارت سریِ
// نمادِ اول را نشان می‌داد (و حجم/فاکتور/رویدادهای تعدیل هم با آن می‌آمدند).
import { act, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type Cfg = { time: string; open: number; high: number; low: number; close: number };
/** چارت KLineData می‌گیرد (`timestamp` میلی‌ثانیه)، نه رشتهٔ سرور */
type Bar = { timestamp: number };
const monthOf = (b: Bar) => new Date(b.timestamp).toISOString().slice(0, 7);
const stamp = (t: string) => Date.parse(`${t}T00:00:00Z`);
type Loader = { getBars: (a: { callback: (bars: unknown[], extra?: unknown) => void }) => void };

const days = (start: '2025-01' | '2025-02', n: number): Cfg[] =>
  Array.from({ length: n }, (_, i) => {
    const p = 100 + i;
    return { time: `${start}-0${i + 1}`, open: p, high: p + 2, low: p - 1, close: p + 1 };
  });

const A = days('2025-01', 5);
const B = days('2025-02', 3);

let loaders: Loader[] = [];
let servedA = 0;
const signals: Record<string, AbortSignal> = {};

const chartStub = () => ({
  setDataLoader: vi.fn((o: Loader) => { loaders.push(o); }),
  setSymbol: vi.fn(), setPeriod: vi.fn(), setFormatter: vi.fn(),
  createIndicator: vi.fn(), removeIndicator: vi.fn(), setPaneOptions: vi.fn(),
  setStyles: vi.fn(), overrideYAxis: vi.fn(), overrideOverlay: vi.fn(),
  createOverlay: vi.fn(() => 'ov'), removeOverlay: vi.fn(), resetData: vi.fn(),
  resize: vi.fn(), getConvertPictureUrl: vi.fn(() => ''), subscribeAction: vi.fn(),
  scrollToRealTime: vi.fn(), getDataList: vi.fn(() => []), setScrollEnabled: vi.fn(),
  getOverlays: vi.fn(() => []),
});

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(), registerOverlay: vi.fn(), registerIndicator: vi.fn(),
  getSupportedOverlays: vi.fn(() => []),
}));

const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as unknown as Response;
const candlesResp = (c: Cfg[]) => ok({
  status: 'success', candles: c, volumes: c.map((x) => ({ time: x.time, value: 10 })),
  factors: c.map((x) => ({ time: x.time, factor: 1 })), adjustEvents: [],
});

/** نماد A عمداً کند است؛ نماد B فوری. ترتیبِ رسیدن با ترتیبِ درخواست یکی نیست. */
function stubSlowFirst() {
  loaders = []; servedA = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: unknown, init?: { signal?: AbortSignal }) => {
    const u = decodeURIComponent(String(url));
    if (init?.signal) signals[u] = init.signal;
    if (u.includes('/api/chart/فولاد')) {
      await new Promise((r) => setTimeout(r, 30));
      servedA += 1;
      return candlesResp(A);
    }
    if (u.includes('/api/chart/خودرو')) return candlesResp(B);
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}

const barsNow = (): Bar[] => {
  const last = loaders[loaders.length - 1];
  expect(last).toBeTruthy();
  let out: unknown[] = [];
  last.getBars({ callback: (bars) => { out = bars as unknown[]; } });
  return out as unknown as Bar[];
};

async function settle(ms = 60) {
  await act(async () => { await new Promise((r) => setTimeout(r, ms)); });
}

beforeEach(() => { vi.clearAllMocks(); });

describe('واکشی کندل با عوض‌شدنِ نماد', () => {
  it('پاسخِ کُندِ نمادِ قبلی رویِ چارتِ نمادِ تازه نمی‌نشیند', async () => {
    stubSlowFirst();
    const { rerender } = render(<KLineChartWrapper initialSymbol="فولاد" />);
    await act(async () => { await Promise.resolve(); });
    rerender(<KLineChartWrapper initialSymbol="خودرو" />);
    await settle();

    expect(servedA).toBe(1);                    // پاسخِ A واقعاً رسیده بود
    const times = new Set(barsNow().map(monthOf));
    expect(times.has('2025-01')).toBe(false);   // سریِ A نشت نکرد
    expect(times.has('2025-02')).toBe(true);   // سریِ B همان‌جا ماند
  });

  it('درخواستِ بی‌مصرفِ نمادِ قبلی abort می‌شود (پس نه پاسخ می‌دهد نه write)', async () => {
    stubSlowFirst();
    const { rerender } = render(<KLineChartWrapper initialSymbol="فولاد" />);
    await act(async () => { await Promise.resolve(); });
    rerender(<KLineChartWrapper initialSymbol="خودرو" />);
    await settle();
    const sig = signals['/api/chart/فولاد'];
    expect(sig).toBeTruthy();
    expect(sig.aborted).toBe(true);
    expect(signals['/api/chart/خودرو']?.aborted).toBe(false);
  });

  it('یکِ نماد، یکِ درخواستِ کامل ⇒ سریِ همان نماد رویِ چارت است (کنترلِ مثبت)', async () => {
    stubSlowFirst();
    render(<KLineChartWrapper initialSymbol="خودرو" />);
    await settle();
    expect(barsNow().map((b) => b.timestamp)).toEqual(B.map((b) => stamp(b.time)));
  });
});
