// src/__tests__/technical-canvas-recovery.spec.tsx
// تست‌های اعتبارسنجی بازیابی کندل‌ها، پارس تاریخ، فال‌بک چندلایه و استایل‌های دیالوگ تنظیمات
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { parseCandleTimestamp, jalaaliToGregorian } from '@features/technical/lib/jalaliDate';
import { ChartSettingsDialog } from '@features/technical/components/ChartSettingsDialog';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

describe('پارس مقاوم تاریخ و زمان برای کندل‌های بوم', () => {
  it('تبدیل جلالی به میلادی jalaaliToGregorian', () => {
    // 1 فروردین 1404 -> 21 مارس 2025
    const [gy, gm, gd] = jalaaliToGregorian(1404, 1, 1);
    expect([gy, gm, gd]).toEqual([2025, 3, 21]);

    // 10 مرداد 1402 -> 1 آگوست 2023
    const [gy2, gm2, gd2] = jalaaliToGregorian(1402, 5, 10);
    expect([gy2, gm2, gd2]).toEqual([2023, 8, 1]);
  });

  it('پارس فرمت عددی ۸ رقمی YYYYMMDD', () => {
    const ts = parseCandleTimestamp('20240115');
    expect(Number.isFinite(ts)).toBe(true);
    const d = new Date(ts);
    expect(d.getUTCFullYear()).toBe(2024);
    expect(d.getUTCMonth()).toBe(0); // ژانویه
    expect(d.getUTCDate()).toBe(15);
  });

  it('پارس فرمت تاریخ شمسی 1402-05-10', () => {
    const ts = parseCandleTimestamp('1402-05-10');
    expect(Number.isFinite(ts)).toBe(true);
    const d = new Date(ts);
    expect(d.getUTCFullYear()).toBe(2023);
    expect(d.getUTCMonth()).toBe(7); // آگوست
    expect(d.getUTCDate()).toBe(1);
  });

  it('پارس فرمت عددی ۸ رقمی شمسی 14020510', () => {
    const ts = parseCandleTimestamp('14020510');
    expect(Number.isFinite(ts)).toBe(true);
    const d = new Date(ts);
    expect(d.getUTCFullYear()).toBe(2023);
    expect(d.getUTCMonth()).toBe(7);
    expect(d.getUTCDate()).toBe(1);
  });

  it('پارس عدد ثانیه‌ای و میلی‌ثانیه‌ای', () => {
    const tsSec = parseCandleTimestamp(1705276800);
    expect(tsSec).toBe(1705276800000);

    const tsMs = parseCandleTimestamp(1705276800000);
    expect(tsMs).toBe(1705276800000);
  });

  it('بازگرداندن NaN برای مقادیر نامعتبر یا خالی', () => {
    expect(Number.isNaN(parseCandleTimestamp(''))).toBe(true);
    expect(Number.isNaN(parseCandleTimestamp('invalid-date'))).toBe(true);
    expect(Number.isNaN(parseCandleTimestamp(null))).toBe(true);
    expect(Number.isNaN(parseCandleTimestamp(undefined))).toBe(true);
    expect(Number.isNaN(parseCandleTimestamp(-100))).toBe(true);
  });
});

describe('بازطراحی استایل و ساختار دیالوگ تنظیمات (ChartSettingsDialog)', () => {
  it('تب خط وضعیت (Status Line) گروه‌بندی ساختاریافته دارد', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} symbol="فولاد" initialTab="status" />);
    
    // عنوان و برچسب نماد در هدر
    expect(screen.getByText('تنظیمات چارت')).toBeInTheDocument();
    expect(screen.getByText('فولاد')).toBeInTheDocument();

    // بخش خطِ وضعیتِ کندل
    expect(screen.getByText('خطِ وضعیتِ کندل')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /مقادیر OHLC/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /حجم معاملات/ })).toBeInTheDocument();

    // بخش اندیکاتورها و افسانه
    expect(screen.getByText('مقادیر اندیکاتورها')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /افسانه/ })).toBeInTheDocument();
    // #168: چسبندگیِ متن گزینهٔ جدا دارد، وگرنه بلوکِ متن گوشۀ بوم را می‌پوشاند
    expect(screen.getByRole('button', { name: /همیشه روی بوم بماند/ })).toBeInTheDocument();
  });

  it('سوئیچ‌های مدرن Toggle در حالت روشن/خاموش درست عمل می‌کنند', () => {
    render(<ChartSettingsDialog open onClose={() => undefined} initialTab="status" />);
    const ohlcBtn = screen.getByRole('button', { name: /مقادیر OHLC/ });
    const initialVal = useFtsConfigStore.getState().view.statusShowOhlc;

    fireEvent.click(ohlcBtn);
    expect(useFtsConfigStore.getState().view.statusShowOhlc).toBe(!initialVal);
  });

  it('فوتر پنجره و دکمه بستن و اعمال به درستی رندر و فراخوانی می‌شود', () => {
    const onClose = vi.fn();
    render(<ChartSettingsDialog open onClose={onClose} />);
    const closeBtn = screen.getByRole('button', { name: 'بستن و اعمال' });
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });
});
