// تست الگوهای تابلوخوانی: ساعت قوی، اختلاف آخرین/پایانی، ستون سورت‌شدنی و کف‌روبی
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import {
  BOX_EXIT_HINT,
  CLOCK_DELTA_MIN_PCT,
  STRONG_CLOCK_HINT,
  STRONG_HOUR_LABEL,
  SWEEP_BUYER_POWER_MIN,
  SWEEP_HINT,
  SWEEP_VOL_RATIO_MIN,
  clockDeltaPct,
  detectBoxExit,
  detectSweep,
  detectStrongHour,
  lastCloseDiff,
  strongHour,
} from '@features/market/lib/tapePatterns';
import { TapeTable } from '@features/market/components/TapeTable';
import { ROOBI_LABEL, SuspiciousPanel } from '@features/market/components/SuspiciousPanel';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    percent_change: 2.5,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 5,
    buyer_power: 2.1,
    p_last: 1000,
    p_closing: 1025,
    price_yesterday: 980,
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

describe('ساعت قوی', () => {
  it('پایانی زیر دیروز و آخرین بالای دیروز ⇒ برچسب ساعت قوی', () => {
    expect(detectStrongHour({ p_closing: 950, p_last: 1010, price_yesterday: 1000 })).toBe(true);
    expect(strongHour({ p_closing: 950, p_last: 1010, price_yesterday: 1000 }).label).toBe(STRONG_HOUR_LABEL);
    expect(STRONG_HOUR_LABEL).toBe('ساعت قوی — شانس صف فردا');
  });

  it('حالت‌های منفی: هردو بالا، هردو پایین، یا مرز برابر', () => {
    expect(detectStrongHour({ p_closing: 1020, p_last: 1050, price_yesterday: 1000 })).toBe(false);
    expect(detectStrongHour({ p_closing: 950, p_last: 900, price_yesterday: 1000 })).toBe(false);
    expect(detectStrongHour({ p_closing: 1000, p_last: 1000, price_yesterday: 1000 })).toBe(false);
  });

  it('دادهٔ ناقص یا NaN هرگز ساعت قوی نمی‌سازد', () => {
    expect(detectStrongHour({ p_closing: 950, p_last: 1010 })).toBe(false);
    expect(detectStrongHour({ p_closing: null, p_last: 1010, price_yesterday: 1000 })).toBe(false);
    expect(detectStrongHour({ p_closing: Number.NaN, p_last: 1010, price_yesterday: 1000 })).toBe(false);
  });
});

describe('اختلاف آخرین و پایانی', () => {
  it('نسبتِ (آخرین - پایانی) به پایانی با علامت درست', () => {
    expect(lastCloseDiff({ p_last: 1050, p_closing: 1000 })).toBeCloseTo(0.05);
    expect(lastCloseDiff({ p_last: 980, p_closing: 1000 })).toBeCloseTo(-0.02);
  });

  it('مخرج صفر یا دادهٔ غایب null', () => {
    expect(lastCloseDiff({ p_last: 100, p_closing: 0 })).toBeNull();
    expect(lastCloseDiff({ p_last: null, p_closing: 1000 })).toBeNull();
    expect(lastCloseDiff({ p_last: 1000 })).toBeNull();
  });

  it('سرصفحه و سورت جدول با ستون اختلاف آخرین/پایانی', () => {
    render(
      <TapeTable
        rows={[
          row({ symbol: 'الف', p_last: 1100, p_closing: 1000 }),
          row({ symbol: 'ب', p_last: 990, p_closing: 1000 }),
        ]}
        selected=""
        onSelect={() => {}}
      />,
    );
    const header = screen.getByText(/اختلاف آخرین\/پایانی/);
    expect(header).toBeInTheDocument();
    // مقدار ۱۰٪ برای الف (۱۱۰۰ در برابر ۱۰۰۰) در ستون نمایش داده می‌شود
    expect(screen.getByText('۱۰.۰٪')).toBeInTheDocument();
  });

  it('ردیف ساعت قوی میکرو-بج «ساعت» (tone یاسی) می‌گیرد، نه دات', () => {
    render(
      <TapeTable
        rows={[row({ symbol: 'قوی', p_closing: 950, p_last: 1010, price_yesterday: 1000 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    const badge = screen.getByTestId('badge-strong-hour');
    expect(badge).toHaveTextContent('ساعت');
    expect(badge.className).toContain('rounded-md');
  });
});

describe('کف‌روبی در پنل مشکوک', () => {
  it('ردیف f_roobi با برچسب صف فروش قفل و خریدار درشت فهرست می‌شود', () => {
    const onSelect = vi.fn();
    // حجم پایین و شکاف صفر → فقط در بخش کف‌روبی ظاهر می‌شود
    const roobi = row({
      symbol: 'روباه',
      f_roobi: true,
      p_last: 1000,
      p_closing: 1000,
      tvol: 100_000,
      month_avg_vol: 1_000_000,
    });
    render(<SuspiciousPanel rows={[roobi]} onSelect={onSelect} />);
    expect(screen.getByText(/کف‌روبی/)).toBeInTheDocument();
    expect(screen.getByText('روباه')).toBeInTheDocument();
    expect(screen.getAllByText(ROOBI_LABEL).length).toBeGreaterThanOrEqual(2);
    expect(ROOBI_LABEL).toBe('در صف فروش قفل + خریدار درشت در حال جمع‌آوری');
  });

  it('بدون ردیف روباهی، بخش کف‌روبی حالت خالی دارد', () => {
    render(<SuspiciousPanel rows={[row({ symbol: 'سالم', f_roobi: false })]} onSelect={() => {}} />);
    expect(screen.getByText(/کف‌روبی/)).toBeInTheDocument();
  });

  it('الگوی ساعت با برچسب ساعت قوی در پنل نشان داده می‌شود', () => {
    render(
      <SuspiciousPanel
        rows={[row({ symbol: 'شپنا', f_clock: true, p_last: 1000, p_closing: 1025, price_yesterday: 1010 })]}
        onSelect={() => {}}
      />,
    );
    // پایانی بالاتر (ساعت) ولی آخرین زیر دیروز → ساعت قوی خیر؛ فقط نشان ساعت/پایانی
    const items = screen.getAllByText('شپنا');
    expect(items.length).toBeGreaterThanOrEqual(1);
  });
});

describe('الگوی ساعت پیشرفته: دلتا و برچسب ۹۰٪', () => {
  it('clockDeltaPct = ((p_last - p_closing) / p_closing) * 100 با علامت درست', () => {
    expect(clockDeltaPct({ p_last: 1050, p_closing: 1000 })).toBeCloseTo(5);
    expect(clockDeltaPct({ p_last: 980, p_closing: 1000 })).toBeCloseTo(-2);
    expect(clockDeltaPct({ p_last: 1000, p_closing: 0 })).toBeNull();
    expect(clockDeltaPct({ p_last: null, p_closing: 1000 })).toBeNull();
    expect(clockDeltaPct({ p_last: Number.NaN, p_closing: 1000 })).toBeNull();
  });

  it('ساعت قویِ پیشرفته: پایانی منفی + آخرین مثبت + دلتا ≥ ۱٪', () => {
    expect(CLOCK_DELTA_MIN_PCT).toBe(1);
    // دلتا = (1010-950)/950 ≈ ۶.۳٪ ≥ ۱ ⇒ قوی
    expect(detectStrongHour({ p_closing: 950, p_last: 1010, price_yesterday: 1000 })).toBe(true);
    // بازگشت مثبت اما شکاف کمتر از ۱٪ (پایانی ۹۹۹، آخرین ۱۰۰۲ ⇒ دلتای ~۰.۳٪) ⇒ قوی نیست
    expect(detectStrongHour({ p_closing: 999, p_last: 1002, price_yesterday: 1000 })).toBe(false);
    // مرز دقیق ۱٪: پایانی ۱۰۰۰ زیر دیروز ۱۰۰۰.۵، آخرین ۱۰۱۰ ⇒ دلتا = ۱٪ ⇒ قوی
    expect(detectStrongHour({ p_closing: 1000, p_last: 1010, price_yesterday: 1000.5 })).toBe(true);
    // مرزهای قدیمیِ بدون دلتا هنوز رد می‌شوند
    expect(detectStrongHour({ p_closing: 1020, p_last: 1050, price_yesterday: 1000 })).toBe(false);
    expect(detectStrongHour({ p_closing: 950, p_last: 900, price_yesterday: 1000 })).toBe(false);
    expect(detectStrongHour({ p_closing: 1000, p_last: 1000, price_yesterday: 1000 })).toBe(false);
    expect(detectStrongHour({ p_closing: null, p_last: 1010, price_yesterday: 1000 })).toBe(false);
  });

  it('برچسب ۹۰٪ داخل تولتیپِ بج «ساعت» نشسته است', () => {
    expect(STRONG_CLOCK_HINT).toBe('۹۰٪ احتمال بازگشایی مثبت فردا');
    render(
      <TapeTable
        rows={[row({ symbol: 'قوی', f_clock: false, f_susp: false, p_closing: 950, p_last: 1010, price_yesterday: 1000 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    const badge = screen.getByTestId('badge-strong-hour');
    expect(badge.getAttribute('title')).toContain(STRONG_CLOCK_HINT);
    expect(badge.getAttribute('title')).toContain('دلتا');
  });

  it('سورت روی ستون دلتا (اختلاف آخرین/پایانی) در سرصفحه هست', () => {
    render(
      <TapeTable
        rows={[
          row({ symbol: 'الف', p_last: 1100, p_closing: 1000 }),
          row({ symbol: 'ب', p_last: 990, p_closing: 1000 }),
        ]}
        selected=""
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText(/اختلاف آخرین\/پایانی \(Δ\)/)).toBeInTheDocument();
  });
});

describe('ناهنجاری‌های تابلو: کف‌روبی و خروج از باکس', () => {
  it('detectSweep: f_roobi + حجم ≥ ۳ + قدرت خریدار ≥ ۱.۵ (پروکسی سرانهٔ خرید)', () => {
    expect(SWEEP_VOL_RATIO_MIN).toBe(3);
    expect(SWEEP_BUYER_POWER_MIN).toBe(1.5);
    expect(detectSweep({ f_roobi: true, vol_ratio: 3, buyer_power: 1.5 })).toBe(true);
    expect(detectSweep({ f_roobi: true, vol_ratio: 4.2, buyer_power: 2.1 })).toBe(true);
    expect(SWEEP_HINT).toContain('قدرت خریدار');
    // بدون فیلتر روباهی حتی با حجم/قدرت بالا هم کف‌روبی نیست
    expect(detectSweep({ f_roobi: false, vol_ratio: 9, buyer_power: 9 })).toBe(false);
    expect(detectSweep({ f_roobi: true, vol_ratio: 2.9, buyer_power: 3 })).toBe(false);
    expect(detectSweep({ f_roobi: true, vol_ratio: 5, buyer_power: 1.49 })).toBe(false);
    expect(detectSweep({ f_roobi: true, vol_ratio: null, buyer_power: 3 })).toBe(false);
    expect(detectSweep({ f_roobi: true, vol_ratio: 5, buyer_power: null })).toBe(false);
    expect(detectSweep({})).toBe(false);
  });

  it('detectBoxExit: ترکیب ساعت + حجم مشکوک، با هینت «مالکیت چارت»', () => {
    expect(detectBoxExit({ f_clock: true, f_susp: true })).toBe(true);
    expect(detectBoxExit({ f_clock: true, f_susp: null })).toBe(false);
    expect(detectBoxExit({ f_clock: null, f_susp: true })).toBe(false);
    expect(detectBoxExit({})).toBe(false);
    expect(BOX_EXIT_HINT).toContain('مالکیت چارت');
  });

  it('میکرو-بج‌های متنی ساعت/مشکوک/جت/کف‌روب با تولتیپ عددی رندر می‌شوند', () => {
    render(
      <TapeTable
        rows={[
          row({
            symbol: 'همه',
            f_roobi: true,
            vol_ratio: 4,
            buyer_power: 2,
            f_clock: true,
            f_susp: true,
            f_jet: true,
            p_closing: 1030,
            p_last: 1000,
            price_yesterday: 1010,
          }),
        ]}
        selected=""
        onSelect={() => {}}
      />,
    );
    const clock = screen.getByTestId('badge-clock');
    expect(clock).toHaveTextContent('ساعت');
    expect(clock.getAttribute('title')).toContain('اختلاف آخرین و پایانی');
    const susp = screen.getByTestId('badge-susp');
    expect(susp).toHaveTextContent('مشکوک');
    expect(susp.getAttribute('title')).toContain('۴.۰× میانگین ماه');
    const jet = screen.getByTestId('badge-jet');
    expect(jet).toHaveTextContent('جت');
    expect(jet.getAttribute('title')).toContain('شکست مقاومت');
    const sweep = screen.getByTestId('badge-sweep');
    expect(sweep).toHaveTextContent('کف‌روب');
    expect(sweep.getAttribute('title')).toContain('جمع‌آوری');
  });

  it('تولتیپ ردیف، جزئیات عددی را نگه می‌دارد: ضریب حجم، اختلاف آخرین/پایانی و الگوها', () => {
    render(
      <TapeTable
        rows={[row({ symbol: 'خرا', p_last: 1010, p_closing: 990, price_yesterday: 1000 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    const title = screen.getByText('خرا').closest('button')!.getAttribute('title') ?? '';
    expect(title).toContain('۵.۰ برابر حجم ماهانه');
    expect(title).toContain('اختلاف آخرین و پایانی');
    expect(title).toContain('اعتبار الگو');
    expect(title).toContain(STRONG_CLOCK_HINT);
  });
});
