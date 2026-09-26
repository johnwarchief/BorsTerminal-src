// تست سیگنال تابلو: تطابق قرارداد و سناریوهای روز عادی و دستکاری شده
import { describe, expect, it } from 'vitest';
import { BaseSignal, TapePayload } from '@contracts/index';
import type { MarketRow } from '@shared/types/marketRow';
import { rowToTapeSignals, rowsToTapeSignals } from '@features/market/signals/tapeSignals';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  const merged: Partial<MarketRow> = {
    symbol: 'شپنا',
    p_last: 1000,
    p_closing: 1002,
    tvol: 800_000,
    month_avg_vol: 1_000_000,
    z_tot_tran: 120,
    buy_i_vol: 500,
    buy_count_i: 10,
    sell_i_vol: 500,
    sell_count_i: 10,
    ...patch,
  };
  // بک‌اند نسبتِ فایل را می‌سازد و فیلترها همان را می‌خوانند؛ در تست هم نسبت
  // از همان tvol/month_avg_vol ساخته می‌شود تا سناریوها با حجم رانده شوند.
  const tvol = merged.tvol as number;
  const avg = merged.month_avg_vol as number;
  return { ...merged, vol_ratio_file: (merged.vol_ratio_file as number) ?? tvol / avg } as MarketRow;
}

describe('سیگنال تابلو', () => {
  it('روز عادی هیچ سیگنالی ندارد', () => {
    expect(rowToTapeSignals(row(), 1726000000000)).toEqual([]);
  });

  it('الگوی ساعت با حمایت سرانه سیگنال صعودی با اعتماد بالا می دهد', () => {
    const signals = rowToTapeSignals(
      row({ p_last: 1025, p_closing: 1000, tvol: 1_200_000, buy_i_vol: 2000, buy_count_i: 10, sell_i_vol: 500, sell_count_i: 10 }),
      1726000000000,
    );
    const clock = signals.filter((s) => s.payload.pattern === 'closing_auction_pop');
    expect(clock).toHaveLength(1);
    expect(clock[0].direction).toBe('bullish');
    expect(clock[0].confidence).toBe('high');
    expect(clock[0].agentId).toBe('tape');
    expect(clock[0].sourceView).toBe('market');
    expect(clock[0].score).toBeGreaterThanOrEqual(0);
    expect(clock[0].score).toBeLessThanOrEqual(100);
    expect(clock[0].rationale.length).toBeGreaterThan(4);
  });

  it('الگوی ساعت بدون سرانه اعتماد متوسط می گیرد', () => {
    const signals = rowToTapeSignals(row({ p_last: 1025, p_closing: 1000, tvol: 1_200_000, buy_count_i: 0 }), 1726000000000);
    const clock = signals.filter((s) => s.payload.pattern === 'closing_auction_pop');
    expect(clock).toHaveLength(1);
    expect(clock[0].confidence).toBe('medium');
  });

  it('حجم مشکوک سیگنال خنثی می دهد', () => {
    const signals = rowToTapeSignals(row({ tvol: 5_000_000 }), 1726000000000);
    const susp = signals.filter((s) => s.payload.pattern === 'suspicious_volume');
    expect(susp).toHaveLength(1);
    expect(susp[0].direction).toBe('neutral');
  });

  it('همه سیگنال ها از اسکیمای قرارداد رد می شوند', () => {
    const signals = rowsToTapeSignals(
      [
        row({ symbol: 'شپنا', p_closing: 1025, buy_i_vol: 2000, buy_count_i: 10, sell_i_vol: 500, sell_count_i: 10 }),
        row({ symbol: 'فولاد', tvol: 5_000_000 }),
        row({ symbol: 'خودرو' }),
      ],
      1726000000000,
    );
    expect(signals.length).toBeGreaterThan(0);
    const ids = new Set(signals.map((s) => s.id));
    expect(ids.size).toBe(signals.length);
    for (const s of signals) {
      expect(BaseSignal.safeParse(s).success).toBe(true);
      expect(TapePayload.safeParse(s.payload).success).toBe(true);
    }
  });

  it('ردیف بدون نماد نادیده گرفته می شود', () => {
    expect(rowToTapeSignals({ ...row(), symbol: '' })).toEqual([]);
  });
});
