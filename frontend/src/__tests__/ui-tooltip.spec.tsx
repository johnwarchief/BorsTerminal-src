// Tooltip — جایگزینِ `title=`ِ بومی، که سیستم‌عامل می‌کشد و نه تأخیرش
// قابلِ تنظیم است، نه با صفحه‌کلید ظاهر می‌شود، نه راست‌چین.
import { afterEach, describe, expect, it, vi } from 'vitest';
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

describe('راهنما رویِ لمس', () => {
  const setPointer = (coarse: boolean) =>
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: coarse && q.includes('coarse'),
      addEventListener: () => {}, removeEventListener: () => {},
    }));
  afterEach(() => vi.unstubAllGlobals());

  it('با اشاره‌گرِ درشت، لمس بازش می‌کند', async () => {
    // Radix فقط hover/focus دارد؛ گوشی hover ندارد و لمس هم فوکوس نمی‌دهد.
    // بی‌این، هر ۲۷۲ جایی که توضیحِ فرمول در راهنماست رویِ موبایل نامرئی است.
    setPointer(true);
    paint();
    fireEvent.pointerDown(screen.getByRole('button'));
    await waitFor(() => expect(screen.getAllByText('توضیحِ فرمول').length).toBeGreaterThan(0));
  });

  it('لمسِ دوم می‌بنددش', async () => {
    setPointer(true);
    paint();
    const btn = screen.getByRole('button');
    fireEvent.pointerDown(btn);
    await waitFor(() => expect(screen.getAllByText('توضیحِ فرمول').length).toBeGreaterThan(0));
    fireEvent.pointerDown(btn);
    await waitFor(() => expect(screen.queryByTestId('tooltip')).toBeNull());
  });

  it('رویِ ماوس رفتارِ قبلی دست‌نخورده می‌ماند', () => {
    setPointer(false);
    paint();
    // بی‌hover و بی‌focus چیزی باز نمی‌شود — همان رفتارِ Radix
    expect(screen.queryByTestId('tooltip')).toBeNull();
  });
});
