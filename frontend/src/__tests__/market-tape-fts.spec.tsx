// تست بهینه‌سازی تابلو (P-02): ستون‌های سرانه + ساعت طلایی + فیلتر پسوند عددی
// وضعیت FTS روی تابلو دیگر نقاشی نمی‌شود (رأیِ مالک: ستونِ FTS از جدول حذف شد)؛
// داوریِ FTS فقط از بک‌اند خوانده می‌شود، پس اینجا تستِ رویتِ آن ندارد.
import { fireEvent, render, screen } from '@testing-library/react';
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

describe('سنجه‌های FTS تابلو (lib/tapeFts)', () => {
  it('سرانه میلیون تومان = (ارزش÷تعداد)÷1e7 با محافظت صفر/ناقص', () => {
    expect(perCapitaMt(5_000_000_000, 100)).toBe(5);
    expect(perCapitaMt(2_000_000_000, 100)).toBe(2);
    expect(perCapitaMt(null, 100)).toBeNull();
    expect(perCapitaMt(100, 0)).toBeNull();
  });

  it('سرانه خرید/فروش از ردیف تابلو — (سهم÷تعداد)×vwap÷1e7', () => {
    const r = row({
      buy_i_vol: 1_000_000, // سهمِ خرید حقیقی (نه ریال)
      buy_count_i: 100,
      sell_i_vol: 200_000,
      sell_count_i: 40,
      q_tot_cap: 5_000_000_000, // ارزش کل ریالی
      q_tot_tran: 500_000, // حجم کل سهمی ⇒ vwap = 10000 ریال
    });
    expect(buyPerCapitaMt(r)).toBe(10); // (1e6/100)*10000/1e7
    expect(sellPerCapitaMt(r)).toBe(5); // (2e5/40)*10000/1e7
  });

  it('vwap غایب ⇒ قیمت پایانی؛ همیشه به‌ارزش تبدیل می‌شود (بدون حدسِ بزرگی)', () => {
    // q_tot_cap/q_tot_tran غایب → vwap = p_closing = 5000 → (1000/2)*5000/1e7 = 0.25
    const r = row({ buy_i_vol: 1000, buy_count_i: 2, p_closing: 5000, p_last: 5000 });
    expect(buyPerCapitaMt(r)).toBe(0.25);
  });

  it('قیمت صفر/غایب ⇒ null، نه صفرِ جعلی', () => {
    const r = row({ buy_i_vol: 1000, buy_count_i: 2, p_closing: 0, p_last: 0 });
    expect(buyPerCapitaMt(r)).toBeNull();
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
});

describe('جدول تابلو بهینه‌شده', () => {
  it('ستون‌های سرانه خرید/فروش را با واحد م.ت نشان می‌دهد و ستون وضعیت FTS حذف شده است', () => {
    // buy_i_vol/sell_i_vol سهم‌اند؛ vwap = q_tot_cap÷q_tot_tran = 10000 ریال
    const r = row({
      buy_i_vol: 500_000, buy_count_i: 100,
      sell_i_vol: 200_000, sell_count_i: 100,
      q_tot_cap: 1_000_000_000, q_tot_tran: 100_000,
    });
    render(<TapeTable rows={[r]} selected="" onSelect={() => {}} />);
    expect(screen.getByText('سرانه خرید')).toBeInTheDocument();
    expect(screen.getByText('سرانه فروش')).toBeInTheDocument();
    expect(screen.getByTitle('سرانه فروش حقیقی — میلیون تومان')).toBeInTheDocument();
    expect(screen.queryByText('وضعیت FTS')).not.toBeInTheDocument();
    expect(screen.getByText('۵.۰')).toBeInTheDocument();
    expect(screen.getByText('۲.۰')).toBeInTheDocument();
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
    expect(screen.getByTestId('badge-golden-hour')).toHaveTextContent('طلایی');
  });
});

describe('حالتِ خالیِ صادق: تا فید نرسیده، فیلترِ کاربر متهم نمی‌شود', () => {
  it('خطایِ فید ⇒ علت + دکمهٔ تلاشِ دوباره که واقعاً تلاش می‌کند', () => {
    const onRetry = vi.fn();
    render(
      <TapeTable rows={[]} selected="" onSelect={() => {}} isError onRetry={onRetry} />,
    );
    expect(screen.getByText('فیدِ تابلو برنگشت')).toBeInTheDocument();
    expect(screen.queryByText('نمادی با این فیلترها نیست')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('tape-retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('بارگذاریِ نخست ⇒ «در حالِ خواندن»، نه پیامِ فیلتر', () => {
    render(<TapeTable rows={[]} selected="" onSelect={() => {}} isLoading />);
    expect(screen.getByText('در حالِ خواندنِ تابلو…')).toBeInTheDocument();
    expect(screen.queryByText('نمادی با این فیلترها نیست')).not.toBeInTheDocument();
  });

  it('فیدِ سالم ولی بی‌نتیجه ⇒ همان راهنمایِ فیلتر', () => {
    render(<TapeTable rows={[]} selected="" onSelect={() => {}} />);
    expect(screen.getByText('نمادی با این فیلترها نیست')).toBeInTheDocument();
  });
});
