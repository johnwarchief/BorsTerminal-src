// تستِ نوارِ داک پایین چارت: همین نوار قبلاً یک علامتِ تنها («⌃») بود و
// کاربر نمی‌فهمید کلیک‌پذیر است؛ حالا چیپِ «باز کردنِ پنل» دارد.
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FtsDock } from '@features/technical/components/FtsDock';

const tabs = [
  { id: 'status', label: 'وضعیت FTS', node: <p>بدنهٔ وضعیت</p> },
  { id: 'audit', label: 'ممیزی', node: <p>بدنهٔ ممیزی</p> },
];

describe('FtsDock — نشانهٔ بازشو', () => {
  it('بسته: بدنه نیست، چیپِ «باز کردنِ پنل» هست و aria-expanded=false', () => {
    render(<FtsDock tabs={tabs} />);
    const btn = screen.getByTestId('fts-dock-toggle');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByText('باز کردنِ پنل')).toBeInTheDocument();
    expect(screen.queryByTestId('fts-dock-body')).not.toBeInTheDocument();
    expect(screen.getByTestId('fts-dock')).toHaveAttribute('data-open', 'false');
  });

  it('با کلیک روی همان چیپ: بدنه می‌آید، چیپ می‌رود و داک باز ثبت می‌شود', () => {
    render(<FtsDock tabs={tabs} />);
    fireEvent.click(screen.getByTestId('fts-dock-toggle'));
    expect(screen.getByTestId('fts-dock-toggle').getAttribute('aria-expanded')).toBe('true');
    expect(screen.queryByText('باز کردنِ پنل')).not.toBeInTheDocument();
    expect(screen.getByTestId('fts-dock-body')).toHaveTextContent('بدنهٔ وضعیت');
    expect(screen.getByTestId('fts-dock')).toHaveAttribute('data-open', 'true');
  });

  it('کلیک روی تب هم داک را باز می‌کند (تب‌ها خودِ دستگیره‌اند)', () => {
    render(<FtsDock tabs={tabs} />);
    fireEvent.click(screen.getByTestId('fts-dock-tab-audit'));
    expect(screen.getByTestId('fts-dock-body')).toHaveTextContent('بدنهٔ ممیزی');
  });
});
