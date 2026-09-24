// src/__tests__/technical-toggle-verification.spec.tsx -- تست جامع دوطرفه (Two-Way Toggle) کلیه گزینه‌های تنظیمات چارت
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { ChartSettingsDialog } from '@features/technical/components/ChartSettingsDialog';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';
import { nahayatNegarDarkTheme, nahayatNegarLightTheme } from '@features/technical/nahayatnegar/lib/chartTheme';

const STORAGE_KEY = 'fts.chart.settings.v1';

describe('اعتبارسنجی دوطرفه (Two-Way Toggle Verification) و ماندگاری تنظیمات چارت', () => {
  beforeEach(() => {
    localStorage.clear();
    // بازنشانی استور به مقادیر پیش‌فرض
    useFtsConfigStore.setState({
      chartType: 'candle_solid',
      chartEngine: 'klinecharts',
      priceScale: 'normal',
      timeframe: 'day',
      showGrid: true,
      showCrosshair: true,
      showRsi: false,
      showVolMa: true,
      view: {
        yAxisReverse: false,
        yAxisInside: false,
        priceScalePos: 'right',
        axisDragLock: false,
        axisTickMargin: 0,
        background: 'dark',
        customBgColor: '#131722',
        candleUp: null,
        candleDown: null,
        borderUp: null,
        borderDown: null,
        wickUp: null,
        wickDown: null,
        showBorders: true,
        showWicks: true,
        wickGray: false,
        statusShowSymbol: true,
        statusShowOhlc: true,
        statusShowVolume: true,
        statusShowIndicators: true,
        showLegend: true,
        gridColor: '#242731',
        gridStyle: 'solid',
        showGridHorz: true,
        showGridVert: true,
        crosshairStyle: 'dashed',
        watermarkOpacity: 5,
        showWatermark: true,
        showCorporateActions: true,
        timezone: 'Asia/Tehran',
        showXAxis: true,
        showYAxis: true,
        splitLayout: 1,
        fibLogarithmic: false,
      },
    });
  });

  it('۱. تست دوطرفه مقادیر OHLC کندل جاری (روشن -> خاموش -> روشن) و ماندگاری در localStorage', () => {
    const { unmount } = render(<ChartSettingsDialog open onClose={() => undefined} initialTab="status" />);

    const ohlcBtn = screen.getByRole('button', { name: /مقادیر OHLC کندل جاری/ });
    expect(ohlcBtn).toBeInTheDocument();
    expect(useFtsConfigStore.getState().view.statusShowOhlc).toBe(true);

    // گام اول: کلیک اول -> تغییر وضعیت به خاموش
    fireEvent.click(ohlcBtn);
    expect(useFtsConfigStore.getState().view.statusShowOhlc).toBe(false);

    let saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.statusShowOhlc).toBe(false);

    // گام دوم: کلیک دوم -> تغییر وضعیت به روشن
    fireEvent.click(ohlcBtn);
    expect(useFtsConfigStore.getState().view.statusShowOhlc).toBe(true);

    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.statusShowOhlc).toBe(true);

    unmount();
  });

  it('۲. تست دوطرفه اندیکاتورهای پایه‌ای: MA حجم ۲۱ و RSI (14)', () => {
    const { unmount } = render(<ChartSettingsDialog open onClose={() => undefined} initialTab="appearance" />);

    // تست دوطرفه MA حجم ۲۱ (پیش‌فرض: روشن -> خاموش -> روشن)
    const volMaBtn = screen.getByRole('button', { name: /MA حجم ۲۱/ });
    expect(useFtsConfigStore.getState().showVolMa).toBe(true);

    fireEvent.click(volMaBtn);
    expect(useFtsConfigStore.getState().showVolMa).toBe(false);
    let saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.showVolMa).toBe(false);

    fireEvent.click(volMaBtn);
    expect(useFtsConfigStore.getState().showVolMa).toBe(true);
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.showVolMa).toBe(true);

    // تست دوطرفه RSI (14) (پیش‌فرض: خاموش -> روشن -> خاموش)
    const rsiBtn = screen.getByRole('button', { name: /RSI \(14\)/ });
    expect(useFtsConfigStore.getState().showRsi).toBe(false);

    fireEvent.click(rsiBtn);
    expect(useFtsConfigStore.getState().showRsi).toBe(true);
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.showRsi).toBe(true);

    fireEvent.click(rsiBtn);
    expect(useFtsConfigStore.getState().showRsi).toBe(false);
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.showRsi).toBe(false);

    unmount();
  });

  it('۳. تست تغییر دوطرفه نوع چارت و مقیاس‌های قیمت (خطی / لگاریتمی / درصدی)', () => {
    const { unmount } = render(<ChartSettingsDialog open onClose={() => undefined} initialTab="scales" />);

    // نوع چارت: کندل شمعی -> خط -> کندل شمعی
    const lineBtn = screen.getByRole('button', { name: 'خط' });
    const candleBtn = screen.getByRole('button', { name: 'کندل شمعی' });

    fireEvent.click(lineBtn);
    expect(useFtsConfigStore.getState().chartType).toBe('line');
    let saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.chartType).toBe('line');

    fireEvent.click(candleBtn);
    expect(useFtsConfigStore.getState().chartType).toBe('candle_solid');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.chartType).toBe('candle_solid');

    // مقیاس قیمت: خطی -> لگاریتمی -> درصدی -> خطی
    const logBtn = screen.getByRole('button', { name: 'لگاریتمی' });
    const pctBtn = screen.getByRole('button', { name: 'درصدی' });
    const normalBtn = screen.getByRole('button', { name: 'خطی' });

    fireEvent.click(logBtn);
    expect(useFtsConfigStore.getState().priceScale).toBe('logarithm');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.priceScale).toBe('logarithm');

    fireEvent.click(pctBtn);
    expect(useFtsConfigStore.getState().priceScale).toBe('percentage');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.priceScale).toBe('percentage');

    fireEvent.click(normalBtn);
    expect(useFtsConfigStore.getState().priceScale).toBe('normal');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.priceScale).toBe('normal');

    unmount();
  });

  it('۴. تست دوطرفه نشانگر رویدادهای تعدیل در تب رویدادها', () => {
    const { unmount } = render(<ChartSettingsDialog open onClose={() => undefined} initialTab="events" />);

    const allEventsBtn = screen.getByRole('button', { name: /نمایش کلیه نشانگرهای رویداد شرکتی روی کندل‌ها/ });
    fireEvent.click(allEventsBtn);
    expect(useFtsConfigStore.getState().view.showCorporateActions).toBe(false);
    let saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.showCorporateActions).toBe(false);

    fireEvent.click(allEventsBtn);
    expect(useFtsConfigStore.getState().view.showCorporateActions).toBe(true);
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.showCorporateActions).toBe(true);

    unmount();
  });

  it('۵. تست دوطرفه واترمارک، خطوط گرید و تفکیک خطوط افقی/عمودی', () => {
    const { unmount } = render(<ChartSettingsDialog open onClose={() => undefined} initialTab="appearance" />);

    // تست دوطرفه نمایش واترمارک
    const watermarkBtn = screen.getByRole('button', { name: /نمایش واترمارک/ });
    fireEvent.click(watermarkBtn);
    expect(useFtsConfigStore.getState().view.showWatermark).toBe(false);
    let saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.showWatermark).toBe(false);

    fireEvent.click(watermarkBtn);
    expect(useFtsConfigStore.getState().view.showWatermark).toBe(true);
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.showWatermark).toBe(true);

    // تست دوطرفه کلیه خطوط شبکه (Grid)
    const gridBtn = screen.getByRole('button', { name: /کلیه خطوط شبکه/ });
    fireEvent.click(gridBtn);
    expect(useFtsConfigStore.getState().showGrid).toBe(false);
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.showGrid).toBe(false);

    fireEvent.click(gridBtn);
    expect(useFtsConfigStore.getState().showGrid).toBe(true);
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.showGrid).toBe(true);

    // تست دوطرفه خطوط افقی و عمودی
    const horzBtn = screen.getByRole('button', { name: /خطوط افقی/ });
    fireEvent.click(horzBtn);
    expect(useFtsConfigStore.getState().view.showGridHorz).toBe(false);

    fireEvent.click(horzBtn);
    expect(useFtsConfigStore.getState().view.showGridHorz).toBe(true);

    const vertBtn = screen.getByRole('button', { name: /خطوط عمودی/ });
    fireEvent.click(vertBtn);
    expect(useFtsConfigStore.getState().view.showGridVert).toBe(false);

    fireEvent.click(vertBtn);
    expect(useFtsConfigStore.getState().view.showGridVert).toBe(true);

    // تست سوئیچ استایل گرید (ممتد / خط‌چین / نقطه‌چین / بدون خط)
    const dashedBtns = screen.getAllByRole('button', { name: 'خط‌چین' });
    const dashedGridBtn = dashedBtns[0];
    const solidBtns = screen.getAllByRole('button', { name: 'ممتد' });
    const solidGridBtn = solidBtns[0];

    fireEvent.click(dashedGridBtn);
    expect(useFtsConfigStore.getState().view.gridStyle).toBe('dashed');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.gridStyle).toBe('dashed');

    fireEvent.click(solidGridBtn);
    expect(useFtsConfigStore.getState().view.gridStyle).toBe('solid');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.gridStyle).toBe('solid');

    unmount();
  });

  it('۶. اعتبارسنجی تم‌های چارت نهایت‌نگر: پیوستگی گرید با separator، اندازه ۳۲px محور زمان و خوانایی تولتیپ اندیکاتور', () => {
    // تم دارک
    expect(nahayatNegarDarkTheme.separator.size).toBe(1);
    expect(nahayatNegarDarkTheme.separator.fill).toBe(true);
    expect(nahayatNegarDarkTheme.separator.color).toBe('#242731');
    expect(nahayatNegarDarkTheme.xAxis.size).toBe(32);
    expect(nahayatNegarDarkTheme.indicator.tooltip.text.size).toBe(11);
    expect(nahayatNegarDarkTheme.indicator.tooltip.text.color).toBe('#d1d4dc');

    // تم لایت
    expect(nahayatNegarLightTheme.separator.size).toBe(1);
    expect(nahayatNegarLightTheme.separator.fill).toBe(true);
    expect(nahayatNegarLightTheme.separator.color).toBe('#f0f3fa');
    expect(nahayatNegarLightTheme.xAxis.size).toBe(32);
    expect(nahayatNegarLightTheme.indicator.tooltip.text.size).toBe(11);
    expect(nahayatNegarLightTheme.indicator.tooltip.text.color).toBe('#131722');
  });

  it('۷. تست دوطرفه تغییر پس‌زمینه چارت (دارک / لایت / کلاسیک) در دیالوگ تنظیمات و ذخیره آن', () => {
    const { unmount } = render(<ChartSettingsDialog open onClose={() => undefined} initialTab="appearance" />);

    // انتخاب تم روشن
    const lightBgBtn = screen.getByRole('button', { name: 'روشن' });
    fireEvent.click(lightBgBtn);
    expect(useFtsConfigStore.getState().view.background).toBe('light');
    let saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.background).toBe('light');

    // انتخاب تم کلاسیک
    const classicBgBtn = screen.getByRole('button', { name: 'کلاسیک تیره' });
    fireEvent.click(classicBgBtn);
    expect(useFtsConfigStore.getState().view.background).toBe('classic');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.background).toBe('classic');

    // انتخاب تم تیره
    const darkBgBtn = screen.getByRole('button', { name: 'تیره مات (#131722)' });
    fireEvent.click(darkBgBtn);
    expect(useFtsConfigStore.getState().view.background).toBe('dark');
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(saved.view.background).toBe('dark');

    unmount();
  });
});
