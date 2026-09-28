// __tests__/fts-funnel-stages.spec.tsx -- منطقِ قیف: کجا کم می‌شود و کجا نباید بشود
//
// سه رأیِ این قیف درِ تست می‌نشینند، چون هر سه «سکوت» می‌کنند اگر نشکنند:
//   1) تکنیکال غربال می‌کند (رأیِ تازهٔ مالک، جای رأیِ 1405-07-07): وتوی هفتگی
//      و نبودِ ستاپِ همان سبک نماد را بیرون می‌اندازد.
//   2) بی‌داده وتو نیست: ردیفی که اسکرینر تحلیلش نکرده «سنجیده نشد» است و به
//      دورِ ریخته‌ها نمی‌رود.
//   3) ورودیِ قیف خودِ پنج فیلتر است، نه الگوهایِ محلی — «ساعت قوی» نماد را
//      داخلِ قیف نمی‌آورد، چون فیلترنویسِ سایت آن را نمی‌شناسد.
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { MarketRow } from '@shared/types/marketRow';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { buildFunnel, type TreePreset } from '@features/master/lib/ftsFunnel';
import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
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
  screened('فولاد', 5, { tech_matrix_decision: 'PERMITTED', tech_trend_w: 'up', tech_jet: true }),
  screened('شپنا', 2, {
    tech_matrix_decision: 'PERMITTED',
    tech_trend_w: 'up',
    tech_fib_zone: '61.8-70',
  }),
  screened('سپ', 4, { tech_matrix_decision: 'PERMITTED', tech_trend_w: 'up' }),
  screened('همراه', 4, { tech_matrix_decision: 'REJECT', weekly_veto: true, tech_trend_w: 'down' }),
];

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

vi.mock('@features/market/api/useMarketFeed', () => ({
  useMarketFeed: () => ({ data: { data: ROWS } }),
}));
vi.mock('@features/fundamental/api/useFtsScreen', () => ({
  useFtsScreen: () => ({ data: { data: SCREEN } }),
}));
vi.mock('@features/portfolio/api/usePortfolio', () => ({
  usePortfolio: () => ({ data: { portfolio: [{ symbol: 'همراه' }] } }),
  useMarketCloses: () => ({ data: new Map() }),
}));
vi.mock('@features/master/api/useFtsTechBoard', () => ({
  useFtsTechBoard: () => ({ map: new Map(), loading: false, wanted: 0, resolved: 0 }),
}));
