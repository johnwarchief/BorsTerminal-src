// __tests__/market-hours-poll.spec.ts — ریتمِ تازه‌سازیِ وابسته به ساعتِ بازار
// پولینگِ ۵ ثانیه‌ایِ کلِ تابلو (پاسخِ ~۴ مگابایتی) در ساعتِ تعطیل هیچ داده‌ای
// را عوض نمی‌کند ولی رندرر را بیدار نگه می‌دارد؛ این تست همان در را می‌بندد.
import { describe, it, expect, vi } from 'vitest';
import { CLOSED_POLL_MS, effectivePollMs, isMarketOpen, sessionPollMs } from '@shared/lib/marketHours';

/** روزِ معاملاتی: دوشنبه ۲۰۲۶‑09‑14 (getDay()=1) */
const WD = (h: number, m: number) => new Date(2026, 8, 14, h, m);

describe('effectivePollMs — تعطیل یعنی بی‌کار نچرخد', () => {
  it('در ساعتِ بازار همان بازهٔ کاربر می‌ماند', () => {
    expect(effectivePollMs(5_000, WD(9, 30))).toBe(5_000);
    expect(effectivePollMs(15_000, WD(12, 30))).toBe(15_000);
  });

  it('پس از بستنِ تابلو به ریتمِ بسته می‌رسد (نه سریع‌تر)', () => {
    expect(effectivePollMs(5_000, WD(12, 31))).toBe(CLOSED_POLL_MS);
    expect(effectivePollMs(15_000, WD(13, 0))).toBe(CLOSED_POLL_MS);
  });

  it('انتخابِ کندترِ کاربر را تند نمی‌کند', () => {
    expect(effectivePollMs(10 * 60_000, WD(13, 0))).toBe(10 * 60_000);
  });

  it('پنجشنبه و جمعه تعطیل است، حتی در میانهٔ ساعت', () => {
    expect(isMarketOpen(new Date(2026, 8, 17, 10, 0))).toBe(false); // پنجشنبه
    expect(isMarketOpen(new Date(2026, 8, 18, 10, 0))).toBe(false); // جمعه
    expect(effectivePollMs(5_000, new Date(2026, 8, 18, 10, 0))).toBe(CLOSED_POLL_MS);
  });
});

describe('sessionPollMs — ریتمِ پنل‌هایِ نشست‌محور (#173)', () => {
  it('در ساعتِ بازار با نفسِ میکروچارت‌ها می‌آید، نه با انتخابِ کاربر', () => {
    expect(sessionPollMs(30_000, WD(9, 30))).toBe(30_000);
    // انتخابِ کاربرِ جدول (۵ ثانیه) رویِ نبض بازار اثر ندارد
    expect(sessionPollMs(30_000, WD(12, 0))).toBe(30_000);
  });

  it('بیرونِ ساعتِ بازار کاملاً خاموش نمی‌شود: ریتمِ آرامِ تابلو را می‌گیرد', () => {
    // پیش‌تر «خاموش» یعنی آخرین نقاطِ روزِ نهایی هیچ‌وقت نمی‌نشستند
    expect(sessionPollMs(30_000, WD(12, 31))).toBe(CLOSED_POLL_MS);
    expect(sessionPollMs(30_000, WD(13, 0))).toBe(CLOSED_POLL_MS);
    expect(sessionPollMs(30_000, new Date(2026, 8, 18, 10, 0))).toBe(CLOSED_POLL_MS);
  });
});

describe('ساعتِ بازار با ساعتِ دیواریِ تهران است، نه TZِ دستگاه', () => {
  // گوشیِ با timezone غیرِ تهران (سفر/تنظیم/ROM) بازارِ باز را «بسته» می‌دید
  // و پولینگِ ۵ثانیه را به ۵ دقیقه می‌انداخت. لحظه‌هایِ زیر مطلقِ UTC‌اند؛
  // درِ هر دو TZ نتیجه باید یکی باشد. ۲۰۲۶-۰۹-۱۴ دوشنبه است.
  // ۰۶:۰۰ UTC == ۰۹:۳۰ تهران (وسطِ نشست) — ۰۲:۰۰ UTC == ۰۵:۳۰ تهران (پیش از بازگشایی)
  const OPEN_UTC = new Date(Date.UTC(2026, 8, 14, 6, 0));
  const CLOSED_UTC = new Date(Date.UTC(2026, 8, 14, 2, 0));

  it('درِ TZ تهران: باز/بسته مثلِ پیش', () => {
    expect(isMarketOpen(OPEN_UTC)).toBe(true);
    expect(isMarketOpen(CLOSED_UTC)).toBe(false);
  });

  it('درِ TZ نیویورک (−۴) هم همان رأی — روزِ هفته و ساعت از تهران خوانده می‌شود', () => {
    vi.resetModules();
    process.env.TZ = 'America/New_York';
    // node درِ process.env.TZ تازه فقط با reloadِ موتورِ زمان می‌خواند؛
    // Intl درِ هر احضارِ ICU مقدارِ جاری را می‌گیرد.
    expect(isMarketOpen(OPEN_UTC)).toBe(true);
    expect(isMarketOpen(CLOSED_UTC)).toBe(false);
    process.env.TZ = 'Asia/Tehran'; // بازگردانی برایِ آزمون‌هایِ بعدِ همین فایل
  });

  it('مرزِ بازگشایی/بستن به دقیقۀِ تهران می‌خورد (۰۸:۴۴ بسته، ۰۸:۴۵ باز)', () => {
    const before = new Date(Date.UTC(2026, 8, 14, 5, 14)); // ۰۸:۴۴ تهران
    const exact = new Date(Date.UTC(2026, 8, 14, 5, 15));  // ۰۸:۴۵ تهران
    expect(isMarketOpen(before)).toBe(false);
    expect(isMarketOpen(exact)).toBe(true);
  });
});
