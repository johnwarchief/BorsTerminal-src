// تست یکپارچه فیلتر نوع دارایی: خروج خودکار مشتقه‌ها از لیست‌های الگو در حالت پیش‌فرض ۵تایی
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { SuspiciousPanel } from '@features/market/components/SuspiciousPanel';
import { applyFilters } from '@features/market/routes/MarketPage';
import { ASSET_TYPES } from '@features/market/lib/assetType';
import { DEFAULT_ASSET_TYPES, useTapeStore } from '@features/market/stores/tapeStore';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'فولاد',
    name: 'فولاد مبارکه',
    sector_name: 'فرآوری مواد معدنی',
    board: 1,
    percent_change: 2.5,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 5,
    vol_ratio_file: 5,   // قیدِ پنلِ حجم مشکوک مبناءِ فایل است
    p_last: 1000,
    p_closing: 1030,
    price_yesterday: 1010,
    z_tot_tran: 120,
    is_live: true,
    f_clock: true,
    f_susp: true,
    ...patch,
  } as MarketRow;
}

const stock = row();
const option = row({ symbol: 'ضفولاد', name: 'اختیار فولاد', sector_name: 'اختیار' });
const bond = row({ symbol: 'اخزا001', name: 'اوراق اخزا', sector_name: 'اوراق تامين' });
const rows = [stock, option, bond];

describe('خروج مشتقه‌ها از لیست‌های تابلو با پیش‌فرض ۵تایی', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  it('applyFilters با پیش‌فرض استور فقط سهام/پایه/حق تقدم/انرژی/صندوق را نگه می‌دارد', () => {
    const state = useTapeStore.getState();
    expect(state.assetTypes).toEqual(DEFAULT_ASSET_TYPES);
    const kept = applyFilters(rows, '', state.assetTypes, [], '', false, 'all', false, 3, false);
    expect(kept.map((r) => r.symbol)).toEqual(['فولاد']);
  });

  it('آرایهٔ خالی یعنی «هیچ» (رفع semantics قدیمی «همه») و مجموعهٔ کامل یعنی همهٔ ۱۱ نماد', () => {
    expect(applyFilters(rows, '', [], [], '', false, 'all', false, 3, false)).toEqual([]);
    const all = applyFilters(rows, '', [...ASSET_TYPES], [], '', false, 'all', false, 3, false);
    expect(all.map((r) => r.symbol)).toEqual(['فولاد', 'ضفولاد', 'اخزا001']);
  });

  it('پنل الگوی ساعت/حجم مشکوک روی ردیف‌های فیلترشده، اختیار معامله را نشان نمی‌دهد', () => {
    const state = useTapeStore.getState();
    const filtered = applyFilters(rows, '', state.assetTypes, [], '', false, 'all', false, 3, false);
    render(<SuspiciousPanel rows={filtered} onSelect={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.some((b) => b.textContent?.includes('ضفولاد'))).toBe(false);
    expect(buttons.some((b) => b.textContent?.includes('اخزا'))).toBe(false);
    expect(buttons.some((b) => b.textContent?.includes('فولاد مبارکه'))).toBe(true);
  });

  it('بدون فیلتر نوع، همان پنل نماد اختیار را نشان می‌دهد (تطبیق منفی)', () => {
    render(<SuspiciousPanel rows={rows} onSelect={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.some((b) => b.textContent?.includes('ضفولاد'))).toBe(true);
  });
});
