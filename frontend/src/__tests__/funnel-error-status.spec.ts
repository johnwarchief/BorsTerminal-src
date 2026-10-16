// پاسخِ ۲۰۰ با بدنۀ خطا ≠ بازاری که خالی است
//
// موتورِ قیف برایِ `fund_mode` ناشناخته HTTP 200 می‌دهد و درِ بدنه می‌گوید
// `status:"error"` (سنجشِ زنده: ۶۷ بایت، `api/funnel.py:255`). این تست همان
// بدنهٔ واقعی را می‌گذارد و می‌سنجد که مصرف‌کننده آن را خطا می‌بیند، نه یک
// جدولِ خالی. کنترلِ منفی: بدنهٔ موفقِ بی‌`status` (پاسخِ قدیمی) نباید خطا
// بخورد، وگرنه هر کلاینتِ کهنه‌ای قرمز می‌شود.
import { describe, expect, it } from 'vitest';
import { funnelPayloadProblem } from '@features/master/api/useFtsFunnel';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';

describe('funnelPayloadProblem — خطایِ درونِ پاسخِ ۲۰۰', () => {
  it('بدنۀ واقعیِ «fund_mode ناشناخته» خطا است، نه جدولِ خالی', () => {
    // همان چیزی که بک‌اند برایِ `fund_mode=strict` برگرداند:
    const real = { status: 'error', message: 'fund_modeِ ناشناخته: strict' };
    expect(funnelPayloadProblem(real)).toBe('fund_modeِ ناشناخته: strict');
  });

  it('پاسخِ ناموفقِ بی‌پیام هم نامش را می‌گیرد (بی‌«—» بی‌محتوا)', () => {
    expect(funnelPayloadProblem({ status: 'unavailable' })).toContain('unavailable');
  });

  it('پاسخِ موفق و پاسخِ قدیمیِ بی‌status هیچ‌کدام خطا نیستند (کنترلِ منفی)', () => {
    expect(funnelPayloadProblem(FUNNEL_FIXTURE)).toBeNull();
    expect(funnelPayloadProblem({ status: 'success' })).toBeNull();
    expect(funnelPayloadProblem({})).toBeNull();
    expect(funnelPayloadProblem(null)).toBeNull();
    expect(funnelPayloadProblem(undefined)).toBeNull();
  });

  it('فیکسچرِ موفق واقعاً statusِ success دارد (تست روِ فرضِ خالی سبز نمی‌شود)', () => {
    expect(FUNNEL_FIXTURE.status).toBe('success');
  });
});
