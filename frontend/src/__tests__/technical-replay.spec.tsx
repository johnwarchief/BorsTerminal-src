// تست بازپخش کندل (T-10 قطعهٔ ۱): کمک‌تابع‌های خالص + استور + نوار کنترل
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { ReplayBar } from '@features/technical/components/ReplayBar';
import { useReplayStore } from '@features/technical/stores/replayStore';
import { REPLAY_SPEEDS, clampCursor, isAtEnd, replayProgress, replaySlice, stepCursor } from '@features/technical/lib/replay';

describe('کمک‌تابع‌های بازپخش', () => {
  it('clampCursor در بازهٔ معتبر', () => {
    expect(clampCursor(-5, 10)).toBe(0);
    expect(clampCursor(99, 10)).toBe(9);
    expect(clampCursor(3.6, 10)).toBe(4);
    expect(clampCursor(0, 0)).toBe(0);
  });

  it('replaySlice کندل‌های بعد از مکان‌نما را پنهان می‌کند', () => {
    const rows = [10, 20, 30, 40, 50];
    expect(replaySlice(rows, 2)).toEqual([10, 20, 30]);
    expect(replaySlice(rows, 0)).toEqual([10]);
    expect(replaySlice([], 3)).toEqual([]);
    expect(replaySlice(rows, 99)).toEqual(rows);
  });

  it('stepCursor و isAtEnd و progress', () => {
    expect(stepCursor(0, 5, -1)).toBe(0);
    expect(stepCursor(4, 5, 1)).toBe(4);
    expect(stepCursor(2, 5, 1)).toBe(3);
    expect(isAtEnd(4, 5)).toBe(true);
    expect(isAtEnd(3, 5)).toBe(false);
    expect(replayProgress(0, 5)).toBe(0);
    expect(replayProgress(4, 5)).toBe(100);
  });
});

describe('استور بازپخش', () => {
  beforeEach(() => {
    useReplayStore.setState({ active: false, cursor: 0, playing: false, speedMs: 500 });
  });

  it('شروع/توقف/گام‌ها', () => {
    const s = useReplayStore.getState();
    s.start(10);
    expect(useReplayStore.getState().active).toBe(true);
    expect(useReplayStore.getState().cursor).toBe(10);
    expect(useReplayStore.getState().playing).toBe(false);
    useReplayStore.getState().setCursor(4);
    expect(useReplayStore.getState().cursor).toBe(4);
    useReplayStore.getState().togglePlay();
    expect(useReplayStore.getState().playing).toBe(true);
    useReplayStore.getState().stop();
    expect(useReplayStore.getState().active).toBe(false);
    expect(useReplayStore.getState().playing).toBe(false);
  });
});

describe('نوار بازپخش', () => {
  beforeEach(() => {
    useReplayStore.setState({ active: false, cursor: 0, playing: false, speedMs: 500 });
  });

  it('بدون دادهٔ کافی، دکمه غیرفعال و پیام صادقانه', () => {
    render(<ReplayBar total={1} />);
    expect(screen.getByTestId('replay-start')).toBeDisabled();
    expect(screen.getByTestId('replay-bar').textContent).toContain('دادهٔ کافی');
  });

  it('شروع، اسلایدر، سرعت و خروج', () => {
    render(<ReplayBar total={120} />);
    fireEvent.click(screen.getByTestId('replay-start'));
    expect(useReplayStore.getState().active).toBe(true);
    expect(useReplayStore.getState().cursor).toBe(119);

    fireEvent.change(screen.getByTestId('replay-slider'), { target: { value: '50' } });
    expect(useReplayStore.getState().cursor).toBe(50);
    expect(screen.getByTestId('replay-progress').textContent).toContain('۵۱');

    fireEvent.click(screen.getByTestId('replay-next'));
    expect(useReplayStore.getState().cursor).toBe(51);
    fireEvent.click(screen.getByTestId('replay-prev'));
    expect(useReplayStore.getState().cursor).toBe(50);

    fireEvent.change(screen.getByTestId('replay-speed'), { target: { value: String(REPLAY_SPEEDS[3]) } });
    expect(useReplayStore.getState().speedMs).toBe(REPLAY_SPEEDS[3]);

    fireEvent.click(screen.getByTestId('replay-play'));
    expect(useReplayStore.getState().playing).toBe(true);

    fireEvent.click(screen.getByTestId('replay-stop'));
    expect(useReplayStore.getState().active).toBe(false);
  });
});
