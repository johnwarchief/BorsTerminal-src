// تست بج استریپ و کارت تحلیل ساختاری FTS (سمت سرور)
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FtsBadgeStrip, jetBadges, trendBadges, trendTone, verdictMeta } from '@features/technical/components/FtsBadgeStrip';
import { FtsTrendPanel, setupBadgesOf } from '@features/technical/components/FtsTrendPanel';
import { FtsAnalysis, type FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';

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
    expect(screen.getByText(/برای این نماد تحلیل FTS آماده نیست/)).toBeInTheDocument();
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
    // فیبو طلایی داخل زون است
    expect(strip.textContent).toContain('۶۱.۸-۷۰٪');
    // حکم احتیاط
    expect(strip.textContent).toContain('احتیاط');
  });
});

describe('کارت تحلیل ساختاری', () => {
  it('بدون داده حالت انتظار', () => {
    render(<FtsTrendPanel data={null} />);
    expect(screen.getByText('در انتظار دریافت تحلیل…')).toBeInTheDocument();
  });

  it('سه تایم فریم، فیبو، موتور خروج و ستاپ ها', () => {
    render(<FtsTrendPanel data={fixture()} />);
    const panel = screen.getByTestId('fts-trend-panel');
    expect(panel.textContent).toContain('روزانه');
    expect(panel.textContent).toContain('هفتگی');
    expect(panel.textContent).toContain('ماهانه');
    expect(panel.textContent).toContain('زون طلایی');
    expect(panel.textContent).toContain('حد ضرر سخت');
    expect(panel.textContent).toContain('زیرِ کف ۲۰ روز معاملاتیِ اخیر');
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

  // ب-۲: «خطِ واگرایی RSI» رویِ چارت رسم نمی‌شود (کرانۀ l4 از سرور منتشر نمی‌شود)،
  // پس همان عددِ سرور درِ ردیفی خوانده می‌شود که تُنش زرد می‌شود. آزمونِ دوم
  // کنترلِ منفی است: در fixture واگرایی false است ولی `rsi_prev_peak` عدد دارد
  // (۴۱.۱) — همان حالتِ «عددِ یتیم» که نباید نمایش داده شود.
  it('واگرایی RSI: اوجِ پیشین از سرور درِ همان ردیفِ RSI می‌آید', () => {
    const f = fixture();
    f.exit_engine!.l4 = { ...f.exit_engine!.l4, rsi_divergence: true };
    render(<FtsTrendPanel data={f} />);
    const panel = screen.getByTestId('fts-trend-panel');
    expect(panel.textContent).toContain('۵۲.۵');
    expect(panel.textContent).toContain('اوجِ پیشین ۴۱.۱');
  });

  it('بی‌واگرایی، ردیفِ RSI عددِ اوجِ پیشین را نشان نمی‌دهد', () => {
    render(<FtsTrendPanel data={fixture()} />);
    expect(screen.getByTestId('fts-trend-panel').textContent).not.toContain('اوجِ پیشین');
  });
});

// ── مأموریتِ ماژور ۱۴۰۵-۰۷-۲۷: رابط باید «قطعی» را از «در حال شکل‌گیری» جدا بیند ──
describe('پروندۀِ سقف/کفِ ماژور در کارتِ روند', () => {
  function majorFixture(): FtsAnalysisData {
    const f = fixture();
    f.trend = {
      ...f.trend,
      as_of: '2026-10-17',
      major_swings: {
        D: {
          timeframe: 'D',
          confirmed_trend: 'up',
          verdict_basis: 'pivots',
          as_of: '2026-10-17',
          daily_as_of: '2026-10-17',
          bars: 392,
          bucket_forming: null,
          major_swings: [
            { idx: 300, time: '2026-06-10', kind: 'high', price: 3492, leg_pct: 0.11, leg_atr_x: 3.1 },
            { idx: 340, time: '2026-08-02', kind: 'low', price: 2182, leg_pct: 0.19, leg_atr_x: 4.2 },
          ],
          counts: { pivots: 71, majors: 51, major_highs: 28, major_lows: 23,
                    minor_highs: 4, minor_lows: 15, undecided: 1, dropped_minor: 20 },
          threshold: { atr_x: 2, floor_pct: 0.005 },
          enough_extremes: true,
          provisional: {
            since_pivot_time: '2026-10-05', bars_since_last_pivot: 6,
            high: { idx: 389, time: '2026-10-12', price: 3600, provisional: true, confirmed: false,
                    bars_since: 2, bars_to_confirm: 1 },
            low: { idx: 386, time: '2026-10-06', price: 3100, provisional: true, confirmed: false,
                   bars_since: 5, bars_to_confirm: 0 },
            note: 'پنجرۀ تأیید این دو کامل نشده؛ رأیِ قطعی روی آن‌ها ساخته نمی‌شود',
          },
          reason: null,
        },
        W: { timeframe: 'W', confirmed_trend: 'na', counts: { major_highs: 1, major_lows: 1,
              dropped_minor: 8 }, enough_extremes: false, bucket_forming: true,
             reason: 'تنها ۱ سقف و ۱ کفِ ماژور از ۹ پیوت (آستانه ۲٫۰×ATR)' },
        M: { timeframe: 'M', confirmed_trend: 'na', enough_extremes: false, reason: null },
      },
    } as unknown as FtsAnalysisData['trend'];
    return f;
  }

  it('شمارِ ماژور و ردیفِ «در حال شکل‌گیری» نشان داده می‌شود', () => {
    render(<FtsTrendPanel data={majorFixture()} />);
    const d = screen.getByTestId('fts-major-counts-D');
    expect(d.textContent).toContain('۲۸/۲۳');
    expect(d.textContent).toContain('۲۰ کوچک');
    const p = screen.getByTestId('fts-provisional-D');
    expect(p.textContent).toContain('در حال شکل‌گیری (تأیید نشده)');
    expect(p.textContent).toContain('۳۶۰۰');
  });

  it('مبنایِ زمانیِ سریِ بسته و دلیلِ کمبودِ ماژور درِ رابط خوانده می‌شود', () => {
    render(<FtsTrendPanel data={majorFixture()} />);
    expect(screen.getByTestId('fts-trend-asof').textContent).toContain('۲۰۲۶-۱۰-۱۷');
    expect(screen.getByTestId('fts-trend-reason-w').textContent).toContain('ماژور');
  });

  it('رأیِ قطعی با بی‌ماژور بودنِ ماهانه عوض نمی‌شود (provisional فقط اطلاع است)', () => {
    const f = majorFixture();
    render(<FtsTrendPanel data={f} />);
    const panel = screen.getByTestId('fts-trend-panel');
    // همان Badgeِ روزانۀِ fixture (down) با رأیِ ماژورِ سرور یکی است؛ رابط هیچ
    // جهتِ تازه‌ای از `provisional` یا `confirmed_trend` نمی‌سازد.
    expect(panel.textContent).toContain('تحلیل ساختاری FTS');
    expect(f.trend!.D!.trend).toBe('down');
    expect(f.trend!.major_swings!.D!.confirmed_trend).toBe('up');
  });

  it('نطقۀِ zod پروندۀِ ماژور را دور نمی‌ریزد', () => {
    const parsed = FtsAnalysis.parse({ ...majorFixture(), trend: { ...majorFixture().trend } });
    expect(parsed.trend?.major_swings?.W?.counts?.major_highs).toBe(1);
    expect(parsed.trend?.major_swings?.W?.reason).toContain('ماژور');
    expect(parsed.trend?.major_swings?.D?.provisional?.high?.confirmed).toBe(false);
    expect(parsed.trend?.as_of).toBe('2026-10-17');
  });

  it('ساختارِ بدونِ پروندۀِ ماژور (payloadِ قدیمی) همانجا می‌شکند، نه با رأیِ تازه', () => {
    render(<FtsTrendPanel data={fixture()} />);
    expect(screen.queryByTestId('fts-major-counts-D')).toBeNull();
    expect(screen.queryByTestId('fts-provisional-D')).toBeNull();
    expect(screen.getByTestId('fts-trend-panel').textContent).toContain('روزانه');
  });
});
