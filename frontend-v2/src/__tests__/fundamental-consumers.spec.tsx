import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { FundamentalCards } from '@features/fundamental/ui/FundamentalCards';
import { FundamentalSummary } from '@features/fundamental/ui/FundamentalSummary';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));

/** سه قبول، یک رد و یک نامشخص — بدون حکم یا رتبهٔ ساختگی. */
const card = {
  status: 'success',
  symbol: 'رنيك',
  sector: 'خدمات فنی',
  passes: {
    '1_growth': true,
    '2_eps_trend': true,
    '3_gross_margin': null,
    '4_sales_to_mcap': false,
    '5_industry': true,
  },
  indicators: {
    '1': { monetary: { monetary_pct: 45.9, threshold: 60, data_gap: false } },
    '2': { eps_series: [1119, 1615, 1672], years_available: 3, years_required: 3 },
    '3': { margin_pct: 11.5, threshold: 40 },
    '4': { sales_to_mcap: 1.15, sales_threshold: 0.33, available: true, data_gap: false },
    '5': { label: 'خنثی' },
  },
} as unknown as FtsCard;

/** همان کارت با محورِ سومِ بی‌نظر (na) — ردِ محور چهارم حفظ می‌شود. */
const abstainingCard = {
  ...card,
  indicators: {
    ...card.indicators,
    '3': { margin_pct: 11.5, threshold: 40, na: true },
  },
} as unknown as FtsCard;

/** R70: pass=false روی محورِ ناموجود نباید «رد» دیده شود. */
const unavailableSalesCard = {
  ...card,
  passes: { ...card.passes, '4_sales_to_mcap': false },
  indicators: {
    ...card.indicators,
    '4': { sales_to_mcap: null, sales_threshold: 0.33, available: false, data_gap: false },
  },
} as unknown as FtsCard;

/** R70: pass=false روی محورِ با شکافِ داده نباید «رد» دیده شود. */
const gappedEpsCard = {
  ...card,
  passes: { ...card.passes, '2_eps_trend': false },
  indicators: {
    ...card.indicators,
    '2': { eps_series: [], years_available: 0, years_required: 3, data_gap: true },
  },
} as unknown as FtsCard;

function serve(payload: FtsCard | undefined, overrides: Record<string, unknown> = {}): void {
  vi.mocked(useFtsCard).mockReturnValue({
    data: payload,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  } as never);
}

function cardText(axis: string): string {
  const root = screen.getByTestId('fundamental-cards');
  return root.querySelector(`[data-axis="${axis}"]`)?.textContent ?? '';
}

function cardStatusClass(axis: string): string {
  const root = screen.getByTestId('fundamental-cards');
  return root.querySelector(`[data-axis="${axis}"] b`)?.className ?? '';
}

function summaryBar(axis: string): HTMLElement {
  return screen.getByTestId('symbol-fund-summary').querySelector(`[data-axis="${axis}"]`) as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
  useFundamentalPrefs.setState({ density: 'comfortable', surface: 'paper' });
  serve(card);
});

afterEach(cleanup);

describe('FundamentalCards (dock variant)', () => {
  it('renders five compact axis cards and never exposes formulas or charts', () => {
    render(<FundamentalCards symbol="رنيك" />);
    const root = screen.getByTestId('fundamental-cards');
    const axes = [...root.querySelectorAll('[data-axis]')];
    expect(axes).toHaveLength(5);
    expect(axes.map((axis) => axis.getAttribute('data-axis')))
      .toEqual(['growth', 'eps', 'margin', 'sales', 'industry']);
    expect(root.textContent).not.toContain('فرمول');
    expect(root.querySelectorAll('svg')).toHaveLength(0);
    expect(root.textContent).toContain('رشد');
    expect(root.textContent).toContain('صنعت');
    expect(root.getAttribute('data-fund-surface')).toBe('paper');
    expect(root.className).toContain('fundamental-surface');
  });

  it('writes the Persian status word and the fd status class for every axis', () => {
    render(<FundamentalCards symbol="رنيك" />);
    expect(cardText('growth')).toContain('قبول');
    expect(cardText('eps')).toContain('قبول');
    expect(cardText('industry')).toContain('قبول');
    expect(cardText('sales')).toContain('رد');
    expect(cardText('margin')).toContain('نامشخص');
    expect(cardStatusClass('growth')).toContain('fd-status--pass');
    expect(cardStatusClass('sales')).toContain('fd-status--fail');
    expect(cardStatusClass('margin')).toContain('fd-status--unknown');
  });

  it('maps an na indicator to بی‌نظر instead of inventing a rejection', () => {
    serve(abstainingCard);
    render(<FundamentalCards symbol="رنيك" />);
    expect(cardText('margin')).toContain('بی‌نظر');
    expect(cardText('margin')).not.toContain('نامشخص');
    expect(cardStatusClass('margin')).toContain('fd-status--na');
    expect(cardText('sales')).toContain('رد');
  });

  it('shows an unavailable axis as نامشخص, not رد (R70)', () => {
    serve(unavailableSalesCard);
    render(<FundamentalCards symbol="رنيك" />);
    expect(cardText('sales')).toContain('نامشخص');
    expect(cardText('sales')).not.toContain('رد');
    cleanup();

    render(<FundamentalSummary symbol="رنيك" />);
    expect(summaryBar('sales').getAttribute('data-status')).toBe('unknown');
    expect(screen.getByTestId('symbol-fund-summary').textContent).not.toContain('رد');
  });

  it('shows a data-gap axis as نامشخص, not رد (R70)', () => {
    serve(gappedEpsCard);
    render(<FundamentalCards symbol="رنيك" />);
    expect(cardText('eps')).toContain('نامشخص');
    expect(cardText('eps')).not.toContain('رد');
    cleanup();

    render(<FundamentalSummary symbol="رنيك" />);
    expect(summaryBar('eps').getAttribute('data-status')).toBe('unknown');
    expect(summaryBar('eps').getAttribute('aria-label')).not.toContain('رد');
    expect(summaryBar('eps').getAttribute('aria-label')).toContain('نامشخص');
  });

  it('follows the surface preference on the cards root', () => {
    useFundamentalPrefs.setState({ surface: 'ink' });
    render(<FundamentalCards symbol="رنيك" />);
    const root = screen.getByTestId('fundamental-cards');
    expect(root.getAttribute('data-fund-surface')).toBe('ink');
    expect(root.className).toContain('fundamental-surface');
  });

  it('keeps honest loading and error messages inside the themed surface', () => {
    serve(undefined, { isLoading: true });
    render(<FundamentalCards symbol="رنيك" />);
    const loading = screen.getByTestId('fundamental-cards-loading');
    expect(loading.textContent).toContain('در حال خواندن');
    expect(loading.getAttribute('data-fund-surface')).toBe('paper');
    expect(loading.className).toContain('fundamental-surface');
    expect(loading.className).toContain('bg-[var(--fd-bg)]');
    cleanup();

    serve(undefined, { isError: true, error: new Error('x') });
    render(<FundamentalCards symbol="رنيك" />);
    const error = screen.getByTestId('fundamental-cards-error');
    expect(error.textContent).toContain('در دسترس نیست');
    expect(error.className).toContain('bg-[var(--fd-bg)]');
  });
});

describe('FundamentalSummary (sidebar variant)', () => {
  it('shows the accepted count and five axis status bars', () => {
    render(<FundamentalSummary symbol="رنيك" />);
    const summary = screen.getByTestId('symbol-fund-summary');
    expect(screen.getByTestId('fund-summary-count').textContent).toBe('۳ از ۵');
    expect(summary.querySelectorAll('[data-axis]')).toHaveLength(5);
    expect(summary.textContent).toContain('۱ رد');
    expect(summary.textContent).toContain('۱ بی‌نظر/نامشخص');
    expect(summaryBar('growth').getAttribute('style')).toContain('var(--fd-up)');
    expect(summaryBar('sales').getAttribute('style')).toContain('var(--fd-down)');
    expect(summaryBar('margin').getAttribute('style')).toContain('var(--fd-warn)');
    expect(summaryBar('margin').getAttribute('data-status')).toBe('unknown');
    expect(summaryBar('margin').getAttribute('aria-label')).toBe('حاشیهٔ ناخالص — نامشخص');
    expect(summaryBar('margin').getAttribute('title')).toBe('حاشیهٔ ناخالص — نامشخص');
    expect(summaryBar('margin').getAttribute('role')).toBe('img');
    expect(summaryBar('margin').className).not.toContain('fd-status--');
    expect(summaryBar('growth').getAttribute('aria-hidden')).toBeNull();
    expect(summaryBar('growth').parentElement?.getAttribute('aria-hidden')).toBeNull();
  });

  it('paints an na axis with the flat token and keeps the count honest', () => {
    serve(abstainingCard);
    render(<FundamentalSummary symbol="رنيك" />);
    expect(screen.getByTestId('fund-summary-count').textContent).toBe('۳ از ۵');
    expect(summaryBar('margin').getAttribute('style')).toContain('var(--fd-flat)');
    expect(summaryBar('margin').getAttribute('data-status')).toBe('na');
    expect(summaryBar('margin').getAttribute('aria-label')).toBe('حاشیهٔ ناخالص — بی‌نظر');
    expect(screen.getByTestId('symbol-fund-summary').textContent).toContain('۱ بی‌نظر/نامشخص');
  });

  it('is a toggle button with aria-expanded only when onToggle is supplied', () => {
    const onToggle = vi.fn();
    render(<FundamentalSummary symbol="رنيك" expanded onToggle={onToggle} />);
    const button = screen.getByRole('button');
    expect(button).toBe(screen.getByTestId('symbol-fund-summary'));
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(button.className).toContain('bg-[var(--fd-bg)]');
    expect(button.textContent).toContain('بستن');
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);

    cleanup();
    render(<FundamentalSummary symbol="رنيك" expanded={false} onToggle={onToggle} />);
    const closed = screen.getByTestId('symbol-fund-summary');
    expect(closed.getAttribute('aria-expanded')).toBe('false');
    expect(closed.textContent).toContain('باز کردن');
  });

  it('stays a static block without a toggle', () => {
    render(<FundamentalSummary symbol="رنيك" />);
    expect(screen.queryByRole('button')).toBeNull();
    const summary = screen.getByTestId('symbol-fund-summary');
    expect(summary.tagName).toBe('DIV');
    expect(summary.className).toContain('bg-[var(--fd-bg)]');
    expect(summary.textContent).not.toContain('کارت‌های بنیادی');
    expect(screen.getByTestId('fund-summary-count').textContent).toBe('۳ از ۵');
  });

  it('explains empty, loading and error states without breaking the sidebar', () => {
    render(<FundamentalSummary symbol={null} />);
    expect(screen.getByTestId('symbol-fund-summary').textContent)
      .toContain('نمادی را از تابلو انتخاب کن');
    cleanup();

    serve(undefined, { isLoading: true });
    render(<FundamentalSummary symbol="رنيك" />);
    expect(screen.getByTestId('symbol-fund-summary').textContent).toContain('در حال خواندن');
    expect(screen.queryByTestId('fund-summary-count')).toBeNull();
    cleanup();

    serve(undefined, { isError: true, error: new Error('x') });
    render(<FundamentalSummary symbol="رنيك" />);
    expect(screen.getByTestId('symbol-fund-unavailable').textContent).toContain('در دسترس نیست');
    expect(screen.queryByTestId('fund-summary-count')).toBeNull();
  });

  it('carries the data surface and never fabricates a weakest axis or ranking', () => {
    useFundamentalPrefs.setState({ surface: 'ink' });
    render(<FundamentalSummary symbol="رنيك" />);
    const summary = screen.getByTestId('symbol-fund-summary');
    expect(summary.getAttribute('data-fund-surface')).toBe('ink');
    expect(summary.className).toContain('fundamental-surface');
    expect(summary.textContent).not.toContain('ضعیف‌ترین');
    expect(summary.textContent).not.toContain('رتبه');
  });
});
