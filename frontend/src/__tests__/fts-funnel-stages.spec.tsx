// __tests__/fts-funnel-stages.spec.tsx -- منطقِ قیف: کجا کم می‌شود و کجا نباید بشود
//
// سه رأیِ این قیف درِ تست می‌نشینند، چون هر سه «سکوت» می‌کنند اگر نشکنند:
//   ۱) تکنیکال حذف نمی‌کند (رأیِ مالک ۱۴۰۵-۰۷-۰۷ — موتور تمام نیست).
//   ۲) بی‌دادهٔ بنیادی وتو نیست: ردیفِ بی‌پوشش به تحویل می‌رود، نه به دور ریخته‌ها.
//   ۳) ورودیِ قیف خودِ پنج فیلتر است، نه الگوهایِ محلی — «ساعت قوی» نماد را
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
  board({ symbol: 'همراه', f_susp: true }),                 // درِ سبد
  // فقط «ساعت قوی» (پایانی زیر دیروز، آخرین بالای دیروز، دلتا ۱٫۵٪) — فیلتر نیست
  board({ symbol: 'قوی‌محلی', f_susp: false, p_closing: 1000, p_last: 1015, price_yesterday: 1008 }),
];

const SCREEN = [
  screened('فولاد', 5, { tech_trend_w: 'up', tech_jet: true }),
  screened('شپنا', 2, { tech_trend_w: 'up' }),
  screened('همراه', 4, { weekly_veto: true }),
];

const build = (preset: TreePreset = 'custom', chips: string[] = []) =>
  buildFunnel(ROWS, DEFAULT_TAPE_FILTER_CONFIG, chips, SCREEN, new Set(['همراه']), preset);

const syms = (list: { symbol: string }[]) => list.map((e) => e.symbol).sort();

describe('قیفِ FTS', () => {
  it('دربِ قیف سبکِ درخت است (چارت ۳): روندگیر = کف‌روبی + نقطه‌زنی، نه هر پنج فیلتر', () => {
    // نوسان‌گیر: ساعت + جت + حجم مشکوک → هر چهار ردیفِ نشانه‌دار می‌آیند
    expect(syms(build('swing').stages.tape.entries)).toEqual(['خار', 'شپنا', 'فولاد', 'همراه']);
    // روندگیر: کف‌روبی + نقطه‌زنی → هیچ‌کدام از این ردیف‌ها آن دو را ندارند
    expect(build('trend').stages.tape.entries).toEqual([]);
    expect(syms(build('custom').stages.tape.entries)).toEqual(['خار', 'شپنا', 'فولاد', 'همراه']);
  });

  it('الگویِ محلیِ «ساعت قوی» نماد را داخلِ قیف نمی‌آورد — فقط پنج فیلتر', () => {
    expect(syms(build('swing').stages.tape.entries)).not.toContain('قوی‌محلی');
  });

  it('مرحلۀ تکنیکال هیچ نمادی را کم نمی‌کند، حتی با وتوی هفتگی', () => {
    const f = build();
    expect(f.stages.technical.entries).toHaveLength(f.stages.tape.entries.length);
    expect(f.stages.technical.dropped).toBe(0);
    expect(f.stages.technical.entries.find((e) => e.symbol === 'همراه')?.tech).toBe('no');
  });

  it('بنیادی: ردِ صریح می‌افتد، بی‌گزارش در صفِ خودش می‌ماند و به تحویل نمی‌رود', () => {
    const f = build();
    expect(f.stages.fundamental.dropped).toBe(1);
    expect(syms(f.stages.fundamental.entries)).toEqual(['فولاد', 'همراه']);
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
