// CollapsibleSection — نبضِ بازار رویِ ۱۳۶۶ بیشترِ ارتفاع را می‌گرفت.
// چکِ اصلی: جمع‌شدن نباید کور کند (خلاصه می‌ماند)، وضعیت باید بماند، و
// محتوا باید از درخت بیرون نرود (وگرنه هر بار بازکردن دوباره fetch می‌شود).
import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CollapsibleSection } from '@shared/components/CollapsibleSection';

const KEY = 'test.section.open';

function paint(props: Partial<Parameters<typeof CollapsibleSection>[0]> = {}) {
  return render(
    <CollapsibleSection title="نبض بازار" storageKey={KEY} summary={<span>شاخص ۲٫۳ میلیون</span>} {...props}>
      <p>محتوایِ سنگین</p>
    </CollapsibleSection>,
  );
}

describe('CollapsibleSection', () => {
  beforeEach(() => localStorage.clear());

  it('پیش‌فرض باز است و aria درست است', () => {
    paint();
    expect(screen.getByTestId('collapsible-toggle').getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('محتوایِ سنگین')).toBeInTheDocument();
  });

  it('جمع می‌شود و خلاصه جایش را می‌گیرد', () => {
    paint();
    fireEvent.click(screen.getByTestId('collapsible-toggle'));
    expect(screen.getByTestId('collapsible-toggle').getAttribute('aria-expanded')).toBe('false');
    // جمع‌شدن نباید کور کند
    expect(screen.getByTestId('collapsible-summary')).toBeInTheDocument();
  });

  it('محتوا در حالتِ جمع از درخت بیرون نمی‌رود', () => {
    // اگر unmount می‌شد، هر بار بازکردن یعنی fetch و انیمیشنِ دوباره
    paint();
    fireEvent.click(screen.getByTestId('collapsible-toggle'));
    expect(screen.getByText('محتوایِ سنگین')).toBeInTheDocument();
  });

  it('وضعیت می‌ماند', () => {
    const { unmount } = paint();
    fireEvent.click(screen.getByTestId('collapsible-toggle'));
    expect(localStorage.getItem(KEY)).toBe('0');
    unmount();
    paint();
    expect(screen.getByTestId('collapsible-toggle').getAttribute('aria-expanded')).toBe('false');
  });

  it('وضعیتِ ذخیره‌شده بر defaultOpen مقدم است', () => {
    localStorage.setItem(KEY, '0');
    paint({ defaultOpen: true });
    expect(screen.getByTestId('collapsible-toggle').getAttribute('aria-expanded')).toBe('false');
  });

  it('ارتفاع با grid-rows انیمیت می‌شود، نه با پیکسل', () => {
    // height:auto قابلِ ترنزیشن نیست؛ 0fr↔1fr تنها راهِ خالصِ CSS است
    const { container } = paint();
    const body = container.querySelector('[id$="-body"]');
    expect(body?.className).toContain('grid-rows-[1fr]');
    fireEvent.click(screen.getByTestId('collapsible-toggle'));
    expect(container.querySelector('[id$="-body"]')?.className).toContain('grid-rows-[0fr]');
  });
});
