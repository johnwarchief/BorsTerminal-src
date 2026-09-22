// تست فلش بدون رفرش: وقتی مقدار prop عوض می‌شود، کلاس flash-up/flash-down
// باید روی همان گره DOM اعمال شود (بدون تخریب نود) تا کاربر تغییر را «در آن واحد» ببیند.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FlashNum } from '@shared/components/FlashNum';

const r = (v: number | null | undefined) => String(v ?? '-');

describe('FlashNum — فلش لحظه‌ای بدون رفرش', () => {
  it('با افزایش مقدار، کلاس flash-up می‌گیرد', () => {
    const { rerender } = render(<FlashNum value={100} render={r} />);
    const el = screen.getByText('100');
    expect(el.className).not.toContain('flash-up');
    rerender(<FlashNum value={125} render={r} />);
    expect(screen.getByText('125').className).toContain('flash-up');
  });

  it('با کاهش مقدار، کلاس flash-down می‌گیرد', () => {
    const { rerender } = render(<FlashNum value={200} render={r} />);
    rerender(<FlashNum value={150} render={r} />);
    expect(screen.getByText('150').className).toContain('flash-down');
  });

  it('همان گره DOM حفظ می‌شود (بدون key/بازسازی)', () => {
    const { rerender } = render(<FlashNum value={10} render={r} />);
    const before = screen.getByText('10');
    rerender(<FlashNum value={20} render={r} />);
    const after = screen.getByText('20');
    expect(after.isSameNode(before)).toBe(true);
  });

  it('مقدار null→عدد فلش نمی‌زند (فقط تغییر واقعی عدد)', () => {
    const { rerender } = render(<FlashNum value={null} render={r} />);
    rerender(<FlashNum value={5} render={r} />);
    expect(screen.getByText('5').className).not.toMatch(/flash-(up|down)/);
  });
});
