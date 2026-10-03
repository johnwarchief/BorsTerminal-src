// __tests__/fts-candidate-engine.spec.tsx -- قراردادِ canonical کاندید: S ➔ T ➔ F ➔ M
//
// سناریوهایِ خواستۀ بازطراحیِ «موتورِ کشفِ نماد»، رویِ تک‌منبعِ داوری
// (`lib/ftsFunnel.ts`) — نه رویِ یک کامپوننت. هر پرچم درِ این فایل یک بار
// شکسته شده بود: رتبه‌بندیِ پنهان، نتیجه‌گیریِ نقطه‌زنی از false، و «بی‌داده = رد».
import { describe, it, expect, beforeEach } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import {
  DEFAULT_FUNNEL_OPTIONS,
  buildFunnel,
  funnelUniverse,
  orderOfficial,
  techQueryQueue,
  type Candidate,
  type FunnelOptions,
  type TreePreset,
} from '@features/master/lib/ftsFunnel';
import { TECH_QUERY_CAP, type TechVerdict } from '@features/master/api/useFtsTechBoard';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';

const board = (over: Partial<MarketRow>): MarketRow =>
  ({ is_live: true, p_last: 1000, p_closing: 990, ...over }) as unknown as MarketRow;

const five = (symbol: string, over: Partial<FtsScreenRow> = {}): FtsScreenRow =>
  ({
    symbol,
    name: symbol,
    sector_name: 'فلزات اساسي',
    pricing_mode: 'آزاد',
    score: 5,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    ...over,
  }) as FtsScreenRow;

const verdict = (over: Partial<TechVerdict> = {}): TechVerdict => ({
  decision: 'PERMITTED',
  matrixDesc: null,
  trendW: 'up',
  trendD: 'up',
  jet: false,
  fibZone: null,
  chochBull: false,
  doubleBottom: false,
  rangeBreak: false,
  hourglass: false,
  pointHunt: false,
  jetResistance: null,
  jetPctAbove: null,
  ...over,
});

const run = (
  rows: MarketRow[],
  screens: FtsScreenRow[],
  opts: {
    preset?: TreePreset;
    chips?: string[];
    tech?: Map<string, TechVerdict>;
    basket?: string[];
    mode?: 'reverse' | 'review';
    tape?: 'live' | 'stale' | 'unavailable';
    funnelOpts?: Partial<FunnelOptions>;
  } = {},
) =>
  buildFunnel(
    rows,
    DEFAULT_TAPE_FILTER_CONFIG,
    opts.chips ?? [],
    screens,
    new Set(opts.basket ?? []),
    opts.preset ?? 'custom',
    opts.tech ?? new Map(),
    { ...DEFAULT_FUNNEL_OPTIONS, ...opts.funnelOpts },
    { mode: opts.mode ?? 'reverse', tape: opts.tape ?? 'live' },
  );

const one = (f: ReturnType<typeof run>, sym: string): Candidate =>
  f.stages.tape.entries.find((e) => e.symbol === sym)!;

const ROWS = [board({ symbol: 'فولاد', f_susp: true, f_clock: true })];
const SCREENS = [five('فولاد')];

describe('زنجیرۀ اصلیِ مهندسیِ معکوس', () => {
  beforeEach(() => useFunnelPrefsStore.getState().reset());

  it('S pass ➔ T pass ➔ F pass ➔ M pass: نماد تا تحویل می‌رسد', () => {
    const f = run(ROWS, SCREENS, { tech: new Map([['فولاد', verdict({ jet: true })]]) });
    const c = one(f, 'فولاد');
    expect(c.status).toEqual({ tape: 'pass', technical: 'pass', fundamental: 'pass', handover: 'pass' });
    expect(f.stages.handover.entries.map((e) => e.symbol)).toEqual(['فولاد']);
    expect(c.techSource).toBe('live');
  });

  it('وتوی هفتگی به بنیادی و تحویل نمی‌رسد (T reject ⇒ پایین‌دست بسته)', () => {
    const f = run(ROWS, SCREENS, { tech: new Map([['فولاد', verdict({ decision: 'REJECT', trendW: 'down', jet: true })]]) });
    const c = one(f, 'فولاد');
    expect(c.status.technical).toBe('reject');
    expect(c.status.handover).toBe('reject');
    expect(f.stages.fundamental.entries).toHaveLength(0);
    expect(f.stages.handover.entries).toHaveLength(0);
    expect(c.why.technical).toContain('وتوی هفتگی');
  });

  it('گیتِ ستاپ به شاخۀ درستِ هفتگی می‌نشیند: هفتگی صعودی + ستاپِ همان سبک', () => {
    // نوسان‌گیر: جت قبول، فیبو ۶۱.۸-۷۰ قبول نیست
    const jet = run(ROWS, SCREENS, { preset: 'swing', tech: new Map([['فولاد', verdict({ jet: true })]]) });
    expect(one(jet, 'فولاد').status.technical).toBe('pass');
    const fib61 = run(ROWS, SCREENS, { preset: 'swing', tech: new Map([['فولاد', verdict({ fibZone: '61.8-70' })]]) });
    expect(one(fib61, 'فولاد').status.technical).toBe('reject');
    const fib33 = run(ROWS, SCREENS, { preset: 'swing', tech: new Map([['فولاد', verdict({ fibZone: '33-40' })]]) });
    expect(one(fib33, 'فولاد').status.technical).toBe('pass');
  });

  it('هفتگیِ UNKNOWN نظر نمی‌دهد — نه رد است نه قبول', () => {
    const f = run(ROWS, SCREENS, { tech: new Map([['فولاد', verdict({ decision: 'UNKNOWN', trendW: 'na' })]]) });
    const c = one(f, 'فولاد');
    expect(c.status.technical).toBe('pending');
    expect(c.status.handover).toBe('pending');
    expect(f.stages.handover.entries).toHaveLength(0);
  });
});

describe('تابلویِ در دسترس نبودن ≠ رد (#2 و #16)', () => {
  beforeEach(() => useFunnelPrefsStore.getState().reset());

  it('مرورِ کامل بازار: بی‌تابلو هم کاندیدها داوری می‌شوند و تابلو «unavailable» می‌خورد', () => {
    const f = run([], [five('فولاد')], {
      mode: 'review',
      tape: 'unavailable',
      tech: new Map([['فولاد', verdict({ jet: true })]]),
    });
    const c = one(f, 'فولاد');
    expect(c.status.tape).toBe('unavailable');
    expect(c.status.fundamental).toBe('pass');
    expect(c.status.handover).toBe('pass');
    expect(c.why.tape).toContain('وتو نیست');
  });

  it('تابلو در مرورِ بازار هیچ‌وقت درِ ورود را نمی‌بندد (بی‌نشانه ⇒ pending، نه reject)', () => {
    const f = run(ROWS, [five('فولاد')], { mode: 'review', tape: 'stale' });
    expect(one(f, 'فولاد').status.tape).toBe('pass'); // فولاد نشانه دارد
    const g = run([board({ symbol: 'شپنا', f_clock: false, f_susp: false, f_jet: false })], [five('شپنا')], {
      mode: 'review',
      tape: 'stale',
    });
    expect(one(g, 'شپنا').status.tape).toBe('pending');
    expect(one(g, 'شپنا').status.handover).not.toBe('reject');
  });

  it('دادهٔ آخرینِ نشست با دادهٔ زنده قاطی نمی‌شود (برچسبِ تازگی درِ علت هست)', () => {
    const f = run(ROWS, SCREENS, { mode: 'review', tape: 'stale', tech: new Map([['فولاد', verdict({ jet: true })]]) });
    expect(one(f, 'فولاد').why.tape).toContain('آخرینِ نشست');
  });
});

describe('N/A بنیادی ≠ رد (#8)', () => {
  beforeEach(() => useFunnelPrefsStore.getState().reset());

  it('ابزاری که پنج‌شاخصه درباره‌اش نظر نمی‌دهد: pending، نه reject', () => {
    const f = run(ROWS, [five('فولاد', { applicable: false, score: 0 })], { tape: 'live' });
    const c = one(f, 'فولاد');
    expect(c.status.fundamental).toBe('pending');
    expect(c.inds).toEqual(['pending', 'pending', 'pending', 'pending', 'pending']);
    expect(c.status.handover).toBe('pending');
  });

  it('ردیفِ اسکرینر نبود: unavailable — و با پیچِ «عبور با برچسب» هم رد خوانده نمی‌شود', () => {
    const held = run(ROWS, [], {});
    expect(one(held, 'فولاد').status.fundamental).toBe('unavailable');
    const carried = run(ROWS, [], { funnelOpts: { unmeasured: 'pass' } });
    expect(one(carried, 'فولاد').status.fundamental).toBe('unavailable');
    expect(one(carried, 'فولاد').status.handover).toBe('pass');
    expect(one(carried, 'فولاد').why.handover).toContain('برچسب');
  });

  it('نرخ‌گذاریِ دستوری همان‌جا وتو است (ردِ صریح، نه بی‌داده)', () => {
    const f = run(ROWS, [five('فولاد', { pricing_mode: 'دستوری' })], {});
    expect(one(f, 'فولاد').status.fundamental).toBe('reject');
    expect(one(f, 'فولاد').why.fundamental).toContain('دستوری');
  });
});

describe('نقطه‌زنی از false مصنوعی نتیجه نمی‌شود (#7)', () => {
  beforeEach(() => useFunnelPrefsStore.getState().reset());

  const trendRows = [board({ symbol: 'سپ', f_noqteh: true })];
  const trendScreens = [five('سپ', { tech_matrix_decision: 'PERMITTED', tech_trend_w: 'up', tech_trend_d: 'range' })];

  it('اسکرینر فیلدِ نقطه‌زنی ندارد ⇒ pending، نه رد', () => {
    const f = run(trendRows, trendScreens, { preset: 'trend' });
    const c = one(f, 'سپ');
    expect(c.status.technical).toBe('pending');
    expect(c.why.technical).toContain('سنجیده نشده');
    expect(c.techSource).toBe('screen');
  });

  it('رأیِ زندهٔ /api/fts اگر نقطه‌زنی را فعال بداند ⇒ قبول', () => {
    const f = run(trendRows, trendScreens, {
      preset: 'trend',
      tech: new Map([['سپ', verdict({ pointHunt: true })]]),
    });
    expect(one(f, 'سپ').status.technical).toBe('pass');
    expect(one(f, 'سپ').setups).toContain('نقطه‌زنی');
  });

  it('رأیِ زنده اگر نقطه‌زنی را صریحاً false بداند ⇒ رد (این‌جا داده هست)', () => {
    const f = run(trendRows, trendScreens, {
      preset: 'trend',
      tech: new Map([['سپ', verdict({ pointHunt: false })]]),
    });
    expect(one(f, 'سپ').status.technical).toBe('reject');
  });
});

describe('هیچ رتبه‌بندیِ پنهانی نیست (#3، #12 و #15)', () => {
  it('صفِ تکنیکال با رتبۀ رسمیِ بک‌اند چیده می‌شود، نه با ترتیبِ تابلو', () => {
    // تابلو «ز» را اول داده ولی اسکرینر «الف» را رتبۀ اول گذاشته است
    const rows = [board({ symbol: 'ز', f_susp: true }), board({ symbol: 'الف', f_susp: true })];
    const screens = [five('الف'), five('ز')];
    const u = funnelUniverse('reverse', rows, DEFAULT_TAPE_FILTER_CONFIG, [], 'custom', screens);
    expect(u.ordered).toEqual(['الف', 'ز']);
    const q = techQueryQueue(u.ordered, u.rank, 1);
    expect(q.symbols).toEqual(['الف']);
    expect(q.beyondCap).toBe(1);
  });

  it('بیرونِ بودجه «رد» نمی‌شود: رأیِ نسنجیده = unavailable', () => {
    const rows = [board({ symbol: 'ز', f_susp: true }), board({ symbol: 'الف', f_susp: true })];
    const screens = [five('الف'), five('ز')];
    const u = funnelUniverse('reverse', rows, DEFAULT_TAPE_FILTER_CONFIG, [], 'custom', screens);
    const q = techQueryQueue(u.ordered, u.rank, TECH_QUERY_CAP);
    expect(q.symbols).toHaveLength(2);
    // فقط «الف» رأیِ زنده می‌گیرد؛ «ز» باید درِ جدول باقی بماند و بی‌داده بخورد
    const f = buildFunnel(
      rows, DEFAULT_TAPE_FILTER_CONFIG, [], screens, new Set(), 'custom',
      new Map([['الف', verdict({ jet: true })]]), DEFAULT_FUNNEL_OPTIONS,
      { mode: 'reverse', tape: 'live' },
    );
    expect(one(f, 'الف').techSource).toBe('live');
    expect(one(f, 'ز').techSource).toBeNull();
    expect(one(f, 'ز').status.technical).toBe('unavailable');
    expect(f.stages.tape.entries).toHaveLength(2);
  });

  it('هیچ سقفِ ۵۰ یا ۱۰‌تایی درِ مدل نیست: هرچه واجد است می‌ماند', () => {
    // نمادها بی‌رقم‌اند: `dropNumericSuffixRows` ردیف‌هایِ «پسوندِ عددی» را از
    // جامعۀ قیف بیرون می‌اندازد و وگرنه این تست صفر ردیف می‌دید.
    const FA = 'ابپتثجچحخدذرزسشصضطظعغفقکگلمنوهی';
    const sym = (i: number) => 'ن' + FA[i % FA.length] + (i < FA.length ? '' : FA[Math.floor(i / FA.length)]);
    const rows = Array.from({ length: 61 }, (_, i) => board({ symbol: sym(i), f_susp: true }));
    const screens = Array.from({ length: 61 }, (_, i) => five(sym(i)));
    const tech = new Map<string, TechVerdict>(screens.map((s) => [s.symbol, verdict({ jet: true })]));
    const f = run(rows, screens, { tech });
    expect(f.stages.tape.entries).toHaveLength(61);
    expect(f.stages.handover.entries).toHaveLength(61);
    expect(f.targets).toEqual({ initial: 50, watchlist: 10, basketMin: 5, basketMax: 7 });
    // شمارشِ چهارحالته با مجموعِ داوری‌شده‌ها می‌خواند (هیچ ردیفی گم نمی‌شود)
    const s = f.counts.handover;
    expect(s.pass + s.reject + s.pending + s.unavailable).toBe(61);
  });

  it('دترمینیسم: همان داده ⇒ همان صف و همان کاندیدها، حتی با ترتیبِ دیگرِ تابلو', () => {
    const rows = [board({ symbol: 'ب', f_susp: true }), board({ symbol: 'ا', f_susp: true }), board({ symbol: 'پ', f_susp: true })];
    const screens = [five('ا'), five('ب'), five('پ')];
    const a = run(rows, screens, {});
    const b = run([...rows].reverse(), screens, {});
    expect(a.stages.tape.entries.map((e) => e.symbol)).toEqual(b.stages.tape.entries.map((e) => e.symbol));
    const u1 = funnelUniverse('reverse', rows, DEFAULT_TAPE_FILTER_CONFIG, [], 'custom', screens);
    const u2 = funnelUniverse('reverse', [...rows].reverse(), DEFAULT_TAPE_FILTER_CONFIG, [], 'custom', screens);
    expect(orderOfficial(u1.ordered, u1.rank)).toEqual(orderOfficial(u2.ordered, u2.rank));
  });

  it('پیچ‌هایِ دستِ مالک رتبه نمی‌سازند: کفِ بنیادی تنها معیارِ عبور است', () => {
    const screens = [five('الف', { score: 4 }), five('ب', { score: 2 })];
    const rows = [board({ symbol: 'الف', f_susp: true }), board({ symbol: 'ب', f_susp: true })];
    const f = run(rows, screens, { funnelOpts: { fundFloor: 3 } });
    expect(f.stages.fundamental.entries.map((e) => e.symbol)).toEqual(['الف']);
    expect(one(f, 'ب').why.fundamental).toContain('زیرِ کف');
  });
});
