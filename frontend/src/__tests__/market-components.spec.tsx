// تست کامپوننت های تابلو با فیکسچر ثابت (بدون شبکه)
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeTable } from '@features/market/components/TapeTable';
import { SuspiciousPanel } from '@features/market/components/SuspiciousPanel';
import { MarketFilters } from '@features/market/components/MarketFilters';
import { useTapeStore } from '@features/market/stores/tapeStore';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    percent_change: 2.5,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 5,
    // قیدِ حجمیِ پنج فیلتر مبناءِ فایل است، نه میانگین ماه — در تست
    // هم همان را می‌دهیم تا پنل و فیلتر یک عدد را ببینند.
    vol_ratio_file: 5,
    buyer_power: 2.1,
    p_last: 1025,
    p_closing: 1000,
    z_tot_tran: 120,
    is_live: true,
    ...patch,
  } as MarketRow;
}

// jsdom اندازه ندارد -- virtualizer را به رندر کامل وادار می کنیم
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

describe('کامپوننت های تابلو', () => {
  it('جدول نمادها را با کلید یکتا نشان می دهد', () => {
    render(<TapeTable rows={[row(), row({ symbol: 'فولاد', name: 'فولاد مبارکه' })]} selected="" onSelect={() => {}} />);
    expect(screen.getByText('شپنا')).toBeInTheDocument();
    expect(screen.getByText('فولاد')).toBeInTheDocument();
  });

  it('جدول خالی حالت خالی نشان می دهد', () => {
    render(<TapeTable rows={[]} selected="" onSelect={() => {}} />);
    expect(screen.getByText('نمادی با این فیلترها نیست')).toBeInTheDocument();
  });

  it('پنل مشکوک الگوی ساعت را فهرست می کند', () => {
    const onSelect = vi.fn();
    // شپنا هر دو پرچمِ canonicalِ تابلو را دارد (همان f_clock/f_susp که چیپ و ستون
    // می‌خوانند)؛ پنل دیگر فرمولِ جدا نمی‌سازد، پس عضویت = داوریِ چیپ (#M2.3).
    render(<SuspiciousPanel rows={[row({ f_clock: true, f_susp: true }), row({ symbol: 'خودرو', p_last: 1000, p_closing: 1001, tvol: 500_000, vol_ratio_file: 0.5 })]} onSelect={onSelect} />);
    // شپنا هم در بخش ساعت هم در بخش حجم مشکوک است (حجم 5 برابر میانگین)
    expect(screen.getAllByText('شپنا')).toHaveLength(2);
    // خودرو هیچ پرچمی ندارد و داوریِ canonical هم ردش می‌کند ⇒ در هیچ بخشی نمی‌آید
    expect(screen.queryByText('خودرو')).not.toBeInTheDocument();
  });
});

describe('نوارِ فیلتر: شمارش و سلامتِ فید', () => {
  it('شمارشِ نمایش/کل را نشان می‌دهد', () => {
    render(<MarketFilters sectors={[]} shown={10} total={50} />);
    const chip = screen.getByTitle('تعداد نمادهای فعال در جدول');
    expect(chip).toHaveTextContent('۱۰');
    expect(chip).toHaveTextContent('از');
    expect(chip).toHaveTextContent('۵۰');
    expect(chip).toHaveTextContent('نماد');
  });

  it('در خطا دکمه تلاش دوباره فراخوانی می شود', () => {
    const onRetry = vi.fn();
    render(<MarketFilters sectors={[]} shown={0} total={0} isError onRetry={onRetry} />);
    fireEvent.click(screen.getByTestId('filters-retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('پیش از رسیدنِ نخستین فید، «در حالِ خواندن» هست — نه چیپِ خطا', () => {
    render(<MarketFilters sectors={[]} shown={0} total={0} isLoading />);
    expect(screen.getByTestId('filters-loading')).toHaveTextContent('در حالِ خواندنِ تابلو');
    expect(screen.queryByTestId('filters-retry')).not.toBeInTheDocument();
  });
});

describe('فیلترهای بازطراحی شده', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  it('چیپ های سریع شمارش عبور را نشان می دهند', () => {
    render(<MarketFilters sectors={[]} matches={{ f_clock: 7, f_susp: 2, f_jet: 0, f_roobi: 1, f_noqteh: 0, f_smart: 0, f_legal: 0 }} />);
    expect(screen.getByText(/الگوی ساعت/)).toBeInTheDocument();
    expect(screen.getByText('(۷)')).toBeInTheDocument();
    expect(screen.getByText('(۲)')).toBeInTheDocument();
  });

  it('با فیلتر فعال دکمه پاک کردن ظاهر و استور را بازنشانی می کند', () => {
    useTapeStore.getState().setDirection('pos');
    // #197: «فقط زنده» پیش‌فرض روشن است، پس انحراف یعنی خاموش‌کردنش
    useTapeStore.getState().setLiveOnly(false);
    render(<MarketFilters sectors={[]} />);
    const reset = screen.getByText(/پاک کردن/);
    expect(reset).toBeInTheDocument();
    fireEvent.click(reset);
    expect(useTapeStore.getState().direction).toBe('all');
    expect(useTapeStore.getState().liveOnly).toBe(true);
  });

  it('#197 سوئیچ «فقط زنده» روی نوار هست و با کلیک عوض می‌شود', () => {
    render(<MarketFilters sectors={[]} />);
    const btn = screen.getByTestId('live-only-toggle');
    expect(btn.textContent).toContain('فقط زنده');
    expect(useTapeStore.getState().liveOnly).toBe(true);
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(btn);
    expect(useTapeStore.getState().liveOnly).toBe(false);
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('بدون فیلتر فعال دکمه پاک کردن نیست', () => {
    render(<MarketFilters sectors={[]} />);
    expect(screen.queryByText(/پاک کردن/)).not.toBeInTheDocument();
  });
});

describe('جدول تابلو نسخه بهبود یافته', () => {
  it('ستون «آخرین» و مقادیر ردیف را نشان می دهد', () => {
    render(
      <TapeTable
        rows={[row({ p_last: 5_350 }), row({ symbol: 'فولاد', name: 'فولاد مبارکه', p_last: 9_120 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText('آخرین')).toBeInTheDocument();
    expect(screen.getByText('۵٬۳۵۰')).toBeInTheDocument();
    expect(screen.getByText('۹٬۱۲۰')).toBeInTheDocument();
  });

  // #122: چهار عددی که جدولِ تابلو نداشت و تریدرز‌آرنا دارد
  it('ستون‌های پایانی/تعداد/ارزش/آخرین٪ مقادیرِ ردیف را نشان می‌دهند', () => {
    render(
      <TapeTable
        rows={[row({ p_closing: 5_300, z_tot_tran: 240, q_tot_cap: 250_000_000_000, percent_last: 1.25 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText('پایانی')).toBeInTheDocument();
    expect(screen.getByText('تعداد')).toBeInTheDocument();
    expect(screen.getByText('ارزش')).toBeInTheDocument();
    expect(screen.getByText('۵٬۳۰۰')).toBeInTheDocument();     // پایانی
    expect(screen.getByText('۲۴۰')).toBeInTheDocument();       // تعدادِ معاملات
    expect(screen.getByText('۲۵۰')).toBeInTheDocument();       // ۲۵۰ میلیارد ریال
  });

  it('نماد صف خرید میکرو-بج «صف+» با تولتیپ می‌گیرد', () => {
    render(
      <TapeTable rows={[row({ symbol: 'وصنا', percent_change: 4.98, p_last: 5_350 })]} selected="" onSelect={() => {}} />,
    );
    expect(screen.getByTestId('badge-limit-up')).toHaveTextContent('صف+');
    expect(screen.getByTestId('badge-limit-up').getAttribute('title')).toContain('صف خرید');
  });

  it('ستون ها با کلیک سرصفحه برعکس می شوند', () => {
    render(<TapeTable rows={[row({ p_last: 5_350, tvol: 100 })]} selected="" onSelect={() => {}} />);
    // «پایانی» یکتا است؛ «آخرین» دو سرصفحه دارد (آخرین و آخرین٪)
    fireEvent.click(screen.getByRole('button', { name: /^پایانی/ }));
    expect(screen.getByRole('button', { name: /پایانی.*↓/ })).toBeInTheDocument();
  });
});
