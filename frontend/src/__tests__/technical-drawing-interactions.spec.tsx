// تست‌های تعاملی نوار ابزار رسم و نوار شناور تنظیمات المان (TradingView Drawing Interactions)
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { FloatingPropertiesBar } from '@features/technical/nahayatnegar/components/FloatingPropertiesBar';
import { DrawingToolbar } from '@features/technical/nahayatnegar/components/DrawingToolbar';

describe('نوار شناور تنظیمات المان (FloatingPropertiesBar)', () => {
  const defaultProps = {
    visible: true,
    selectedToolName: 'خط روند',
    currentColor: '#2962ff',
    currentWidth: 2,
    currentStyle: 'solid' as const,
    isLocked: false,
    onColorChange: vi.fn(),
    onWidthChange: vi.fn(),
    onStyleChange: vi.fn(),
    onToggleLock: vi.fn(),
    onDelete: vi.fn(),
    onClose: vi.fn(),
  };

  it('در حالت visible=false هیچ چیز رندر نمی‌کند', () => {
    const { container } = render(<FloatingPropertiesBar {...defaultProps} visible={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('رندر دکمه‌های استایل خط: ممتد، خط‌چین و نقطه‌چین', () => {
    render(<FloatingPropertiesBar {...defaultProps} />);
    expect(screen.getByRole('button', { name: 'خط ممتد' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'خط‌چین' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'نقطه‌چین' })).toBeInTheDocument();
  });

  it('کلیک روی سبک‌های مختلف، onStyleChange را با آرگومان درست صدا می‌زند', () => {
    const onStyleChange = vi.fn();
    render(<FloatingPropertiesBar {...defaultProps} onStyleChange={onStyleChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'نقطه‌چین' }));
    expect(onStyleChange).toHaveBeenCalledWith('dotted');

    fireEvent.click(screen.getByRole('button', { name: 'خط‌چین' }));
    expect(onStyleChange).toHaveBeenCalledWith('dashed');

    fireEvent.click(screen.getByRole('button', { name: 'خط ممتد' }));
    expect(onStyleChange).toHaveBeenCalledWith('solid');
  });

  it('کلیک روی ضخامت‌ها، onWidthChange را صدا می‌زند', () => {
    const onWidthChange = vi.fn();
    render(<FloatingPropertiesBar {...defaultProps} onWidthChange={onWidthChange} />);

    fireEvent.click(screen.getByTitle('ضخامت 3 پیکسل'));
    expect(onWidthChange).toHaveBeenCalledWith(3);

    fireEvent.click(screen.getByTitle('ضخامت 1 پیکسل'));
    expect(onWidthChange).toHaveBeenCalledWith(1);
  });

  it('کلیک روی قفل، حذف و بستن نوار، متدهای مربوطه را صدا می‌زند', () => {
    const onToggleLock = vi.fn();
    const onDelete = vi.fn();
    const onClose = vi.fn();

    render(
      <FloatingPropertiesBar
        {...defaultProps}
        onToggleLock={onToggleLock}
        onDelete={onDelete}
        onClose={onClose}
      />
    );

    fireEvent.click(screen.getByTitle('قفل کردن المان'));
    expect(onToggleLock).toHaveBeenCalled();

    fireEvent.click(screen.getByTitle('حذف این المان'));
    expect(onDelete).toHaveBeenCalled();

    fireEvent.click(screen.getByTitle('بستن نوار تنظیمات'));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('نوار ابزار رسم (DrawingToolbar)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const defaultToolbarProps = {
    activeToolId: 'trendLine',
    onSelectTool: vi.fn(),
    onClearDrawings: vi.fn(),
    isMagnetActive: false,
    onToggleMagnet: vi.fn(),
    isLocked: false,
    onToggleLock: vi.fn(),
    isHideActive: false,
    onToggleHide: vi.fn(),
  };

  it('رندر اسلات‌های ابزار و ابزارهای کنترل سایدبار چپ', () => {
    render(<DrawingToolbar {...defaultToolbarProps} />);
    expect(screen.getByTitle('خط‌کش اندازه‌گیری')).toBeInTheDocument();
    expect(screen.getByTitle('آهنربا: غیرفعال')).toBeInTheDocument();
    expect(screen.getByTitle('قفل ترسیم‌ها: باز')).toBeInTheDocument();
    expect(screen.getByTitle('ترسیم‌ها: نمایان')).toBeInTheDocument();
    expect(screen.getByTitle('حذف تمام ترسیم‌ها')).toBeInTheDocument();
  });

  it('کلیک روی سطل زباله، تاییدیه می‌خواهد و در صورت لغو پاک نمی‌کند', () => {
    const onClearDrawings = vi.fn();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<DrawingToolbar {...defaultToolbarProps} onClearDrawings={onClearDrawings} />);
    fireEvent.click(screen.getByTitle('حذف تمام ترسیم‌ها'));

    expect(confirmSpy).toHaveBeenCalled();
    expect(onClearDrawings).not.toHaveBeenCalled();
  });

  it('کلیک روی سطل زباله، در صورت تایید کاربر onClearDrawings را صدا می‌زند', () => {
    const onClearDrawings = vi.fn();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<DrawingToolbar {...defaultToolbarProps} onClearDrawings={onClearDrawings} />);
    fireEvent.click(screen.getByTitle('حذف تمام ترسیم‌ها'));

    expect(confirmSpy).toHaveBeenCalled();
    expect(onClearDrawings).toHaveBeenCalledTimes(1);
  });

  it('کلیک روی اکشن‌های مگنت، قفل و مخفی‌سازی متدهای مربوطه را صدا می‌زند', () => {
    const onToggleMagnet = vi.fn();
    const onToggleLock = vi.fn();
    const onToggleHide = vi.fn();

    render(
      <DrawingToolbar
        {...defaultToolbarProps}
        onToggleMagnet={onToggleMagnet}
        onToggleLock={onToggleLock}
        onToggleHide={onToggleHide}
      />
    );

    fireEvent.click(screen.getByTitle('آهنربا: غیرفعال'));
    expect(onToggleMagnet).toHaveBeenCalled();

    fireEvent.click(screen.getByTitle('قفل ترسیم‌ها: باز'));
    expect(onToggleLock).toHaveBeenCalled();

    fireEvent.click(screen.getByTitle('ترسیم‌ها: نمایان'));
    expect(onToggleHide).toHaveBeenCalled();
  });
});
