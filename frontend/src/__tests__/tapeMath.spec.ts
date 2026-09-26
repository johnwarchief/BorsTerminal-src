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
    expect(closingGap(102, 100)).toBeCloseTo(0.02, 4);
    expect(closingGap(102, 0)).toBeNull();
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
  // مبناءِ فیلترها ستونِ bک‌اندیِ vol_ratio_file است (Σ[ih][0..29]/۳۰)، نه
  // month_avg_volِ نمایشی. base هر دو را دارد تا تفاوتِ دو مبناء تست شود.
  const base = {
    p_last: 1020, p_closing: 1000, tvol: 2_000_000, month_avg_vol: 1_000_000,
    vol_ratio_file: 2, z_tot_tran: 40,
  };

  it('شکاف 2 درصد با حجم و معاملات کافی شکار می شود', () => {
    const r = detectClockPattern(base);
    expect(r.hit).toBe(true);
    expect(r.gap).toBeCloseTo(0.02, 4);
  });

  it('شکاف کمتر از 2 درصد شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, p_last: 1005 }).hit).toBe(false);
  });

  it('معاملات 30 یا کمتر شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, z_tot_tran: 30 }).hit).toBe(false);
  });

  it('حجم زیر مبناءِ فایل شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, vol_ratio_file: 0.9 }).hit).toBe(false);
  });

  it('نبودنِ مبناءِ فایل «رد» است، نه ردِ بی‌صدا از روی میانگین ماه', () => {
    // month_avg_vol عدد دارد و tvol هم ۲× آن است؛ با این حال نمادِ ۱۰‌روزه
    // سنجیده نمی‌شود (رأیِ ۱۸: قاعدۀِ «تقسیم بر ۳۰» برای آن عددِ جعلی می‌سازد).
    expect(detectClockPattern({ ...base, vol_ratio_file: null }).hit).toBe(false);
  });

  it('قیمت نامعتبر شکار نمی شود', () => {
    expect(detectClockPattern({ ...base, p_last: null }).hit).toBe(false);
  });
});

describe('حجم مشکوک', () => {
  it('سه برابرِ مبناءِ فایل با معاملات کافی', () => {
    const r = detectSuspiciousVolume({ tvol: 3_100_000, month_avg_vol: 1_000_000,
                                       vol_ratio_file: 3.1, z_tot_tran: 60 });
    expect(r.hit).toBe(true);
    expect(r.multiple).toBeCloseTo(3.1, 4);
  });

  it('مرز سه برابر و مرز پنجاه معامله رد می‌شوند', () => {
    expect(detectSuspiciousVolume({ vol_ratio_file: 3.0, z_tot_tran: 60 }).hit).toBe(false);
    expect(detectSuspiciousVolume({ vol_ratio_file: 5.0, z_tot_tran: 50 }).hit).toBe(false);
  });

  it('مبناءِ فایل بی‌نهایت یا NaN «داده» نیست', () => {
    expect(detectSuspiciousVolume({ vol_ratio_file: Number.NaN, z_tot_tran: 60 }).hit).toBe(false);
    expect(detectSuspiciousVolume({ vol_ratio_file: Number.POSITIVE_INFINITY, z_tot_tran: 60 }).hit).toBe(false);
  });
});
