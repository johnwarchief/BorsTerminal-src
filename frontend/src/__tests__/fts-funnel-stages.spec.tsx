// __tests__/fts-funnel-stages.spec.tsx -- منطقِ قیف: کجا کم می‌شود و کجا نباید بشود
//
// سه رأیِ این قیف درِ تست می‌نشینند، چون هر سه «سکوت» می‌کنند اگر نشکنند:
//   1) تکنیکال به‌ترتیب روندِ هفتگی سپس روزانه داوری می‌شود: فقط هفتگیِ نزولی/خنثی وتو است؛
//      روزانه سه شاخهٔ معتبر دارد و ستاپ‌ها فقط شواهد/امتیاز کمکی‌اند.
//   2) بی‌داده وتو نیست: ردیفی که اسکرینر تحلیلش نکرده «سنجیده نشد» است و به
//      دورِ ریخته‌ها نمی‌رود.
//   3) ورودیِ قیف خودِ پنج فیلتر است، نه الگوهایِ محلی — «ساعت قوی» نماد را
//      داخلِ قیف نمی‌آورد، چون فیلترنویسِ سایت آن را نمی‌شناسد.
import type { ReactElement } from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { MarketRow } from '@shared/types/marketRow';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import { useTapeStore } from '@features/market/stores/tapeStore';
import {
  buildFunnel,
  DEFAULT_FUNNEL_OPTIONS,
  IND_COLUMNS,
  type FunnelOptions,
  type TreePreset,
} from '@features/master/lib/ftsFunnel';
import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';

/** هر سطرِ قیف حالا `navigate()` می‌کند، پس تست‌ها هم درِ Router می‌نشینند. */
const renderRouted = (ui: ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import type { TechVerdict } from '@features/master/api/useFtsTechBoard';

const board = (over: Partial<MarketRow>): MarketRow =>
  ({
    symbol: 'فولاد',
    name: 'فولاد مبارکه اصفهان',
    sector_name: 'فلزات اساسي',
    is_live: true,
    p_last: 1000,
    p_closing: 990,
    ...over,
  }) as unknown as MarketRow;

const screened = (symbol: string, score: number, over: Partial<FtsScreenRow> = {}): FtsScreenRow =>
  ({ symbol, name: symbol, sector_name: 'فلزات اساسي', score, pricing_mode: 'آزاد', ...over }) as FtsScreenRow;

const ROWS = [
  board({ symbol: 'فولاد', f_susp: true }),
  board({ symbol: 'شپنا', f_clock: true }),
  board({ symbol: 'خار', f_jet: true }),                    // بی‌پوششِ اسکرینر
  board({ symbol: 'همراه', f_susp: true }),                 // درِ سبد + وتوی هفتگی
  board({ symbol: 'سپ', f_noqteh: true }),                  // هفتگی صعودی، بی‌ستاپ
  // فقط «ساعت قوی» (پایانی زیر دیروز، آخرین بالای دیروز، دلتا 1.5%) — فیلتر نیست
  board({ symbol: 'قوی‌محلی', f_susp: false, p_closing: 1000, p_last: 1015, price_yesterday: 1008 }),
];

const SCREEN = [
  screened('فولاد', 5, {
    tech_matrix_decision: 'PERMITTED',
    tech_trend_w: 'up',
    tech_trend_d: 'up',
    tech_jet: true,
    // پنج شاخص یکی‌یکی، همان چیزی که ستون‌هایِ مرحلۀ بنیادی می‌خوانند
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    rev_growth: 52, eps_last: 318, gross_margin: 26, sales_to_mcap: 0.41,
  }),
  screened('شپنا', 2, {
    tech_matrix_decision: 'PERMITTED',
    tech_trend_w: 'up',
    tech_trend_d: 'down',
    tech_fib_zone: '61.8-70',
    i1_pass: false, i2_pass: null, i3_pass: false, i4_pass: true, i5_pass: true,
    rev_growth: 11, gross_margin: 12,
  }),
  screened('سپ', 4, { tech_matrix_decision: 'PERMITTED', tech_trend_w: 'up', tech_trend_d: 'range' }),
  screened('همراه', 4, { tech_matrix_decision: 'REJECT', weekly_veto: true, tech_trend_w: 'down', tech_trend_d: 'down' }),
];

/** هاب‌هایِ قابل‌تغییر برایِ دو mockِ داده — تستِ نگارشِ ستون‌ها ردیف می‌چیند. */
const feedMock = { rows: ROWS as MarketRow[] };
const screenMock = { rows: SCREEN as FtsScreenRow[] };

const build = (preset: TreePreset = 'custom', chips: string[] = []) =>
  buildFunnel(ROWS, DEFAULT_TAPE_FILTER_CONFIG, chips, SCREEN, new Set(['همراه']), preset);

const syms = (list: { symbol: string }[]) => list.map((e) => e.symbol).sort();
const markOf = (f: ReturnType<typeof build>, key: 'technical' | 'fundamental', sym: string) =>
  f.stages[key].entries.find((e) => e.symbol === sym)?.status[key];

describe('قیفِ FTS', () => {
  it('دربِ قیف سبکِ درخت است (چارت 3): روندگیر = کف‌روبی + نقطه‌زنی، نه هر پنج فیلتر', () => {
    // نوسان‌گیر: ساعت + جت + حجم مشکوک → چهار ردیفِ نشانه‌دار می‌آیند
    expect(syms(build('swing').stages.tape.entries)).toEqual(['خار', 'شپنا', 'فولاد', 'همراه']);
    // روندگیر: کف‌روبی + نقطه‌زنی → فقط «سپ» (نقطه‌زنی) از این ردیف‌ها رد می‌شود
    expect(syms(build('trend').stages.tape.entries)).toEqual(['سپ']);
    expect(syms(build('custom').stages.tape.entries)).toEqual(['خار', 'سپ', 'شپنا', 'فولاد', 'همراه']);
  });

  it('الگویِ محلیِ «ساعت قوی» نماد را داخلِ قیف نمی‌آورد — فقط پنج فیلتر', () => {
    expect(syms(build('swing').stages.tape.entries)).not.toContain('قوی‌محلی');
  });

  it('تکنیکال: هفتگی داورِ اصلی است و نبودِ ستاپ دیگر گیت نیست', () => {
    const f = build();
    expect(f.stages.technical.entries).toHaveLength(f.stages.tape.entries.length);
    // همراه = وتوی هفتگی؛ سپ = هفتگی صعودی + روزانه خنثی، بدون نیاز به ستاپ
    expect(f.stages.technical.dropped).toBe(1);
    expect(markOf(f, 'technical', 'همراه')).toBe('reject');
    expect(markOf(f, 'technical', 'سپ')).toBe('pass');
    // خار تحلیل نشده: «سنجیده نشد» — وتو نیست
    expect(f.stages.technical.entries.find((e) => e.symbol === 'خار')?.status.technical).toBe('unavailable');
    expect(f.stages.technical.unmeasured).toBe(1);
    // فقط وتوی هفتگی به بنیادی نمی‌رسد؛ نمادِ بی‌ستاپ ولی دارای روند معتبر می‌رسد
    expect(syms(f.stages.fundamental.entries)).not.toContain('همراه');
    expect(syms(f.stages.fundamental.entries)).toContain('سپ');
  });

  it('رأیِ زندۀ /api/fts درِ تکنیکال را می‌بندد، حتی وقتی اسکرینر تحلیل نکرده', () => {
    const v = (over: Partial<TechVerdict>): TechVerdict => ({
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
    const verdicts = new Map<string, TechVerdict>([
      // «خار» ردیفِ اسکرینر ندارد؛ رأیِ زنده وتوی هفتگی می‌گوید
      ['خار', v({ decision: 'REJECT', trendW: 'down', matrixDesc: 'تایم هفتگی نزولی — وتوی کامل' })],
      ['شپنا', v({ jet: true })],
    ]);
    const f = buildFunnel(ROWS, DEFAULT_TAPE_FILTER_CONFIG, [], [], new Set(), 'custom', verdicts);
    const mark = (s: string) => f.stages.technical.entries.find((e) => e.symbol === s)?.status.technical;
    expect(mark('خار')).toBe('reject');
    expect(mark('شپنا')).toBe('pass');
    // بی‌منبع = «سنجیده نشد» (unavailable)، نه رد
    expect(mark('فولاد')).toBe('unavailable');
    expect(f.stages.technical.dropped).toBe(1);
    // وتوی تکنیکال به بنیادی نمی‌رسد، ولی بی‌رأی می‌رسد (بی‌داده وتو نیست)
    expect(syms(f.stages.fundamental.pending)).toContain('فولاد');
    expect(syms(f.stages.fundamental.pending)).not.toContain('خار');
  });

  it('شاخهٔ روزانه تعیین‌کنندهٔ متن و ستاپ‌ها فقط شواهدِ کمکی هستند', () => {
    const swing = build('swing').stages.technical.entries.find((e) => e.symbol === 'شپنا');
    expect(swing?.status.technical).toBe('pass');
    expect(swing?.trendW).toBe('up');
    expect(swing?.trendD).toBe('down');
    expect(swing?.why.technical).toContain('فیبو');
    const trend = build('trend').stages.technical.entries.find((e) => e.symbol === 'سپ');
    // «سپ» بدون ستاپِ سنجیده هم عبور می‌کند؛ چون هفتگی صعودی و روزانه خنثی
    // شاخهٔ معتبر چارت است. ستاپ‌ها فقط شواهد/امتیاز کمکی‌اند.
    expect(trend?.status.technical).toBe('pass');
    expect(trend?.trendW).toBe('up');
    expect(trend?.trendD).toBe('range');
    expect(trend?.techSource).toBe('screen');
  });

  it('امتیاز تکنیکال: روندها از ستاپ‌ها مهم‌ترند و ستاپ گیت نیست', () => {
    const f = build();
    const فولاد = f.stages.technical.entries.find((e) => e.symbol === 'فولاد');
    const شپنا = f.stages.technical.entries.find((e) => e.symbol === 'شپنا');
    const سپ = f.stages.technical.entries.find((e) => e.symbol === 'سپ');
    expect(فولاد?.technicalPoints).toBe(5); // weekly up + daily up + one setup
    expect(شپنا?.technicalPoints).toBe(4); // weekly up + daily down + one setup
    expect(سپ?.technicalPoints).toBe(3); // weekly up + daily range + no setup
  });

  it('بدونِ روندِ روزانهٔ معتبر، تکنیکال pending است و ستاپ جایِ روند را نمی‌گیرد', () => {
    const rows = [board({ symbol: 'ناقص', f_susp: true })];
    const screens = [screened('ناقص', 5, {
      tech_matrix_decision: 'PERMITTED',
      tech_trend_w: 'up',
      tech_trend_d: null,
      tech_jet: true,
      i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    })];
    const f = buildFunnel(rows, DEFAULT_TAPE_FILTER_CONFIG, [], screens, new Set(), 'custom');
    const e = f.stages.technical.entries.find((x) => x.symbol === 'ناقص');
    expect(e?.status.technical).toBe('pending');
    expect(e?.technicalPoints).toBeNull();
  });

  it('بنیادی: ردِ صریح می‌افتد، بی‌گزارش در صفِ خودش می‌ماند و به تحویل نمی‌رود', () => {
    const f = build();
    expect(f.stages.fundamental.dropped).toBe(1);
    expect(syms(f.stages.fundamental.entries)).toEqual(['سپ', 'فولاد']);
    expect(syms(f.stages.fundamental.pending)).toEqual(['خار']);
  });

  it('تحویل = بنیادِ قبول‌شدۀ بیرونِ سبد، و نشانه‌ها عینِ بجِ تابلویند', () => {
    const f = build();
    expect(syms(f.stages.handover.entries)).toEqual(['سپ', 'فولاد']);
    expect(f.stages.tape.entries.find((e) => e.symbol === 'فولاد')?.patterns).toEqual(['مشکوک']);
  });

  it('هر مرحلۀ ردیف‌هایش را با کلیدِ پایدارِ نماد می‌دهد (FLIP بی‌کلید، پرش دارد)', () => {
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );
    expect(useTapeStore.getState().quickFilters).toEqual([]);
    for (const k of ['tape', 'technical', 'fundamental', 'handover']) {
      expect(screen.getByTestId(`funnel-stage-${k}`)).toBeInTheDocument();
    }
    expect(document.querySelectorAll('[data-fkey]').length).toBeGreaterThan(0);
  });
});

describe('پیچ‌هایِ درِ بنیادی (حقِ انتخاب دستِ کاربر)', () => {
  const buildWith = (opts: Partial<FunnelOptions> = {}) =>
    buildFunnel(
      ROWS,
      DEFAULT_TAPE_FILTER_CONFIG,
      [],
      SCREEN,
      new Set<string>(),
      'custom',
      new Map(),
      { ...DEFAULT_FUNNEL_OPTIONS, ...opts },
    );

  it('پیش‌فرض عینِ جزوه است: کفِ سه و «سنجیده نشد» در صفِّ خودش', () => {
    expect(DEFAULT_FUNNEL_OPTIONS.fundFloor).toBe(3);
    expect(DEFAULT_FUNNEL_OPTIONS.unmeasured).toBe('hold');
    const f = buildWith();
    // شپنا نمرۀ ۲ دارد ⇒ زیرِ کفِ سه؛ خار بی‌ردیفِ اسکرینر است ⇒ صف
    expect(syms(f.stages.fundamental.entries)).toEqual(['سپ', 'فولاد']);
    expect(syms(f.stages.fundamental.pending)).toEqual(['خار']);
    expect(syms(f.stages.handover.entries)).toEqual(['سپ', 'فولاد']);
  });

  it('کفِ دو، ردیفِ نمره‌دو را رد نمی‌کند و کفِ پنج فقط نمره‌پنج را نگه می‌دارد', () => {
    expect(syms(buildWith({ fundFloor: 2 }).stages.fundamental.entries)).toEqual(['سپ', 'شپنا', 'فولاد']);
    expect(syms(buildWith({ fundFloor: 5 }).stages.fundamental.entries)).toEqual(['سپ', 'فولاد']);
    // علتِ رد هم کفِ دستِ کاربر را می‌گوید، نه «سه»ی ثابت
    const five = buildWith({ fundFloor: 5 });
    expect(five.stages.technical.entries.find((e) => e.symbol === 'شپنا')?.why.fundamental).toContain('کف');
  });

  it('«عبور با برچسب» سنجیده‌نشده را به تحویل می‌برد، «حذف» از قیف بیرونش می‌اندازد', () => {
    const pass = buildWith({ unmeasured: 'pass' });
    expect(syms(pass.stages.fundamental.entries)).toContain('خار');
    expect(pass.stages.fundamental.pending).toHaveLength(0);
    expect(syms(pass.stages.handover.entries)).toEqual(['خار', 'سپ', 'فولاد']);
    // برچسبِ «سنجیده نشد» رویِ خودش می‌ماند تا کاربر بداند بنیادش خوانده نشده
    expect(pass.stages.handover.entries.find((e) => e.symbol === 'خار')?.status.fundamental).toBe('unavailable');

    const drop = buildWith({ unmeasured: 'drop' });
    expect(drop.stages.fundamental.pending).toHaveLength(0);
    expect(syms(drop.stages.fundamental.entries)).toEqual(['سپ', 'فولاد']);
    // شپنا (ردِ صریح) + خار (حذف‌شدۀ سنجیده‌نشده) ⇒ دو افت
    expect(drop.stages.fundamental.dropped).toBe(2);
  });

  it('پیچ‌ها در همان نوارِ قیف دستکاری می‌شوند و به حالتِ جزوه برمی‌گردند', async () => {
    useFunnelPrefsStore.getState().reset();
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByTestId('funnel-floor-2'));
    expect(useFunnelPrefsStore.getState().fundFloor).toBe(2);
    fireEvent.click(screen.getByTestId('funnel-unmeasured-pass'));
    expect(useFunnelPrefsStore.getState().unmeasured).toBe('pass');
    // «بازگشت به جزوه» فقط وقتی بیرونِ جزوه هستیم پیدا است
    fireEvent.click(screen.getByTestId('funnel-prefs-reset'));
    expect(useFunnelPrefsStore.getState().fundFloor).toBe(3);
    expect(useFunnelPrefsStore.getState().unmeasured).toBe('hold');
    expect(screen.queryByTestId('funnel-prefs-reset')).not.toBeInTheDocument();
  });

  it('مرحلۀ خالی علتِ خالی‌بودنش را می‌گوید («به این در کسی نرسید» ≠ «همه رد شدند»)', () => {
    useFunnelPrefsStore.getState().reset();
    // تنها ردیفِ تابلویی که درِ نوسان‌گیر رد می‌شود «همراه» است (وتوی هفتگیِ
    // صریحِ موتور) ⇒ بنیادی هیچ رسیدۀ داوری‌شده‌ای ندارد و باید همین را بگوید.
    feedMock.rows = [board({ symbol: 'همراه', f_susp: true })];
    try {
      renderRouted(
        <QueryClientProvider client={new QueryClient()}>
          <FtsFunnelStages preset="swing" />
        </QueryClientProvider>,
      );
      const empty = screen.getByTestId('funnel-empty-fundamental');
      expect(empty.textContent).toContain('تکنیکال');
      expect(empty.textContent).toContain('۱ نماد');
      expect(screen.getByTestId('funnel-empty-handover').textContent).toContain('بنیادی');
    } finally {
      feedMock.rows = ROWS;
    }
  });
});

vi.mock('@features/market/api/useMarketFeed', () => ({
  useMarketFeed: () => ({ data: { data: feedMock.rows } }),
}));
vi.mock('@features/fundamental/api/useFtsScreen', () => ({
  useFtsScreen: () => ({ data: { data: screenMock.rows } }),
}));
vi.mock('@features/portfolio/api/usePortfolio', () => ({
  usePortfolio: () => ({ data: { portfolio: [{ symbol: 'همراه' }] } }),
  useMarketCloses: () => ({ data: new Map() }),
}));
vi.mock('@features/master/api/useFtsTechBoard', () => ({
  // خودِ سقفِ واقعی را می‌دهد تا صفِ بودجه درِ تست با صفِ برنامه یکی بماند
  TECH_QUERY_CAP: 60,
  useFtsTechBoard: (symbols: string[]) => ({
    map: new Map(),
    asOf: new Map<string, number>(),
    loading: false,
    wanted: Math.min(60, symbols.length),
    queued: symbols.length,
    beyondCap: Math.max(0, symbols.length - 60),
    resolved: 0,
  }),
}));

/**
 * مالک: «اول روند هفتگی، بعد روزانه؛ جت/پولبک و بقیۀ شاخه‌ها امتیاز مثبت باشند، نه گیت.»
 * دو چیزِ این‌جا تست می‌شود: سرستون‌هایِ جدا برایِ هر مرحله (تا پیش از این
 * چهار جدول یک سرستون مشترک داشتند)، و کلیدِ «خودم چک می‌کنم» که با
 * پیش‌فرضِ جزوه (غربال) خاموش است و ردشده‌ها را فقط برچسب می‌زند.
 */
describe('قیف: ستون‌هایِ خودِ هر مرحله + «تکنیکال را خودم چک می‌کنم»', () => {
  const buildWith = (opts: Partial<FunnelOptions> = {}) =>
    buildFunnel(
      ROWS,
      DEFAULT_TAPE_FILTER_CONFIG,
      [],
      SCREEN,
      new Set<string>(),
      'custom',
      new Map(),
      { ...DEFAULT_FUNNEL_OPTIONS, ...opts },
    );

  it('پیش‌فرضِ قیف: تکنیکال غربال می‌کند، اما فقط وتوی هفتگی را حذف می‌کند', () => {
    expect(DEFAULT_FUNNEL_OPTIONS.techScreens).toBe(true);
  });

  it('«رد نکند»: هیچ نمادی نمی‌افتد، ولی ردِّ تکنیکال رویش می‌ماند و به بنیادی می‌رسد', () => {
    const on = buildWith();
    expect(on.stages.technical.dropped).toBe(1);
    expect(syms(on.stages.fundamental.entries)).not.toContain('همراه');

    const off = buildWith({ techScreens: false });
    // هیچی حذف نشده، پس dropped صفر است؛ شمارِ رد خورده پنهان نمی‌شود
    expect(off.stages.technical.dropped).toBe(0);
    expect(off.stages.technical.rejected).toBe(1);
    // برچسب و دلیل سرِ جایشان‌اند تا کاربر بداند چرا این دو رد شده‌اند
    const hamrah = off.stages.technical.entries.find((e) => e.symbol === 'همراه');
    expect(hamrah?.status.technical).toBe('reject');
    expect(hamrah?.why.technical).toContain('روندِ هفتگی');
    // و به مرحلۀ بنیادی رسیده‌اند: آنجا خودشان داوری می‌شوند
    expect(syms(off.stages.fundamental.entries)).toEqual(['سپ', 'فولاد', 'همراه']);
    // (شپنا بنیادش رد است — نمرۀ ۲ زیرِ کفِ سه — پس از همین‌جا می‌افتد)
    expect(off.stages.fundamental.rejected).toBe(1);
  });

  it('روندِ دو زمانه از همان ردیفِ اسکرینر به ستون‌هایِ تکنیکال می‌رسد', () => {
    const f = buildWith({ techScreens: false });
    const t = (s: string) => f.stages.technical.entries.find((e) => e.symbol === s);
    expect(t('فولاد')?.trendW).toBe('up');
    expect(t('فولاد')?.trendD).toBe('up');
    expect(t('همراه')?.trendW).toBe('down');
    // خار ردیفِ اسکرینر ندارد ⇒ نه روندی، نه ستاپی؛ «سنجیده نشد» نه «رد»
    expect(t('خار')?.trendW).toBeNull();
    expect(t('خار')?.status.technical).toBe('unavailable');
    expect(t('فولاد')?.setups).toContain('جت');
  });

  it('پنج شاخص یکی‌یکی در ستون‌هایِ خودِ مرحلۀ بنیادی، با عددِ همان شاخص', () => {
    const f = buildWith({ techScreens: false });
    const e = f.stages.fundamental.entries.find((x) => x.symbol === 'فولاد');
    expect(e?.inds).toEqual(['pass', 'pass', 'pass', 'pass', 'pass']);
    // شپنا در بنیادی رد می‌شود، پس ردیفش را از مرحلۀ تکنیکال می‌خوانیم
    const sh = f.stages.technical.entries.find((x) => x.symbol === 'شپنا');
    expect(sh?.inds).toEqual(['reject', 'pending', 'reject', 'pass', 'pass']);
    // خار هیچ ردیفِ اسکرینری ندارد ⇒ پنج «na»، نه پنج «no»
    expect(f.stages.technical.entries.find((x) => x.symbol === 'خار')?.inds)
      .toEqual(['pending', 'pending', 'pending', 'pending', 'pending']);
  });

  it('عددِ هر شاخص با جداکنندهٔ هزارگان و به زبانِ خودِ جدول می‌آید (free ⇒ آزاد)', () => {
    // دو نقصِ دیدنی رویِ دادهٔ زنده: رشد فروشِ میلیاردی بی‌جداکننده خوانده
    // نمی‌شد، و نرخ‌گذاری با واژگانِ بک‌اند («free») به کاربر نشان داده می‌شد.
    useFunnelPrefsStore.getState().reset();
    screenMock.rows = [screened('بزرگ', 5, {
      tech_matrix_decision: 'PERMITTED', tech_trend_w: 'up', tech_jet: true,
      i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
      rev_growth: 3885990000, eps_last: -342895, gross_margin: 26, sales_to_mcap: 0.41,
      pricing_mode: 'free',
    })];
    feedMock.rows = [board({ symbol: 'بزرگ', f_susp: true })];
    try {
      renderRouted(
        <QueryClientProvider client={new QueryClient()}>
          <FtsFunnelStages preset="custom" />
        </QueryClientProvider>,
      );
      const stage = screen.getByTestId('funnel-stage-fundamental');
      const row = stage.querySelector('tbody tr[data-fkey="بزرگ"]');
      const text = row?.textContent ?? '';
      expect(text).toContain('۳٬۸۸۵٬۹۹۰٬۰۰۰٪');
      expect(text).toContain('آزاد');
      expect(text).not.toContain('free');
      expect(text).toContain('✓');
      // عددِ غیرمعقول همان هشدارِ جدولِ غربالگری را می‌گیرد، نه حذفِ عدد
      expect(text).toContain('⚠');
      expect(row?.querySelector('td[title*="غیرمعقول"]')).not.toBeNull();
    } finally {
      screenMock.rows = SCREEN;
      feedMock.rows = ROWS;
    }
  });

  it('نرخ‌گذاریِ «سایر صنایع» به فارسی می‌آید (۴۰۴ شرکت از ۸۷۳ neutral‌اند)', () => {
    useFunnelPrefsStore.getState().reset();
    screenMock.rows = [screened('خنثی‌صنعت', 5, {
      tech_matrix_decision: 'PERMITTED', tech_trend_w: 'up', tech_jet: true,
      i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
      rev_growth: 52, eps_last: 318, gross_margin: 26, sales_to_mcap: 0.41,
      pricing_mode: 'neutral',
    })];
    feedMock.rows = [board({ symbol: 'خنثی‌صنعت', f_susp: true })];
    try {
      renderRouted(
        <QueryClientProvider client={new QueryClient()}>
          <FtsFunnelStages preset="custom" />
        </QueryClientProvider>,
      );
      const row = screen
        .getByTestId('funnel-stage-fundamental')
        .querySelector('tbody tr[data-fkey="خنثی‌صنعت"]');
      const text = row?.textContent ?? '';
      expect(text).toContain('سایر صنایع');
      expect(text).not.toContain('neutral');
    } finally {
      screenMock.rows = SCREEN;
      feedMock.rows = ROWS;
    }
  });

  it('سرستون‌ها دیگر یکسان نیستند: تکنیکال هفتگی/روزانه/ستاپ دارد، تابلو ندارد', () => {    useFunnelPrefsStore.getState().reset();
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );
    const tech = within(screen.getByTestId('funnel-stage-technical'));
    for (const h of ['هفتگی', 'روزانه', 'شواهد', 'امتیاز', 'داوری']) {
      expect(tech.getByRole('columnheader', { name: h })).toBeInTheDocument();
    }
    expect(tech.queryByRole('columnheader', { name: 'حجم/ماه' })).not.toBeInTheDocument();

    const tape = within(screen.getByTestId('funnel-stage-tape'));
    expect(tape.getByRole('columnheader', { name: 'نشانه' })).toBeInTheDocument();
    expect(tape.queryByRole('columnheader', { name: 'هفتگی' })).not.toBeInTheDocument();

    const fund = within(screen.getByTestId('funnel-stage-fundamental'));
    for (const c of IND_COLUMNS) {
      // سرستون از همان IND_COLUMNS می‌آید، نه از متنِ دومی در UI — پس تست هم
      // از همان منبع می‌خواند (یک جای واحد برای نامِ هر شاخص).
      expect(fund.getAllByRole('columnheader', { name: c.label }).length).toBeGreaterThan(0);
    }
  });

  it('روندِ هفتگی در جدولِ تکنیکال به زبانِ خودِ چارت نوشته می‌شود (نزولی، نه null)', () => {
    useFunnelPrefsStore.getState().reset();
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );
    const row = screen.getByTestId('funnel-stage-technical').querySelector('[data-fkey="همراه"]');
    expect(row?.textContent).toContain('نزولی');
    expect(row?.textContent).toContain('رد');
  });

  it('کلیدِ درِ تکنیکال کنارِ همان مرحله است، با پیش‌فرضِ جزوه، و برگشت دارد', () => {
    useFunnelPrefsStore.getState().reset();
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );
    expect(useFunnelPrefsStore.getState().techScreens).toBe(true);
    expect(screen.queryByTestId('funnel-rejected-technical')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('funnel-tech-selfcheck'));
    expect(useFunnelPrefsStore.getState().techScreens).toBe(false);
    // حالا ردشده‌ها در جدول‌اند و شمارِ «رد (بی‌حذف)» پیدا می‌شود
    expect(screen.getByTestId('funnel-rejected-technical').textContent).toContain('۱');
    expect(screen.getByTestId('funnel-tech-selfcheck')).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByTestId('funnel-tech-screens'));
    expect(useFunnelPrefsStore.getState().techScreens).toBe(true);
    expect(screen.queryByTestId('funnel-rejected-technical')).not.toBeInTheDocument();
    // «بازگشت به جزوه» با همین پیچ هم بیرون از جزوه می‌آید
    fireEvent.click(screen.getByTestId('funnel-tech-selfcheck'));
    fireEvent.click(screen.getByTestId('funnel-prefs-reset'));
    expect(useFunnelPrefsStore.getState().techScreens).toBe(true);
  });
});

/**
 * مالک پرسید «چرا برای قیف غربالگری انتخاب استراتژی‌ها حذف شد؟» — بعد از
 * جابه‌جاییِ قیف به تبِ «استراتژی FTS»، دربِ قیف از استورِ افق خوانده می‌شد ولی
 * کلیدش درِ جایِ دیگری (داوریِ نماد) بود. پس قیف باید خودش انتخاب کند.
 */
describe('دربِ قیف: انتخابِ استراتژی رویِ خودِ قیف', () => {
  const renderFunnel = (props: Parameters<typeof FtsFunnelStages>[0]) =>
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages {...props} />
      </QueryClientProvider>,
    );

  it('بی‌onPresetChange هیچ کلیدی رسم نمی‌شود (قیفِ ایستا کلیدِ مرده ندارد)', () => {
    renderFunnel({ preset: 'swing' });
    expect(screen.queryByTestId('funnel-preset-picker')).not.toBeInTheDocument();
  });

  it('سه دربِ جزوه‌ای هست و همان که والد داده پریده است', () => {
    renderFunnel({ preset: 'swing', onPresetChange: () => {} });
    for (const p of ['swing', 'trend', 'hourglass']) {
      expect(screen.getByTestId(`funnel-preset-${p}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId('funnel-preset-swing')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('funnel-preset-trend')).toHaveAttribute('aria-pressed', 'false');
  });

  it('کلیک رویِ روندگیر، همان نام را به والد می‌دهد (دربِ واقعی درِ استورِ افق است)', () => {
    const seen: string[] = [];
    renderFunnel({ preset: 'swing', onPresetChange: (p) => seen.push(p) });
    fireEvent.click(screen.getByTestId('funnel-preset-trend'));
    fireEvent.click(screen.getByTestId('funnel-preset-hourglass'));
    expect(seen).toEqual(['trend', 'hourglass']);
  });

  it('عنوانِ هر درب، ورودیِ پنج‌فیلترهٔ خودش را می‌گوید تا «درب» مبهم نماند', () => {
    renderFunnel({ preset: 'swing', onPresetChange: () => {} });
    expect(screen.getByTestId('funnel-preset-trend').getAttribute('title')).toContain('روندگیر');
  });
});

/**
 * رأیِ مالک: «بغل نماد برچسب داده بشه که … مجمع عمومی داره هشدار داده بشه و
 * اینکه وتو بخوره». داوریِ وتو در بک‌اند است (`assembly_veto` در /api/screener)
 * و قیف فقط همان پرچم را می‌خواند — فرمولِ دومی در فرانت نیست.
 * جای وتو مرحلۀ تحویل است نه بنیادی: مجمع ضعفِ بنیادی نیست، زمان‌بندیِ ورود است.
 */
describe('وتوی مجمع: زمان‌بندیِ ورود، نه ضعفِ بنیادی', () => {
  const okScreen = (sym: string, over: Partial<FtsScreenRow> = {}): FtsScreenRow =>
    screened(sym, 5, {
      tech_matrix_decision: 'PERMITTED', tech_trend_w: 'up', tech_trend_d: 'up', tech_jet: true,
      i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
      rev_growth: 52, eps_last: 318, gross_margin: 26, sales_to_mcap: 0.41, ...over,
    });

  const SYM = 'مجمع‌دار';
  const run = (over: Partial<FtsScreenRow> = {}) =>
    buildFunnel(
      [board({ symbol: SYM, f_susp: true })],
      DEFAULT_TAPE_FILTER_CONFIG,
      [],
      [okScreen(SYM, over)],
      new Set<string>(),
      'custom',
    );
  const first = (f: ReturnType<typeof run>, k: 'tape' | 'handover' | 'fundamental') =>
    f.stages[k].entries[0];

  it('نمرۀ پنج با مجمعِ سه روز دیگر ⇒ بنیادی قبول، تحویل خالی', () => {
    const f = run({ assembly_veto: true, assembly_days: 3, assembly_date: '2026-10-02' });
    expect(syms(f.stages.fundamental.entries)).toEqual([SYM]);
    // وتو نمره را کم نمی‌کند: داوریِ پنج‌شاخصه دست‌نخورده می‌ماند
    expect(first(f, 'fundamental').inds).toEqual(['pass', 'pass', 'pass', 'pass', 'pass']);
    expect(first(f, 'fundamental').status.fundamental).toBe('pass');
    expect(f.stages.handover.entries).toHaveLength(0);
    expect(f.stages.handover.dropped).toBe(1);
    // وتوی مجمع توقفِ زمانبندی است، نه ردِ کیفی: درِ `pending` می‌نشیند (#15)
    expect(f.stages.handover.rejected).toBe(0);
    expect(f.stages.handover.pending.map((e) => e.symbol)).toEqual([SYM]);
  });

  it('کنترلِ منفی: بی‌پرچم همان نماد به تحویل می‌رسد', () => {
    const f = run();
    expect(syms(f.stages.handover.entries)).toEqual([SYM]);
    expect(f.stages.handover.dropped).toBe(0);
  });

  it('نمادی که هم در سبد است هم مجمع: تحویل را «وتوی مجمع» نخور', () => {
    // handover = passed ∧ ¬سبد ∧ ¬وتو؛ پس شمارِ «ردشده به‌خاطرِ مجمع» باید فقط
    // آن‌هایی باشد که جز‌و‌بد بدونِ مجمع به تحویل می‌رسیدند. بی‌این شرط، عددِ
    // ردِ مرحلۀ تحویل با نمادهایِ ازپیش‌خریداریشه‌شده تورم می‌خورد.
    const f = buildFunnel(
      [board({ symbol: SYM, f_susp: true })],
      DEFAULT_TAPE_FILTER_CONFIG,
      [],
      [okScreen(SYM, { assembly_veto: true, assembly_days: 3 })],
      new Set<string>([SYM]),
      'custom',
    );
    expect(f.stages.handover.entries).toHaveLength(0);
    // `dropped` = هرچه به تحویل نرسید (سبد یا مجمع)؛ تضمینِ ضدِّ تورم درِ
    // `rejected` و درِ *علت* است: علتِ توقفِ این نماد «سبد» است نه «مجمع».
    expect(f.stages.handover.dropped).toBe(1);
    expect(f.stages.handover.rejected).toBe(0);
    expect(f.stages.handover.pending[0].why.handover).toContain('سبد');
    expect(f.stages.handover.pending[0].why.handover).not.toContain('مجمع');
  });

  it('بی‌داده وتو نیست: پرچمِ غایب یا false یا فقط assembly_days هیچ وتویی نمی‌سازد', () => {
    for (const over of [{}, { assembly_veto: false }, { assembly_days: 3 }, { assembly_veto: null }]) {
      const f = run(over as Partial<FtsScreenRow>);
      expect(first(f, 'tape').assemblyVeto).toBe(false);
      expect(syms(f.stages.handover.entries)).toEqual([SYM]);
    }
  });

  it('علتِ وتو از همان ردیف خوانده می‌شود و امروز «۰ روز» نمی‌گیرد', () => {
    const three = first(run({ assembly_veto: true, assembly_days: 3 }), 'tape');
    expect(three.assemblyVeto).toBe(true);
    expect(three.assemblyWhy).toContain('۳ روز تا مجمع عمومی');
    const today = first(run({ assembly_veto: true, assembly_days: 0 }), 'tape');
    expect(today.assemblyWhy).toContain('امروز مجمع عمومی دارد');
    expect(today.assemblyWhy).not.toContain('۰ روز');
    // بی‌شمارِ روز هم وتو می‌ماند، فقط دلیلش کوتاه‌تر
    expect(first(run({ assembly_veto: true }), 'tape').assemblyVeto).toBe(true);
  });

  it('برچسبِ قرمز در هر سه مرحله پیدا است — نماد فقط در تحویل گم می‌شود', () => {
    useFunnelPrefsStore.getState().reset();
    screenMock.rows = [okScreen(SYM, { assembly_veto: true, assembly_days: 3 })];
    feedMock.rows = [board({ symbol: SYM, f_susp: true })];
    try {
      renderRouted(
        <QueryClientProvider client={new QueryClient()}>
          <FtsFunnelStages preset="custom" />
        </QueryClientProvider>,
      );
      for (const k of ['tape', 'technical', 'fundamental']) {
        const chip = screen
          .getByTestId(`funnel-stage-${k}`)
          .querySelector(`[data-testid="funnel-assembly-veto-${SYM}"]`);
        expect(chip, `مرحلهٔ ${k}`).not.toBeNull();
        expect(chip?.textContent).toBe('وتوی مجمع');
      }
      // جدولِ اصلیِ تحویل خالی است (نماد تحویل داده نمی‌شود)…
      expect(screen.getByTestId('funnel-empty-handover')).toBeInTheDocument();
      // …ولی «گم» نمی‌شود: در گروهِ متوقفانِ همین در، با علتِ مجمع دیده می‌شود.
      const held = screen.getByTestId('funnel-pending-handover');
      expect(held.textContent).toContain('متوقف درِ تحویل');
      expect(held.querySelector(`[data-testid="funnel-assembly-veto-${SYM}"]`)).not.toBeNull();
    } finally {
      screenMock.rows = SCREEN;
      feedMock.rows = ROWS;
    }
  });

  it('تحویلِ خالی از وتوی مجمع می‌گوید، نه «بنیادی کسی را قبول نکرد»', () => {
    useFunnelPrefsStore.getState().reset();
    screenMock.rows = [okScreen(SYM, { assembly_veto: true, assembly_days: 3 })];
    feedMock.rows = [board({ symbol: SYM, f_susp: true })];
    try {
      renderRouted(
        <QueryClientProvider client={new QueryClient()}>
          <FtsFunnelStages preset="custom" />
        </QueryClientProvider>,
      );
      const why = screen.getByTestId('funnel-empty-handover');
      expect(why.textContent).toContain('مجمع');
      expect(why.textContent).toContain('۱ نماد');
      expect(why.textContent).not.toContain('بنیادی کسی را قبول نکرد');
      // قاعدۀ خودِ مرحله هم وتوی مجمع را می‌گوید تا «چرا خالی است» مبهم نماند
      expect(screen.getByTestId('funnel-stage-handover').textContent).toContain('وتوی مجمع');
    } finally {
      screenMock.rows = SCREEN;
      feedMock.rows = ROWS;
    }
  });
});

/**
 * مالک: «تنظیماتِ مرحلۀ بنیادی رو روی نوارِ جدول بنیادی بذار و برای بقیۀ
 * جدول‌ها هم روی نوارشون تنظیماتی بذار که کاربر روش و نحوۀ غربالگری رو انتخاب
 * کنه». پس جایِ هر پیچ، نوارِ خودِ همان مرحله است — نه یک نوارِ سراسری که
 * کاربر نفهمد به کدام در می‌خورد.
 */
describe('پیچ‌ها رویِ نوارِ خودِ هر مرحله', () => {
  const renderStages = () => {
    useFunnelPrefsStore.getState().reset();
    useTapeStore.setState({ quickFilters: [] });
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages preset="custom" />
      </QueryClientProvider>,
    );
  };
  const ownerSection = (id: string) =>
    screen.getByTestId(id).closest('section')?.getAttribute('data-testid');

  it('پیچ‌هایِ بنیادی داخلِ همان مرحلۀ بنیادی‌اند، نه در نوارِ سراسری', () => {
    renderStages();
    expect(ownerSection('funnel-prefs')).toBe('funnel-stage-fundamental');
    expect(screen.getAllByTestId('funnel-prefs')).toHaveLength(1);
    // کلیک از رویِ همان نوار واقعاً به استور می‌نشیند (سیم زنده است، نه تزئینی)؛
    // اینکه خودِ استور مرحلۀ بنیادی را عوض می‌کند در «پیچ‌هایِ درِ بنیادی» سنجیده شده.
    fireEvent.click(screen.getByTestId('funnel-floor-5'));
    expect(useFunnelPrefsStore.getState().fundFloor).toBe(5);
    expect(screen.getByTestId('funnel-floor-5')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('funnel-prefs').textContent).toContain('عبور با این پیچ‌ها');
  });

  it('مرحلۀ تابلو چیپ‌هایِ پنج‌فیلترهٔ خودش را رویِ نوارش دارد و ورودیِ قیف را تغییر می‌دهد', () => {
    renderStages();
    expect(ownerSection('funnel-tape-prefs')).toBe('funnel-stage-tape');
    // بی‌هیچ چیپی ورودی از دربِ سبک می‌آید؛ با «الگوی ساعت» فقط ردیف‌هایِ ساعت‌دار
    const before = screen.getByTestId('funnel-stage-tape').querySelectorAll('tbody tr').length;
    fireEvent.click(screen.getByTestId('funnel-tape-chip-f_clock'));
    expect(useTapeStore.getState().quickFilters).toEqual(['f_clock']);
    const after = screen.getByTestId('funnel-stage-tape').querySelectorAll('tbody tr').length;
    expect(after).toBeLessThan(before);
    expect(after).toBeGreaterThan(0);
    expect(screen.getByTestId('funnel-tape-chip-f_clock')).toHaveAttribute('aria-pressed', 'true');
  });

  it('کلیدِ تکنیکال همان‌جا مانده است (الگویِ همین تقسیم، نه چیزِ تازه)', () => {
    renderStages();
    expect(ownerSection('funnel-tech-gate')).toBe('funnel-stage-technical');
  });
});

describe('قیف: snapshotِ بازگشت (Task #78 — stage/scroll پس از Back)', () => {
  const SNAP_KEY = 'bors.funnel.snapshot.v1';
  const renderSnap = () =>
    renderRouted(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );

  it('کلیک روی سطر، مرحلۀ فعال را پیش از رفتن به Master ثبت می‌کند', () => {
    sessionStorage.clear();
    useFunnelPrefsStore.getState().reset();
    renderSnap();
    const tr = screen.getByTestId('funnel-stage-tape').querySelector('tbody tr');
    fireEvent.click(tr!.querySelector('button')!);
    const snap = JSON.parse(sessionStorage.getItem(SNAP_KEY) ?? '{}');
    expect(snap.stage).toBe('tape');
    expect(typeof snap.scroll).toBe('number');
  });

  it('تبِ قیف فقط هایلایت نیست — کارتِ همان مرحله را به دید می‌آورد (UX Round 79)', () => {
    sessionStorage.clear();
    const spy = vi.fn();
    Element.prototype.scrollIntoView = spy;
    useFunnelPrefsStore.getState().reset();
    renderSnap();
    fireEvent.click(screen.getByTestId('funnel-step-technical'));
    expect(screen.getByTestId('funnel-step-technical')).toHaveAttribute('aria-selected', 'true');
    expect(spy).toHaveBeenCalled();
  });

  it('snapshotِ ذخیره‌شده، تبِ مرحلۀ قیف را پس از بازگشت برمی‌گرداند', () => {
    useFunnelPrefsStore.getState().reset();
    sessionStorage.setItem(SNAP_KEY, JSON.stringify({ stage: 'fundamental', scroll: 0 }));
    renderSnap();
    expect(screen.getByTestId('funnel-step-fundamental')).toHaveAttribute('aria-selected', 'true');
    sessionStorage.clear();
  });
});
