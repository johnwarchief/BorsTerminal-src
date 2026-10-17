// __tests__/mobile-resume-check.spec.ts — دریچۀِ بازگشت ازِ پس‌زمینه برایِ
// بررسیِ بستۀِ داده. بی‌این، گوشیِ همیشه‌باز بی‌restartِ کامل هرگز بستهٔ
// تازه‌تر نمی‌دید (تایمرِ ۱۵ثانیه‌ای یک‌بار می‌خواست و پنجرۀِ ۲۴ساعته بی‌
// گشودنِ دوبارۀِ دیتابیس باز نمی‌شد). دو در رفتارِ درست است:
//   ۱) cooldownِ ۶۰ ثانیه‌ای: تاگ‌هایِ پشت‌سرهم یک fetchAdded موج نمی‌سازند.
//   ۲) گیتِ اصلی همانِ runCheck است: پس ازِ شکست، backoff (نه cooldown)
//      بررسیِ بعدی را عقب می‌اندازد — resume اجازه می‌دهد، runCheck رد می‌کند.
// مسیرِ بی‌کلیدِ عمومی امضا درِ بیلدِ تست عمداً استفاده می‌شود: همان اول
// رد می‌شود (fail-closed) و تنها اثرِ قابل‌مشاهده، وضعیتِ localStorage است.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const FAILS_KEY = 'bors_snapshot_fail_streak';
const NEXT_TRY_KEY = 'bors_snapshot_next_try_at';

// cooldownِ resume یکِ شمارندۀِ ماژولی است؛ هر آزمون باید ماژولِ تازه ببیند
// وگرنه دورِ آزمونِ یکم، آزمونِ دوم را درِ cooldown قفل می‌کند.
async function freshResume(): Promise<() => void> {
  vi.resetModules();
  const m = await import('@shared/api/local/localData');
  return m.resumeSnapshotCheck;
}

beforeEach(() => {
  localStorage.clear();
  vi.useRealTimers();
});

describe('resumeSnapshotCheck', () => {
  it('دورِ نخست می‌دود و شکستِ fail-closed را ثبت می‌کند؛ دورِ دوم درِ cooldown رد می‌شود', async () => {
    const resume = await freshResume();
    resume();
    await vi.waitFor(() => {
      expect(Number(localStorage.getItem(FAILS_KEY) ?? 0)).toBe(1);
    });
    resume(); // همان ماژول، ثانیه‌ها بعد — درِ ۶۰ ثانیه
    await new Promise((r) => setTimeout(r, 20));
    expect(Number(localStorage.getItem(FAILS_KEY) ?? 0)).toBe(1); // cooldown، نه دورِ دوم
  });

  it('پس ازِ cooldown، backoffِ خودِ runCheck راه را می‌بندد (resume فقط در است)', async () => {
    vi.useFakeTimers();
    try {
      const resume = await freshResume();
      resume();
      await vi.advanceTimersByTimeAsync(10);
      expect(Number(localStorage.getItem(FAILS_KEY) ?? 0)).toBe(1);
      expect(Number(localStorage.getItem(NEXT_TRY_KEY) ?? 0)).toBeGreaterThan(Date.now());
      vi.advanceTimersByTime(61_000); // cooldown رد؛ پنجرۀِ ۵دقیقۀِ backoff باز نه
      resume();
      await vi.advanceTimersByTimeAsync(10);
      expect(Number(localStorage.getItem(FAILS_KEY) ?? 0)).toBe(1); // runCheck رد کرد
    } finally {
      vi.useRealTimers();
    }
  });
});
