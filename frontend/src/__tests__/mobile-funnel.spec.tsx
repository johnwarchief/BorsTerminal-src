// گاردِ غربالگریِ آفلاین — مسیرِ قیف رویِ گوشی
//
// پیش از این این فایل `buildFunnel` را می‌آزمود (داوریِ درونِ مرورگر). آن داور
// عمداً حذف شد: تنها داورِ مجاز `api/funnel.py` است. پس پرسشِ واقعیِ موبایل
// دیگر «آیا اشتراک درست حساب می‌شود؟» نیست — آن را خودِ تست‌هایِ دسکتاپ و
// گاردهایِ پایتون می‌سنجند — بلکه این است:
//   ۱) گوشی همان خروجیِ پختۀ موتور را می‌گیرد، بی‌هیچ بازنویسیِ درونِ کلاینت؛
//   ۲) اگر کلیدِ پختۀ سازنده با کلیدی که resolver می‌سازد نخواند، صفحه **خطا
//      با علت** می‌دهد نه جدولِ خالی (جدولِ خالی رویِ گوشی «بازار خالی» خوانده
//      می‌شود — همان اشتباهی که «۵۹ شرکت» را ساخت).
// فیکسچر از همان `fixtures/funnelApi.ts` است که دسکتاپ می‌خواند، پس این تست
// شکلِ ساختگیِ جدا ندارد.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from '@shared/api/http';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';
import OFFLINE_KEYS from './fixtures/funnelOfflineKeys.json';
import { funnelFromApi } from '../features/master/lib/funnelView';

const bakedMap = new Map<string, unknown>();

vi.mock('@shared/api/local/localData', () => ({
  baked: async (key: string) => (bakedMap.has(key) ? bakedMap.get(key) : null),
  metaValue: async (k: string) => (k === 'app_version' ? '1.1.1' : '2026-10-16T00:00:00'),
  query: async () => [] as Record<string, unknown>[],
  normFa: (s: string) => (s ?? '').trim().replace(/ي/g, 'ی').replace(/ك/g, 'ک'),
  getDb: async () => ({}),
  bootTiming: { source: 'bundle', gzBytes: 0, rawBytes: 0, fetchMs: 0, gunzipMs: 0, openMs: 0, totalMs: 0 },
}));
vi.mock('@shared/api/local/live', () => ({
  liveWatch: async () => null,
  liveChart: async () => null,
  liveClientType: async () => null,
  liveTedpix: async () => null,
  liveTodayCandle: async () => null,
  overlayBoard: () => 0,
  tehranToday: () => '2026-10-16',
  mwRowFromJson: (r: Record<string, unknown>) => r,
}));

const { resolveLocal, funnelKey } = await import('@shared/api/local/resolvers');

const POST_BODY = { preset: 'trend', chain: [] as string[], logic: 'and',
                   fund_mode: 'standard', exceptions: {}, drop_suffix: true };

/** شبکهٔ کلیدها از fixtureِ مشترک خوانده می‌شود؛ همان فایلی که
 *  `dev/mobile_funnel_offline_v1116.py --emit` از خودِ پایتون می‌نویسد. پس اگر
 *  یکی از دو طرف برود، این فایل و آن گارد با هم قرمز می‌شوند. */
const GRID = (OFFLINE_KEYS.keys as string[]).map((k) => {
  const [, preset, logic, fundMode, ds] = k.split('/');
  return { src: k, made: funnelKey(preset, logic, fundMode, ds === 'ds1') };
});

/** خطا را می‌گیرد تا متنِ علت آزموده شود؛ اگر resolveLocal خطا نداد، خودِ
 *  این کمکی قرمز می‌شود (سبزِ بی‌شاهد نداریم). */
async function expectFunnelError(url: string, body?: unknown): Promise<string> {
  try {
    await resolveLocal(url, body === undefined ? 'GET' : 'POST', body);
  } catch (e) {
    if (e instanceof HttpError) return e.message;
    throw e;
  }
  throw new Error('سنجه انتظار HttpError داشت ولی resolveLocal پاسخ داد');
}

beforeEach(() => {
  bakedMap.clear();
  for (const g of GRID) bakedMap.set(g.made, FUNNEL_FIXTURE);
  bakedMap.set('funnel_registry', { status: 'success', filters: [] });
});

describe('قراردادِ کلیدِ مشترک (سازندۀ پایتون ⇄ resolver)', () => {
  it('هر %d کلیدِ fixture دقیقاً همان چیزی است که TS می‌سازد', () => {
    expect(GRID.length).toBeGreaterThanOrEqual(8);
    for (const g of GRID) expect(g.made).toBe(g.src);
  });
});

describe('غربالگریِ آفلاین: همان پاسخِ موتور، بی‌داوریِ دوباره', () => {
  it('پیش‌فرضِ POST از کلیدِ درستِ بستۀ آفلاین خوانده می‌شود', async () => {
    bakedMap.clear();
    bakedMap.set('funnel/trend/and/standard/ds1', FUNNEL_FIXTURE);
    const out = await resolveLocal('/api/funnel', 'POST', POST_BODY);
    // برابریتِ آبجکت (نه فقط ساختار) ثابت می‌کند هیچ بازنویسی در مسیر نبوده.
    expect(out).toBe(FUNNEL_FIXTURE);
  });

  it('منطقِ or کلیدِ خودش را می‌خواهد، نه پاسخِ and را', async () => {
    bakedMap.clear();
    bakedMap.set('funnel/trend/or/standard/ds1', { marker: 'or-answer' });
    bakedMap.set('funnel/trend/and/standard/ds1', { marker: 'and-answer' });
    const out = await resolveLocal('/api/funnel', 'POST', { ...POST_BODY, logic: 'or' });
    expect(out).toEqual({ marker: 'or-answer' });
  });

  it('GET هم به همان کلید می‌نشیند (لینکِ مرحلۀ استپّر)', async () => {
    const out = await resolveLocal('/api/funnel?preset=hourglass&logic=and', 'GET');
    expect(out).toBe(FUNNEL_FIXTURE);
  });

  it('کلیدِ نبودِ پاسخ را با نامِ خودش می‌گوید — بی‌جدولِ خالی', async () => {
    bakedMap.delete('funnel/swing/and/standard/ds1');
    const msg = await expectFunnelError('/api/funnel', { ...POST_BODY, preset: 'swing' });
    expect(msg).toContain('funnel/swing/and/standard/ds1');
  });

  it('زنجیرۀ دستِ کاربر، استثنا، حالتِ سخت و بی‌پسوند همگی صریح رد می‌شوند', async () => {
    const cases: Array<[string, unknown]> = [
      ['/api/funnel', { ...POST_BODY, preset: 'swing', chain: ['f_jet'] }],
      ['/api/funnel', { ...POST_BODY, preset: 'swing', exceptions: { tape: ['فولاد'] } }],
      ['/api/funnel', { ...POST_BODY, preset: 'swing', fund_mode: 'hard' }],
      ['/api/funnel', { ...POST_BODY, preset: 'swing', drop_suffix: false }],
      ['/api/funnel', { ...POST_BODY, preset: 'swing', params: { f_jet: { days: 3 } } }],
    ];
    for (const [url, body] of cases) {
      const msg = await expectFunnelError(url, body);
      expect(msg).toContain('پخته نشده');
      // هیچ‌کدام نباید رد شوند بی‌آنکه بگویند چه چیزی خواسته شده است
      expect(msg).toContain('swing');
    }
  });

  it('رجیستری و ردپا هم دربِ روشن دارند', async () => {
    expect(await resolveLocal('/api/funnel/registry', 'GET')).toEqual({ status: 'success', filters: [] });
    const traceMsg = await expectFunnelError('/api/funnel/trace?symbol=فولاد&preset=trend');
    expect(traceMsg).toContain('ردپا');
  });
});

describe('نگاشتِ همان پاسخ به چهار گام (همان فیکسچرِ دسکتاپ)', () => {
  const view = funnelFromApi(FUNNEL_FIXTURE, 'reverse');

  it('هیچ گامی نمادی از گامِ بالاتر اضافه نمی‌کند — لوله‌ای، نه اجتماع', () => {
    const tape = view.stages.tape.entries.map((e) => e.symbol);
    const tech = view.stages.technical.entries.map((e) => e.symbol);
    const fund = view.stages.fundamental.entries.map((e) => e.symbol);
    const hand = view.stages.handover.entries.map((e) => e.symbol);
    // کنترلِ بی‌کور: اگر فیکسچر خالی بود، «subset» بی‌معنی سبز می‌شد.
    expect(tape.length).toBeGreaterThan(0);
    expect(tech.length).toBeGreaterThan(0);
    for (const s of tech) expect(tape).toContain(s);
    for (const s of fund) expect(tech).toContain(s);
    for (const s of hand) expect(fund).toContain(s);
  });

  it('تصمیم‌هایِ ردِ موتور درِ گوشی هم رد می‌مانند (null به pass تبدیل نمی‌شود)', () => {
    const rejected = view.stages.tape.entries.filter((e) => e.status?.tape === 'reject');
    expect(rejected.length).toBeGreaterThan(0);
    expect(view.counts.tape.reject).toBeGreaterThan(0);
  });
});
