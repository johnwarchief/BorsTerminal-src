// Tooltip — جایگزینِ `title=`ِ بومی، که سیستم‌عامل می‌کشد و نه تأخیرش
// قابلِ تنظیم است، نه با صفحه‌کلید ظاهر می‌شود، نه راست‌چین.
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Tooltip, TooltipProvider } from '@shared/ui/Tooltip';

const paint = (content: React.ReactNode = 'توضیحِ فرمول') =>
  render(
    <TooltipProvider>
      <Tooltip content={content}>
        <button type="button">رشد فروش</button>
      </Tooltip>
    </TooltipProvider>,
  );

describe('Tooltip', () => {
  it('در حالتِ عادی پنهان است', () => {
    paint();
    expect(screen.queryByTestId('tooltip')).toBeNull();
  });

  it('با فوکوسِ صفحه‌کلید باز می‌شود — چیزی که title بومی هرگز نمی‌کرد', async () => {
    paint();
    fireEvent.focus(screen.getByRole('button'));
    await waitFor(() => expect(screen.getAllByText('توضیحِ فرمول').length).toBeGreaterThan(0));
  });

  it('محتوایِ تهی اصلاً راهنما نمی‌سازد، فقط فرزند را برمی‌گرداند', () => {
    render(
      <TooltipProvider>
        <Tooltip content={null}>
          <button type="button">بی‌راهنما</button>
        </Tooltip>
      </TooltipProvider>,
    );
    fireEvent.focus(screen.getByRole('button'));
    expect(screen.queryByTestId('tooltip')).toBeNull();
    expect(screen.getByRole('button')).toBeInTheDocument();
  });
});
