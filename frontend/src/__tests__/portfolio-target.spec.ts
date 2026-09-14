// تست پرتفوی هدف: دونات، نرمال‌سازی، ویرایش/بازنشانی، نوار دلتا
import { describe, expect, it } from 'vitest';
import {
  FTS_DEFAULT_TARGETS,
  buildDelta,
  isValidAllocation,
  normalizePct,
  sumPct,
} from '@features/portfolio/stores/targetAllocation';
import { donutSegments } from '@features/portfolio/components/TargetDonut';
import { deltaLabel, deltaTone } from '@features/portfolio/components/DeltaBar';

describe('طبقات پیش‌فرض FTS', () => {
  it('شش طبقه با جمع دقیق ۱۰۰٪', () => {
    expect(FTS_DEFAULT_TARGETS).toHaveLength(6);
    const total = sumPct(FTS_DEFAULT_TARGETS);
    expect(total).toBeCloseTo(100, 5);
  });

  it('تفکیک استاندارد طلا: فیزیکی ۲۵٪ + صندوق/گواهی ۲۰٪', () => {
    const gold = FTS_DEFAULT_TARGETS.find((c) => c.id === 'gold');
    const cert = FTS_DEFAULT_TARGETS.find((c) => c.id === 'gold-cert');
    expect(gold).toBeDefined();
    expect(gold!.pct).toBe(25);
    expect(gold!.label).toBe('طلای فیزیکی، سکه و شمش');
    expect(cert).toBeDefined();
    expect(cert!.pct).toBe(20);
    expect(cert!.label).toBe('صندوق‌ها و گواهی سپردهٔ طلا');
  });

  it('سقف سهام طبق فرمول ریسک سیستماتیک (طبقه equity ۱۵٪)', () => {
    const equity = FTS_DEFAULT_TARGETS.find((c) => c.id === 'equity');
    expect(equity).toBeDefined();
    expect(equity!.pct).toBe(15);
    expect(equity!.hint).toContain('۲۰');
  });

  it('سایر طبقات: ارز ۱۵٪ · نقره ۱۰٪ · درآمد ثابت ۱۵٪', () => {
    expect(FTS_DEFAULT_TARGETS.find((c) => c.id === 'crypto')!.pct).toBe(15);
    expect(FTS_DEFAULT_TARGETS.find((c) => c.id === 'silver')!.pct).toBe(10);
    expect(FTS_DEFAULT_TARGETS.find((c) => c.id === 'fixed')!.pct).toBe(15);
  });
});

describe('نرمال‌سازی و اعتبارسنجی', () => {
  it('جمع بالای ۱۰۰ به ۱۰۰ نرمال می شود', () => {
    const norm = normalizePct([
      { id: 'a', label: 'A', pct: 60, color: '#000' },
      { id: 'b', label: 'B', pct: 60, color: '#111' },
    ]);
    expect(sumPct(norm)).toBeCloseTo(100, 1);
    expect(norm[0].pct).toBeCloseTo(50, 1);
  });

  it('جمع زیر ۱۰۰ به ۱۰۰ نرمال می شود (بازه شروع پیش‌فرض)', () => {
    const norm = normalizePct([
      { id: 'a', label: 'A', pct: 30, color: '#000' },
      { id: 'b', label: 'B', pct: 30, color: '#111' },
    ]);
    expect(sumPct(norm)).toBeCloseTo(100, 1);
    expect(norm[0].pct).toBeCloseTo(50, 1);
  });

  it('جمع ۱۰۰ دست‌نخورده می ماند', () => {
    const input = [
      { id: 'a', label: 'A', pct: 40, color: '#000' },
      { id: 'b', label: 'B', pct: 60, color: '#111' },
    ];
    expect(normalizePct(input).map((c) => c.pct)).toEqual([40, 60]);
  });

  it('جمع صفر ⇒ بازگشت به پیش‌فرض FTS', () => {
    const norm = normalizePct([{ id: 'a', label: 'A', pct: 0, color: '#000' }]);
    expect(norm).toHaveLength(6);
    expect(sumPct(norm)).toBeCloseTo(100, 5);
  });

  it('اعتبارسنجی: جمع ۰ رد، جمع ۱۰۰ قبول، جمع ۱۰۵ رد', () => {
    expect(isValidAllocation([{ id: 'a', label: 'A', pct: 0, color: '#000' }])).toBe(false);
    expect(isValidAllocation(FTS_DEFAULT_TARGETS)).toBe(true);
    expect(isValidAllocation([{ id: 'a', label: 'A', pct: 60, color: '#000' }, { id: 'b', label: 'B', pct: 60, color: '#111' }])).toBe(false);
  });
});

describe('چارت دونات (SVG خالص)', () => {
  it('قطعه‌های مثبت ساخته می شوند و صفرها حذف', () => {
    const segs = donutSegments([
      { id: 'a', label: 'A', pct: 30, color: '#000' },
      { id: 'b', label: 'B', pct: 0, color: '#111' },
      { id: 'c', label: 'C', pct: 15, color: '#222' },
    ]);
    expect(segs).toHaveLength(2);
    expect(segs[0].pct).toBe(30);
  });

  it('درصد نامعتبر (NaN/منفی) حذف می شود', () => {
    const segs = donutSegments([
      { id: 'a', label: 'A', pct: Number.NaN, color: '#000' },
      { id: 'b', label: 'B', pct: -5, color: '#111' },
      { id: 'c', label: 'C', pct: 10, color: '#222' },
    ]);
    expect(segs).toHaveLength(1);
  });
});

describe('نوار شکاف و ری‌بالانس (Delta)', () => {
  it('مازاد مثبت ⇒ فروش سبز', () => {
    expect(deltaTone(5)).toBe('green');
    expect(deltaLabel(5)).toContain('فروش');
    expect(deltaLabel(5)).toContain('۵');
  });

  it('کسری منفی ⇒ خرید قرمز', () => {
    expect(deltaTone(-5)).toBe('red');
    expect(deltaLabel(-5)).toContain('خرید');
  });

  it('نزدیک صفر ⇒ در هدف', () => {
    expect(deltaTone(0)).toBe('gray');
    expect(deltaLabel(0)).toBe('در هدف');
  });

  it('دلتای طبقه سهام از وزن سبد واقعی ساخته می شود', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [
      { weight_eff_pct: 6 },
      { weight_eff_pct: 4 },
      { weight_eff_pct: 5 },
      { weight_eff_pct: null },
    ]);
    const eq = rows.find((r) => r.id === 'equity');
    expect(eq).toBeDefined();
    expect(eq!.currentPct).toBe(15);
    // هدف سهام ۱۵ ⇒ دلتا صفر
    expect(eq!.delta).toBe(0);
  });

  it('سبد خالی ⇒ کسری کامل طبقه سهام', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, []);
    const eq = rows.find((r) => r.id === 'equity');
    expect(eq!.currentPct).toBe(0);
    expect(eq!.delta).toBeLessThan(0);
  });

  it('سایر طبقات بدون داده فعلی ⇒ کسری کامل نسبت به هدف', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [{ weight_eff_pct: 10 }]);
    const gold = rows.find((r) => r.id === 'gold');
    expect(gold!.currentPct).toBe(0);
    expect(gold!.delta).toBe(-gold!.targetPct);
  });
});
