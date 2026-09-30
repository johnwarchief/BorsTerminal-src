// Select — جایگزینِ <select>ِ بومی رویِ Radix.
// چیزی که سلکتِ بومی نمی‌توانست: جستجو در فهرستِ چهل‌تاییِ صنایع.
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Select } from '@shared/ui/Select';

const OPTS = [
  { value: '', label: 'همه صنایع' },
  { value: 'فلزات', label: 'فلزات اساسی' },
  { value: 'بانک', label: 'بانک‌ها' },
  { value: 'خودرو', label: 'خودرو و ساخت قطعات' },
];

function paint(value = '', onChange = vi.fn(), opts = OPTS) {
  render(<Select value={value} options={opts} onChange={onChange} ariaLabel="فیلتر صنعت" searchThreshold={4} />);
  return onChange;
}

/** Radix منو را با pointerdownِ دکمهٔ چپ باز می‌کند، نه با click. */
function openMenu() {
  fireEvent.pointerDown(
    screen.getByTestId('ui-select'),
    { button: 0, ctrlKey: false, pointerType: 'mouse' },
  );
}

describe('Select', () => {
  it('برچسبِ گزینهٔ فعال را نشان می‌دهد، نه مقدارِ خام', () => {
    paint('فلزات');
    expect(screen.getByTestId('ui-select').textContent).toContain('فلزات اساسی');
  });

  it('با کلیک باز می‌شود و گزینه‌ها می‌آیند', () => {
    paint();
    openMenu();
    expect(screen.getByTestId('ui-select-item-بانک')).toBeInTheDocument();
  });

  it('انتخاب، مقدار را خبر می‌دهد', () => {
    const onChange = paint();
    openMenu();
    fireEvent.click(screen.getByTestId('ui-select-item-خودرو'));
    expect(onChange).toHaveBeenCalledWith('خودرو');
  });

  it('جستجو فهرست را تنگ می‌کند', () => {
    paint();
    openMenu();
    fireEvent.change(screen.getByTestId('ui-select-search'), { target: { value: 'بانک' } });
    expect(screen.getByTestId('ui-select-item-بانک')).toBeInTheDocument();
    expect(screen.queryByTestId('ui-select-item-خودرو')).toBeNull();
  });

  it('«ي» و «ك»ِ عربی هم پیدا می‌شوند', () => {
    // کاربر با صفحه‌کلیدِ عربی «بانك» می‌نویسد؛ نباید دستِ خالی برگردد.
    paint('', vi.fn(), [
      { value: 'b', label: 'بانک‌ها' }, { value: 'x', label: 'خودرو' },
      { value: 'y', label: 'فلزات' }, { value: 'z', label: 'سیمان' },
    ]);
    openMenu();
    fireEvent.change(screen.getByTestId('ui-select-search'), { target: { value: 'بانك' } });
    expect(screen.getByTestId('ui-select-item-b')).toBeInTheDocument();
  });

  it('نتیجهٔ خالی پیام می‌دهد، نه فهرستِ سفید', () => {
    paint();
    openMenu();
    fireEvent.change(screen.getByTestId('ui-select-search'), { target: { value: 'زیزیزی' } });
    expect(screen.getByText('چیزی پیدا نشد')).toBeInTheDocument();
  });

  it('فهرستِ کوتاه جعبهٔ جستجو نمی‌گیرد', () => {
    paint('', vi.fn(), OPTS.slice(0, 2));
    openMenu();
    expect(screen.queryByTestId('ui-select-search')).toBeNull();
  });
});
