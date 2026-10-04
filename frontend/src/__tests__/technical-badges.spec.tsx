// تست بج استریپ و کارت تحلیل ساختاری FTS (سمت سرور)
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FtsBadgeStrip, jetBadges, trendBadges, trendTone, verdictMeta } from '@features/technical/components/FtsBadgeStrip';
import { FtsTrendPanel, setupBadgesOf } from '@features/technical/components/FtsTrendPanel';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';

function fixture(): FtsAnalysisData {
  return {
    trend: {
      D: { trend: 'down', hh: false, hl: false, last_high: 3367, prev_high: 3492, last_low: 2182, prev_low: 3195 },
      W: { trend: 'range', hh: true, hl: false, last_high: 4490, prev_high: 3237, last_low: 2182, prev_low: 3260 },
      M: { trend: 'up', hh: true, hl: true, last_high: 4490, prev_high: 6360, last_low: 2010, prev_low: 3771 },
      alignment: 'na',
    },
    fib: {
      retrace_base_high: 3367,
      retrace_base_low: 2010,
      zone_33_40: { lo: 2739.2, hi: 2839.93, in_zone: false },
      zone_618_70: { lo: 2346.44, hi: 2447.83, in_zone: true },
    },
    jet: { active: false, resistance: 4490, ath: false, close: 2967, pct_above_res: -33.92 },
    choch: { bearish: false, bullish: false, level: null, label: null },
    point_hunt: { touches: 12, floor_price: 2820, active: true, floor_idx: 339 },
    double_bottom: { active: false, neckline: null, pct_above_neck: null },
    range_box: { active: false, top: 3492, bottom: 2182, pct_above_top: null },
    exit_engine: {
      verdict: 'caution',
      signals: ['ma14_watch'],
      l1: { hard_stop: 2072.9, stop_basis: 'swing_low', stop_hit: false, ma14_exit: false, ma14_exit_pending: true, ma14: 2550.14, close: 2967 },
      l2: { choch_break: false, channel_break: false, level: null, touches: 12 },
      l3: { third_peak: false, double_top: false, hs_break: false, neckline: null, level: null },
      l4: { rsi_divergence: false, rsi_rollover: false, rsi: 52.5, rsi_prev_peak: 41.1 },
    },
  };
}

describe('حالت های نشان', () => {
  it('رنگ روند از واژه سرور', () => {
    expect(trendTone('up')).toBe('green');
    expect(trendTone('down')).toBe('red');
    expect(trendTone('range')).toBe('yellow');
    expect(trendTone('na')).toBe('gray');
    expect(trendTone(null)).toBe('gray');
  });

  it('حکم موتور خروج فارسی می شود', () => {
    expect(verdictMeta('stop').label).toBe('حد ضرر');
    expect(verdictMeta('exit').label).toBe('خروج');
    expect(verdictMeta('caution').label).toBe('احتیاط');
    expect(verdictMeta('hold').label).toBe('نگهداری');
    // دورِ J (پینِ برگردانده‌شده): کلمۀ ناشناخته یا رأیِ نیامده «نگهداری» نیست؛
    // «نگهداری» یعنی سنجیدیم و خروجی نداریم. چیزی که موتور نگفته ⇒ نسنجیده.
    expect(verdictMeta('unknown-word').label).toBe('خروج: نسنجیده');
    expect(verdictMeta(undefined).label).toBe('خروج: نسنجیده');
  });

  it('سه روند و بدون هم راستایی', () => {
    const bs = trendBadges(fixture());
    expect(bs).toHaveLength(3);
    expect(bs[0].value).toBe('نزولی');
    expect(bs[1].value).toBe('رنج');
    expect(bs[2].value).toBe('صعودی');
  });

  it('هم راستایی وقتی سه تایم فریم هم جهتند', () => {
    const f = fixture();
    f.trend!.alignment = 'up';
    const bs = trendBadges(f);
    expect(bs).toHaveLength(4);
    expect(bs[3].value).toBe('صعودی');
  });

  it('جت غیر فعال بج نمی دهد؛ فعال با ATH', () => {
    const f = fixture();
    expect(jetBadges(f)).toHaveLength(0);
    f.jet!.active = true;
    f.jet!.ath = true;
    const bs = jetBadges(f);
    expect(bs).toHaveLength(1);
    expect(bs[0].label).toContain('ATH');
  });
});

describe('بج استریپ رندر', () => {
  it('حالت خالی صادقانه پیام می دهد', () => {
    render(<FtsBadgeStrip data={null} empty={true} />);
    expect(screen.getByTestId('fts-badges-empty')).toBeInTheDocument();
    expect(screen.getByText(/تحلیل سمت سرور برای این نماد موجود نیست/)).toBeInTheDocument();
  });

  it('در حال بارگذاری نشان انتظار', () => {
    render(<FtsBadgeStrip data={undefined} empty={false} />);
    expect(screen.getByTestId('fts-badges-loading')).toBeInTheDocument();
  });

  it('داده کامل: فیبو، شکار نقطه و حکم خروج', () => {
    render(<FtsBadgeStrip data={fixture()} empty={false} />);
    const strip = screen.getByTestId('fts-badges');
    expect(strip).toBeInTheDocument();
    expect(strip.textContent).toContain('روند روزانه');
    expect(strip.textContent).toContain('شکار نقطه');
    expect(strip.textContent).toContain('موتور خروج');
    // فیبو طلایی داخل کمربند است
    expect(strip.textContent).toContain('۶۱.۸-۷۰٪');
    // حکم احتیاط
    expect(strip.textContent).toContain('احتیاط');
  });
});

describe('کارت تحلیل ساختاری', () => {
  it('بدون داده حالت انتظار', () => {
    render(<FtsTrendPanel data={null} />);
    expect(screen.getByText('در انتظار داده تحلیل...')).toBeInTheDocument();
  });

  it('سه تایم فریم، فیبو، موتور خروج و ستاپ ها', () => {
    render(<FtsTrendPanel data={fixture()} />);
    const panel = screen.getByTestId('fts-trend-panel');
    expect(panel.textContent).toContain('روزانه');
    expect(panel.textContent).toContain('هفتگی');
    expect(panel.textContent).toContain('ماهانه');
    expect(panel.textContent).toContain('کمربند طلایی');
    expect(panel.textContent).toContain('حد ضرر سخت');
    expect(panel.textContent).toContain('زیرِ کف ۲۰ نشستِ اخیر');
    expect(panel.textContent).toContain('RSI');
    // ستاپ شکار نقطه فعال
    const setups = setupBadgesOf(fixture());
    expect(setups.map((s) => s.label)).toContain('شکار نقطه');
  });

  it('مقاومت جت وقتی ستاپ فعال نیست نشان داده می شود', () => {
    render(<FtsTrendPanel data={fixture()} />);
    const panel = screen.getByTestId('fts-trend-panel');
    expect(panel.textContent).toContain('مقاومت جت');
  });
});
