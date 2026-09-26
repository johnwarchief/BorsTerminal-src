// تستِ نگهبانِ مقیاسِ عمودی (#167) — درگِ افقی نباید چارت را عمودی بتکاند
import { describe, expect, it } from 'vitest';
import { SCALE_DRIFT_RELEASE, createScaleLock } from '@features/technical/nahayatnegar/lib/axisScaleLock';

/** فراخوانی با پنجرۀ دیدِ تازه و محدوده‌ای که موتور خودش می‌خواهد */
const call = (lock: ReturnType<typeof createScaleLock>, window: [number, number], auto: [number, number]) =>
  lock.createRange({ chart: { getVisibleRange: () => ({ from: window[0], to: window[1] }) }, defaultRange: { from: auto[0], to: auto[1] } });

describe('createScaleLock', () => {
  it('نخستین فراخوانی همان محدودۀ خودکار است — چیزی اختراع نمی‌شود', () => {
    const lock = createScaleLock();
    expect(call(lock, [0, 100], [2000, 3400])).toEqual({ from: 2000, to: 3400 });
  });

  it('درگِ افقی مقیاسِ عمودی را نگه می‌دارد', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    // همان عرضِ پنجره، جابه‌جا شده؛ موتور می‌خواهد ۲۵۰۰..۳۹۰۰ بشیند
    expect(call(lock, [12, 112], [2500, 3900])).toEqual({ from: 2000, to: 3400 });
  });

  it('زوم (تغییرِ عرضِ پنجره) مقیاس را از نو می‌چیند', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    expect(call(lock, [20, 60], [2900, 3200])).toEqual({ from: 2900, to: 3200 });
  });

  it('فراخوانیِ دوباره با همانِ پنجره مقیاسِ نگه‌داشته را نمی‌شکند (خزش)', () => {
    // موتور بعد از درگ، با همانِ پنجره چند بار دیگر هم می‌پرسد؛ اگر فقط لحظهٔ
    // جابه‌جایی نگه داشته شود، پرش یک فریم دیرتر برمی‌گردد.
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    call(lock, [12, 112], [2500, 3900]);
    expect(call(lock, [12, 112], [2120, 3520])).toEqual({ from: 2000, to: 3400 });
    expect(call(lock, [12, 112], [2050, 3450])).toEqual({ from: 2000, to: 3400 });
  });

  it('کلاپسِ لبهٔ راست (یک-دو کندل جابه‌جاییِ عرض) زوم شمرده نمی‌شود', () => {
    // در ۱۹۲ دیده شد: موتور عرضِ دید را یکی دو کندل عوض کرد، آزمونِ «عرض ثابت»
    // سخت‌گیرانه شکست و مقیاس پرید.
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    expect(call(lock, [12, 113], [2500, 3900])).toEqual({ from: 2000, to: 3400 });
  });

  it('اگر دید از محدودهٔ نگه‌داشته خیلی دور شود آزاد می‌شود — کندل پشتِ کادر نمی‌ماند', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3000]);
    const span = 1000;
    const far: [number, number] = [2000 + span * (SCALE_DRIFT_RELEASE + 0.5), 3000 + span * (SCALE_DRIFT_RELEASE + 0.5)];
    expect(call(lock, [400, 500], far)).toEqual({ from: far[0], to: far[1] });
  });

  it('قفلِ کامل: زوم هم مقیاس را نمی‌شکند', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    lock.setFullLock(true);
    expect(call(lock, [20, 60], [2900, 3200])).toEqual({ from: 2000, to: 3400 });
    lock.setFullLock(false);
    // خاموش‌کردنِ قفل آزادش می‌کند
    expect(call(lock, [20, 60], [2900, 3200])).toEqual({ from: 2900, to: 3200 });
  });

  it('release برای تغییرِ نماد/بازه/تعدیل', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    lock.release();
    expect(call(lock, [0, 100], [50, 120])).toEqual({ from: 50, to: 120 });
  });

  it('محدودۀ نامعتبر (to<=from) قفل نمی‌کند و می‌گذرد', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    expect(call(lock, [5, 105], [2500, 2500])).toEqual({ from: 2500, to: 2500 });
  });
});
