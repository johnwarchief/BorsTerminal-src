// __tests__/tape-algorithms-settings.spec.tsx -- تست‌های اعتبارسنجی الگوریتم‌های شخصی‌سازی تابلو
import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { MarketRow } from '@shared/types/marketRow';
import {
  DEFAULT_TAPE_FILTER_CONFIG,
  TAPE_PRESETS,
  isConfigCustomized,
  matchClockPattern,
  matchJetFilter,
  matchNoqtehFilter,
  matchSuspiciousVolume,
} from '@features/market/lib/tapeAlgorithms';
import { TapeFilterSettingsModal } from '@features/market/components/TapeFilterSettingsModal';
import { useTapeStore } from '@features/market/stores/tapeStore';

const mockRow = (overrides: Partial<MarketRow> = {}): MarketRow => ({
  symbol: 'تست',
  p_closing: 1000,
  p_last: 1020,
  price_yesterday: 990,
  percent_change: 1.0,
  q_tot_tran: 3000000,
  z_tot_tran: 100,
  month_avg_vol: 1000000,
  prev_day_vol: 1000000,
  tvol: 3000000,
  vol_ratio: 3.0,
  vol_dod: 3.0,
  buyer_power: 2.0,
  p_min: 980,
  min30_low: 975,
  h5_max: 1010,
  h9_max: 1030,
  h19_max: 1050,
  ...overrides,
});

describe('الگوریتم‌های پویا و شخصی‌سازی فیلترهای تابلو', () => {
  it('الگوی ساعت با دلتای شخصی‌سازی‌شده و ساعت طلایی', () => {
    const row = mockRow({ p_closing: 1000, p_last: 1015, price_yesterday: 1010 });
    // دلتای ۱.۵٪
    expect(matchClockPattern(row, { minDeltaPct: 1.0, requireGoldenHour: false, minVolRatio: 1.0, minTradeCount: 30 })).toBe(true);
    expect(matchClockPattern(row, { minDeltaPct: 2.0, requireGoldenHour: false, minVolRatio: 1.0, minTradeCount: 30 })).toBe(false);

    // شرط ساعت طلایی (پایانی زیر دیروز و آخرین بالای دیروز)
    const goldenRow = mockRow({ p_closing: 990, p_last: 1010, price_yesterday: 1000 });
    expect(matchClockPattern(goldenRow, { minDeltaPct: 1.0, requireGoldenHour: true, minVolRatio: 1.0, minTradeCount: 30 })).toBe(true);

    const nonGoldenRow = mockRow({ p_closing: 1010, p_last: 1025, price_yesterday: 1000 });
    expect(matchClockPattern(nonGoldenRow, { minDeltaPct: 1.0, requireGoldenHour: true, minVolRatio: 1.0, minTradeCount: 30 })).toBe(false);
  });

  it('حجم مشکوک با تایم‌فریم‌های ۳۰ روزه و روز قبل (DoD)', () => {
    const row = mockRow({ vol_ratio: 3.5, vol_dod: 1.5, z_tot_tran: 100 });
    // بر مبنای ۳۰ روزه
    expect(matchSuspiciousVolume(row, { timeframe: 'monthly_30d', minRatio: 3.0, minTradeCount: 50 })).toBe(true);
    // بر مبنای روز قبل (DoD)
    expect(matchSuspiciousVolume(row, { timeframe: 'prev_day_dod', minRatio: 2.0, minTradeCount: 50 })).toBe(false);
  });

  it('فیلتر جت با تایم‌فریم‌های مختلف شکست سقف (Lookback High)', () => {
    // قیمت ۱۰۰۰: بالای سقف ۵ روزه (۹۹۰) اما زیر سقف ۱۹ روزه (۱۰۵۰)
    const row = mockRow({ p_closing: 1000, p_last: 1010, h5_max: 990, h19_max: 1050, buyer_power: 2.0, vol_ratio: 3.0 });
    
    // در تایم‌فریم ۵ روزه شکست رخ داده است
    expect(matchJetFilter(row, { lookbackDays: 5, minBuyerPower: 1.5, minVolRatio: 2.0, requireLastAboveClose: true, minChangePct: 0 })).toBe(true);
    // در تایم‌فریم ۱۹ روزه هنوز سقف شکسته نشده است
    expect(matchJetFilter(row, { lookbackDays: 19, minBuyerPower: 1.5, minVolRatio: 2.0, requireLastAboveClose: true, minChangePct: 0 })).toBe(false);
  });

  it('نقطه‌زنی با آستانه فاصله از کف ۳۰ روزه', () => {
    // کف ۹۷۵، قیمت ۱۰۰۰ → فاصله ۲.۵٪
    const row = mockRow({ p_closing: 1000, min30_low: 975, vol_ratio: 1.5, z_tot_tran: 50 });
    expect(matchNoqtehFilter(row, { maxDistPct: 3.0, minTradeCount: 5, minVolRatio: 1.0 })).toBe(true);
    expect(matchNoqtehFilter(row, { maxDistPct: 2.0, minTradeCount: 5, minVolRatio: 1.0 })).toBe(false);
  });

  it('تشخیص شخصی‌سازی کانفیگ', () => {
    expect(isConfigCustomized(DEFAULT_TAPE_FILTER_CONFIG)).toBe(false);
    expect(isConfigCustomized(TAPE_PRESETS.scalp.config)).toBe(true);
  });
});

describe('مدال تنظیمات شخصی‌سازی فیلترها (TapeFilterSettingsModal)', () => {
  beforeEach(() => {
    useTapeStore.getState().resetTapeFilterConfig();
  });

  it('اعمال پریست استراتژی آماده از مدال', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    expect(screen.getByText('⚙️ تنظیمات فیلترها')).toBeInTheDocument();
    
    // کلیک روی پریست نوسان‌گیری سریع
    fireEvent.click(screen.getByText('نوسان‌گیری سریع و ساعت قوی'));
    const current = useTapeStore.getState().tapeFilterConfig;
    expect(current.clock.minDeltaPct).toBe(1.5);
    expect(current.jet.lookbackDays).toBe(5);
  });

  it('تغییر مستقیم پارامتر ساعت در تب ساعت', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('⏰ الگوی ساعت'));
    
    expect(screen.getByText('فقط ساعت طلایی (پایانی منفی و آخرین مثبت)')).toBeInTheDocument();
    const goldenBox = screen.getByRole('checkbox', { name: /فقط ساعت طلایی/ });
    fireEvent.click(goldenBox);

    expect(useTapeStore.getState().tapeFilterConfig.clock.requireGoldenHour).toBe(true);
  });

  it('تغییر تایم‌فریم شکست سقف جت به دوره‌های متنوع', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('🚀 فیلتر جت (سقف)'));

    expect(screen.getByText('تایم‌فریم شکست سقف قیمتی (Lookback High)')).toBeInTheDocument();
    expect(screen.getByText('۱ روزه')).toBeInTheDocument();
    expect(screen.getByText('۵۰ روزه')).toBeInTheDocument();
    expect(screen.getByText('۶۰ روزه')).toBeInTheDocument();

    fireEvent.click(screen.getByText('۶۰ روزه'));
    expect(useTapeStore.getState().tapeFilterConfig.jet.lookbackDays).toBe(59);

    fireEvent.click(screen.getByText('۱ روزه'));
    expect(useTapeStore.getState().tapeFilterConfig.jet.lookbackDays).toBe(1);
  });
});
