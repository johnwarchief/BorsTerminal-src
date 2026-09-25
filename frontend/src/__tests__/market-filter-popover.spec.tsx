// پاپ‌اور تنظیمات آستانهٔ هر فیلتر: باز/بسته شدن نباید ترتیب هوک‌ها را عوض کند
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FilterConfigPopover } from '@features/market/components/FilterConfigPopover';
import type { QuickFilter } from '@features/market/stores/tapeStore';

const ANCHOR = {
  x: 120, y: 12, width: 104, height: 28, top: 12, left: 120, bottom: 40, right: 224,
  toJSON: () => ({}),
} as DOMRect;

function paint(open: boolean) {
  return (
    <FilterConfigPopover
      filter={'f_clock' as QuickFilter}
      open={open}
      anchorRect={open ? ANCHOR : null}
      onClose={() => {}}
    />
  );
}

describe('پاپ‌اور «تنظیم آستانه‌ها» در تابلو', () => {
  it('از حالت بسته به باز پرتاب نمی‌کند (شش هوک، نه چهار)', () => {
    const { rerender } = render(paint(false));
    expect(screen.queryByRole('dialog')).toBeNull();

    rerender(paint(true));
    expect(screen.getByRole('dialog', { name: 'تنظیمات فیلتر الگوی ساعت' })).toHaveTextContent(
      'الگوی ساعت',
    );
  });

  it('بسته→باز→بسته→باز همان هوک‌ها را نگه می‌دارد', () => {
    const { rerender } = render(paint(true));
    rerender(paint(false));
    expect(screen.queryByRole('dialog')).toBeNull();
    rerender(paint(true));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    rerender(paint(false));
    rerender(paint(true));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('برای هر پنج فیلترِ چرخ‌دنده‌دار محتوای خودش را باز می‌کند', () => {
    const filters: QuickFilter[] = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'];
    for (const f of filters) {
      const { unmount } = render(
        <FilterConfigPopover filter={f} open anchorRect={ANCHOR} onClose={vi.fn()} />,
      );
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      unmount();
    }
  });
});
