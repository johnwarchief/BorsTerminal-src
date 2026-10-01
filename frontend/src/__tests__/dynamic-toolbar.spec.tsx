// DynamicToolbar — برداشت از @uselayouts/dynamic-toolbar.
// انگیزه: نوارِ فیلترهایِ تابلوخوانی رویِ ۱۳۶۶ به چهار ردیف می‌شکست و
// ~۹۵ پیکسل از ارتفاع را می‌خورد؛ در صفحه‌ای با جدولِ هزاران‌ردیفی گران است.
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { DynamicToolbar } from '@shared/ui/DynamicToolbar';

const paint = () =>
  render(
    <DynamicToolbar
      primary={<button type="button">چیپ</button>}
      secondary={<button type="button">تنظیم</button>}
    />,
  );

describe('DynamicToolbar', () => {
  it('در آغاز رویِ صفحهٔ اول است', () => {
    paint();
    const box = screen.getByTestId('dynamic-toolbar').querySelector('[data-page]');
    expect(box?.getAttribute('data-page')).toBe('primary');
  });

  it('کلید، صفحه را عوض می‌کند و برمی‌گرداند', () => {
    paint();
    const btn = screen.getByTestId('dynamic-toolbar-toggle');
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('هر دو صفحه در DOM می‌مانند — فوکوس و حالتِ کنترل‌ها از بین نمی‌رود', () => {
    // جابه‌جایی با transform است نه با unmount؛ وگرنه اسلایدری که کاربر
    // وسطِ تنظیمش بود هر بار از نو ساخته می‌شد.
    paint();
    expect(screen.getByText('چیپ')).toBeInTheDocument();
    expect(screen.getByText('تنظیم')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('dynamic-toolbar-toggle'));
    expect(screen.getByText('چیپ')).toBeInTheDocument();
    expect(screen.getByText('تنظیم')).toBeInTheDocument();
  });

  it('صفحهٔ پنهان از صفحه‌خوان مخفی می‌شود', () => {
    paint();
    expect(screen.getByTestId('dynamic-toolbar-secondary').getAttribute('aria-hidden')).toBe('true');
    fireEvent.click(screen.getByTestId('dynamic-toolbar-toggle'));
    expect(screen.getByTestId('dynamic-toolbar-primary').getAttribute('aria-hidden')).toBe('true');
  });

  it('بی‌ResizeObserver هم می‌شکند نه — فقط انیمیشن را از دست می‌دهد', () => {
    const ro = globalThis.ResizeObserver;
    // @ts-expect-error — شبیه‌سازیِ WebViewِ قدیمی
    delete globalThis.ResizeObserver;
    expect(() => paint()).not.toThrow();
    globalThis.ResizeObserver = ro;
  });
});
