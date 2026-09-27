// تست ۴ قابلیت جدید ترسیم (T-12): قفل · کپی · اندازه همه · گروه‌های اشکال
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DrawingToolbar } from '@features/technical/components/DrawingToolbar';
import type { ChartDrawApi } from '@features/technical/components/KLineChartWrapper';

function api(overrides: Partial<Record<string, unknown>> = {}) {
  const base = {
    startDraw: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    clearDrawings: vi.fn(),
    hideDrawings: vi.fn(),
    updateLast: vi.fn(),
    getLastPoints: vi.fn(() => []),
    saveAsDefault: vi.fn(),
    setLockAll: vi.fn(),
    copyLast: vi.fn(),
    resizeAll: vi.fn(),
    listGroups: vi.fn(() => [
      { id: 'fts-draw', count: 2 },
      { id: 'گروه‌۱', count: 1 },
    ]),
    setGroupVisible: vi.fn(),
    removeGroup: vi.fn(),
    setTargetGroup: vi.fn(),
    ...overrides,
  };
  return base as unknown as ChartDrawApi & typeof base;
}

describe('قفل / کپی / اندازهٔ همه', () => {
  it('قفل ترسیم‌ها toggles و api را صدا می‌زند', () => {
    const a = api();
    render(<DrawingToolbar api={a} />);
    fireEvent.click(screen.getByTestId('draw-lock'));
    expect(a.setLockAll).toHaveBeenCalledWith(true);
    expect(screen.getByTestId('draw-lock').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByTestId('draw-lock'));
    expect(a.setLockAll).toHaveBeenLastCalledWith(false);
  });

  it('کپی آخرین ترسیم api را صدا می‌زند', () => {
    const a = api();
    render(<DrawingToolbar api={a} />);
    fireEvent.click(screen.getByTestId('draw-copy'));
    expect(a.copyLast).toHaveBeenCalledTimes(1);
  });

  it('تغییر اندازهٔ همه به‌صورت چرخهٔ ۱→۲→۳→۱', () => {
    const a = api();
    render(<DrawingToolbar api={a} />);
    fireEvent.click(screen.getByTestId('draw-resize'));
    expect(a.resizeAll).toHaveBeenLastCalledWith(2);
    fireEvent.click(screen.getByTestId('draw-resize'));
    expect(a.resizeAll).toHaveBeenLastCalledWith(3);
    fireEvent.click(screen.getByTestId('draw-resize'));
    expect(a.resizeAll).toHaveBeenLastCalledWith(1);
  });

  it('بدون api دکمه‌های جدید غیرفعال‌اند', () => {
    render(<DrawingToolbar api={null} />);
    expect(screen.getByTestId('draw-lock')).toBeDisabled();
    expect(screen.getByTestId('draw-copy')).toBeDisabled();
    expect(screen.getByTestId('draw-resize')).toBeDisabled();
    expect(screen.getByTestId('draw-groups')).toBeDisabled();
  });
});

describe('گروه‌های اشکال (پوشه)', () => {
  it('باز کردن، فهرست گروه‌ها را از api می‌گیرد', () => {
    const a = api();
    render(<DrawingToolbar api={a} />);
    expect(screen.queryByTestId('draw-groups-flyout')).toBeNull();
    fireEvent.click(screen.getByTestId('draw-groups'));
    expect(a.listGroups).toHaveBeenCalled();
    const fly = screen.getByTestId('draw-groups-flyout');
    expect(fly.textContent).toContain('fts-draw');
    expect(fly.textContent).toContain('گروه‌۱');
  });

  it('پنهان/نمایان و حذف گروه api را صدا می‌زنند', () => {
    const a = api();
    render(<DrawingToolbar api={a} />);
    fireEvent.click(screen.getByTestId('draw-groups'));
    fireEvent.click(screen.getByTestId('group-toggle-fts-draw'));
    expect(a.setGroupVisible).toHaveBeenCalledWith('fts-draw', false);
    fireEvent.click(screen.getByTestId('group-remove-گروه‌۱'));
    expect(a.removeGroup).toHaveBeenCalledWith('گروه‌۱');
    // ردیف حذف‌شده از فهرست UI می‌رود
    expect(screen.queryByTestId('group-remove-گروه‌۱')).toBeNull();
  });

  it('تعیین گروه هدف برای ترسیم‌های بعدی', () => {
    const a = api();
    render(<DrawingToolbar api={a} />);
    fireEvent.click(screen.getByTestId('draw-groups'));
    fireEvent.change(screen.getByTestId('group-target-input'), { target: { value: 'گروه‌۲' } });
    fireEvent.click(screen.getByTestId('group-target-apply'));
    expect(a.setTargetGroup).toHaveBeenCalledWith('گروه‌۲');
    // با فیلد خالی ⇒ بازگشت به گروه پیش‌فرض (null)
    fireEvent.change(screen.getByTestId('group-target-input'), { target: { value: '   ' } });
    fireEvent.click(screen.getByTestId('group-target-apply'));
    expect(a.setTargetGroup).toHaveBeenLastCalledWith(null);
  });
});
