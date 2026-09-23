// __tests__/market-hours-poll.spec.ts — ریتمِ تازه‌سازیِ وابسته به ساعتِ بازار
// پولینگِ ۵ ثانیه‌ایِ کلِ تابلو (پاسخِ ~۴ مگابایتی) در ساعتِ تعطیل هیچ داده‌ای
// را عوض نمی‌کند ولی رندرر را بیدار نگه می‌دارد؛ این تست همان در را می‌بندد.
import { describe, it, expect } from 'vitest';
import { CLOSED_POLL_MS, effectivePollMs, isMarketOpen } from '@shared/lib/marketHours';

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
