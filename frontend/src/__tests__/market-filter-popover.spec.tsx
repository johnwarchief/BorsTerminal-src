// پاپ‌اور تنظیمات آستانهٔ هر فیلتر: باز/بسته شدن نباید ترتیب هوک‌ها را عوض کند
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FilterConfigPopover } from '@features/market/components/FilterConfigPopover';
import type { QuickFilter } from '@features/market/stores/tapeStore';
import { useTapeStore } from '@features/market/stores/tapeStore';

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

describe('دستگیره‌های مبنایِ داوری در پاپ‌اورِ هر فیلتر (#226)', () => {
  it('الگوی ساعت: دستگیرۀ «امروز داخلِ مبنایِ میانگین» را دارد و در استور می‌نویسد', () => {
    useTapeStore.getState().resetTapeFilterConfig();
    render(<FilterConfigPopover filter="f_clock" open anchorRect={ANCHOR} onClose={() => {}} />);
    const box = screen.getByRole('checkbox', { name: /امروز داخلِ مبنایِ میانگین/ });
    expect(box).not.toBeChecked();
    fireEvent.click(box);
    expect(useTapeStore.getState().tapeFilterConfig.basis.includeTodayInVolumeBase).toBe(true);
  });

  it('نقطه‌زنی: هر دو دستگیره هست («دروازۀ ۲۹-نشست» فقط اینجا)', () => {
    render(<FilterConfigPopover filter="f_noqteh" open anchorRect={ANCHOR} onClose={() => {}} />);
    expect(screen.getByRole('checkbox', { name: /امروز داخلِ مبنایِ میانگین/ })).toBeInTheDocument();
    const hist = screen.getByRole('checkbox', { name: /دروازۀ ۲۹-نشستِ تاریخچه/ });
    expect(hist).toBeChecked();
    fireEvent.click(hist);
    expect(useTapeStore.getState().tapeFilterConfig.basis.requireLowBaseHistory).toBe(false);
  });

  it('جت — که مبناءش دست‌نخورده می‌ماند — این ردیف‌ها را ندارد', () => {
    render(<FilterConfigPopover filter="f_jet" open anchorRect={ANCHOR} onClose={() => {}} />);
    expect(screen.queryByRole('checkbox', { name: /امروز داخلِ مبنایِ میانگین/ })).not.toBeInTheDocument();
  });
});
});
