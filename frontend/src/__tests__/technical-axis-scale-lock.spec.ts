// تستِ نگهبانِ مقیاسِ عمودی (#167) — درگِ افقی نباید چارت را عمودی بتکاند
import { describe, expect, it } from 'vitest';
import { SCALE_DRIFT_RELEASE, createScaleLock, type FullAxisRange } from '@features/technical/nahayatnegar/lib/axisScaleLock';

/** فراخوانی با پنجرۀ دیدِ تازه و محدوده‌ای که موتور خودش می‌خواهد */
const call = (lock: ReturnType<typeof createScaleLock>, window: [number, number], auto: [number, number]) =>
  lock.createRange({ chart: { getVisibleRange: () => ({ from: window[0], to: window[1] }) }, defaultRange: { from: auto[0], to: auto[1] } });

describe('createScaleLock', () => {
  it('نخستین فراخوانی همان محدودۀ خودکار است — چیزی اختراع نمی‌شود', () => {
    const lock = createScaleLock();
    expect(call(lock, [0, 100], [2000, 3400])).toMatchObject({ from: 2000, to: 3400 });
  });

  it('درگِ افقی مقیاسِ عمودی را نگه می‌دارد', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    // همان عرضِ پنجره، جابه‌جا شده؛ موتور می‌خواهد ۲۵۰۰..۳۹۰۰ بشیند
    expect(call(lock, [12, 112], [2500, 3900])).toMatchObject({ from: 2000, to: 3400 });
  });

  it('زوم (تغییرِ عرضِ پنجره) مقیاس را از نو می‌چیند', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    expect(call(lock, [20, 60], [2900, 3200])).toMatchObject({ from: 2900, to: 3200 });
  });

  it('فراخوانیِ دوباره با همانِ پنجره مقیاسِ نگه‌داشته را نمی‌شکند (خزش)', () => {
    // موتور بعد از درگ، با همانِ پنجره چند بار دیگر هم می‌پرسد؛ اگر فقط لحظهٔ
    // جابه‌جایی نگه داشته شود، پرش یک فریم دیرتر برمی‌گردد.
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    call(lock, [12, 112], [2500, 3900]);
    expect(call(lock, [12, 112], [2120, 3520])).toMatchObject({ from: 2000, to: 3400 });
    expect(call(lock, [12, 112], [2050, 3450])).toMatchObject({ from: 2000, to: 3400 });
  });

  it('کلاپسِ لبهٔ راست (یک-دو کندل جابه‌جاییِ عرض) زوم شمرده نمی‌شود', () => {
    // در ۱۹۲ دیده شد: موتور عرضِ دید را یکی دو کندل عوض کرد، آزمونِ «عرض ثابت»
    // سخت‌گیرانه شکست و مقیاس پرید.
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    expect(call(lock, [12, 113], [2500, 3900])).toMatchObject({ from: 2000, to: 3400 });
  });

  it('اگر دید از محدودهٔ نگه‌داشته خیلی دور شود آزاد می‌شود — کندل پشتِ کادر نمی‌ماند', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3000]);
    const span = 1000;
    const far: [number, number] = [2000 + span * (SCALE_DRIFT_RELEASE + 0.5), 3000 + span * (SCALE_DRIFT_RELEASE + 0.5)];
    expect(call(lock, [400, 500], far)).toMatchObject({ from: far[0], to: far[1] });
  });

  it('قفلِ کامل: زوم هم مقیاس را نمی‌شکند', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    lock.setFullLock(true);
    expect(call(lock, [20, 60], [2900, 3200])).toMatchObject({ from: 2000, to: 3400 });
    lock.setFullLock(false);
    // خاموش‌کردنِ قفل آزادش می‌کند
    expect(call(lock, [20, 60], [2900, 3200])).toMatchObject({ from: 2900, to: 3200 });
  });

  it('release برای تغییرِ نماد/بازه/تعدیل', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    lock.release();
    expect(call(lock, [0, 100], [50, 120])).toMatchObject({ from: 50, to: 120 });
  });

  it('محدودۀ نامعتبر (to<=from) قفل نمی‌کند و می‌گذرد', () => {
    const lock = createScaleLock();
    call(lock, [0, 100], [2000, 3400]);
    expect(call(lock, [5, 105], [2500, 2500])).toMatchObject({ from: 2500, to: 2500 });
  });
});

// ── فضایِ محور: قفل نباید تبدیلِ خودِ محور را ببلعد (سنجشِ ۱۴۰-۰۷-۲۷) ──
describe('فضایِ محورِ عمودی (لگاریتمی/درصدی)', () => {
  const full = (
    lock: ReturnType<typeof createScaleLock>,
    window: [number, number],
    auto: [number, number],
    space: 'normal' | 'logarithm' | 'percentage',
  ): FullAxisRange => {
    lock.setSpace(space);
    return lock.createRange({
      chart: { getVisibleRange: () => ({ from: window[0], to: window[1] }) },
      defaultRange: { from: auto[0], to: auto[1] },
    }) as FullAxisRange;
  };

  it('normal: real* همانِ display است (رفتارِ اثبات‌شدۀِ خطی دست‌نخورده)', () => {
    const r = full(createScaleLock(), [0, 100], [2000, 3400], 'normal');
    expect(r).toMatchObject({ from: 2000, to: 3400, realFrom: 2000, realTo: 3400, realRange: 1400,
                             displayFrom: 2000, displayTo: 3400, displayRange: 1400 });
  });

  it('logarithm: real* باید log10 باشد — نبودش کلِ کندل‌ها را بیرونِ پن می‌اندازد', () => {
    const r = full(createScaleLock(), [0, 100], [2182, 4540], 'logarithm');
    expect(r.realFrom).toBeCloseTo(Math.log10(2182), 10);
    expect(r.realTo).toBeCloseTo(Math.log10(4540), 10);
    expect(r.realRange).toBeCloseTo(Math.log10(4540) - Math.log10(2182), 10);
    // and the display endpoints stay in rial — only the real space transforms
    expect(r).toMatchObject({ from: 2182, to: 4540, displayFrom: 2182, displayTo: 4540 });
    // نرخِ یکِ قیمتِ میانی درِ فضایِ real باید وسطِ بازۀِ لگاریتمی باشد، نه ~۱-
    const mid = (Math.log10(2182) + Math.log10(4540)) / 2;
    const rate = (mid - r.realFrom) / r.realRange;
    expect(rate).toBeCloseTo(0.5, 6);
  });

  it('قفل درِ لگاریتمی هم درگ را نگه می‌دارد و باز درِ فضایِ log می‌سازد', () => {
    const lock = createScaleLock();
    full(lock, [0, 100], [2182, 4540], 'logarithm');
    const held = full(lock, [12, 112], [2500, 4900], 'logarithm');
    expect(held).toMatchObject({ from: 2182, to: 4540 });
    expect(held.realFrom).toBeCloseTo(Math.log10(2182), 10);
    expect(held.realTo).toBeCloseTo(Math.log10(4540), 10);
  });

  it('percentage: قفل دخالتِ نمی‌کند — تبدیلِ خودِ محور دست‌نخورده می‌ماند', () => {
    const lock = createScaleLock();
    const r = full(lock, [0, 100], [50, 120], 'percentage');
    expect(r).toEqual({ from: 50, to: 120 });   // همان شیئی که موتور داد
  });

  it('تغییرِ فضا بی‌ازنو‌سازیِ قفل نیست، ولی real* را بازمی‌سازد', () => {
    const lock = createScaleLock();
    full(lock, [0, 100], [2000, 3400], 'normal');
    const r = full(lock, [12, 112], [2500, 3900], 'logarithm');
    expect(r).toMatchObject({ from: 2000, to: 3400 });
    expect(r.realFrom).toBeCloseTo(Math.log10(2000), 10);
  });
});
