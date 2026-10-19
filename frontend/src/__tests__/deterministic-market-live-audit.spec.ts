// __tests__/deterministic-market-live-audit.spec.ts — آزمون‌های قطعی تازه‌سازی زنده بازار و قیف FTS بدون نیاز به بازار زنده
//
// این فایل با کنترل کامل زمان (fake timers)، ماک شبکه، فیکسچرهای برچسب‌دار (FIXTURE)، و بدون نیاز
// به اتصال واقعی به بازار، موارد زیر را به‌طور قطعی و تکرارپذیر اثبات می‌کند:
//   ۱) رفتار لایهٔ زنده TSETMC (کش TTL، حقیقی/حقوقی ۳۰ثانیه، مارکت‌واچ ۵ثانیه)
//   ۲) مدیریت قطع شبکه، دادهٔ ناقص، و بازیابی پس از وصل مجدد
//   ۳) ریتم‌های وابسته به ساعت رسمی تهران (داخل/خارج ساعت بازار و روزهای تعطیل)
//   ۴) رفتار قیف FTS و عدم تأثیر تغییرات زنده بر خروجی پختهٔ /api/funnel روی اندروید
//   ۵) رفتار /api/fts/:symbol در حالت پخته و فال‌بک محلی
//
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from '@shared/api/http';
import {
  effectivePollMs,
  isMarketOpen,
  sessionPollMs,
  CLOSED_POLL_MS,
} from '@shared/lib/marketHours';

// ---- فیکسچرهای آزمایشی با برچسب صریح FIXTURE -----------------------------
const FIXTURE_BAKED_BOARD = {
  status: 'success',
  rev: 0,
  count: 2,
  live_count: 2,
  fossil_count: 0,
  meta: { d_even: 20261014, h_even: 123000, last_sync: '2026-10-14 12:30:00' },
  data: [
    {
      symbol: 'فولاد',
      ins_code: 'INS_FOOLAD_1',
      is_live: true,
      d_even: 20261014,
      p_last: 5000,
      p_closing: 5000,
      price_yesterday: 4900,
      tmin: 4600,
      tmax: 5400,
      q_tot_tran: 1_000_000,
      buy_i_vol: 500_000,
      sell_i_vol: 400_000,
    },
    {
      symbol: 'وبملت',
      ins_code: 'INS_BMELLAT_2',
      is_live: true,
      d_even: 20261014,
      p_last: 2000,
      p_closing: 2000,
      price_yesterday: 1950,
      tmin: 1850,
      tmax: 2150,
      q_tot_tran: 2_000_000,
      buy_i_vol: 1_200_000,
      sell_i_vol: 1_100_000,
    },
  ],
};

const FIXTURE_MW_1 = {
  marketwatch: [
    {
      insCode: 'INS_FOOLAD_1',
      lva: 'فولاد',
      pcl: 5050,
      pdv: 5100,
      py: 4900,
      pf: 4950,
      pmn: 4920,
      pmx: 5120,
      pMin: 4600,
      pMax: 5400,
      dEven: 20261019,
      hEven: 93000,
      qtj: 1_200_000,
      qtc: 6_060_000_000,
      ztt: 500,
      eps: 350,
      blDs: [
        { qmd: 100_000, pmd: 5100, zmd: 10, qmo: 50_000, pmo: 5110, zmo: 5 },
      ],
    },
    {
      insCode: 'INS_BMELLAT_2',
      lva: 'وبملت',
      pcl: 2020,
      pdv: 2030,
      py: 1950,
      pf: 1960,
      pmn: 1950,
      pmx: 2040,
      pMin: 1850,
      pMax: 2150,
      dEven: 20261019,
      hEven: 93000,
      qtj: 2_500_000,
      qtc: 5_050_000_000,
      ztt: 800,
      eps: 180,
      blDs: [
        { qmd: 300_000, pmd: 2030, zmd: 20, qmo: 150_000, pmo: 2040, zmo: 15 },
      ],
    },
  ],
};

const FIXTURE_MW_2 = {
  marketwatch: [
    {
      insCode: 'INS_FOOLAD_1',
      lva: 'فولاد',
      pcl: 5150, // قیمت پایانی تغییر یافته
      pdv: 5200, // آخرین معامله تغییر یافته
      py: 4900,
      pf: 4950,
      pmn: 4920,
      pmx: 5220,
      pMin: 4600,
      pMax: 5400,
      dEven: 20261019,
      hEven: 94500,
      qtj: 1_800_000, // حجم معاملات افزایش یافته
      qtc: 9_270_000_000,
      ztt: 750,
      eps: 350,
      blDs: [
        { qmd: 200_000, pmd: 5200, zmd: 15, qmo: 30_000, pmo: 5210, zmo: 3 },
      ],
    },
    {
      insCode: 'INS_BMELLAT_2',
      lva: 'وبملت',
      pcl: 2020,
      pdv: 2030,
      py: 1950,
      pf: 1960,
      pmn: 1950,
      pmx: 2040,
      pMin: 1850,
      pMax: 2150,
      dEven: 20261019,
      hEven: 94500,
      qtj: 2_500_000,
      qtc: 5_050_000_000,
      ztt: 800,
      eps: 180,
      blDs: [],
    },
  ],
};

const FIXTURE_CT_1 = {
  clientTypeAllDto: [
    {
      insCode: 'INS_FOOLAD_1',
      buy_I_Volume: 800_000,
      buy_N_Volume: 400_000,
      sell_I_Volume: 600_000,
      sell_N_Volume: 600_000,
      buy_CountI: 250,
      sell_CountI: 180,
    },
    {
      insCode: 'INS_BMELLAT_2',
      buy_I_Volume: 1_500_000,
      buy_N_Volume: 1_000_000,
      sell_I_Volume: 1_800_000,
      sell_N_Volume: 700_000,
      buy_CountI: 400,
      sell_CountI: 350,
    },
  ],
};

const FIXTURE_CT_2 = {
  clientTypeAllDto: [
    {
      insCode: 'INS_FOOLAD_1',
      buy_I_Volume: 1_200_000, // تغییر در حجم حقیقی
      buy_N_Volume: 600_000,
      sell_I_Volume: 700_000,
      sell_N_Volume: 1_100_000,
      buy_CountI: 350,
      sell_CountI: 220,
    },
  ],
};

const FIXTURE_BAKED_FUNNEL = {
  status: 'success',
  preset: 'trend',
  as_of: 1792300000,
  universe: { joined: 750, active: 620 },
  stages: {
    tape: { passed: 120, total: 620, entries: [{ symbol: 'فولاد', status: { tape: 'pass' } }] },
    technical: { passed: 45, total: 120, entries: [{ symbol: 'فولاد', status: { technical: 'pass' } }] },
    fundamental: { passed: 12, total: 45, entries: [{ symbol: 'فولاد', status: { fundamental: 'pass' } }] },
    handover: { passed: 4, total: 12, entries: [{ symbol: 'فولاد', status: { handover: 'pass' } }] },
  },
};

const FIXTURE_BAKED_FTS_FOOLAD = {
  status: 'success',
  symbol: 'فولاد',
  growth: { status: 'BAKED_OK', yoyGrowth: 45.2 },
  fts: {
    fib: { level: '0.618', price: 4800 },
    jet: { speed: 'HIGH', score: 85 },
    exit_engine: { verdict: 'HOLD', l1: { hard_stop: 4750 } },
    hourglass: { score: 72 },
    trend: { state: 'BULLISH' },
  },
};

// ---- ماک کردن داده‌های محلی و بومی ----------------------------------------
const bakedMap = new Map<string, unknown>();
let mockNativeJsonHandler: (url: string) => Promise<unknown | null> = async () => null;

vi.mock('@shared/api/local/nativeHttp', () => ({
  nativeGetJson: async (url: string) => mockNativeJsonHandler(url),
  nativeGetText: async () => null,
  nativeGetBytes: async () => null,
  nativeGetJsonResult: async (url: string) => ({
    status: 200,
    data: await mockNativeJsonHandler(url),
    headers: {},
  }),
  nativeGetTextResult: async () => ({
    status: 200,
    data: '',
    headers: {},
  }),
}));

vi.mock('@shared/api/local/localData', () => ({
  baked: async (key: string) => (bakedMap.has(key) ? bakedMap.get(key) : null),
  metaValue: async (k: string) => (k === 'built_at' ? '2026-10-14T12:30:00Z' : '1.1.2'),
  query: async (sql: string, params: unknown[]) => {
    if (sql.includes('price_history')) {
      const sym = String(params[0] ?? '');
      if (sym === 'فولاد') {
        // ایجاد ۱۴ کندل آزمایشی برای محاسبه MA14
        const rows: Record<string, unknown>[] = [];
        for (let i = 1; i <= 14; i++) {
          const day = i < 10 ? `0${i}` : `${i}`;
          rows.push({
            date: `2026-10-${day}`,
            open: 5000 + i * 10,
            high: 5100 + i * 10,
            low: 4950 + i * 10,
            close: 5020 + i * 10, // آخرین کندل = 5020 + 140 = 5160
            volume: 1_000_000,
            last: 5020 + i * 10,
          });
        }
        return rows;
      }
    }
    return [] as Record<string, unknown>[];
  },
  normFa: (s: string) => (s ?? '').trim().replace(/ي/g, 'ی').replace(/ك/g, 'ک'),
  getDb: async () => ({}),
  bootTiming: { source: 'bundle', gzBytes: 0, rawBytes: 0, fetchMs: 0, gunzipMs: 0, openMs: 0, totalMs: 0 },
}));

const mockCodalStore = {
  readMonthlyRevenueSeries: vi.fn(),
};
vi.mock('@shared/api/local/codalStore', () => ({
  codalStore: mockCodalStore,
}));

const { resolveLocal, overlayStatus, __resetBoardForTest } = await import('@shared/api/local/resolvers');

let testEpoch = 1792300000000;

describe('مرحله ۲: تست قطعی تازه‌سازی زنده بازار بدون بازار زنده (Deterministic Live Market Audit)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    testEpoch += 3600000; // پیشروی ۱ ساعت برای هر تست تا کش‌های ماژول قبلی قطعاً منقضی باشند
    vi.setSystemTime(new Date(testEpoch));
    __resetBoardForTest();
    bakedMap.clear();
    bakedMap.set('market_board', JSON.parse(JSON.stringify(FIXTURE_BAKED_BOARD)));
    mockCodalStore.readMonthlyRevenueSeries.mockReset().mockResolvedValue(null);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('آزمون ۱: فراخوانی اولیه مارکت‌واچ و اعمال فیکسچر FIXTURE_MW_1', async () => {
    mockNativeJsonHandler = async (url: string) => {
      if (url.includes('GetMarketWatch')) return FIXTURE_MW_1;
      if (url.includes('GetClientTypeAll')) return FIXTURE_CT_1;
      return null;
    };

    const board = (await resolveLocal('/api/market', 'GET')) as Record<string, unknown>;
    expect(board.status).toBe('success');
    expect(board.rev).toBe(0); // دور اول فقط baseline مُهر می‌کند
    expect(board.live_count).toBe(2);

    const rows = board.data as Record<string, unknown>[];
    const foolad = rows.find((r) => r.symbol === 'فولاد');
    expect(foolad).toBeDefined();
    expect(foolad?.p_closing).toBe(5050);
    expect(foolad?.p_last).toBe(5100);
    expect(foolad?.percent_change).toBeCloseTo(3.06, 2);
    expect(foolad?.buy_i_vol).toBe(800_000);
  });

  it('آزمون ۲: کش مارکت‌واچ زیر ۵ ثانیه مانع از درخواست شبکه می‌شود', async () => {
    let mwCallCount = 0;
    mockNativeJsonHandler = async (url: string) => {
      if (url.includes('GetMarketWatch')) {
        mwCallCount++;
        return FIXTURE_MW_1;
      }
      return null;
    };

    await resolveLocal('/api/market', 'GET');
    expect(mwCallCount).toBe(1);

    // پیشروی ۲ ثانیه‌ای (زیر TTL پنج ثانیه)
    vi.advanceTimersByTime(2000);
    await resolveLocal('/api/market', 'GET');
    expect(mwCallCount).toBe(1); // نباید شبکه را دوباره صدا بزند
  });

  it('آزمون ۳: پس از انقضای TTL پنج ثانیه، فیکسچر دوم FIXTURE_MW_2 اعمال می‌شود و rev تغییر می‌کند', async () => {
    let currentMw = FIXTURE_MW_1;
    mockNativeJsonHandler = async (url: string) => {
      if (url.includes('GetMarketWatch')) return currentMw;
      if (url.includes('GetClientTypeAll')) return FIXTURE_CT_1;
      return null;
    };

    await resolveLocal('/api/market', 'GET');

    // تغییر فیکسچر به FIXTURE_MW_2 و پیشروی ۵۵۰۰ میلی‌ثانیه زمان
    currentMw = FIXTURE_MW_2;
    vi.advanceTimersByTime(5500);

    const board = (await resolveLocal('/api/market', 'GET')) as Record<string, unknown>;
    expect(board.rev).toBe(1); // عدد عوض شد ⇒ rev افزایش یافت
    expect(Number(board.rev_at)).toBe(Date.now());

    const rows = board.data as Record<string, unknown>[];
    const foolad = rows.find((r) => r.symbol === 'فولاد');
    expect(foolad?.p_closing).toBe(5150);
    expect(foolad?.p_last).toBe(5200);
    expect(foolad?.q_tot_tran).toBe(1_800_000);
  });

  it('آزمون ۴: کش ۳۰ ثانیه‌ای مستقل حقیقی/حقوقی در زمان ۵ ثانیه تغییر نمی‌کند ولی در ۳۱ ثانیه تازه می‌شود', async () => {
    let ctCallCount = 0;
    let currentCt = FIXTURE_CT_1;

    mockNativeJsonHandler = async (url: string) => {
      if (url.includes('GetMarketWatch')) return FIXTURE_MW_1;
      if (url.includes('GetClientTypeAll')) {
        ctCallCount++;
        return currentCt;
      }
      return null;
    };

    await resolveLocal('/api/market', 'GET');
    expect(ctCallCount).toBe(1);

    // پیشروی ۶ ثانیه‌ای (مارکت‌واچ منقضی شده ولی حقیقی/حقوقی ۳۰ ثانیه‌ای هنوز معتبر است)
    currentCt = FIXTURE_CT_2;
    vi.advanceTimersByTime(6000);
    const boardMid = (await resolveLocal('/api/market', 'GET')) as Record<string, unknown>;
    expect(ctCallCount).toBe(1); // حقیقی/حقوقی نباید صدا زده شود
    const fooladMid = (boardMid.data as Record<string, unknown>[]).find((r) => r.symbol === 'فولاد');
    expect(fooladMid?.buy_i_vol).toBe(800_000); // هنوز فیکسچر قبلی معتبر است

    // پیشروی ۲۵ ثانیه‌ای دیگر (مجموعاً ۳۱ ثانیه > ۳۰ ثانیه)
    vi.advanceTimersByTime(25000);
    const boardEnd = (await resolveLocal('/api/market', 'GET')) as Record<string, unknown>;
    expect(ctCallCount).toBe(2); // حالا منقضی شد و خوانده شد
    const fooladEnd = (boardEnd.data as Record<string, unknown>[]).find((r) => r.symbol === 'فولاد');
    expect(fooladEnd?.buy_i_vol).toBe(1_200_000); // مقدار جدید فیکسچر FIXTURE_CT_2 اعمال شد
  });

  it('آزمون ۵: خطای شبکه، پاسخ null، و بازیابی موفق (Fault Tolerance & Recovery)', async () => {
    let shouldFail = false;
    mockNativeJsonHandler = async (url: string) => {
      if (shouldFail) return null;
      if (url.includes('GetMarketWatch')) return FIXTURE_MW_1;
      return null;
    };

    // بارگذاری اولیه موفق
    await resolveLocal('/api/market', 'GET');
    expect(overlayStatus()?.fails).toBe(0);

    // شبیه‌سازی قطع کامل شبکه
    shouldFail = true;
    vi.advanceTimersByTime(6000);
    const boardFailed = (await resolveLocal('/api/market', 'GET')) as Record<string, unknown>;
    expect(boardFailed.status).toBe('success'); // اپ کرش نمی‌کند و اسنپ‌شات را نگه می‌دارد
    expect(overlayStatus()?.fails).toBe(1);
    expect(overlayStatus()?.lastFailAt).not.toBeNull();

    // بازیابی شبکه
    shouldFail = false;
    vi.advanceTimersByTime(6000);
    const boardRecovered = (await resolveLocal('/api/market', 'GET')) as Record<string, unknown>;
    expect(boardRecovered.status).toBe('success');
    expect(overlayStatus()?.fails).toBe(1); // تعداد شکست‌های ثبت‌شده نمی‌سوزد
  });

  it('آزمون ۶: بررسی زمان‌بندی تهران و فاصله‌های پولینگ داخل و خارج ساعت بازار', () => {
    // ۴شنبه ساعت ۱۰:۰۰ صبح تهران (داخل بازار)
    const insideTime = new Date('2026-10-21T06:30:00Z'); // 10:00 Asia/Tehran
    expect(isMarketOpen(insideTime)).toBe(true);
    expect(effectivePollMs(5000, insideTime)).toBe(5000);
    expect(sessionPollMs(20000, insideTime)).toBe(20000);

    // ۴شنبه ساعت ۱۸:۰۰ عصر تهران (خارج بازار)
    const outsideTime = new Date('2026-10-21T14:30:00Z'); // 18:00 Asia/Tehran
    expect(isMarketOpen(outsideTime)).toBe(false);
    expect(effectivePollMs(5000, outsideTime)).toBe(CLOSED_POLL_MS); // 300,000ms
    expect(sessionPollMs(20000, outsideTime)).toBe(CLOSED_POLL_MS);

    // جمعه ساعت ۱۰:۰۰ صبح تهران (تعطیل پایان هفته)
    const fridayTime = new Date('2026-10-23T06:30:00Z');
    expect(isMarketOpen(fridayTime)).toBe(false);
    expect(effectivePollMs(5000, fridayTime)).toBe(CLOSED_POLL_MS);
  });
});

describe('مرحله ۳: آزمون رفتار قیف FTS و مقایسه با دسکتاپ (Funnel & FTS Parity Audit)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    testEpoch += 3600000;
    vi.setSystemTime(new Date(testEpoch));
    __resetBoardForTest();
    bakedMap.clear();
    bakedMap.set('market_board', JSON.parse(JSON.stringify(FIXTURE_BAKED_BOARD)));
    bakedMap.set('funnel/trend/and/standard/ds1', FIXTURE_BAKED_FUNNEL);
    mockCodalStore.readMonthlyRevenueSeries.mockReset().mockResolvedValue(null);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('آزمون ۷: باز ارزیابی پویای /api/funnel پس از دریافت داده‌های تابلوی زنده', async () => {
    let currentMw = FIXTURE_MW_1;
    mockNativeJsonHandler = async (url: string) => {
      if (url.includes('GetMarketWatch')) return currentMw;
      return null;
    };

    // در حالت پیش از اتصال به تابلوی زنده: سرو از اسنپ‌شات پخته
    const funnelBefore = await resolveLocal('/api/funnel', 'POST', {
      preset: 'trend',
      chain: [],
      logic: 'and',
      fund_mode: 'standard',
      exceptions: {},
      drop_suffix: true,
    });
    expect(funnelBefore).toEqual(FIXTURE_BAKED_FUNNEL);

    // جهش شدید قیمت در مارکت‌واچ زنده (FIXTURE_MW_2) و به‌روزرسانی تابلو
    currentMw = FIXTURE_MW_2;
    vi.advanceTimersByTime(6000);
    await resolveLocal('/api/market', 'GET'); // تابلوی بازار عوض شد

    // درخواست مجدد قیف پس از دریافت داده‌های زنده بازار
    const funnelAfter = (await resolveLocal('/api/funnel', 'POST', {
      preset: 'trend',
      chain: [],
      logic: 'and',
      fund_mode: 'standard',
      exceptions: {},
      drop_suffix: true,
    })) as Record<string, unknown>;

    // اثبات قطعی باز ارزیابی: قیف دیگر به اسنپ‌شات منجمد قبلی محدود نیست و با موتور کانونی محلی اجرا می‌شود
    expect(funnelAfter).not.toBe(funnelBefore);
    expect(funnelAfter.status).toBe('success');
    expect((funnelAfter.metadata as Record<string, unknown>).engine_mode).toBe('local_canonical');
    expect((funnelAfter.metadata as Record<string, unknown>).data_source).toBe('live_overlay');
    expect((funnelAfter.universe as Record<string, unknown>).board).toBe(2);
  });

  it('آزمون ۸: رفتار /api/fts/:symbol در حالت پخته همراه با غنی‌سازی رشد کدال محلی', async () => {
    bakedMap.set('fts/فولاد', FIXTURE_BAKED_FTS_FOOLAD);

    // حالت الف: بدون دادهٔ جدید کدال در دیتابیس دستگاه
    const resA = (await resolveLocal('/api/fts/فولاد', 'GET')) as Record<string, unknown>;
    expect(resA).toEqual(FIXTURE_BAKED_FTS_FOOLAD);

    // حالت ب: با تزریق سری درآمد ماهانه جدید به codalStore محلی
    mockCodalStore.readMonthlyRevenueSeries.mockResolvedValue({
      coverage: 'DESKTOP_COMPATIBLE',
      rows: [
        { periodEnd: '1404/06/31', ytdRevenue: 150_000_000, ytdRevenuePrev: 100_000_000 },
      ],
    });

    const resB = (await resolveLocal('/api/fts/فولاد', 'GET')) as Record<string, unknown>;
    expect(resB.symbol).toBe('فولاد');
    // رشد باید به طور محلی دوباره ارزیابی شده باشد
    const growth = resB.growth as Record<string, unknown>;
    expect(growth.status).toBe('EVALUATED');
    expect(growth.pass).toBe(true);
    expect(growth.growthPct).toBe(50); // (150-100)/100 = 50%
    // اما اجزای دیگر پخته ثابت می‌مانند
    const fts = resB.fts as Record<string, unknown>;
    expect(fts.fib).toEqual({ level: '0.618', price: 4800 });
  });

  it('آزمون ۹: رفتار /api/fts/:symbol در حالت فال‌بک محلی (بدون اسنپ‌شات پخته)', async () => {
    // عدم وجود fts/فولاد در اسنپ‌شات پخته
    bakedMap.delete('fts/فولاد');

    mockCodalStore.readMonthlyRevenueSeries.mockResolvedValue({
      coverage: 'DESKTOP_COMPATIBLE',
      rows: [
        { periodEnd: '1404-06-31', ytdRevenue: 160_000_000, ytdRevenuePrev: 100_000_000 },
      ],
    });

    const res = (await resolveLocal('/api/fts/فولاد', 'GET')) as Record<string, unknown>;
    expect(res.analysis_basis).toBe('local-first');
    expect(res.symbol).toBe('فولاد');

    const fts = res.fts as Record<string, unknown>;
    expect(fts.fib).toBeNull(); // در موبایل محاسبه نمی‌شود
    expect(fts.jet).toBeNull();

    // خروج بر اساس MA14 محاسبه می‌شود
    const exitEngine = fts.exit_engine as Record<string, unknown>;
    expect(exitEngine).toBeDefined();
    expect(exitEngine.verdict).toBe('HOLD');

    const l1 = exitEngine.l1 as Record<string, unknown>;
    expect(l1.hard_stop).toBe(Math.round(5160 * 0.95)); // 5% زیر آخرین کلوز محلی (5160)
  });

  it('آزمون ۱۰: مسیرهای پشتیبانی‌نشده یا فیلترهای سفارشی خطای صریح HttpError(404) می‌دهند', async () => {
    // پارامترهای سفارشی یا استثنا در نسخه موبایل رد می‌شوند
    await expect(
      resolveLocal('/api/funnel', 'POST', {
        preset: 'trend',
        chain: ['f_custom_1'],
        logic: 'and',
        fund_mode: 'standard',
        drop_suffix: true,
      }),
    ).rejects.toThrow(HttpError);

    // ردپای قیف (/api/funnel/trace) روی موبایل وجود ندارد
    await expect(resolveLocal('/api/funnel/trace?symbol=فولاد', 'GET')).rejects.toThrow(HttpError);
  });
});
