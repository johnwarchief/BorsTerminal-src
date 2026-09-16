// تست بهینه‌سازی تابلو (P-02): ستون‌های سرانه/وضعیت FTS + ساعت طلایی + فیلتر پسوند عددی
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeTable } from '@features/market/components/TapeTable';
import {
  buyPerCapitaMt,
  dropNumericSuffixRows,
  isInsuranceSector,
  isNumericSuffixSymbol,
  normSymbol,
  perCapitaMt,
  sellPerCapitaMt,
} from '@features/market/lib/tapeFts';
import {
  buildScreenerMap,
  resolveFtsStatus,
  splitReasons,
  type ScreenerFeed,
} from '@features/market/api/useFtsScreener';

// jsdom اندازه ندارد -- virtualizer را به رندر کامل وادار می‌کنیم
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 40,
      getVirtualItems: () => Array.from({ length: count }, (_, i) => ({ key: i, index: i, start: i * 40 })),
    }),
  };
});

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    percent_change: 1.11,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 4.4,
    buyer_power: 1.23,
    p_last: 1234,
    p_closing: 1240,
    price_yesterday: 1200,
    buy_i_vol: 5_000_000_000,
    buy_count_i: 100,
    sell_i_vol: 2_000_000_000,
    sell_count_i: 100,
    z_tot_tran: 120,
    is_live: true,
    ...patch,
  } as MarketRow;
}

const feed = (data: ScreenerFeed['data']): ScreenerFeed => ({ status: 'success', data });

describe('سنجه‌های FTS تابلو (lib/tapeFts)', () => {
  it('سرانه میلیون تومان = (ارزش÷تعداد)÷1e7 با محافظت صفر/ناقص', () => {
    expect(perCapitaMt(5_000_000_000, 100)).toBe(5);
    expect(perCapitaMt(2_000_000_000, 100)).toBe(2);
    expect(perCapitaMt(null, 100)).toBeNull();
    expect(perCapitaMt(100, 0)).toBeNull();
  });

  it('سرانه خرید/فروش از ردیف تابلو', () => {
    const r = row();
    expect(buyPerCapitaMt(r)).toBe(5);
    expect(sellPerCapitaMt(r)).toBe(2);
  });

  it('پسوند عددی (عمده/بلوکی/حق‌تقدم غیرعادی) تشخیص و فیلتر می‌شود', () => {
    expect(isNumericSuffixSymbol('فولاد1')).toBe(true);
    expect(isNumericSuffixSymbol('وبملت۲')).toBe(true);
    expect(isNumericSuffixSymbol('فولاد')).toBe(false);
    expect(dropNumericSuffixRows([row({ symbol: 'فولاد' }), row({ symbol: 'فولاد1' })]).map((x) => x.symbol)).toEqual(['فولاد']);
  });

  it('نرمال‌سازی نماد (عربی→فارسی) و وتوی بیمه', () => {
    expect(normSymbol('كگل')).toBe('کگل');
    expect(normSymbol('دامين')).toBe('دامین');
    expect(isInsuranceSector('بیمه و صندوق بازنشستگی')).toBe(true);
    expect(isInsuranceSector('خودرو و ساخت قطعات')).toBe(false);
  });

  it('تفکیک دلایل رشته‌ای/آرایه‌ای', () => {
    expect(splitReasons('صنعت بیمه · نماد تعلیق')).toEqual(['صنعت بیمه', 'نماد تعلیق']);
    expect(splitReasons(['ماده ۱۴۱'])).toEqual(['ماده ۱۴۱']);
    expect(splitReasons(null)).toEqual([]);
  });
});

describe('حل وضعیت FTS', () => {
  const map = buildScreenerMap(
    feed([
      { symbol: 'شپنا', excluded: false, score: 4 },
      { symbol: 'فولاد', excluded: true, score: 1, exclusion_reasons: 'قیمت‌گذاری دستوری · نماد تعلیق' },
    ]),
  );

  it('در اسکرینر و غیرمردود ⇒ تأیید با امتیاز', () => {
    const v = resolveFtsStatus({ symbol: 'شپنا' }, map);
    expect(v.status).toBe('confirm');
    expect(v.score).toBe(4);
  });

  it('excluded ⇒ رد همراه دلایل', () => {
    const v = resolveFtsStatus({ symbol: 'فولاد' }, map);
    expect(v.status).toBe('reject');
    expect(v.reasons).toContain('نماد تعلیق');
  });

  it('نبود در اسکرینر ⇒ N/A صادقانه', () => {
    expect(resolveFtsStatus({ symbol: 'خودرو' }, map).status).toBe('na');
  });

  it('وتوی سخت‌گیرانه بیمه حتی بدون حضور در اسکرینر', () => {
    const v = resolveFtsStatus({ symbol: 'اسب', sector_name: 'بیمه' }, new Map());
    expect(v.status).toBe('reject');
    expect(v.reasons[0]).toContain('REJECT_ALL_INSURANCE');
  });
});

describe('جدول تابلو بهینه‌شده', () => {
  it('ستون‌های سرانه خرید/فروش و وضعیت FTS را نشان می‌دهد', () => {
    render(<TapeTable rows={[row()]} selected="" onSelect={() => {}} />);
    expect(screen.getByText('سرانه خرید')).toBeInTheDocument();
    expect(screen.getByText('سرانه فروش')).toBeInTheDocument();
    expect(screen.getByText('وضعیت FTS')).toBeInTheDocument();
    expect(screen.getByText('۵.۰')).toBeInTheDocument();
    expect(screen.getByText('۲.۰')).toBeInTheDocument();
  });

  it('بج وضعیت FTS تأیید/رد/N/A و هاورکارت دلایل را رندر می‌کند', () => {
    const map = buildScreenerMap(
      feed([
        { symbol: 'شپنا', excluded: false, score: 5 },
        { symbol: 'فولاد', excluded: true, score: 0, exclusion_reasons: 'صنعت بیمه — حذف خودکار' },
      ]),
    );
    render(
      <TapeTable
        rows={[row({ symbol: 'شپنا' }), row({ symbol: 'فولاد' }), row({ symbol: 'خودرو' })]}
        selected=""
        onSelect={() => {}}
        ftsMap={map}
      />,
    );
    expect(screen.getByTestId('fts-badge-شپنا')).toHaveTextContent('تأیید');
    expect(screen.getByTestId('fts-badge-فولاد')).toHaveAttribute('data-fts-status', 'reject');
    expect(screen.getByTestId('fts-badge-خودرو')).toHaveTextContent('N/A');
    // هاورکارت دلایل در DOM هست (برای hover نمایش داده می‌شود)
    expect(screen.getByTestId('fts-card-فولاد')).toHaveTextContent('صنعت بیمه — حذف خودکار');
  });

  it('وتوی بیمه در جدول: ردیف بیمه بدون اسکرینر هم «رد» می‌شود', () => {
    render(
      <TapeTable rows={[row({ symbol: 'اسب', sector_name: 'بیمه' })]} selected="" onSelect={() => {}} />,
    );
    expect(screen.getByTestId('fts-badge-اسب')).toHaveAttribute('data-fts-status', 'reject');
  });

  it('ساعت طلایی (پایانی منفی و آخرین مثبت) از ساعت معمولی تفکیک می‌شود', () => {
    // پایانی ۹۹۵ (زیر دیروز ۱۰۰۰)، آخرین ۱۰۰۳ (بالای دیروز) ⇒ دلتا ۰.۸٪ < ۱٪ ⇒ طلایی نه قوی
    render(
      <TapeTable
        rows={[row({ symbol: 'طلا', p_closing: 995, p_last: 1003, price_yesterday: 1000 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    expect(screen.getByTestId('badge-golden-hour')).toHaveTextContent('ساعت طلایی');
  });
});
