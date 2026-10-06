import { render, screen, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { LiveNumber } from '@shared/components/ui/live-number';
import { fmtInt } from '@shared/lib/fmt';

describe('LiveNumber — نمایشگر زنده عدد با انیمیشن روان و فلاش مارکت', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('۱. رندر مقدار اولیه: بلافاصله بدون انیمیشن یا فلاش نمایش داده می‌شود', () => {
    render(<LiveNumber value={100} />);
    const el = screen.getByRole('text');
    expect(el).toBeInTheDocument();
    expect(el.getAttribute('aria-label')).toBe(fmtInt(100));
    expect(el.className).not.toContain('live-flash-up');
    expect(el.className).not.toContain('live-flash-down');
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(100));
  });

  it('۲. گذار صعودی پیوسته (۱۰۰ ← ۱۱۰): فلاش مثبت (live-flash-up) می‌زند و درون‌یابی تدریجی دارد', () => {
    const { rerender } = render(<LiveNumber value={100} duration={500} />);
    const el = screen.getByRole('text');

    rerender(<LiveNumber value={110} duration={500} />);
    expect(el.className).toContain('live-flash-up');
    expect(el.className).not.toContain('live-flash-down');

    // در میانه انیمیشن (۲۰۰ms)، عدد هنوز ۱۱۰ نشده و در حال گذار است
    act(() => {
      vi.advanceTimersByTime(200);
    });
    const midText = screen.getByTestId('live-number-display').textContent;
    expect(midText).not.toBe(fmtInt(100));
    // در پایان (۶۰۰ms)، دقیقاً ۱۱۰ است
    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(el.getAttribute('aria-label')).toBe(fmtInt(110));
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(110));
  });

  it('۳. گذار نزولی پیوسته (۱۱۰ ← ۹۰): فلاش منفی (live-flash-down) می‌زند و به مقدار نهایی می‌رسد', () => {
    const { rerender } = render(<LiveNumber value={110} duration={500} />);
    const el = screen.getByRole('text');

    rerender(<LiveNumber value={90} duration={500} />);
    expect(el.className).toContain('live-flash-down');
    expect(el.className).not.toContain('live-flash-up');

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(el.getAttribute('aria-label')).toBe(fmtInt(90));
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(90));
  });

  it('۴. جایگزینی هدف در میانه انیمیشن (۱۰۰ ← ۱۱۰ ← ۱۰۵): انیمیشن از مقدار در حال رندر ادامه می‌یابد نه از ۱۰۰ یا صفر', () => {
    const { rerender } = render(<LiveNumber value={100} duration={500} />);

    // به سمت ۱۱۰ حرکت می‌کند
    rerender(<LiveNumber value={110} duration={500} />);
    act(() => {
      vi.advanceTimersByTime(200);
    });
    // مقدار میانی مثلاً ۱۰۶ است
    const midVal = screen.getByTestId('live-number-display').textContent;
    expect(midVal).not.toBe(fmtInt(100));
    expect(midVal).not.toBe(fmtInt(110));

    // ناگهان هدف به ۱۰۵ تغییر می‌کند
    rerender(<LiveNumber value={105} duration={500} />);

    // بررسی که به سمت ۱۰۵ هدایت می‌شود و ریست به ۱۰۰ یا صفر نمی‌شود
    act(() => {
      vi.advanceTimersByTime(10);
    });
    const afterReTarget = screen.getByTestId('live-number-display').textContent;
    expect(afterReTarget).not.toBe(fmtInt(100));
    expect(afterReTarget).not.toBe(fmtInt(0));

    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(105));
  });

  it('۵. تغییرات سریع چندباره (۱۰۰ ← ۱۱۰ ← ۱۰۵ ← ۹۹): تنها یک انیمیشن فعال و همگرایی پایدار به ۹۹', () => {
    const { rerender } = render(<LiveNumber value={100} duration={500} />);
    const el = screen.getByRole('text');

    rerender(<LiveNumber value={110} duration={500} />);
    act(() => {
      vi.advanceTimersByTime(100);
    });

    rerender(<LiveNumber value={105} duration={500} />);
    act(() => {
      vi.advanceTimersByTime(100);
    });

    rerender(<LiveNumber value={99} duration={500} />);
    expect(el.className).toContain('live-flash-down');

    act(() => {
      vi.advanceTimersByTime(600);
    });

    // رسیدن قطعی و دقیق به آخرین مقدار کانونی
    expect(el.getAttribute('aria-label')).toBe(fmtInt(99));
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(99));
  });

  it('۶. مقدار یکسان (SAME value ۹۰ ← ۹۰): هیچ انیمیشن یا فلاشی ایجاد نمی‌شود', () => {
    const { rerender } = render(<LiveNumber value={90} duration={500} />);
    const el = screen.getByRole('text');

    rerender(<LiveNumber value={90} duration={500} />);
    expect(el.className).not.toContain('live-flash-up');
    expect(el.className).not.toContain('live-flash-down');
  });

  it('۷. گذارهای null: ۱۰۰ ← null بلافاصله «-» می‌شود و null ← ۱۰۰ بدون شمارش از صفر مستقیماً ۱۰۰ می‌نشیند', () => {
    const { rerender } = render(<LiveNumber value={100} duration={500} />);
    rerender(<LiveNumber value={null} duration={500} />);
    expect(screen.getByTestId('live-number-display')).toHaveTextContent('-');

    // برگشت از null به ۱۰۰
    rerender(<LiveNumber value={100} duration={500} />);
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(100));
  });

  it('۸. پایداری چیدمان (No Layout Shift) در تغییر ارقام (۱٬۰۰۰٬۰۰۰ ↔ ۹۹۹٬۹۹۹)', () => {
    const { rerender } = render(<LiveNumber value={1000000} duration={500} />);
    
    // هنگام کاهش رقم، باکس رزروکننده همواره عریض‌ترین مقدار (۱٬۰۰۰٬۰۰۰) را حفظ می‌کند
    rerender(<LiveNumber value={999999} duration={500} />);
    
    const invisibleSpacer = screen.getByTestId('live-number-spacer');
    expect(invisibleSpacer).toBeInTheDocument();
    expect(invisibleSpacer).toHaveTextContent(fmtInt(1000000));

    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(999999));
  });

  it('۹. کاهش انیمیشن (prefers-reduced-motion): بدون تأخیر مقدار نهایی نشان داده می‌شود', () => {
    // شبیه‌سازی prefers-reduced-motion
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('prefers-reduced-motion: reduce'),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const { rerender } = render(<LiveNumber value={100} duration={500} />);
    rerender(<LiveNumber value={150} duration={500} />);

    // بلافاصله بدون اجرای advanceTimers به ۱۵۰ می‌رسد
    expect(screen.getByTestId('live-number-display')).toHaveTextContent(fmtInt(150));

    window.matchMedia = originalMatchMedia;
  });

  it('۱۰. پاکسازی کامل در خروج (Unmount Cleanup): لغو RAF و تایمرهای فلاش بدون خطا', () => {
    const { unmount, rerender } = render(<LiveNumber value={100} duration={500} />);
    rerender(<LiveNumber value={200} duration={500} />);
    expect(() => unmount()).not.toThrow();
  });
});
