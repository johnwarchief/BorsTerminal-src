// تست دیالوگ تنظیمات چارت (فاز ۳ — TV parity)
// پنلِ تنظیمات ابزارِ ترسیم (ToolPropertiesPanel) با رپرِ قدیمی از برنامه
// بیرون رفت؛ تنظیماتِ ابزارِ زنده در FloatingPropertiesBar است.
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChartSettingsDialog } from '@features/technical/components/ChartSettingsDialog';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

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

  it('سوییچ موتورِ رندر دیگر گزینه نیست: چارتِ برنامه یکی است', () => {
    // «موتور رندر → Lightweight Charts» دکمهٔ بی‌اثر بود: هیچ مصرف‌کننده‌ای
    // آن را نمی‌خواند و رپرِ lightweight مرده بود. قانونِ خودِ دیالوگ: هر
    // گزینه باید در چارتِ زنده اثر بگذارد.
    render(<ChartSettingsDialog open onClose={() => undefined} initialTab="symbol" />);
    expect(screen.queryByRole('button', { name: 'Lightweight Charts' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'klinecharts (فعلی)' })).not.toBeInTheDocument();
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
