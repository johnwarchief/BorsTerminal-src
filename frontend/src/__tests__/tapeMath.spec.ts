// تست ریاضیات تابلو: سرانه و الگوی ساعت و حجم مشکوک
import { describe, expect, it } from 'vitest';
import {
  buyerPowerRatio,
  closingGap,
  detectClockPattern,
  detectSuspiciousVolume,
  lastVsClose,
  perCapita,
  volumeMultiple,
} from '@features/market/lib/tapeMath';

describe('فرمول های پایه', () => {
  it('اختلاف آخرین به پایانی', () => {
    expect(lastVsClose(100, 102)).toBeCloseTo(-0.0196, 4);
    expect(lastVsClose(102, 100)).toBeCloseTo(0.02, 4);
    expect(lastVsClose(null, 100)).toBeNull();
    expect(lastVsClose(100, 0)).toBeNull();
    expect(lastVsClose(100, null)).toBeNull();
  });

  it('شکاف پایانی به آخرین', () => {
    expect(closingGap(100, 102)).toBeCloseTo(0.02, 4);
    expect(closingGap(0, 102)).toBeNull();
  });

  it('سرانه با تعداد صفر قابل محاسبه نیست', () => {
    expect(perCapita(1000, 0)).toBeNull();
    expect(perCapita(1000, null)).toBeNull();
    expect(perCapita(1000, 4)).toBe(250);
  });

  it('نسبت قدرت خریدار با سقف 10', () => {
    expect(buyerPowerRatio(3000, 2, 1000, 2)).toBe(3);
    expect(buyerPowerRatio(100000, 1, 10, 10)).toBe(10);
    expect(buyerPowerRatio(1000, 0, 1000, 2)).toBeNull();
    expect(buyerPowerRatio(1000, 2, 1000, 0)).toBeNull();
  });

  it('نسبت حجم با میانگین صفر قابل محاسبه نیست', () => {
    expect(volumeMultiple(300, 100)).toBe(3);
    expect(volumeMultiple(300, 0)).toBeNull();
    expect(volumeMultiple(300, null)).toBeNull();
  });
});

describe('الگوی ساعت', () => {
  const base = { p_last: 1000, p_closing: 1020, tvol: 2_000_000, month_avg_vol: 1_000_000, z_tot_tran: 40 };

  it('شکاف 2 درصد با حجم و معاملات کافی شکار می شود', () => {
    const r = detectClockPattern(base);
    expect(r.hit).toBe(true);
    expect(r.gap).toBeCloseTo(0.02, 4);
  });

  it('شکاف کمتر از 2 درصد شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, p_closing: 1010 }).hit).toBe(false);
  });

  it('معاملات 30 یا کمتر شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, z_tot_tran: 30 }).hit).toBe(false);
  });

  it('حجم زیر میانگین شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, tvol: 900_000 }).hit).toBe(false);
  });

  it('قیمت نامعتبر شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, p_last: null }).hit).toBe(false);
  });
});

describe('حجم مشکوک', () => {
  it('سه برابر میانگین با معاملات کافی', () => {
    const r = detectSuspiciousVolume({ tvol: 3_100_000, month_avg_vol: 1_000_000, z_tot_tran: 60 });
    expect(r.hit).toBe(true);
    expect(r.multiple).toBeCloseTo(3.1, 4);
  });

  it('مرز سه برابر رد می شود', () => {
    expect(detectSuspiciousVolume({ tvol: 3_000_000, month_avg_vol: 1_000_000, z_tot_tran: 60 }).hit).toBe(false);
    expect(detectSuspiciousVolume({ tvol: 5_000_000, month_avg_vol: 1_000_000, z_tot_tran: 50 }).hit).toBe(false);
  });
});
