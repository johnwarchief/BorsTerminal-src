// __tests__/shared-idle-gate.spec.ts
// گاردِ بیکاری: مصرفِ GPU در پنجرهٔ بازِ دست‌نخورده (اندازه‌گیری v1.0.26) از
// انیمیشن‌های بی‌پایان بود. اگر این گارد خاموش شود، همان ۱۲٪ برمی‌گردد؛
// اگر زودتر از حد خاموش شود، کاربر صفحهٔ یخ‌زده می‌بیند. پس هر دو جهت تست است.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { startIdleGate } from '@shared/lib/idleGate';

const idleAttr = () => document.documentElement.dataset.idle;
const hiddenAttr = () => document.documentElement.dataset.hidden;

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
}

describe('idleGate', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setHidden(false);
    delete document.documentElement.dataset.idle;
    delete document.documentElement.dataset.hidden;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('while the user is active the gate stays off', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    for (let i = 0; i < 6; i++) {
      vi.advanceTimersByTime(150);
      window.dispatchEvent(new Event('pointermove'));
    }
    expect(idleAttr()).toBe('0');
    stop();
  });

  it('after the idle window with no input it turns on', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    vi.advanceTimersByTime(1300);
    expect(idleAttr()).toBe('1');
    stop();
  });

  it('any input un-idles immediately', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    vi.advanceTimersByTime(1300);
    expect(idleAttr()).toBe('1');
    window.dispatchEvent(new Event('keydown'));
    expect(idleAttr()).toBe('0');
    stop();
  });

  it('hidden window is idle right away, and coming back clears it', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    setHidden(true);
    document.dispatchEvent(new Event('visibilitychange'));
    expect(idleAttr()).toBe('1');
    setHidden(false);
    document.dispatchEvent(new Event('visibilitychange'));
    expect(idleAttr()).toBe('0');
    stop();
  });

  /**
   * data-idle دو علتِ متفاوت را در یک پرچم مخلوط می‌کرد: «دست روی موس نیست» و
   * «پنجره وجود ندارد». استثنایِ جریانِ درخت (pilot: گزینهٔ c) باید فقط به اولی
   * بگوید بله — پس دومی پرچمِ جدای خودش را دارد.
   */
  it('بی‌حرکتیِ موس را از پنهانیِ پنجره جدا می‌گوید', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    expect(hiddenAttr()).toBe('0');
    vi.advanceTimersByTime(1300);
    expect(idleAttr()).toBe('1');
    // نگاهِ بی‌حرکت به پنجرهٔ باز: بی‌کار است ولی پنه نیست
    expect(hiddenAttr()).toBe('0');
    setHidden(true);
    document.dispatchEvent(new Event('visibilitychange'));
    expect(hiddenAttr()).toBe('1');
    setHidden(false);
    vi.advanceTimersByTime(200);
    expect(hiddenAttr()).toBe('0');
    stop();
  });

  it('پیش از اجرا هیچ پرچمی رویِ ریشۀ سند نماند', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    setHidden(true);
    document.dispatchEvent(new Event('visibilitychange'));
    stop();
    expect(idleAttr()).toBe('0');
    expect(hiddenAttr()).toBe('0');
  });

  it('dispose stops the timer and clears the flag', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    stop();
    expect(idleAttr()).toBe('0');
    vi.advanceTimersByTime(10_000);
    expect(idleAttr()).toBe('0');
  });
});
