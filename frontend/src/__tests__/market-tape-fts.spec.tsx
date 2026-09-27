// تست بهینه‌سازی تابلو (P-02): ستون‌های سرانه + ساعت طلایی + فیلتر پسوند عددی
// وضعیت FTS روی تابلو دیگر نقاشی نمی‌شود (رأیِ مالک: ستونِ FTS از جدول حذف شد)؛
// داوریِ FTS فقط از بک‌اند خوانده می‌شود، پس اینجا تستِ رویتِ آن ندارد.
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { TapeTable } from '@features/market/components/TapeTable';
import {
  buyPerCapitaMt,
  buySellShare,
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

  it('سهمِ خرید از دو سرانه — غایب یا مجموعِ صفر ⇒ null، نه «فروش صفر»ِ جعلی', () => {
    expect(buySellShare(5, 2)).toBeCloseTo(5 / 7, 10);
    expect(buySellShare(10, 0)).toBe(1);
    expect(buySellShare(0, 10)).toBe(0);
    expect(buySellShare(0, 0)).toBeNull();
    expect(buySellShare(null, 2)).toBeNull();
    expect(buySellShare(3, null)).toBeNull();
  });
});

describe('جدول تابلو بهینه‌شده', () => {
  it('یک ستونِ خرید/فروش با دو سرانۀ دیدنی: نوارِ دوسُره به نسبتِ سرانه‌ها + عددِ قدرت', () => {
    // buy_i_vol/sell_i_vol سهم‌اند؛ vwap = q_tot_cap÷q_tot_tran = 10000 ریال
    // ⇒ سرانۀ خرید ۵ م.ت در برابر سرانۀ فروش ۲ م.ت ⇒ سهمِ خرید ۵/۷
    const r = row({
      buy_i_vol: 500_000, buy_count_i: 100,
      sell_i_vol: 200_000, sell_count_i: 100,
      q_tot_cap: 1_000_000_000, q_tot_tran: 100_000,
    });
    render(<TapeTable rows={[r]} selected="" onSelect={() => {}} />);
    expect(screen.getByText('خرید / فروش')).toBeInTheDocument();
    // تیترهایِ ستونِ جدا در سرستون تکرار نمی‌شوند (#146 سرِ جای خودش را گرفت)
    expect(screen.queryByText('سرانه خرید')).not.toBeInTheDocument();
    expect(screen.queryByText('سرانه فروش')).not.toBeInTheDocument();
    expect(screen.queryByText('قدرت')).not.toBeInTheDocument();
    expect(screen.queryByText('وضعیت FTS')).not.toBeInTheDocument();

    const cell = screen.getByTestId('tape-buy-sell');
    const buyBar = cell.querySelector('.bg-accent-green') as HTMLElement | null;
    const sellBar = cell.querySelector('.bg-accent-red') as HTMLElement | null;
    expect(buyBar).not.toBeNull();
    expect(sellBar).not.toBeNull();
    expect(parseFloat(buyBar!.style.width)).toBeCloseTo(71.43, 1);
    expect(parseFloat(sellBar!.style.width)).toBeCloseTo(28.57, 1);
    // #172: دو سرانه دیگر فقط در title نیستند — با واحد در خودِ ستون دیده می‌شوند
    expect(within(cell).getByTestId('tape-buy-pc').textContent).toBe(`${toFaDigits('5.0')}م.ت`);
    expect(within(cell).getByTestId('tape-sell-pc').textContent).toBe(`${toFaDigits('2.0')}م.ت`);
    expect(cell.getAttribute('title')).toContain('م.ت');
    // عددِ قدرت از فیلدِ بک‌اند رندر می‌شود (داوریِ مجدد در JSX نیست)
    expect(cell.textContent).toContain('۱.۲۳');
  });

  it('سرانهٔ غایب ⇒ نوار رسم نمی‌شود؛ «۰٪ فروش» و «۰ م.ت» دروغ نیست', () => {
    const r = row({ buy_count_i: null, sell_count_i: null, buyer_power: null });
    render(<TapeTable rows={[r]} selected="" onSelect={() => {}} />);
    const cell = screen.getByTestId('tape-buy-sell');
    expect(cell.querySelector('.bg-accent-green')).toBeNull();
    expect(cell.textContent).not.toContain('۱.۰۰');
    // «—» تنها نشانهٔ نبودِ داده است؛ صفرِ با واحد ساخته نمی‌شود
    expect(within(cell).getByTestId('tape-buy-pc').textContent).toBe('—');
    expect(within(cell).getByTestId('tape-sell-pc').textContent).toBe('—');
  });

  it('#172: سرانۀ بالای ۱۰۰ م.ت اعشار نمی‌گیرد تا ستون نترکد', () => {
    // vwap = ۱e۹ ÷ ۱e۵ = ۱۰٬۰۰۰ ریال ⇒ ۲۰٬۰۰۰٬۰۰۰ سهم ÷ ۱۰۰ معامله × ۱۰٬۰۰۰ = ۲۰۰ م.ت
    const r = row({
      buy_i_vol: 20_000_000, buy_count_i: 100,
      sell_i_vol: 200_000, sell_count_i: 100,
      q_tot_cap: 1_000_000_000, q_tot_tran: 100_000,
    });
    render(<TapeTable rows={[r]} selected="" onSelect={() => {}} />);
    const cell = screen.getByTestId('tape-buy-sell');
    expect(within(cell).getByTestId('tape-buy-pc').textContent).toBe(`${fmtInt(200)}م.ت`);
    // خودِ عدد اعشار ندارد (وگرنه «۲۰۰.۰م.ت» از ستون بیرون می‌زد)
    expect(within(cell).getByTestId('tape-buy-pc').querySelector('.num')?.textContent).toBe(fmtInt(200));
    // زیرِ ۱۰۰ همان یک رقمِ اعشار می‌ماند
    expect(within(cell).getByTestId('tape-sell-pc').textContent).toBe(`${toFaDigits('2.0')}م.ت`);
  });

  it('#172: اختلافِ ساعت یک ستونِ عددیِ مستقل است، بج‌ها در ستونِ «الگو»', () => {
    // پایانیِ بالاتر از آخرین ⇒ دلتای منفی؛ پیش از این همین عدد در همان خانهٔ
    // بج‌ها می‌نشست و به «مشکوک» می‌چسبید («۰.۹٪مشکوک» خوانده می‌شد).
    const r = row({ f_susp: true, p_last: 1234, p_closing: 1240, price_yesterday: 1200 });
    render(<TapeTable rows={[r]} selected="" onSelect={() => {}} />);
    const head = screen.getByTestId('tape-head');
    expect(within(head).getByText('اختلاف٪')).toBeInTheDocument();
    expect(within(head).getByText('الگو')).toBeInTheDocument();
    // «ساعت» دیگر نامِ ستون نیست؛ فقط برچسبِ خودِ الگوست
    expect(within(head).queryByText('ساعت')).not.toBeInTheDocument();

    const cells = screen.getByTestId('tape-row').children;
    expect(cells).toHaveLength(12);
    // #194: اختلاف «آخرین تا پایانی» بغلِ خودِ پایانی نشسته، نه ته جدول کنارِ بج‌ها
    const delta = cells[3];
    const patterns = cells[11];
    expect(cells[2].textContent).toBe(fmtInt(1240));       // پایانی
    expect(delta.textContent).toBe(fmtPct(((1234 - 1240) / 1240) * 100));
    expect(delta.querySelector('[data-testid^="badge-"]')).toBeNull();
    expect(patterns.querySelector('[data-testid^="badge-"]')).not.toBeNull();
    // خانهٔ بج هیچ درصدی در خودش ندارد
    expect(patterns.textContent).not.toContain('٪');
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
