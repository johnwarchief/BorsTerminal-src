// تست دیالوگ تنظیمات چارت و پنل تنظیمات ابزار ترسیم (فاز ۳ — TV parity)
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChartSettingsDialog } from '@features/technical/components/ChartSettingsDialog';
import { ToolPropertiesPanel } from '@features/technical/components/ToolPropertiesPanel';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';
import type { ChartDrawApi } from '@features/technical/components/KLineChartWrapper';

function api(): ChartDrawApi & { updateLast: ReturnType<typeof vi.fn>; saveAsDefault: ReturnType<typeof vi.fn> } {
  return {
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
    listGroups: vi.fn(() => []),
    setGroupVisible: vi.fn(),
    removeGroup: vi.fn(),
    setTargetGroup: vi.fn(),
  } as unknown as ChartDrawApi & { updateLast: ReturnType<typeof vi.fn>; saveAsDefault: ReturnType<typeof vi.fn> };
}

describe('دیالوگ تنظیمات چارت', () => {
  it('بسته هیچ نمی‌سازد', () => {
    render(<ChartSettingsDialog open={false} onClose={() => undefined} />);
    expect(screen.queryByTestId('chart-settings')).toBeNull();
  });

  it('باز، تغییر نوع چارت/مقیاس را به استور می‌دهد', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} />);
    expect(screen.getByTestId('chart-settings')).toBeInTheDocument();
    // نوع چارت در تبِ نماد است، مقیاسِ قیمت در تبِ مقیاس‌ها
    fireEvent.click(screen.getByTestId('settings-tab-symbol'));
    fireEvent.click(screen.getByRole('button', { name: 'اریا' }));
    expect(useFtsConfigStore.getState().chartType).toBe('area');
    fireEvent.click(screen.getByTestId('settings-tab-scales'));
    fireEvent.click(screen.getByRole('button', { name: 'لگاریتمی' }));
    expect(useFtsConfigStore.getState().priceScale).toBe('logarithm');
  });

  it('دکمهٔ بستن onClose را صدا می‌زند', () => {
    const onClose = vi.fn();
    render(<ChartSettingsDialog open onClose={onClose} />);
    fireEvent.click(screen.getByTestId('chart-settings-close'));
    expect(onClose).toHaveBeenCalled();
  });

  it('سوییچ موتور چارت: پیش‌فرض klinecharts و تغییر به lightweight', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} initialTab="symbol" />);
    expect(['klinecharts', 'lightweight']).toContain(useFtsConfigStore.getState().chartEngine);
    fireEvent.click(screen.getByRole('button', { name: 'Lightweight Charts' }));
    expect(useFtsConfigStore.getState().chartEngine).toBe('lightweight');
    fireEvent.click(screen.getByRole('button', { name: 'klinecharts (فعلی)' }));
    expect(useFtsConfigStore.getState().chartEngine).toBe('klinecharts');
  });

  it('تب رنگ‌بندی: پس‌زمینه و رنگ کندل روی view اثر می‌گذارد', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} />);
    fireEvent.click(screen.getByTestId('settings-tab-colors'));
    fireEvent.click(screen.getByRole('button', { name: 'کلاسیک تیره' }));
    expect(useFtsConfigStore.getState().view.background).toBe('classic');
    fireEvent.click(screen.getByTestId('up-#26a69a'));
    expect(useFtsConfigStore.getState().view.candleUp).toBe('#26a69a');
    fireEvent.click(screen.getByTestId('reset-up'));
    expect(useFtsConfigStore.getState().view.candleUp).toBeNull();
  });

  it('تب مقیاس‌ها: معکوس‌سازی، قفل درگ محور و قفلِ مقیاسِ عمودی (#167)', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} />);
    const before = useFtsConfigStore.getState().view.yAxisReverse;
    fireEvent.click(screen.getByRole('button', { name: /معکوس‌سازی/ }));
    expect(useFtsConfigStore.getState().view.yAxisReverse).toBe(!before);
    fireEvent.click(screen.getByRole('button', { name: /قفل درگ محور/ }));
    expect(useFtsConfigStore.getState().view.axisDragLock).toBe(true);
    const lock = useFtsConfigStore.getState().view.axisScaleLock;
    fireEvent.click(screen.getByRole('button', { name: /قفلِ قیمت به نسبتِ کندل/ }));
    expect(useFtsConfigStore.getState().view.axisScaleLock).toBe(!lock);
  });

  it('تب خط وضعیت: چسبندگیِ متن (#168) روی view نوشته می‌شود', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} initialTab="status" />);
    const before = useFtsConfigStore.getState().view.legendAlways === true;
    fireEvent.click(screen.getByRole('button', { name: /همیشه روی بوم بماند/ }));
    expect(useFtsConfigStore.getState().view.legendAlways).toBe(!before);
  });

  it('تب دقت و اعشار: عددِ صریح و خودکار روی view می‌نشیند', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} initialTab="precision" />);
    fireEvent.click(screen.getByRole('button', { name: '۲' }));
    expect(useFtsConfigStore.getState().view.pricePrecision).toBe(2);
    fireEvent.click(screen.getByRole('button', { name: 'خودکار' }));
    expect(useFtsConfigStore.getState().view.pricePrecision).toBe('auto');
  });

  it('تب رویدادها: سوئیچ‌های مستقل D/S حذف‌اند، چون سرور نوعِ رویداد را نمی‌فرستد', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} />);
    fireEvent.click(screen.getByTestId('settings-tab-events'));
    expect(screen.getByTestId('settings-events-note')).toBeInTheDocument();
    expect(screen.getByText(/ساختگی/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /سود نقدی مصوب/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /افزایش سرمایه و سهام جایزه/ })).not.toBeInTheDocument();
  });

  it('شش تبِ استاندارد هست و هیچ گزینه‌ای دو بار تکرار نشده', () => {
    const { container } = render(<ChartSettingsDialog open onClose={() => undefined} />);
    for (const id of ['symbol', 'status', 'scales', 'colors', 'precision', 'events']) {
      expect(screen.getByTestId(`settings-tab-${id}`)).toBeInTheDocument();
    }
    // نامِ متغیرِ خامِ موتور نباید به‌جای فارسیِ خوانا به کاربر نشان داده شود
    expect(container.textContent).not.toContain('candle.upColor');
    expect(container.textContent).not.toContain('candle.downColor');
    // ردیفِ رنگ فقط یک بار، در تبِ رنگ‌بندی
    fireEvent.click(screen.getByTestId('settings-tab-symbol'));
    expect(screen.queryByTestId('up-#26a69a')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('settings-tab-colors'));
    expect(screen.getByTestId('up-#26a69a')).toBeInTheDocument();
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

  it('تب مختصات نقطه‌های آخرین ترسیم را نشان می‌دهد', () => {
    const a = api();
    (a.getLastPoints as unknown as ReturnType<typeof vi.fn>).mockReturnValue([
      { price: 1234, date: '1404/06/23' },
      { price: 987, date: '1404/06/20' },
    ]);
    render(<ToolPropertiesPanel api={a} last={{ id: 'x', name: 'straightLine' }} />);
    fireEvent.click(screen.getByTestId('tool-tab-coords'));
    expect(screen.getByTestId('tool-coords').textContent).toContain('1404/06/23');
    expect(screen.getByTestId('tool-coords').textContent).toContain('1234');
  });

  it('ذخیره به‌عنوان پیش‌فرض api را صدا می‌زند', () => {
    const a = api();
    render(<ToolPropertiesPanel api={a} last={{ id: 'x', name: 'straightLine' }} />);
    fireEvent.click(screen.getByTestId('tool-color-#38bdf8'));
    fireEvent.click(screen.getByTestId('tool-save-default'));
    expect(a.saveAsDefault).toHaveBeenCalledWith({ styles: { color: '#38bdf8' }, extendData: {} });
  });

  it('تب نمایان مقدار visible را override می‌کند', () => {
    const a = api();
    render(<ToolPropertiesPanel api={a} last={{ id: 'x', name: 'segment' }} />);
    fireEvent.click(screen.getByTestId('tool-tab-visibility'));
    fireEvent.click(screen.getByRole('button', { name: 'نمایان' }));
    expect(a.updateLast).toHaveBeenCalledWith({ styles: { visible: false } });
  });
});
