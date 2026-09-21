// __tests__/flash-num.spec.tsx -- رفتارِ فلشِ نوسان: سبز برای افزایش، قرمز برای کاهش
//
// مکانیزم: FlashNum کلاسِ flash-up/flash-down را روی همان DOM node می‌گذارد
// (بدونِ key-change یا re-mount) تا در ترافیکِ بالا فریم نیفتد. این تست
// مستقیماً همان کلاس‌ها را رویِ span می‌خواند.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FlashNum } from '../shared/components/FlashNum';

function Cell({ value }: { value: number | null | undefined }) {
  return <FlashNum value={value} render={(v) => (v == null ? '-' : String(v))} data-testid="cell" />;
}

describe('FlashNum — فلشِ نوسانِ بهینه', () => {
  it('مقدارِ اولیه را بدونِ فلش رندر می‌کند', () => {
    render(<Cell value={100} />);
    const el = screen.getByTestId('cell');
    expect(el.textContent).toBe('100');
    expect(el.className).not.toMatch(/flash-(up|down)/);
  });

  it('افزایش → flash-up (سبز)', () => {
    const { rerender } = render(<Cell value={100} />);
    rerender(<Cell value={110} />);
    const el = screen.getByTestId('cell');
    expect(el.textContent).toBe('110');
    expect(el.className).toContain('flash-up');
    expect(el.className).not.toContain('flash-down');
  });

  it('کاهش → flash-down (قرمز)', () => {
    const { rerender } = render(<Cell value={100} />);
    rerender(<Cell value={95} />);
    const el = screen.getByTestId('cell');
    expect(el.textContent).toBe('95');
    expect(el.className).toContain('flash-down');
    expect(el.className).not.toContain('flash-up');
  });

  it('مقدارِ یکسان فلش نمی‌زند (ترافیکِ بالا بدونِ انیمیشنِ بی‌مورد)', () => {
    const { rerender } = render(<Cell value={100} />);
    rerender(<Cell value={100} />);
    const el = screen.getByTestId('cell');
    expect(el.className).not.toMatch(/flash-(up|down)/);
  });

  it('null → عدد فلش نمی‌زند و برعکس', () => {
    const { rerender } = render(<Cell value={null} />);
    rerender(<Cell value={50} />);
    const el = screen.getByTestId('cell');
    expect(el.textContent).toBe('50');
    expect(el.className).not.toMatch(/flash-(up|down)/);
  });

  it('همان DOM node حفظ می‌شود (بدونِ re-mount، یعنی بدونِ re-renderِ سنگین)', () => {
    const { rerender } = render(<Cell value={100} />);
    const before = screen.getByTestId('cell');
    rerender(<Cell value={110} />);
    const after = screen.getByTestId('cell');
    // همان مرجعِ آبجکت ⇒ React نود را تخریب/ساختن نکرده است.
    expect(after).toBe(before);
  });

  it('دو فلشِ پشتِ سر هم بازنشانی می‌شوند (انیمیشنِ دوم هم اجرا می‌شود)', () => {
    const { rerender } = render(<Cell value={100} />);
    rerender(<Cell value={110} />);
    expect(screen.getByTestId('cell').className).toContain('flash-up');
    // کاهشِ بعدی باید کلاسِ flash-up را پاک کند و flash-down بگذارد.
    rerender(<Cell value={105} />);
    const el = screen.getByTestId('cell');
    expect(el.className).toContain('flash-down');
    expect(el.className).not.toContain('flash-up');
  });
});
