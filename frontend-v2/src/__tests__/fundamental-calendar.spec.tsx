import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSymbolCalendar } from '@features/fundamental/api/useCalendar';
import { CorporateCalendar } from '@features/fundamental/ui/CorporateCalendar';

vi.mock('@features/fundamental/api/useCalendar', () => ({ useSymbolCalendar: vi.fn() }));

const mockedCalendar = vi.mocked(useSymbolCalendar);

beforeEach(() => {
  mockedCalendar.mockReturnValue({
    data: {
      status: 'ok',
      symbol: 'فولاد',
      count: 2,
      events: [
        { date: '2099-01-01', ts: 1, title: 'دعوت به مجمع عمومی عادی', cat: 'assembly', date_source: 'title' },
        { date: '2020-01-01', ts: 0, title: 'تصویب تقسیم سود نقدی', cat: 'other', date_source: 'title' },
        { date: '2099-02-01', ts: 2, title: 'اطلاعیهٔ بدون تاریخِ برگزاری', cat: 'other', date_source: 'publication_fallback' },
      ],
    },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useSymbolCalendar>);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('corporate calendar', () => {
  it('separates future events and labels dividend notices', () => {
    render(<CorporateCalendar symbol="فولاد" />);
    const future = screen.getByTestId('calendar-future');
    expect(future.textContent).toContain('مجمع');
    expect(future.textContent).toContain('دعوت به مجمع');
    const past = screen.getByTestId('calendar-event-2020-01-01');
    expect(past.textContent).toContain('سود نقدی');
    expect(past.textContent).toContain('گذشته');
    const notices = screen.getByTestId('calendar-notices');
    expect(notices.textContent).toContain('بدون تاریخِ برگزاری');
    expect(future.textContent).not.toContain('بدون تاریخِ برگزاری');
  });

  it('says when no future event exists in the cache', () => {
    mockedCalendar.mockReturnValue({
      data: {
        status: 'ok', symbol: 'فولاد', count: 1,
        events: [{ date: '2020-01-01', ts: 0, title: 'افزایش سرمایه', cat: 'capitalIncrease', date_source: 'title' }],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useSymbolCalendar>);
    render(<CorporateCalendar symbol="فولاد" />);
    expect(screen.getByTestId('calendar-no-future')).toBeTruthy();
    expect(screen.getByTestId('calendar-event-2020-01-01').textContent).toContain('افزایش سرمایه');
  });

  it('shows an honest empty state', () => {
    mockedCalendar.mockReturnValue({
      data: { status: 'ok', symbol: 'فولاد', count: 0, events: [] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useSymbolCalendar>);
    render(<CorporateCalendar symbol="فولاد" />);
    expect(screen.getByTestId('calendar-empty').textContent).toContain('نبودِ رویداد');
  });
});
