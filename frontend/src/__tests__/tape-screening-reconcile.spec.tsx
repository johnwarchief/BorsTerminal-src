// __tests__/tape-screening-reconcile.spec.tsx — گاردِ «هماهنگی شمارندۀ تابلو و غربالگری» (گزینهٔ الف)
//
// چهار ادعا نگهبانی می‌شوند (بدونِ تغییرِ هیچ قاعدۀ FTS یا جامعۀ مجاز):
//   ۱) شمارۀ چیپِ تابلو تعدادِ واقعیِ نمادهایِ منطبق را در جامعۀ تابلو می‌شمرد و
//      نمادِ متوقف/ممنوع را برایِ برابرشدن با قیف کم نمی‌کند.
//   ۲) نمادی که فیلترِ تابلو را دارد ولی موتورِ غربالگری آن را candidate نمی‌گیرد،
//      برچسبِ «خارج از غربالگری» + علت می‌گیرد؛ نمادِ واجدِ شرایطِ بی‌فیلتر نه.
//   ۳) تنظیمِ «نمایشِ ردیفِ پسوندِ عددی»ِ تابلو، قاعدۀ پذیرشِ قیف را عوض نمی‌کند.
//   ۴) شمارنده‌ها با این توضیحات/فیلدهایِ جدید دست‌کاری نمی‌شوند (یکسان با و بدونِ
//      کلیدهایِ screening_*).
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeRow } from '@features/market/components/TapeTable';
import { countQuickMatches } from '@features/market/components/MarketFilters';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';

// ردیفی که از خانۀ «الگوی ساعت» پاس می‌گیرد: پرچمِ بک‌اند روشن و بی‌ورودیِ فرمول،
// پس `tapeFilterState` همان پرچم را داوری می‌کند (مسیرِ میراثی) — بجِ filter:true.
const row = (over: Record<string, unknown> = {}): MarketRow =>
  ({
    symbol: 'آزمون', name: 'شرکت آزمون', p_last: 1000, p_closing: 990,
    percent_change: 2, tvol: 1_000_000, z_tot_tran: 40, q_tot_cap: 5_000_000_000,
    vol_ratio: 1.4, buyer_power: 1.8, is_live: true, f_clock: true,
    ...over,
  }) as unknown as MarketRow;

const cfg = DEFAULT_TAPE_FILTER_CONFIG;

describe('۱ و ۴) شمارۀ چیپِ تابلو واقعی است و با فیلدهایِ غربالگری دست‌کاری نمی‌شود', () => {
  it('نمادِ منطبقِ «خارج از غربالگری» هم درِ شمارۀ چیپ می‌ماند (کم نمی‌شود)', () => {
    const rows = [
      row({ symbol: 'الف', screening_eligible: true }),
      row({ symbol: 'ب', screening_eligible: false, screening_exclusion_code: 'STOPPED', screening_exclusion_reason: 'متوقف: بلوکی' }),
    ];
    expect(countQuickMatches(rows, cfg, [], 'and').f_clock).toBe(2);
  });

  it('حذفِ کلیدهایِ screening_* شمارۀ چیپ را عوض نمی‌کند (توضیح، نمایشی است)', () => {
    const withFields = [
      row({ symbol: 'الف', screening_eligible: false, screening_exclusion_code: 'FORBIDDEN_STATE', screening_exclusion_reason: 'ممنوع' }),
      row({ symbol: 'ب', screening_eligible: true }),
    ];
    const stripped = withFields.map((r) => {
      const { screening_eligible, screening_exclusion_code, screening_exclusion_reason, ...rest } = r as Record<string, unknown>;
      void screening_eligible; void screening_exclusion_code; void screening_exclusion_reason;
      return rest as unknown as MarketRow;
    });
    expect(countQuickMatches(stripped, cfg, [], 'and').f_clock)
      .toBe(countQuickMatches(withFields, cfg, [], 'and').f_clock);
  });
});

describe('۲) برچسبِ «خارج از غربالگری» با علت', () => {
  it('نمادِ دارایِ فیلتر که موتور آن را candidate نمی‌گیرد ⇒ برچسب + علت', () => {
    render(<TapeRow row={row({ screening_eligible: false, screening_exclusion_code: 'STOPPED', screening_exclusion_reason: 'متوقف: مجامع' })} selected={false} onSelect={() => undefined} />);
    const badge = screen.getByTestId('badge-out-of-screening');
    expect(badge.textContent).toBe('خارج از غربالگری');
    expect(badge.getAttribute('title')).toContain('متوقف: مجامع');
  });

  it('نمادِ واجدِ شرایطِ بی‌فیلتر ⇒ برچسب نمی‌گیرد (فقط «فیلترِ تابلو را دارند»)', () => {
    render(<TapeRow row={row({ f_clock: false, screening_eligible: false, screening_exclusion_code: 'FORBIDDEN_STATE', screening_exclusion_reason: 'ممنوع‌المعامله' })} selected={false} onSelect={() => undefined} />);
    expect(screen.queryByTestId('badge-out-of-screening')).toBeNull();
  });

  it('نمادِ منطبقِ داخلِ غربالگری ⇒ برچسب نمی‌گیرد', () => {
    render(<TapeRow row={row({ screening_eligible: true })} selected={false} onSelect={() => undefined} />);
    expect(screen.queryByTestId('badge-out-of-screening')).toBeNull();
  });

  it('بی‌اطلاعی (پاسخِ قدیمی، کلید نیامده) ⇒ برچسب نمی‌زند، نه «خارج»', () => {
    render(<TapeRow row={row()} selected={false} onSelect={() => undefined} />);
    expect(screen.queryByTestId('badge-out-of-screening')).toBeNull();
  });
});

describe('۳) تنظیمِ پسوندِ عددیِ تابلو قاعدۀ پذیرشِ قیف را عوض نمی‌کند', () => {
  it('تغییرِ showNumericSuffix مقدارِ dropSuffixِ قیف را دست نمی‌زند', () => {
    const funnelBefore = useFunnelPrefsStore.getState().dropSuffix;
    const tapeBefore = useTapeStore.getState().showNumericSuffix;
    useTapeStore.getState().setShowNumericSuffix(!tapeBefore);
    expect(useFunnelPrefsStore.getState().dropSuffix).toBe(funnelBefore);
    // و برعکس: تغییرِ قیف، تنظیمِ تابلو را عوض نمی‌کند
    const tapeNow = useTapeStore.getState().showNumericSuffix;
    useFunnelPrefsStore.getState().setDropSuffix(!funnelBefore);
    expect(useTapeStore.getState().showNumericSuffix).toBe(tapeNow);
    // بازگرداندنِ وضعیتِ store تا آزمونِ دیگری آلوده نشود
    useTapeStore.getState().setShowNumericSuffix(tapeBefore);
    useFunnelPrefsStore.getState().setDropSuffix(funnelBefore);
  });
});
