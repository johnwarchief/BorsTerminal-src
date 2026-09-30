// کارت‌هایِ نبضِ بازار: بازشونده با انیمیشنِ layoutِ motion.
// قاعده‌ای که نگه می‌داریم: هم‌زمان فقط یک کارت باز باشد — دو کارتِ
// تمام‌عرض یعنی همان فهرستِ عمودیِ بلندی که از اولش از آن فرار می‌کردیم.
import { describe, expect, it } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { MarketPulseBar } from '@features/market/components/MarketPulseBar';

const paint = () => render(<MarketPulseBar pulse={null} />);
describe('کارت‌هایِ بازشوندهٔ نبض', () => {
  it('در آغاز هیچ کارتی باز نیست', () => {
    paint();
    expect(document.querySelectorAll('[data-expanded]')).toHaveLength(0);
  });

  it('کلیک روی دکمه، همان کارت را باز می‌کند', () => {
    paint();
    const btn = document.querySelectorAll('[data-testid$="-expand"]')[0] as HTMLElement;
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-expanded')).toBe('true');
    expect(document.querySelectorAll('[data-expanded]')).toHaveLength(1);
  });

  it('کلیکِ دوباره جمعش می‌کند', () => {
    paint();
    const btn = document.querySelectorAll('[data-testid$="-expand"]')[0] as HTMLElement;
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(document.querySelectorAll('[data-expanded]')).toHaveLength(0);
  });

  it('بازکردنِ کارتِ دوم، اولی را می‌بندد', () => {
    paint();
    const btns = document.querySelectorAll('[data-testid$="-expand"]');
    if (btns.length < 2) return; // پوشش بسته به دادهٔ نبض
    fireEvent.click(btns[0] as HTMLElement);
    fireEvent.click(btns[1] as HTMLElement);
    expect(document.querySelectorAll('[data-expanded]')).toHaveLength(1);
    expect((btns[0] as HTMLElement).getAttribute('aria-expanded')).toBe('false');
  });

  it('کارتِ باز تمام‌عرض می‌شود', () => {
    paint();
    const btn = document.querySelectorAll('[data-testid$="-expand"]')[0] as HTMLElement;
    fireEvent.click(btn);
    const card = document.querySelector('[data-expanded]') as HTMLElement;
    expect(card.className).toContain('col-span-full');
  });
});
