// تست دیالوگ تنظیمات چارت و پنل تنظیمات ابزار ترسیم (فاز ۳ — TV parity)
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChartSettingsDialog } from '@features/technical/components/ChartSettingsDialog';
import { ToolPropertiesPanel } from '@features/technical/components/ToolPropertiesPanel';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';
import type { ChartDrawApi } from '@features/technical/components/KLineChartWrapper';

function api(): ChartDrawApi & { updateLast: ReturnType<typeof vi.fn> } {
  return {
    startDraw: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    clearDrawings: vi.fn(),
    hideDrawings: vi.fn(),
    updateLast: vi.fn(),
  } as unknown as ChartDrawApi & { updateLast: ReturnType<typeof vi.fn> };
}

describe('دیالوگ تنظیمات چارت', () => {
  it('بسته هیچ نمی‌سازد', () => {
    render(<ChartSettingsDialog open={false} onClose={() => undefined} />);
    expect(screen.queryByTestId('chart-settings')).toBeNull();
  });

  it('باز، تغییر نوع چارت/مقیاس را به استور می‌دهد', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} />);
    expect(screen.getByTestId('chart-settings')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'اریا' }));
    expect(useFtsConfigStore.getState().chartType).toBe('area');
    fireEvent.click(screen.getByRole('button', { name: 'لگاریتمی' }));
    expect(useFtsConfigStore.getState().priceScale).toBe('logarithm');
  });

  it('دکمهٔ بستن onClose را صدا می‌زند', () => {
    const onClose = vi.fn();
    render(<ChartSettingsDialog open onClose={onClose} />);
    fireEvent.click(screen.getByTestId('chart-settings-close'));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('پنل تنظیمات ابزار ترسیم', () => {
  it('بدون ترسیم هیچ نمی‌سازد', () => {
    render(<ToolPropertiesPanel api={api()} last={null} />);
    expect(screen.queryByTestId('tool-properties')).toBeNull();
  });

  it('تب‌ها و اعمال رنگ روی آخرین ترسیم', () => {
    const a = api();
    render(<ToolPropertiesPanel api={a} last={{ id: 'x', name: 'straightLine' }} />);
    expect(screen.getByTestId('tool-properties')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('tool-color-#10b981'));
    expect(a.updateLast).toHaveBeenCalledWith({ styles: { color: '#10b981' } });
  });

  it('تب هشدار صادقانه غیرفعال است', () => {
    render(<ToolPropertiesPanel api={api()} last={{ id: 'x', name: 'ftsFib' }} />);
    fireEvent.click(screen.getByTestId('tool-tab-alerts'));
    expect(screen.getByTestId('tool-alerts-note')).toBeInTheDocument();
  });

  it('تب نمایان مقدار visible را override می‌کند', () => {
    const a = api();
    render(<ToolPropertiesPanel api={a} last={{ id: 'x', name: 'segment' }} />);
    fireEvent.click(screen.getByTestId('tool-tab-visibility'));
    fireEvent.click(screen.getByRole('button', { name: 'نمایان' }));
    expect(a.updateLast).toHaveBeenCalledWith({ styles: { visible: false } });
  });
});
