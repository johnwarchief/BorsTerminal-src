// Modal مشترک رویِ Radix Dialog.
// انگیزه: بازرسیِ ۱٫۰٫۶۶ نشان داد از هشت مودالِ برنامه شش‌تا Escape نداشتند
// و هفت‌تا تلهٔ فوکوس. یعنی کاربر با Tab از داخلِ مودال به صفحهٔ پشتی
// می‌رفت — جایی که نمی‌دید کجاست.
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Modal } from '@shared/ui/Modal';

function paint(open = true, onClose = vi.fn()) {
  render(
    <Modal open={open} onClose={onClose} title="تنظیمات" description="توضیح">
      <button type="button">داخل</button>
    </Modal>,
  );
  return onClose;
}

describe('Modal', () => {
  it('بسته که باشد هیچ‌چیز در DOM نیست', () => {
    paint(false);
    expect(screen.queryByTestId('modal')).toBeNull();
  });

  it('نامِ دسترسی‌پذیر و نقشِ dialog دارد', () => {
    paint();
    const d = screen.getByRole('dialog');
    expect(d).toBeInTheDocument();
    expect(screen.getByText('تنظیمات')).toBeInTheDocument();
  });

  it('Escape می‌بندد — چیزی که شش مودالِ قبلی نداشتند', () => {
    const onClose = paint();
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape', code: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('دکمهٔ بستن کار می‌کند', () => {
    const onClose = paint();
    fireEvent.click(screen.getByTestId('modal-close'));
    expect(onClose).toHaveBeenCalled();
  });

  it('پس‌زمینه از صفحه‌خوان پنهان می‌شود', () => {
    // Radix به‌جایِ aria-modal رویِ خودِ دیالوگ، رویِ خواهرهایش
    // aria-hidden می‌گذارد. این روشِ مقاوم‌تری است: aria-modal را بعضی
    // صفحه‌خوان‌ها نادیده می‌گیرند، ولی aria-hidden را همه می‌فهمند.
    const bg = document.createElement('div');
    bg.textContent = 'محتوایِ پشتِ مودال';
    document.body.appendChild(bg);
    paint();
    expect(bg.getAttribute('aria-hidden')).toBe('true');
    bg.remove();
  });

  it('عنوان به دیالوگ گره خورده است (aria-labelledby)', () => {
    paint();
    const d = screen.getByRole('dialog');
    const id = d.getAttribute('aria-labelledby');
    expect(id).toBeTruthy();
    expect(document.getElementById(id as string)?.textContent).toBe('تنظیمات');
  });
  it('فوتر وقتی داده شود رندر می‌شود', () => {
    render(
      <Modal open onClose={() => {}} title="t" footer={<span>پانوشت</span>}>
        <p>x</p>
      </Modal>,
    );
    expect(screen.getByText('پانوشت')).toBeInTheDocument();
  });
});
