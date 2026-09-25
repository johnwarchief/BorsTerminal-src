// __tests__/shared-idle-gate.spec.ts
// گاردِ بیکاری: مصرفِ GPU در پنجرهٔ بازِ دست‌نخورده (اندازه‌گیری v1.0.26) از
// انیمیشن‌های بی‌پایان بود. اگر این گارد خاموش شود، همان ۱۲٪ برمی‌گردد؛
// اگر زودتر از حد خاموش شود، کاربر صفحهٔ یخ‌زده می‌بیند. پس هر دو جهت تست است.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { startIdleGate } from '@shared/lib/idleGate';

const idleAttr = () => document.documentElement.dataset.idle;

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
}

describe('idleGate', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setHidden(false);
    delete document.documentElement.dataset.idle;
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

  it('dispose stops the timer and clears the flag', () => {
    const stop = startIdleGate({ idleMs: 1000, checkMs: 200 });
    stop();
    expect(idleAttr()).toBe('0');
    vi.advanceTimersByTime(10_000);
    expect(idleAttr()).toBe('0');
  });
});
