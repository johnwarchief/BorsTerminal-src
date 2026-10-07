// گاردِ resolver آفلاین — همان سه مسیری که رویِ گوشی تب‌ها را پر می‌کند:
// اسکرینر (بنیادی)، تاریخچۀ چارت (price_history) و عمقِ صف.
// localData و live ماک‌اند؛ خودِ منطقِ انتخاب/برشِ مسیر در resolvers.ts آزموده
// می‌شود، چون همان‌جا بود که ۸۷۳ شرکت به ۶۰ رسید و چارت خالی ماند.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const bakedMap = new Map<string, unknown>();
const sql = vi.fn(async (text: string, params?: unknown[]) => {
  void [text, params]; // پیش‌فرض: هیچ کوئری‌ای ردیفی برنمی‌گرداند؛ هر تست جا را عوض می‌کند
  return [] as Record<string, unknown>[];
});

vi.mock('@shared/api/local/localData', () => ({
  baked: async (key: string) => (bakedMap.has(key) ? bakedMap.get(key) : null),
  metaValue: async (k: string) => (k === 'app_version' ? '1.0.78' : '2026-10-07T09:29:30'),
  query: (text: string, params?: unknown[]) => sql(text, params),
  normFa: (s: string) => (s ?? '').trim().replace(/ي/g, 'ی').replace(/ك/g, 'ک'),
  getDb: async () => ({}),
  bootTiming: { source: 'bundle', gzBytes: 0, rawBytes: 0, fetchMs: 0, gunzipMs: 0, openMs: 0, totalMs: 0 },
}));

const live = {
  liveWatch: vi.fn(),
  liveChart: vi.fn(),
  liveClientType: vi.fn(),
  liveTedpix: vi.fn(),
  liveTodayCandle: vi.fn(),
  overlayBoard: vi.fn(() => 0),
  tehranToday: () => '2026-10-07',
  mwRowFromJson: (r: Record<string, unknown>) => r,
};
vi.mock('@shared/api/local/live', () => live);

const { resolveLocal } = await import('@shared/api/local/resolvers');

type BookOut = { status: string; levels: unknown[]; session?: { d_even?: number }; totals?: unknown };

const ROWS = [1, 2, 3, 4, 5].map((i) => ({ symbol: `نماد${i}`, score: i, excluded: i === 5 }));

beforeEach(() => {
  bakedMap.clear();
  sql.mockResolvedValue([]);
  live.liveWatch.mockResolvedValue(null);
  live.liveChart.mockResolvedValue(null);
  live.liveClientType.mockResolvedValue(null);
  live.liveTodayCandle.mockResolvedValue(null);
  live.overlayBoard.mockReturnValue(0);
});

describe('/api/screener در حالتِ آفلاین', () => {
  beforeEach(() => bakedMap.set('screener', { status: 'success', count: ROWS.length, data: ROWS }));

  it('بی‌?limit همان چیزی است که تبِ بنیادی می‌خواهد: کلِ ردیف‌ها، بی‌برش', async () => {
    const out = (await resolveLocal('/api/screener', 'GET')) as { data: unknown[]; count: number };
    expect(out.data).toHaveLength(5);
    expect(out.count).toBe(5);
  });

  it('?limit فقط وقتی صریحاً آمده برش می‌زند (و دروغ نمی‌گوید)', async () => {
    const out = (await resolveLocal('/api/screener?limit=2', 'GET')) as { data: unknown[]; count: number };
    expect(out.data).toHaveLength(2);
    expect(out.count).toBe(2);
  });
});

describe('تاریخچۀ چارت از price_history', () => {
  const ph = (withLast: boolean) => {
    sql.mockImplementation(async (text: string) => {
      if (withLast && !text.includes('last')) return Promise.reject(new Error('no such column: last'));
      return [
        { date: '2026-10-06', open: 100, high: 110, low: 95, close: 105, volume: 10, last: 120 },
        { date: '2026-10-07', open: 106, high: 112, low: 104, close: 108, volume: 20, last: null },
      ];
    });
  };

  it('مبنایِ نمایش «آخرین» است و پایانی درِ closing می‌ماند (همتا: price_basis)', async () => {
    ph(true);
    const out = (await resolveLocal('/api/history/فولاد', 'GET')) as {
      candles: { time: string; close: number; closing?: number; last?: number | null }[];
    };
    expect(out.candles[0]).toMatchObject({ close: 120, closing: 105, last: 120 });
    // بی‌«آخرین» عدد ساخته نمی‌شود؛ پایانی همان می‌ماند
    expect(out.candles[1]).toMatchObject({ close: 108, closing: 108, last: null });
  });

  it('اسنپ‌شاتِ کهنه (بی‌ستونِ last) می‌افتد رویِ مسیرِ پایانی، نه خطا', async () => {
    sql.mockImplementation(async (text: string) => {
      if (text.includes('last')) throw new Error('no such column: last');
      return [{ date: '2026-10-06', open: 100, high: 110, low: 95, close: 105, volume: 10 }];
    });
    const out = (await resolveLocal('/api/history/فولاد', 'GET')) as {
      candles: { close: number }[];
    };
    expect(out.candles).toHaveLength(1);
    expect(out.candles[0].close).toBe(105);
  });

  it('بی‌ردیف ⇒ status empty (نه صفرِ ساختگی)', async () => {
    const out = (await resolveLocal('/api/history/ناموجود', 'GET')) as { status: string; candles: unknown[] };
    expect(out.status).toBe('empty');
    expect(out.candles).toEqual([]);
  });
});

describe('/api/order-book رویِ گوشی', () => {
  const levels = [{ buy_px: 100, buy_vol: 10, buy_cnt: 2, sell_px: 103, sell_vol: 5, sell_cnt: 1 }];

  it('عمقِ زنده از مارکت‌واچ مقدم است و نشستِ خودش را اعلام می‌کند', async () => {
    sql.mockResolvedValue([{ ins_code: 'A1' }]);
    live.liveWatch.mockResolvedValue(new Map([['A1', { levels, den: 20261007, hen: 120000, q: { bq: 10, bc: 2, sq: 5, sc: 1 } }]]));
    const out = (await resolveLocal('/api/order-book/فولاد', 'GET')) as BookOut;
    expect(out.status).toBe('ok');
    expect(out.levels).toEqual(levels);
    expect(out.session?.d_even).toBe(20261007);
    expect(out.totals).toEqual({ buy_vol: 10, buy_cnt: 2, sell_vol: 5, sell_cnt: 1 });
  });

  it('بی‌زنده، بستهٔ پخت‌شده می‌آید؛ بی‌آن هم «no_data» نه صفِ جعلی', async () => {
    sql.mockResolvedValue([{ ins_code: 'A1' }]);
    bakedMap.set('orderbook/فولاد', { status: 'ok', symbol: 'فولاد', levels });
    expect(((await resolveLocal('/api/order-book/فولاد', 'GET')) as { levels: unknown[] }).levels).toEqual(levels);
    bakedMap.delete('orderbook/فولاد');
    const empty = (await resolveLocal('/api/order-book/ناموجود', 'GET')) as { status: string; levels: unknown[] };
    expect(empty.status).toBe('no_data');
    expect(empty.levels).toEqual([]);
  });
});
