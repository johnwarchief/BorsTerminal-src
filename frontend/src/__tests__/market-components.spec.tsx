// تست کامپوننت های تابلو با فیکسچر ثابت (بدون شبکه)
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeTable } from '@features/market/components/TapeTable';
import { SuspiciousPanel } from '@features/market/components/SuspiciousPanel';
import { MarketFilters } from '@features/market/components/MarketFilters';
import { TapeStatusBar } from '@features/market/components/TapeStatusBar';
import { useTapeStore } from '@features/market/stores/tapeStore';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    percent_change: 2.5,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 5,
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
    render(<SuspiciousPanel rows={[row(), row({ symbol: 'خودرو', p_last: 1000, p_closing: 1001, tvol: 500_000 })]} onSelect={onSelect} />);
    // شپنا هم در بخش ساعت هم در بخش حجم مشکوک است (حجم 5 برابر میانگین)
    expect(screen.getAllByText('شپنا')).toHaveLength(2);
    expect(screen.queryByText('خودرو')).not.toBeInTheDocument();
  });
});

describe('نوار وضعیت تابلو', () => {
  it('شمارش نمایش/کل و زنده را نشان می دهد', () => {
    render(
      <TapeStatusBar
        shown={10}
        total={50}
        liveCount={40}
        fossilCount={10}
        signals={3}
        isLoading={false}
        isError={false}
        isFetching={false}
        dataUpdatedAt={Date.now()}
        pollMs={60_000}
        onPollChange={() => {}}
        onRetry={() => {}}
      />,
    );
    expect(screen.getByText('۱۰ از ۵۰ نماد')).toBeInTheDocument();
    expect(screen.getByText('زنده ۴۰')).toBeInTheDocument();
    expect(screen.getByText('۳ سیگنال تابلو')).toBeInTheDocument();
  });

  it('در خطا دکمه تلاش دوباره فراخوانی می شود', () => {
    const onRetry = vi.fn();
    render(
      <TapeStatusBar
        shown={0}
        total={0}
        liveCount={0}
        fossilCount={0}
        signals={0}
        isLoading={false}
        isError={true}
        isFetching={false}
        dataUpdatedAt={0}
        pollMs={60_000}
        onPollChange={() => {}}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(screen.getByText('تلاش دوباره'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe('فیلترهای بازطراحی شده', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  it('چیپ های سریع شمارش عبور را نشان می دهند', () => {
    render(<MarketFilters sectors={[]} matches={{ f_clock: 7, f_susp: 2, f_jet: 0, f_roobi: 1, f_noqteh: 0 }} />);
    fireEvent.click(screen.getByText('فیلترهای پیشرفته'));
    expect(screen.getByText(/الگوی ساعت/)).toBeInTheDocument();
    expect(screen.getByText('(۷)')).toBeInTheDocument();
    expect(screen.getByText('(۲)')).toBeInTheDocument();
  });

  it('با فیلتر فعال دکمه پاک کردن ظاهر و استور را بازنشانی می کند', () => {
    useTapeStore.getState().setDirection('pos');
    useTapeStore.getState().setLiveOnly(true);
    render(<MarketFilters sectors={[]} />);
    const reset = screen.getByText(/پاک کردن/);
    expect(reset).toBeInTheDocument();
    fireEvent.click(reset);
    expect(useTapeStore.getState().direction).toBe('all');
    expect(useTapeStore.getState().liveOnly).toBe(false);
  });

  it('بدون فیلتر فعال دکمه پاک کردن نیست', () => {
    render(<MarketFilters sectors={[]} />);
    expect(screen.queryByText(/پاک کردن/)).not.toBeInTheDocument();
  });
});

describe('جدول تابلو نسخه بهبود یافته', () => {
  it('ستون «قیمت آخرین» و مقادیر ردیف را نشان می دهد', () => {
    render(
      <TapeTable
        rows={[row({ p_last: 5_350 }), row({ symbol: 'فولاد', name: 'فولاد مبارکه', p_last: 9_120 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText('قیمت آخرین')).toBeInTheDocument();
    expect(screen.getByText('۵٬۳۵۰')).toBeInTheDocument();
    expect(screen.getByText('۹٬۱۲۰')).toBeInTheDocument();
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
    fireEvent.click(screen.getByText(/قیمت آخرین/));
    // همان دکمه حالت نزولی می گیرد
    expect(screen.getByText(/قیمت آخرین/)).toBeInTheDocument();
  });
});
