// RA-3: همسنجیِ دو نماد رویِ همان چارت — مبنایِ بازدهی، ثبتِ مطالعه و نوارِ ابزار
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { comparePctLabel, compareRows } from '@features/technical/lib/compareSeries';
import {
  COMPARE_INDICATOR,
  getCompareRows,
  registerCompareIndicator,
  setCompareRows,
} from '@features/technical/lib/compareIndicator';
import { FtsToolbar } from '@features/technical/nahayatnegar/components/FtsToolbar';

const bar = (timestamp: number, close: number) => ({
  timestamp,
  open: close,
  high: close,
  low: close,
  close,
});

const D = 24 * 60 * 60 * 1000;
const t0 = Date.parse('2026-01-05T00:00:00Z');
const t1 = t0 + D;
const t2 = t0 + 2 * D;

describe('مبنایِ همسنجی', () => {
  it('هر دو خط در میلهٔ مبنا ۱۰۰اند و اختلافِ بعدی یعنی اختلافِ بازدهی', () => {
    const main = [bar(t0, 1000), bar(t1, 1100), bar(t2, 1210)];
    const other = [bar(t0, 500), bar(t1, 500), bar(t2, 550)];
    const out = compareRows(main, other);
    expect(out.rows).toHaveLength(3);
    expect(out.rows[0]).toEqual({ self: 100, other: 100 });
    // نمادِ اول ۱۰٪، نمادِ دوم صفرِ درصد در میلهٔ دوم
    expect(out.rows[1].self).toBeCloseTo(110, 6);
    expect(out.rows[1].other).toBeCloseTo(100, 6);
    expect(out.selfChangePct).toBeCloseTo(21, 6);
    expect(out.otherChangePct).toBeCloseTo(10, 6);
    expect(out.commonBars).toBe(3);
  });

  it('میله‌ای که نمادِ دوم در آن بسته نشده عددِ ساختگی نمی‌گیرد', () => {
    const main = [bar(t0, 1000), bar(t1, 1100), bar(t2, 1210)];
    const other = [bar(t0, 500), bar(t2, 550)];
    const out = compareRows(main, other);
    expect(out.rows[1].other).toBeUndefined();
    // خودِ سریِ اصلی در همان میله هست؛ فقط خطِ همسنج می‌شکند
    expect(out.rows[1].self).toBeCloseTo(110, 6);
    expect(out.commonBars).toBe(2);
  });

  it('مبنا نخستین میلهٔ مشترک است، نه نخستین میلهٔ چارت', () => {
    const main = [bar(t0, 1000), bar(t1, 1100), bar(t2, 1210)];
    const other = [bar(t1, 500), bar(t2, 600)];
    const out = compareRows(main, other);
    expect(out.rows[0].other).toBeUndefined();
    expect(out.rows[1].other).toBeCloseTo(100, 6);
    expect(out.otherChangePct).toBeCloseTo(20, 6);
  });

  it('کمتر از دو میلهٔ مشترک ⇒ درصدی نشان داده نمی‌شود، نه صفر', () => {
    const out = compareRows([bar(t0, 1000), bar(t1, 1100)], [bar(t0, 500)]);
    expect(out.commonBars).toBeLessThan(2);
    expect(out.selfChangePct).toBeNull();
    expect(out.otherChangePct).toBeNull();
    expect(comparePctLabel(out.otherChangePct)).toBe('—');
  });

  it('قیمتِ صفر یا بی‌اعتبار در هیچ‌کدام از دو سری مبنای تقسیم نمی‌شود', () => {
    const out = compareRows([bar(t0, 0), bar(t1, 1100)], [bar(t0, 500), bar(t1, 500)]);
    expect(out.rows[0].self).toBeUndefined();
    expect(out.rows[1].self).toBeCloseTo(100, 6);
    expect(out.commonBars).toBe(1);
  });

  it('برچسبِ درصد علامت و رقمِ فارسی دارد', () => {
    expect(comparePctLabel(12.34)).toBe('+۱۲.۳٪');
    expect(comparePctLabel(-3)).toBe('−۳.۰٪');
    expect(comparePctLabel(0)).toBe('۰.۰٪');
  });

  it('مبنایِ خواسته‌شده از ابتدایِ دید گرفته می‌شود، نه اولِ تاریخچه', () => {
    const main = [bar(t0, 1000), bar(t1, 1100), bar(t2, 1210)];
    const other = [bar(t0, 500), bar(t1, 500), bar(t2, 550)];
    const out = compareRows(main, other, t1);
    expect(out.anchorTimestamp).toBe(t1);
    expect(out.rows[1]).toEqual({ self: 100, other: 100 });
    // از میلهٔ t1: این نماد ۱۰٪ و همسنج ۱۰٪ ⇒ نسبتِ بازدهی صفر، نه تفاضلِ دو درصد
    expect(out.relativePct).toBeCloseTo(0, 6);
  });

  it('نسبتِ بازدهی خواناست نه تفاضلِ دو درصدِ بی‌سابقه', () => {
    const main = [bar(t0, 100), bar(t1, 100)];
    const other = [bar(t0, 100), bar(t1, 105)];
    const out = compareRows(main, other);
    expect(out.selfChangePct).toBeCloseTo(0, 6);
    expect(out.otherChangePct).toBeCloseTo(5, 6);
    expect(out.relativePct).toBeCloseTo(5, 6);
  });

  it('میلهٔ خواسته‌شده اگر مشترک نباشد، نخستین میلهٔ مشترک مبنا می‌ماند', () => {
    const main = [bar(t0, 1000), bar(t1, 1100), bar(t2, 1210)];
    const other = [bar(t1, 500), bar(t2, 600)];
    const out = compareRows(main, other, t2 + D);
    expect(out.anchorTimestamp).toBe(t1);
    expect(out.rows[1].other).toBeCloseTo(100, 6);
  });
});

describe('ثبتِ مطالعهٔ همسنج', () => {
  it('یک‌بار ثبت می‌شود و فراخوانیِ دوباره ثبتِ تکراری نمی‌سازد', () => {
    const registered: unknown[] = [];
    const api = {
      registerIndicator: (d: unknown) => registered.push(d),
      getSupportedIndicators: () => [] as string[],
    };
    expect(registerCompareIndicator(api)).toBe(true);
    expect(registerCompareIndicator({ ...api, getSupportedIndicators: () => [COMPARE_INDICATOR] })).toBe(true);
    expect(registered).toHaveLength(1);
    const def = registered[0] as {
      name: string;
      figures: { key: string; styles: unknown }[];
      calc: () => unknown[];
    };
    expect(def.name).toBe(COMPARE_INDICATOR);
    expect(def.figures.map((f) => f.key)).toEqual(['self', 'other']);
    // کرشِ زنده: klinecharts v10 styles را صدا می‌زند (figure.styles.call(...))؛
    // شیءِ ساده یعنی «l.call is not a function» روی چارتِ کاربر
    for (const f of def.figures) {
      expect(typeof f.styles).toBe('function');
      expect((f.styles as () => { color: string })()).toEqual(
        expect.objectContaining({ color: expect.any(String) }),
      );
    }
    setCompareRows([{ self: 100, other: 105 }]);
    expect(def.calc()).toEqual([{ self: 100, other: 105 }]);
    expect(getCompareRows()).toHaveLength(1);
  });

  it('موتورِ بی‌registerIndicator خطا نمی‌دهد، فقط همسنجی خاموش می‌شود', () => {
    expect(() =>
      registerCompareIndicator({
        registerIndicator: () => {
          throw new Error('ثبت ممکن نیست');
        },
      }),
    ).not.toThrow();
  });
});

describe('دکمهٔ همسنجی در نوارِ ابزار', () => {
  const base = {
    symbolName: 'فولاد',
    companyName: 'فولاد مبارکه',
    onOpenSymbolSearch: () => {},
    activeTimeframe: 'D' as const,
    onTimeframeChange: () => {},
    activeCandleType: 'candle_solid',
    onCandleTypeChange: () => {},
    activeAdjustment: 'combined' as const,
    onAdjustmentChange: () => {},
    onOpenIndicators: () => {},
    isFtsActive: false,
    onToggleFts: () => {},
    isFullscreen: false,
    onToggleFullscreen: () => {},
  };

  it('بی‌همسنج یک دکمه است، با همسنج نامِ نمادِ دوم و دکمهٔ برداشتن', () => {
    const onOpen = vi.fn();
    const onClear = vi.fn();
    const { rerender } = render(<FtsToolbar {...base} onOpenCompareSearch={onOpen} onClearCompare={onClear} />);
    fireEvent.click(screen.getByTestId('compare-open'));
    expect(onOpen).toHaveBeenCalledTimes(1);

    rerender(
      <FtsToolbar
        {...base}
        compareSymbol="شپنا"
        onOpenCompareSearch={onOpen}
        onClearCompare={onClear}
      />,
    );
    expect(screen.getByTestId('compare-chip').textContent).toContain('شپنا');
    fireEvent.click(screen.getByTestId('compare-clear'));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('اختلافِ بازدهی به فارسی روی چیپ خوانده می‌شود', () => {
    render(
      <FtsToolbar
        {...base}
        compareSymbol="شپنا"
        compareGap="+۴.۲٪"
        onOpenCompareSearch={() => {}}
        onClearCompare={() => {}}
      />,
    );
    expect(screen.getByTestId('compare-gap').textContent).toBe('+۴.۲٪');
  });

  it('بی‌میلهٔ مشترک صادقانه گفته می‌شود، نه یک خطِ ساختگی', () => {
    render(
      <FtsToolbar
        {...base}
        compareSymbol="شپنا"
        compareNoOverlap
        compareGap="+۴.۲٪"
        onOpenCompareSearch={() => {}}
        onClearCompare={() => {}}
      />,
    );
    expect(screen.getByTestId('compare-no-overlap').textContent).toContain('مشترک');
    expect(screen.queryByTestId('compare-gap')).toBeNull();
  });
});
