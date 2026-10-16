import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  __resetVerdictChangesForTests,
  useVerdictChanges,
  type StageDelta,
} from '@features/master/lib/funnelChangeTrack';
import type { FunnelEntry, FunnelStageKey } from '@features/master/lib/ftsFunnel';

const STAGE: FunnelStageKey = 'technical';

/** فقط چیزی که ردیاب می‌خواند: نماد + حکمِ همان گام. */
function entry(symbol: string, status: string): FunnelEntry {
  return { symbol, status: { [STAGE]: status } } as unknown as FunnelEntry;
}

const counts = (passed: number, ruled = 100): StageDelta => ({ passed, ruled });

describe('ردیابِ «همین حالا چه چیزی عوض شد» درِ قیف', () => {
  beforeEach(() => __resetVerdictChangesForTests());

  it('نخستین دور هیچ تغییری گزارش نمی‌کند (کنترلِ منفی: نشانه‌ای از خود نمی‌سازد)', () => {
    const { result } = renderHook(() =>
      useVerdictChanges(STAGE, [entry('A', 'pass'), entry('B', 'reject')], counts(2, 100)));
    expect(result.current.changed.size).toBe(0);
    expect(result.current.delta).toBeNull();
  });

  it('فقط نمادی که حکمش عوض شده علامت می‌خورد، نه همسایه‌هایش', () => {
    const first = renderHook(() =>
      useVerdictChanges(STAGE, [entry('A', 'pass'), entry('B', 'reject'), entry('C', 'pending')],
        counts(1, 100)));
    expect(first.result.current.changed.size).toBe(0);

    const second = renderHook(() =>
      useVerdictChanges(STAGE, [entry('A', 'reject'), entry('B', 'reject'), entry('C', 'pending')],
        counts(4, 102)));
    expect(Array.from(second.result.current.changed)).toEqual(['A']);
  });

  it('دورِ بی‌تغییر، ردیفِ بی‌تغییر نمی‌سازد (و دلتا صفر است)', () => {
    renderHook(() => useVerdictChanges(STAGE, [entry('A', 'pass')], counts(1, 50)));
    const { result } = renderHook(() =>
      useVerdictChanges(STAGE, [entry('A', 'pass')], counts(1, 50)));
    expect(result.current.changed.size).toBe(0);
    expect(result.current.delta).toEqual({ passed: 0, ruled: 0 });
  });

  it('دلتا از شمارِ دورِ پیش کم می‌کند، نه از حدس', () => {
    renderHook(() => useVerdictChanges(STAGE, [entry('A', 'pass')], counts(120, 400)));
    const { result } = renderHook(() =>
      useVerdictChanges(STAGE, [entry('A', 'pass')], counts(124, 398)));
    expect(result.current.delta).toEqual({ passed: 4, ruled: -2 });
  });

  it('نمادِ تازه‌وارد «تغییرِ حکم» خوانده نمی‌شود', () => {
    renderHook(() => useVerdictChanges(STAGE, [entry('A', 'pass')], counts(1, 10)));
    const { result } = renderHook(() =>
      useVerdictChanges(STAGE, [entry('A', 'pass'), entry('N', 'reject')], counts(1, 11)));
    expect(result.current.changed.size).toBe(0);
    expect(result.current.delta).toEqual({ passed: 0, ruled: 1 });
  });

  it('گام‌ها یکدیگر را آلوده نمی‌کنند (کلیدِ جدا برایِ هر مرحلۀ قیف)', () => {
    renderHook(() => useVerdictChanges('tape', [entry('A', 'pass')], counts(1, 10)));
    const { result } = renderHook(() =>
      useVerdictChanges('fundamental', [entry('A', 'pass')], counts(1, 10)));
    expect(result.current.changed.size).toBe(0);
    expect(result.current.delta).toBeNull();
  });
});
