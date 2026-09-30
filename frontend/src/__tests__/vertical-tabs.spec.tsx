// VerticalTabs — تبِ عمودیِ دست‌ساز (بی‌motion، بی‌hugeicons).
// چکِ اصلی: قراردادِ tablist رعایت شود (نقش‌ها، aria-selected، roving tabindex،
// پیمایشِ فلش) و شاخصِ لغزان فقط با transform جابه‌جا شود — نه با اندازه‌گیریِ
// DOM، چون برنامه رویِ بیشترِ ماشین‌ها رندرِ نرم‌افزاری دارد.
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { VerticalTabs, type VerticalTabItem } from '@shared/components/VerticalTabs';

type K = 'a' | 'b' | 'c';
const ITEMS: readonly VerticalTabItem<K>[] = [
  { key: 'a', icon: '⏰', label: 'یک', hint: 'تبِ یک' },
  { key: 'b', icon: '🚀', label: 'دو' },
  { key: 'c', label: 'سه' },
];

function setup(active: K = 'a') {
  const onChange = vi.fn();
  const r = render(
    <VerticalTabs items={ITEMS} active={active} onChange={onChange} ariaLabel="نمونه">
      <p>محتوا</p>
    </VerticalTabs>,
  );
  return { onChange, ...r };
}

describe('VerticalTabs', () => {
  it('قراردادِ tablist را رعایت می‌کند', () => {
    setup('b');
    const list = screen.getByRole('tablist');
    expect(list.getAttribute('aria-orientation')).toBe('vertical');
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(3);
    expect(tabs[1].getAttribute('aria-selected')).toBe('true');
    expect(tabs[0].getAttribute('aria-selected')).toBe('false');
    // roving tabindex: فقط تبِ فعال در ترتیبِ Tab است
    expect(tabs.map((t) => t.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
    // پنل به تبِ فعال گره خورده
    const panel = screen.getByRole('tabpanel');
    expect(panel.getAttribute('aria-labelledby')).toBe(tabs[1].id);
    expect(tabs[1].getAttribute('aria-controls')).toBe(panel.id);
  });

  it('کلیک تبِ تازه را خبر می‌دهد', () => {
    const { onChange } = setup('a');
    fireEvent.click(screen.getByRole('tab', { name: /سه/ }));
    expect(onChange).toHaveBeenCalledWith('c');
  });

  it('فلشِ پایین/بالا می‌چرخد و Home/End به دو سر می‌رود', () => {
    const { onChange } = setup('a');
    const list = screen.getByRole('tablist');
    fireEvent.keyDown(list, { key: 'ArrowDown' });
    expect(onChange).toHaveBeenLastCalledWith('b');
    fireEvent.keyDown(list, { key: 'ArrowUp' });
    expect(onChange).toHaveBeenLastCalledWith('c'); // از اولی به آخری می‌پیچد
    fireEvent.keyDown(list, { key: 'End' });
    expect(onChange).toHaveBeenLastCalledWith('c');
    fireEvent.keyDown(list, { key: 'Home' });
    expect(onChange).toHaveBeenLastCalledWith('a');
  });

  it('کلیدِ بی‌ربط را نمی‌بلعد', () => {
    const { onChange } = setup('a');
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'x' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('شاخص فقط با transform جابه‌جا می‌شود (نه top/height پیکسلی)', () => {
    const { rerender } = setup('a');
    const ind = screen.getByTestId('vertical-tabs-indicator');
    expect(ind.style.transform).toBe('translateY(calc(0 * 100%))');
    expect(ind.style.top).toBe('');
    rerender(
      <VerticalTabs items={ITEMS} active="c" onChange={() => {}} ariaLabel="نمونه">
        <p>محتوا</p>
      </VerticalTabs>,
    );
    expect(screen.getByTestId('vertical-tabs-indicator').style.transform).toBe(
      'translateY(calc(2 * 100%))',
    );
  });

  it('کلیدِ ناشناخته در فهرستِ خالی نمی‌ترکد', () => {
    render(
      <VerticalTabs items={[]} active={'a' as K} onChange={() => {}} ariaLabel="خالی">
        <p>هیچ</p>
      </VerticalTabs>,
    );
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'ArrowDown' });
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });
});
