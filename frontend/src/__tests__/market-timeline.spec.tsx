// تست میکروچارت‌های درون‌روز: زیپ سری، Bullish Cross، معکوس breadth و دراور با fetch ماک‌شده
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MicroChartsDrawer } from '@features/market/components/MicroChartsDrawer';
import {
  MIN_CHART_POINTS,
  detectBreadthFlip,
  detectBullishCross,
  numCell,
  timeCell,
  timelinePoints,
  toSeriesColumns,
} from '@features/market/lib/timelineMath';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function jsonResponse(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}
function deadResponse(): Response {
  return { ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response;
}

function timelineBody(series: Record<string, unknown>) {
  return {
    status: 'ok',
    mode: 'cum',
    ready: true,
    day: 20260913,
    series,
    session_open: '08:55',
    session_close: '13:00',
    note: null,
    source: 'local:market.db',
  };
}

function mockTimeline(series: Record<string, unknown> | null) {
  fetchMock.mockImplementation((url: string) => {
    if (!String(url).includes('mstat/timeline')) return Promise.resolve(deadResponse());
    if (series === null) return Promise.resolve(deadResponse());
    return Promise.resolve(jsonResponse(timelineBody(series)));
  });
}

describe('timelinePoints -- زیپ ستون‌های موازی', () => {
  it('زمان‌های معتبر را با مقادیر (یا null) جفت می‌کند و زمان ناقص را می‌اندازد', () => {
    const pts = timelinePoints({
      t: ['09:00', null, '10:30'],
      bq_bt: [10, 20],
      sq_bt: [5, 8, 12, 99],
      pos: [100, 110, 120],
      neg: [50, null, 60],
    });
    expect(pts).toHaveLength(2);
    expect(pts[0]).toEqual({ t: '09:00', bq: 10, sq: 5, pos: 100, neg: 50 });
    expect(pts[1]).toEqual({ t: '10:30', bq: null, sq: 12, pos: 120, neg: 60 });
  });

  it('بدون سری یا بدون زمان → آرایه خالی', () => {
    expect(timelinePoints(null)).toEqual([]);
    expect(timelinePoints({ t: [] })).toEqual([]);
    expect(timelinePoints({})).toEqual([]);
  });

  it('حد نصاب رندر منحنی دو نقطه است', () => {
    expect(MIN_CHART_POINTS).toBe(2);
  });
});

describe('toSeriesColumns -- یکدست‌ساز قالب پاسخ تایم‌لاین', () => {
  it('numCell رشتهٔ عددی را به عدد و زباله را به null تبدیل می‌کند', () => {
    expect(numCell('75.6')).toBe(75.6);
    expect(numCell(75.6)).toBe(75.6);
    expect(numCell('')).toBeNull();
    expect(numCell('abc')).toBeNull();
    expect(numCell(Number.NaN)).toBeNull();
    expect(numCell(null)).toBeNull();
    expect(numCell(undefined)).toBeNull();
    expect(timeCell(930)).toBe('930');
    expect(timeCell('12:58')).toBe('12:58');
    expect(timeCell(null)).toBeNull();
    expect(timeCell('')).toBeNull();
  });

  it('قالب ستونی (واقعِ بک‌اند) را دست‌نخورک و کامل می‌گیرد، رشته‌ها را coerce می‌کند', () => {
    const cols = toSeriesColumns({
      t: ['09:00', '10:00'],
      bq_bt: ['10', 20],
      sq_bt: [15, '22'],
      pos: [100, null],
      neg: ['50', 60],
    });
    expect(cols.t).toEqual(['09:00', '10:00']);
    expect(cols.bq_bt).toEqual([10, 20]);
    expect(cols.sq_bt).toEqual([15, 22]);
    expect(cols.pos).toEqual([100, null]);
    expect(cols.neg).toEqual([50, 60]);
    expect(timelinePoints(cols)).toHaveLength(2);
  });

  it('قالب ردیفیِ نقطه‌ای را هم به ستونی نرمال می‌کند', () => {
    const cols = toSeriesColumns([
      { t: '09:00', bq_bt: 10, sq_bt: 15, pos: 100, neg: 110 },
      { t: '10:00', bq_bt: 20, sq_bt: 12, pos: 120, neg: 90 },
    ]);
    expect(timelinePoints(cols)).toEqual([
      { t: '09:00', bq: 10, sq: 15, pos: 100, neg: 110 },
      { t: '10:00', bq: 20, sq: 12, pos: 120, neg: 90 },
    ]);
  });

  it('ورودی نامعتبر/تهی → ساختار خالیِ امن (بدون کرش، «بدون داده» صادق)', () => {
    expect(toSeriesColumns(null)).toEqual({ t: [], bq_bt: [], sq_bt: [], pos: [], neg: [] });
    expect(toSeriesColumns('x')).toEqual({ t: [], bq_bt: [], sq_bt: [], pos: [], neg: [] });
    expect(toSeriesColumns({})).toEqual({ t: [], bq_bt: [], sq_bt: [], pos: [], neg: [] });
    expect(toSeriesColumns([1, 2, 3])).toEqual({ t: [], bq_bt: [], sq_bt: [], pos: [], neg: [] });
    expect(timelinePoints(toSeriesColumns(null))).toEqual([]);
  });
});

describe('Bullish Cross -- عبور ارزش صف خرید از فروش', () => {
  it('عبور + فاصله گرفتن ⇒ سیگنال کامل', () => {
    const r = detectBullishCross([10, 20, 35, 60], [15, 22, 23, 24]);
    expect(r.hit).toBe(true);
    expect(r.crossIndex).toBe(2);
    expect(r.widening).toBe(true);
  });

  it('عبور در آخرین نقطه (بدون شاهدِ فاصله‌گرفتن) سیگنال کامل نیست', () => {
    const r = detectBullishCross([10, 20, 45], [15, 22, 24]);
    expect(r.crossIndex).toBe(2);
    expect(r.hit).toBe(false);
  });

  it('عبور و سپس جمع شدن شکاف ⇒ نه', () => {
    expect(detectBullishCross([10, 30, 22], [15, 12, 14])).toEqual({ hit: false, crossIndex: 1, widening: false });
  });

  it('بدون عبور، سری کوتاه و داده ناقص ⇒ نه', () => {
    expect(detectBullishCross([5, 6, 7], [10, 11, 12]).hit).toBe(false);
    expect(detectBullishCross([null, 9], [5, null]).hit).toBe(false);
    expect(detectBullishCross([40], [10]).hit).toBe(false);
    expect(detectBullishCross(null, [1, 2]).hit).toBe(false);
    expect(detectBullishCross([1, 2], null).hit).toBe(false);
  });
});

describe('detectBreadthFlip -- معکوس جهت روز', () => {
  it('عبور pos-neg از منفی به مثبت ⇒ bull و برعکس ⇒ bear', () => {
    expect(detectBreadthFlip([10, 40], [20, 20])).toBe('bull');
    expect(detectBreadthFlip([40, 10], [20, 20])).toBe('bear');
    expect(detectBreadthFlip([30, 40], [20, 20])).toBeNull();
    expect(detectBreadthFlip([10], [20])).toBeNull();
    expect(detectBreadthFlip(null, [1, 2])).toBeNull();
  });
});

describe('دراور میکروچارت با تایم‌لاین ماک‌شده', () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  function renderDrawer() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={qc}>
        <MicroChartsDrawer />
      </QueryClientProvider>,
    );
  }

  it('باز کردن دراور و دیدن Bullish Cross روی سری عبور+فاصله', async () => {
    // پیلود چندنقطه‌ای شبیه پاسخ واقعی /api/mstat/timeline?mode=cum
    // (هر ۱۱ سری + رشته‌های عددی برای امتحان coerce در لایهٔ مدل)
    mockTimeline({
      t: ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00'],
      val_bt: ['12000', '25000', '40000', '55000', '72000', '90000', '110000'],
      flow_eq_bt: [10, 20, null, 45, 60, 70, 88],
      flow_fixed_bt: [-10, -5, 0, 5, 10, 15, 20],
      pos: [100, 120, 130, 140, 150, 160, 180],
      neg: [110, 100, 90, 80, 75, 70, 60],
      bq_bt: ['10', 20, 28, 35, 44, 52, 60],
      sq_bt: ['15', 22, 23, 23.5, 24, 24, 24],
      pc_buy: [70, 72, 74, 75, 76, 77, 78],
      pc_sell: [40, 41, 42, 43, 44, 45, 46],
      bq_n: [1200, 1300, 1400, 1420, 1450, 1460, 1479],
      sq_n: [400, 380, 360, 340, 330, 320, 313],
    });
    renderDrawer();
    fireEvent.click(screen.getByRole('button', { name: /نبض درون‌روز/ }));
    await waitFor(() => expect(screen.getByTestId('bullish-cross')).toBeInTheDocument());
    expect(screen.getByTestId('micro-orderbook').textContent).toContain('▲ برتری تقاضا');
    expect(screen.getByTestId('micro-orderbook').querySelectorAll('polyline')).toHaveLength(2);
    expect(screen.getByTestId('micro-breadth').querySelectorAll('polyline')).toHaveLength(2);
  });

  it('سری تک‌نقطه‌ای Circuit Breaker می‌خورد: بدون داده', async () => {
    mockTimeline({ t: ['12:58'], bq_bt: [64935], sq_bt: [16198], pos: [1147], neg: [807] });
    renderDrawer();
    fireEvent.click(screen.getByRole('button', { name: /نبض درون‌روز/ }));
    await waitFor(() => expect(screen.getByTestId('micro-orderbook')).toBeInTheDocument());
    expect(screen.getByTestId('micro-orderbook').textContent).toContain('بدون داده');
    expect(screen.getByTestId('micro-breadth').textContent).toContain('بدون داده');
    expect(screen.queryByTestId('bullish-cross')).not.toBeInTheDocument();
  });

  it('معکوس breadth در حالت ماک نمایش داده می‌شود', async () => {
    mockTimeline({ t: ['09:00', '10:00'], pos: [10, 40], neg: [20, 20], bq_bt: [5, 6], sq_bt: [9, 9] });
    renderDrawer();
    fireEvent.click(screen.getByRole('button', { name: /نبض درون‌روز/ }));
    await waitFor(() => expect(screen.getByTestId('breadth-flip')).toBeInTheDocument());
    expect(screen.getByTestId('breadth-flip').textContent).toContain('معکوس به مثبت');
    expect(screen.queryByTestId('bullish-cross')).not.toBeInTheDocument();
  });
});
