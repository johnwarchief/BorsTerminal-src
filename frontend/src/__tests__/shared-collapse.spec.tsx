// تستِ نشانهٔ بازشو (Collapse): همان چیزی که کاربر باید ببیند — دکمهٔ
// کلیک‌پذیر بودنِ نوار را می‌فهمد و محتوا با انیمیشن باز می‌شود.
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { Chevron, CollapseBody, CollapseToggle } from '@shared/components/Collapse';

function Demo() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <CollapseToggle open={open} onToggle={() => setOpen((v) => !v)} testId="t" label="نوارِ نمودارها" openLabel="باز کردنِ نمودارها" />
      <CollapseBody open={open} testId="t-body">
        <p>محتوا</p>
      </CollapseBody>
    </div>
  );
}

describe('نشانهٔ نوارهای بازشو', () => {
  it('بسته: تیترِ متنی نیست — شِورون، برچسبِ «باز کردنِ …» و aria-expanded=false', () => {
    render(<Demo />);
    const btn = screen.getByTestId('t');
    expect(btn.tagName).toBe('BUTTON');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByTestId('t-hint')).toHaveTextContent('باز کردنِ نمودارها');
    expect(screen.queryByTestId('t-body')).not.toBeInTheDocument();
    expect(btn.querySelector('svg')).not.toBeNull();
  });

  it('با کلیک: محتوا با کلاسِ انیمیشن می‌آید، برچسب می‌رود و شِورون ۱۸۰ درجه می‌چرخد', () => {
    render(<Demo />);
    fireEvent.click(screen.getByTestId('t'));
    expect(screen.getByTestId('t').getAttribute('aria-expanded')).toBe('true');
    expect(screen.queryByTestId('t-hint')).not.toBeInTheDocument();
    expect(screen.getByTestId('t-body')).toHaveClass('collapse-in');
    expect(screen.getByTestId('t').querySelector('.rotate-180')).not.toBeNull();
  });

  it('بستنِ دوباره: همان دور، محتوا از DOM بیرون می‌رود (رندرِ پنهان نداریم)', () => {
    render(<Demo />);
    fireEvent.click(screen.getByTestId('t'));
    fireEvent.click(screen.getByTestId('t'));
    expect(screen.queryByTestId('t-body')).not.toBeInTheDocument();
    expect(screen.getByTestId('t').querySelector('.rotate-180')).toBeNull();
  });

  it('Chevron به‌تنهایی: باز ⇒ rotate-180، بسته ⇒ بدونِ چرخش', () => {
    const { rerender, container } = render(<Chevron open={false} />);
    expect(container.querySelector('.rotate-180')).toBeNull();
    expect(container.querySelector('svg')).not.toBeNull();
    rerender(<Chevron open />);
    expect(container.querySelector('.rotate-180')).not.toBeNull();
  });
});
