// __tests__/mobile-board-freshness.spec.ts — تازگیِ تابلو رویِ گوشی با لایۀ زنده
//
// سه باگِ اثبات‌شده درِ مأموریت ۱۴۰۴-۰۷-۲۶ که «برنامه درِ ساعاتِ معاملات درست
// کار نمی‌کند» را می‌ساختند، همه درِ همۀ همین boardPayload جمع بودند:
//   ۱) بدنهٔ پخت rev=0 و بی‌rev_at داشت؛ پولینگ هرگز rev را عوض ندید و
//      FreshnessBadge بعدِ پنج دقیقه «ایستاده/کهنه» می‌گفت — با اعدادی که
//      هر ۵ ثانیه از TSETMC عوض می‌شدند.
//   ۲) live_count شمارشِ روزِ پخت بود تا ابد؛ بی‌لایۀ زنده «۳۶۱۴ ردیف زندهٔ
//      امروز» درحالی‌که اسنپ‌شات دیروز است.
//   ۳) خطایِ شبکهٔ لایۀ زنده هیچ‌جا ثبت نمی‌شد (null بی‌صدا).
// قالبِ ردیف‌ها از فیکسچرِ mobile-live-overlay (خودِ دسکتاپ) است.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const bakedMap = new Map<string, unknown>();

vi.mock('@shared/api/local/localData', () => ({
  baked: async (key: string) => (bakedMap.has(key) ? bakedMap.get(key) : null),
  metaValue: async (k: string) => (k === 'built_at' ? '2026-10-14T12:33:04Z' : '1.1.1'),
  query: async () => [] as Record<string, unknown>[],
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
  overlayBoard: vi.fn(),
  tehranToday: vi.fn(() => '2026-10-17'),
  mwRowFromJson: (r: Record<string, unknown>) => r,
};
vi.mock('@shared/api/local/live', () => live);

const { resolveLocal, overlayStatus, __resetBoardForTest } = await import('@shared/api/local/resolvers');

const mwRow = (pcl: number, qtj: number) => ({ pcl, qtj, pdv: pcl, py: pcl, den: 20261017 });

// رونشانیِ ماک هم‌رفتارِ واقعی: ردیفِ هم‌ins_code را می‌یابد و is_live را از
// d_evenِ آخرین نشست می‌سازد — همان قاعدۀ overlayBoard واقعی.
function overlayStub(rows: Record<string, unknown>[], mw: Map<string, ReturnType<typeof mwRow>> | null): number {
  if (!mw) return 0;
  let n = 0; let maxDen = -1;
  rows.forEach((row) => {
    const m = mw.get(String(row.ins_code ?? ''));
    if (!m) { row.is_live = false; return; }
    n += 1;
    row.p_closing = m.pcl; row.q_tot_tran = m.qtj; row.d_even = m.den;
    if ((m.den ?? -1) > maxDen) maxDen = m.den ?? -1;
  });
  if (maxDen >= 0) for (const row of rows) row.is_live = Number(row.d_even ?? -1) === maxDen;
  return n;
}

const twoRows = () => ([
  { symbol: 'فولاد', ins_code: 'A1', is_live: false, d_even: 20261014, p_closing: 4500, q_tot_tran: 1 },
  { symbol: 'وبملت', ins_code: 'B2', is_live: false, d_even: 20261014, p_closing: 1500, q_tot_tran: 1 },
]);

const boardWrapper = () => ({
  status: 'success', rev: 0, count: 2, data: twoRows(),
  live_count: 3614, fossil_count: 2404, // شمارش‌های فرسودۀ روزِ پخت — must be replaced or zeroed
  meta: { d_even: 20261014, h_even: 160254, last_sync: '2026-10-14 16:03:04' },
});

async function board(): Promise<Record<string, unknown>> {
  return (await resolveLocal('/api/market', 'GET')) as Record<string, unknown>;
}

beforeEach(() => {
  __resetBoardForTest();
  bakedMap.clear();
  bakedMap.set('market_board', boardWrapper());
  live.liveWatch.mockReset().mockResolvedValue(null);
  live.liveClientType.mockReset().mockResolvedValue(null);
  live.tehranToday.mockReset().mockReturnValue('2026-10-17');
  live.overlayBoard.mockReset().mockImplementation(
    (rows: Record<string, unknown>[], mw: Map<string, ReturnType<typeof mwRow>> | null) => overlayStub(rows, mw),
  );
});

describe('rev/rev_at زنده رویِ بستۀ پخت', () => {
  it('دورِ نخستِ زنده فقط مُهر می‌کند؛ rev ۰→۱ِ بی‌مغزا نمی‌شود', async () => {
    live.liveWatch.mockResolvedValue(new Map([['A1', mwRow(4410, 100)], ['B2', mwRow(1532, 50)]]));
    const out = await board();
    expect(out.rev).toBe(0);
    // rev_atِ بی‌عوض‌شدنِ عدد = مِهرِ last_syncِ تهران، نه «الان»
    expect(Number(out.rev_at)).toBe(Date.UTC(2026, 9, 14, 12, 33, 4));
    expect(out.live_count).toBe(2);  // رونشانی شد و هر دو ردیف نشستِ جاری شدند
  });

  it('جابه‌جاییِ یکِ عددِ واقعی rev را بالا می‌برد و rev_at را «الان» می‌کند', async () => {
    live.liveWatch.mockResolvedValue(new Map([['A1', mwRow(4410, 100)], ['B2', mwRow(1532, 50)]]));
    await board();
    const t0 = Date.now();
    live.liveWatch.mockResolvedValue(new Map([['A1', mwRow(4415, 120)], ['B2', mwRow(1532, 50)]]));
    const out = await board();
    expect(out.rev).toBe(1);
    expect(Number(out.rev_at)).toBeGreaterThanOrEqual(t0);
  });

  it('پاسخِ بی‌تغییری rev را تکان نمی‌دهد — «درخواست رسید» ≠ «داده عوض شد»', async () => {
    const same = new Map([['A1', mwRow(4410, 100)], ['B2', mwRow(1532, 50)]]);
    live.liveWatch.mockResolvedValue(same);
    await board();
    await board();
    const out = await board();
    expect(out.rev).toBe(0);
  });

  it('رونشانیِ صفرردیف (ins_codeهای بی‌اشتراک) جعلِ live_count و rev نمی‌سازد', async () => {
    // پیشینۀ نگاشتِ ردیف‌هایِ ناهمسان رویِ بسته‌هایِ قدیمیِ با ins_code
    live.overlayBoard.mockImplementation(() => 0);
    live.liveWatch.mockResolvedValue(new Map([['ZZ', mwRow(1, 1)]]));
    const out = await board();
    expect(out.rev).toBe(0);
    expect(out.live_count).toBe(3614); // دست‌نخورده — داوری‌ای نشده که جایگزینش کنیم
  });
});

describe('live_count صادقانه وقتی زنده نیست', () => {
  it('بی‌زنده و با مِهرِ نشستِ غیرامروز ⇒ صفر، نه ۳۶۱۴ فرسوده', async () => {
    const out = await board();
    expect(out.live_count).toBe(0);
    expect(out.fossil_count).toBe(2);
  });

  it('بی‌زنده ولی مِهرِ نشست == امروز ⇒ شمارشِ پخت دست‌نخورده (ردیف‌ها همان روزند)', async () => {
    bakedMap.set('market_board', {
      ...boardWrapper(),
      meta: { d_even: 20261017, last_sync: '2026-10-17 12:30:00' },
    });
    const out = await board();
    expect(out.live_count).toBe(3614);
  });

  it('پس ازِ رونشانیِ موفقِ نشست، قطعِ زنده live_countِ امروز را صفر نمی‌کند', async () => {
    live.liveWatch.mockResolvedValue(new Map([['A1', mwRow(4410, 100)], ['B2', mwRow(1532, 50)]]));
    await board(); // نشستِ زنده: live_count=2 از شمارشِ واقعی
    live.liveWatch.mockResolvedValue(null); // پرواز
    const out = await board();
    expect(out.live_count).toBe(2); // دروغِ جهۀِ مخالف ممنوع
  });

  it('rev_atِ بی‌رونشانیِ زنده = مِهرِ last_syncِ تهران (clock-safe)، نه صفر', async () => {
    const out = await board();
    // 2026-10-14 16:03:04 تهران == 12:33:04 UTC
    expect(Number(out.rev_at)).toBe(Date.UTC(2026, 9, 14, 12, 33, 4));
  });
});

describe('خطایِ زنده دیده می‌شود (پنلِ 🛠)', () => {
  it('رونشانیِ نخستِ ناموفق هیچ نمی‌شمارد (هنوز چیزی موفق نبوده)؛ پس ازِ موفقیت، هر دورِ بی‌زنده یکِ شکست', async () => {
    await board();
    expect(overlayStatus()).toBeNull();
    live.liveWatch.mockResolvedValue(new Map([['A1', mwRow(4410, 100)]]));
    await board();
    expect(overlayStatus()?.fails).toBe(0);
    live.liveWatch.mockResolvedValue(null);
    await board();
    const st = overlayStatus();
    expect(st?.fails).toBe(1);
    expect(st?.lastFailAt).not.toBeNull();
  });
});
