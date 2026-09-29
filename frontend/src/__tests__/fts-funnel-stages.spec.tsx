// __tests__/fts-funnel-stages.spec.tsx -- منطقِ قیف: کجا کم می‌شود و کجا نباید بشود
//
// سه رأیِ این قیف درِ تست می‌نشینند، چون هر سه «سکوت» می‌کنند اگر نشکنند:
//   1) تکنیکال غربال می‌کند (رأیِ تازهٔ مالک، جای رأیِ 1405-07-07): وتوی هفتگی
//      و نبودِ ستاپِ همان سبک نماد را بیرون می‌اندازد.
//   2) بی‌داده وتو نیست: ردیفی که اسکرینر تحلیلش نکرده «سنجیده نشد» است و به
//      دورِ ریخته‌ها نمی‌رود.
//   3) ورودیِ قیف خودِ پنج فیلتر است، نه الگوهایِ محلی — «ساعت قوی» نماد را
//      داخلِ قیف نمی‌آورد، چون فیلترنویسِ سایت آن را نمی‌شناسد.
import { render, screen, fireEvent, within } from '@testing-library/react';
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
  f.stages[key].entries.find((e) => e.symbol === sym)?.tech;

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

  it('تکنیکال غربال می‌کند: وتوی هفتگی و نبودِ ستاپ بیرون می‌افتند، بی‌داده نه', () => {
    const f = build();
    expect(f.stages.technical.entries).toHaveLength(f.stages.tape.entries.length);
    // همراه = وتوی هفتگی، سپ = هفتگی صعودی بی‌ستاپ
    expect(f.stages.technical.dropped).toBe(2);
    expect(markOf(f, 'technical', 'همراه')).toBe('no');
    expect(markOf(f, 'technical', 'سپ')).toBe('no');
    // خار تحلیل نشده: «سنجیده نشد» — وتو نیست
    expect(f.stages.technical.entries.find((e) => e.symbol === 'خار')?.tech).toBe('na');
    expect(f.stages.technical.unmeasured).toBe(1);
    // هیچ‌کدام از دو ردِ تکنیکال به بنیادی نمی‌رسند
    expect(syms(f.stages.fundamental.entries)).not.toContain('همراه');
    expect(syms(f.stages.fundamental.entries)).not.toContain('سپ');
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
      ...over,
    });
    const verdicts = new Map<string, TechVerdict>([
      // «خار» ردیفِ اسکرینر ندارد؛ رأیِ زنده وتوی هفتگی می‌گوید
      ['خار', v({ decision: 'REJECT', trendW: 'down', matrixDesc: 'تایم هفتگی نزولی — وتوی کامل' })],
      ['شپنا', v({ jet: true })],
    ]);
    const f = buildFunnel(ROWS, DEFAULT_TAPE_FILTER_CONFIG, [], [], new Set(), 'custom', verdicts);
    const mark = (s: string) => f.stages.technical.entries.find((e) => e.symbol === s)?.tech;
    expect(mark('خار')).toBe('no');
    expect(mark('شپنا')).toBe('ok');
    // بی‌رأی = «سنجیده نشد»، نه رد
    expect(mark('فولاد')).toBe('na');
    expect(f.stages.technical.dropped).toBe(1);
    // وتوی تکنیکال به بنیادی نمی‌رسد، ولی بی‌رأی می‌رسد (بی‌داده وتو نیست)
    expect(syms(f.stages.fundamental.pending)).toContain('فولاد');
    expect(syms(f.stages.fundamental.pending)).not.toContain('خار');
  });

  it('ستاپِ پذیرفتنی از سبک می‌آید: فیبوی 61.8-70 برای نوسان‌گیر ستاپ نیست، برای روندگیر هست', () => {
    const swing = build('swing').stages.technical.entries.find((e) => e.symbol === 'شپنا');
    expect(swing?.tech).toBe('no');
    expect(swing?.techWhy).toContain('ستاپ');
    const trend = build('trend').stages.technical.entries.find((e) => e.symbol === 'سپ');
    // «سپ» بی‌ستاپ است، پس در روندگیر هم رد می‌شود — سبک فقط آستانه را عوض می‌کند
    expect(trend?.tech).toBe('no');
  });

  it('بنیادی: ردِ صریح می‌افتد، بی‌گزارش در صفِ خودش می‌ماند و به تحویل نمی‌رود', () => {
    const f = build();
    expect(f.stages.fundamental.dropped).toBe(1);
    expect(syms(f.stages.fundamental.entries)).toEqual(['فولاد']);
    expect(syms(f.stages.fundamental.pending)).toEqual(['خار']);
  });

  it('تحویل = بنیادِ قبول‌شدۀ بیرونِ سبد، و نشانه‌ها عینِ بجِ تابلویند', () => {
    const f = build();
    expect(syms(f.stages.handover.entries)).toEqual(['فولاد']);
    expect(f.stages.tape.entries.find((e) => e.symbol === 'فولاد')?.patterns).toEqual(['مشکوک']);
  });

  it('هر مرحلۀ ردیف‌هایش را با کلیدِ پایدارِ نماد می‌دهد (FLIP بی‌کلید، پرش دارد)', () => {
    render(
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
    expect(syms(f.stages.fundamental.entries)).toEqual(['فولاد']);
    expect(syms(f.stages.fundamental.pending)).toEqual(['خار']);
    expect(syms(f.stages.handover.entries)).toEqual(['فولاد']);
  });

  it('کفِ دو، ردیفِ نمره‌دو را رد نمی‌کند و کفِ پنج فقط نمره‌پنج را نگه می‌دارد', () => {
    expect(syms(buildWith({ fundFloor: 2 }).stages.fundamental.entries)).toEqual(['شپنا', 'فولاد']);
    expect(syms(buildWith({ fundFloor: 5 }).stages.fundamental.entries)).toEqual(['فولاد']);
    // علتِ رد هم کفِ دستِ کاربر را می‌گوید، نه «سه»ی ثابت
    const five = buildWith({ fundFloor: 5 });
    expect(five.stages.technical.entries.find((e) => e.symbol === 'شپنا')?.fundWhy).toContain('کف');
  });

  it('«عبور با برچسب» سنجیده‌نشده را به تحویل می‌برد، «حذف» از قیف بیرونش می‌اندازد', () => {
    const pass = buildWith({ unmeasured: 'pass' });
    expect(syms(pass.stages.fundamental.entries)).toContain('خار');
    expect(pass.stages.fundamental.pending).toHaveLength(0);
    expect(syms(pass.stages.handover.entries)).toEqual(['خار', 'فولاد']);
    // برچسبِ «سنجیده نشد» رویِ خودش می‌ماند تا کاربر بداند بنیادش خوانده نشده
    expect(pass.stages.handover.entries.find((e) => e.symbol === 'خار')?.fund).toBe('na');

    const drop = buildWith({ unmeasured: 'drop' });
    expect(drop.stages.fundamental.pending).toHaveLength(0);
    expect(syms(drop.stages.fundamental.entries)).toEqual(['فولاد']);
    // شپنا (ردِ صریح) + خار (حذف‌شدۀ سنجیده‌نشده) ⇒ دو افت
    expect(drop.stages.fundamental.dropped).toBe(2);
  });

  it('پیچ‌ها در همان نوارِ قیف دستکاری می‌شوند و به حالتِ جزوه برمی‌گردند', async () => {
    useFunnelPrefsStore.getState().reset();
    render(
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
    render(
      <QueryClientProvider client={new QueryClient()}>
        {/* روندگیر با کف‌روبی+نقطه‌زنی باز می‌شود و «سپ» تنها ردیفِ آن است؛
            او وتوی تکنیکال می‌گیرد ⇒ بنیادی خالی، ولی بی‌هیچ رسیدۀ رد شده. */}
        <FtsFunnelStages preset="trend" />
      </QueryClientProvider>,
    );
    const empty = screen.getByTestId('funnel-empty-fundamental');
    expect(empty.textContent).toContain('تکنیکال');
    expect(screen.getByTestId('funnel-empty-handover').textContent).toContain('بنیادی');
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
  useFtsTechBoard: () => ({ map: new Map(), loading: false, wanted: 0, resolved: 0 }),
}));

/**
 * مالک: «هر بخش باید ستونِ مربوط به خودش را داشته باشد، مثلا تکنیکال هفتگی
 * صعودیه یا نزولی … یکاری هم بکن که تکنیکال رد نشن تا به بنیادی برسن».
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

  it('پیش‌فرضِ جزوه: تکنیکال غربال می‌کند (رأیِ ملغی‌شدۀ «فقط نشانه» برگشته نیست)', () => {
    expect(DEFAULT_FUNNEL_OPTIONS.techScreens).toBe(true);
  });

  it('«رد نکند»: هیچ نمادی نمی‌افتد، ولی ردِّ تکنیکال رویش می‌ماند و به بنیادی می‌رسد', () => {
    const on = buildWith();
    expect(on.stages.technical.dropped).toBe(2);
    expect(syms(on.stages.fundamental.entries)).not.toContain('همراه');

    const off = buildWith({ techScreens: false });
    // هیچی حذف نشده، پس dropped صفر است؛ شمارِ رد خورده پنهان نمی‌شود
    expect(off.stages.technical.dropped).toBe(0);
    expect(off.stages.technical.rejected).toBe(2);
    // برچسب و دلیل سرِ جایشان‌اند تا کاربر بداند چرا این دو رد شده‌اند
    const hamrah = off.stages.technical.entries.find((e) => e.symbol === 'همراه');
    expect(hamrah?.tech).toBe('no');
    expect(hamrah?.techWhy).toContain('وتوی هفتگی');
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
    expect(t('خار')?.tech).toBe('na');
    expect(t('فولاد')?.setups).toContain('جت');
  });

  it('پنج شاخص یکی‌یکی در ستون‌هایِ خودِ مرحلۀ بنیادی، با عددِ همان شاخص', () => {
    const f = buildWith({ techScreens: false });
    const e = f.stages.fundamental.entries.find((x) => x.symbol === 'فولاد');
    expect(e?.inds).toEqual(['ok', 'ok', 'ok', 'ok', 'ok']);
    // شپنا در بنیادی رد می‌شود، پس ردیفش را از مرحلۀ تکنیکال می‌خوانیم
    const sh = f.stages.technical.entries.find((x) => x.symbol === 'شپنا');
    expect(sh?.inds).toEqual(['no', 'na', 'no', 'ok', 'ok']);
    // خار هیچ ردیفِ اسکرینری ندارد ⇒ پنج «na»، نه پنج «no»
    expect(f.stages.technical.entries.find((x) => x.symbol === 'خار')?.inds)
      .toEqual(['na', 'na', 'na', 'na', 'na']);
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
      render(
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
    } finally {
      screenMock.rows = SCREEN;
      feedMock.rows = ROWS;
    }
  });

  it('سرستون‌ها دیگر یکسان نیستند: تکنیکال هفتگی/روزانه/ستاپ دارد، تابلو ندارد', () => {    useFunnelPrefsStore.getState().reset();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );
    const tech = within(screen.getByTestId('funnel-stage-technical'));
    for (const h of ['هفتگی', 'روزانه', 'ستاپ', 'داوری']) {
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
    render(
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
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FtsFunnelStages />
      </QueryClientProvider>,
    );
    expect(useFunnelPrefsStore.getState().techScreens).toBe(true);
    expect(screen.queryByTestId('funnel-rejected-technical')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('funnel-tech-selfcheck'));
    expect(useFunnelPrefsStore.getState().techScreens).toBe(false);
    // حالا ردشده‌ها در جدول‌اند و شمارِ «رد (بی‌حذف)» پیدا می‌شود
    expect(screen.getByTestId('funnel-rejected-technical').textContent).toContain('۲');
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
    render(
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
