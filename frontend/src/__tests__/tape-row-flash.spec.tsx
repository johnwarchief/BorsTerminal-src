// __tests__/tape-row-flash.spec.tsx -- هر خانۀِ عددیِ ردیف تابلو هم تاز می‌شود هم رنگ
//
// دو ادعا اینجا نگهبانی می‌شوند:
//   ۱) مدتِ فلاش از ریتمِ تیک می‌آید، نه از عددِ ثابت (رأیِ مالک: بازۀِ ۵ ثانیه
//      ← ۳ تا ۴ ثانیه رنگ).
//   ۲) هیچ ستونِ عددیِ تابلو بی‌فلاش نمانده باشد — از جمله دو سرانۀِ خرید و
//      فروش که درِ ستونِ «خرید / فروش» بودند و بی‌خبر عوض می‌شدند.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeRow } from '@features/market/components/TapeTable';
import { applyFlashClock, flashDurationMs } from '@shared/lib/flashClock';
import { JET_LADDER } from '@features/market/lib/tapeMath';

const row = (over: Partial<MarketRow> = {}): MarketRow =>
  ({
    symbol: 'آزمون',
    name: 'شرکت آزمون',
    p_last: 1000,
    p_closing: 990,
    price_yesterday: 985,
    percent_change: 1.5,
    percent_last: 0.5,
    tvol: 1_000_000,
    z_tot_tran: 40,
    q_tot_cap: 5_000_000_000,
    vol_ratio: 1.4,
    buyer_power: 1.8,
    buy_i_vol: 700_000,
    buy_count_i: 7,
    sell_i_vol: 300_000,
    sell_count_i: 3,
    hist_sessions: 60,
    prior30_vol: 20_000_000,
    min_low_29: 900,
    min30_low: 900,
    ...Object.fromEntries(JET_LADDER.map((k) => [`h${k}_max`, 800])),
    ...over,
  }) as unknown as MarketRow;

const next = row({
  p_last: 1020,
  p_closing: 1010,
  percent_change: 2.6,
  percent_last: 1.6,
  tvol: 1_200_000,
  z_tot_tran: 52,
  q_tot_cap: 6_400_000_000,
  vol_ratio: 1.9,
  buyer_power: 2.4,
  buy_i_vol: 900_000,
  buy_count_i: 8,
  sell_i_vol: 250_000,
  sell_count_i: 2,
});

const flashed = (c: HTMLElement) => c.querySelectorAll('.flash-up, .flash-down').length;

describe('مدتِ فلاش از ریتمِ تیک می‌آید', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 26, 10, 0, 0)); // شنبه ۱۰:۰۰ — بازار باز
  });
  afterEach(() => {
    vi.useRealTimers();
    document.documentElement.style.removeProperty('--bors-flash-dur');
  });

  it('بازۀِ ۵ ثانیه → ۳٫۵ ثانیه رنگ (خواستِ مالک: ۳ تا ۴)', () => {
    expect(flashDurationMs(5_000)).toBe(3_500);
    expect(flashDurationMs(15_000)).toBe(4_000);   // سقف: فلاش رویِ سلول خشک نشود
    expect(flashDurationMs(1_000)).toBe(1_200);    // کف: یک چشم‌برهم‌زدن کامل دیده شود
  });

  it('متغیرِ CSS رویِ همان عدد می‌نشیند و بازارِ بسته ریتمِ آرام دارد', () => {
    expect(applyFlashClock(5_000)).toBe(3_500);
    expect(document.documentElement.style.getPropertyValue('--bors-flash-dur')).toBe('3500ms');
    vi.setSystemTime(new Date(2026, 8, 26, 14, 30, 0)); // پس از بستن
    expect(applyFlashClock(5_000)).toBe(4_000);         // ریتمِ واقعی ۵ دقیقه است
  });
});

describe('ستون‌های عددیِ ردیفِ تابلو فلاش می‌گیرند', () => {
  it('هر دوازده خانۀِ عددی با تازۀِ مقدار رنگ می‌بینند', () => {
    const { container, rerender } = render(
      <TapeRow row={row()} selected={false} onSelect={() => undefined} />,
    );
    expect(flashed(container)).toBe(0);
    rerender(<TapeRow row={next} selected={false} onSelect={() => undefined} />);
    // آخرین | پایانی | اختلاف٪ | تغییر٪ | آخرین٪ | حجم | تعداد | ارزش | حجم/ماه |
    // نسبتِ خرید/فروش | سرانۀِ خرید | سرانۀِ فروش
    expect(flashed(container)).toBe(12);
    for (const id of ['tape-buy-pc', 'tape-sell-pc']) {
      const cell = container.querySelector(`[data-testid="${id}"]`);
      expect(cell?.querySelector('.flash-up, .flash-down')).not.toBeNull();
    }
  });

  it('بدونِ تغییرِ مقدار، هیچ خانه‌ای رنگ نمی‌گیرد', () => {
    const { container, rerender } = render(
      <TapeRow row={row()} selected={false} onSelect={() => undefined} />,
    );
    rerender(<TapeRow row={row()} selected={false} onSelect={() => undefined} />);
    expect(flashed(container)).toBe(0);
  });
});
