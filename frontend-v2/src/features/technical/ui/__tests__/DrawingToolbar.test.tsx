/**
 * frontend-v2/src/features/technical/ui/__tests__/DrawingToolbar.test.tsx
 *
 * آزمون‌های واحد و یکپارچگی نوار ابزار رسم (DrawingToolbar):
 * ۱. رندر نوار ابزار عمودی در سمت راست و دکمه‌های ۳ دسته اصلی
 * ۲. باز و بسته شدن پاپ‌اور انتخاب ابزار و نمایش اسامی فارسی
 * ۳. انتخاب ابزار رسم و به‌روزرسانی activeDrawingTool در technicalStore
 * ۴. عملکرد دکمه لغو ابزار فعال و بازنشانی وضعیت
 * ۵. انتشار رویداد kline:clear-drawings هنگام کلیک روی دکمه سطل زباله
 * ۶. بستن پاپ‌اور با فشردن کلید Escape
 */

import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { DrawingToolbar } from '../DrawingToolbar';
import { useTechnicalStore } from '../../model/technicalStore';

describe('DrawingToolbar', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders vertical drawing toolbar with category buttons and actions', () => {
    render(<DrawingToolbar />);

    const toolbar = screen.getByTestId('drawing-toolbar');
    expect(toolbar).toBeDefined();

    // دکمه‌های دسته‌بندی
    expect(screen.getByTitle('ابزارهای خطی')).toBeDefined();
    expect(screen.getByTitle('ابزارهای فیبوناچی و هندسی')).toBeDefined();
    expect(screen.getByTitle('زون‌ها و اشکال')).toBeDefined();

    // دکمه‌های کنترلی لغو و پاک‌سازی
    expect(screen.getByTestId('cancel-tool-button')).toBeDefined();
    expect(screen.getByTestId('clear-drawings-button')).toBeDefined();
  });

  it('opens category popover on button click and displays Persian tool names', () => {
    render(<DrawingToolbar />);

    const linesBtn = screen.getByTitle('ابزارهای خطی');
    fireEvent.click(linesBtn);

    // ابزارهای خطی در پاپ‌اور نمایش داده می‌شوند
    expect(screen.getByText('خط روند')).toBeDefined();
    expect(screen.getByText('خط افقی')).toBeDefined();
    expect(screen.getByText('کانال موازی')).toBeDefined();
    expect(screen.getByText('کانال رگرسیون')).toBeDefined();
  });

  it('selects a drawing tool and updates technicalStore activeDrawingTool', () => {
    render(<DrawingToolbar />);

    // باز کردن دسته خطوط و کلیک روی خط روند
    fireEvent.click(screen.getByTitle('ابزارهای خطی'));
    const trendLineBtn = screen.getByText('خط روند');
    fireEvent.click(trendLineBtn);

    expect(useTechnicalStore.getState().activeDrawingTool).toBe('trendLine');
  });

  it('cancels active tool when cancel button is clicked', () => {
    useTechnicalStore.getState().setActiveDrawingTool('fibonacciRetracement');
    render(<DrawingToolbar />);

    const cancelBtn = screen.getByTestId('cancel-tool-button');
    expect(cancelBtn.hasAttribute('disabled')).toBe(false);

    fireEvent.click(cancelBtn);
    expect(useTechnicalStore.getState().activeDrawingTool).toBeNull();
  });

  it('dispatches kline:clear-drawings custom event and triggers onClearDrawings callback', () => {
    const handleClear = vi.fn();
    const eventListener = vi.fn();
    window.addEventListener('kline:clear-drawings', eventListener);

    render(<DrawingToolbar onClearDrawings={handleClear} />);

    const clearBtn = screen.getByTestId('clear-drawings-button');
    fireEvent.click(clearBtn);

    expect(eventListener).toHaveBeenCalledTimes(1);
    expect(handleClear).toHaveBeenCalledTimes(1);
    expect(useTechnicalStore.getState().activeDrawingTool).toBeNull();

    window.removeEventListener('kline:clear-drawings', eventListener);
  });

  it('closes popover on Escape key press', () => {
    render(<DrawingToolbar />);

    fireEvent.click(screen.getByTitle('زون‌ها و اشکال'));
    expect(screen.getByText('مستطیل عرضه و تقاضا')).toBeDefined();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByText('مستطیل عرضه و تقاضا')).toBeNull();
  });

  it('toggles Rahavard 365 drawing ergonomics: magnet, lock, and hide', () => {
    render(<DrawingToolbar />);

    const magnetBtn = screen.getByTestId('magnet-mode-button');
    expect(useTechnicalStore.getState().isMagnetMode).toBe(false);
    fireEvent.click(magnetBtn);
    expect(useTechnicalStore.getState().isMagnetMode).toBe(true);

    const lockBtn = screen.getByTestId('lock-drawings-button');
    expect(useTechnicalStore.getState().isLockedAllDrawings).toBe(false);
    fireEvent.click(lockBtn);
    expect(useTechnicalStore.getState().isLockedAllDrawings).toBe(true);

    const hideBtn = screen.getByTestId('hide-drawings-button');
    expect(useTechnicalStore.getState().isHideAllDrawings).toBe(false);
    fireEvent.click(hideBtn);
    expect(useTechnicalStore.getState().isHideAllDrawings).toBe(true);
  });
});
