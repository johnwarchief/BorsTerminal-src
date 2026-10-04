// دو فیلترِ تازۀ فایل درِ رابط — ادعایِ اصلی: **یک داوری**. رابط هیچ‌وقت با
// فرمولِ خودِ‌اش «پول هوشمند» نمی‌سازد؛ فقط پرچمِ tape_flags.py را می‌خواند.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarketFilters } from '@features/market/components/MarketFilters';
import {
  DEFAULT_TAPE_FILTER_CONFIG,
  tapeFilterVerdict,
} from '@features/market/lib/tapeAlgorithms';
import { patternBadges } from '@features/market/lib/tapeBadges';
import type { MarketRow } from '@shared/types/marketRow';

const cfg = DEFAULT_TAPE_FILTER_CONFIG;

const base = {
  symbol: 'آزمون', is_live: true, hist_sessions: 60, prior30_vol: 30_000_000,
  tvol: 4_000_000, vol_ratio_file: 4, p_closing: 1000, p_last: 1025,
  percent_last: 4.6, z_tot_tran: 120, buyer_power: 2.4, month_avg_vol: 1_000_000,
  f_clock: false, f_susp: false, f_jet: false, f_roobi: false, f_noqteh: false,
  f_smart: false, f_legal: false,
} as unknown as MarketRow;

const MATCHES = {
  f_clock: 0, f_susp: 0, f_jet: 0, f_roobi: 0, f_noqteh: 0, f_smart: 3, f_legal: 1,
};

describe('پول هوشمند و کد به کد — داوریِ واحد درِ رابط', () => {
  it('داوری عینِ پرچم است؛ نه فرمولِ دوم، نه جهتِ اعداد', () => {
    expect(tapeFilterVerdict({ ...base, f_smart: true }, 'f_smart', cfg)).toBe(true);
    // ردیفی که ریاضی‌اش «شبیه» پول هوشمند است ولی پرچم ندارد ⇒ رد — آینه‌ای درِ کار نیست
    expect(tapeFilterVerdict({ ...base, buyer_power: 99, vol_ratio_file: 99 }, 'f_smart', cfg)).toBe(false);
    expect(tapeFilterVerdict({ ...base, f_legal: true }, 'f_legal', cfg)).toBe(true);
    // پنلِ بی‌ستون‌هایِ فرمول (hasTapeFormulaInputs=false) هم همین مسیر را می‌رود
    expect(tapeFilterVerdict({ f_smart: true } as MarketRow, 'f_smart', cfg)).toBe(true);
    // فسیلِ بیرونِ تابلو هیچ‌وقت قبول نیست (دروازۀ zنده، عینِ پنجگانۀ فایل)
    expect(tapeFilterVerdict({ ...base, f_smart: true, is_live: false }, 'f_smart', cfg)).toBe(false);
  });

  it('بج‌ها از همان پرچم می‌آیند — چیپ و بج یکی‌اند', () => {
    const labels = patternBadges({ ...base, f_smart: true, f_legal: true }, cfg).map((b) => b.label);
    expect(labels).toContain('پول هوشمند');
    expect(labels).toContain('کد به کد');
    // ردیفِ بی‌پرچم هیچ‌کدام را نمی‌گیرد، با این‌که ارقامش شبیه است
    expect(patternBadges(base, cfg).map((b) => b.label)).not.toContain('پول هوشمند');
  });

  it('چیپ‌ها درِ نوارِ فیلتر رندر می‌شوند و چرخ‌دندۀ بی‌محتوا ندارند', () => {
    render(<MarketFilters sectors={[]} matches={MATCHES} />);
    expect(screen.getByText(/ورود پول هوشمند/)).toBeInTheDocument();
    expect(screen.getByText(/کد به کد حقوقی به حقیقی/)).toBeInTheDocument();
    expect(screen.queryByLabelText('تنظیمات ورود پول هوشمند')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('تنظیمات کد به کد حقوقی به حقیقی')).not.toBeInTheDocument();
    // مقایسه: فیلترِ تنظیم‌شدنی چرخ‌دنده دارد و این، ادعایِ «بی‌دکمهٔ جعلی» را معنادار می‌کند
    expect(screen.getByLabelText('تنظیمات الگوی ساعت')).toBeInTheDocument();
  });
});
