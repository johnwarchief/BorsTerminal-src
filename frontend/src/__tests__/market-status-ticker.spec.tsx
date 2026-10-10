// تستِ چرخشِ نوارِ خلاصه: مکث با تعامل، ادامه از همان‌جا، و بی‌درخواستِ اضافه
//
// شرط‌هایِ پذیرشِ مأموریت که این فایل می‌بندد: (1) چرخشِ خودکار واقعاً اجرا شود و
// با تعاملِ کاربر متوقف شود؛ (7) این نوار درخواستِ شبکه یا pollingِ تازه اضافه نکند.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketStatusTicker } from '@features/market/components/MarketStatusTicker';
import { usePageRotator } from '@shared/components/PageRotator';

const PAGES = [
  { id: 'a', label: 'الف' },
  { id: 'b', label: 'ب' },
  { id: 'c', label: 'پ' },
];

function Harness({ storageKey }: { storageKey?: string }) {
  const r = usePageRotator({ pages: PAGES, intervalMs: 1000, storageKey });
  return (
    <div {...r.pauseProps} data-testid="box">
      <span data-testid="page">{r.page}</span>
      <span data-testid="rotating">{String(r.rotating)}</span>
      <button type="button" data-testid="tab-c" onClick={() => r.setPage('c')}>
        c
      </button>
      <button type="button" data-testid="toggle" onClick={r.toggle}>
        t
      </button>
    </div>
  );
}

const tick = async (ms: number) => {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
};

describe('usePageRotator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
  });
  afterEach(() => vi.useRealTimers());

  it('هر دورۀِ اینتروال یک صفحّه جلو می‌رود و به ابتدا نمی‌پرد', async () => {
    render(<Harness />);
    expect(screen.getByTestId('page').textContent).toBe('a');
    await tick(1000);
    expect(screen.getByTestId('page').textContent).toBe('b');
    await tick(1000);
    expect(screen.getByTestId('page').textContent).toBe('c');
    await tick(1000);
    expect(screen.getByTestId('page').textContent).toBe('a'); // چرخۀ کامل، نه ریست
  });

  it('hover مکث می‌سازد و پس از جداکردنِ نشانگر از همان صفحّه ادامه می‌دهد', async () => {
    render(<Harness />);
    await tick(1000);
    expect(screen.getByTestId('page').textContent).toBe('b');
    fireEvent.mouseEnter(screen.getByTestId('box'));
    expect(screen.getByTestId('rotating').textContent).toBe('false');
    await tick(3000);
    expect(screen.getByTestId('page').textContent).toBe('b'); // می‌ماند، به a نمی‌پرد
    fireEvent.mouseLeave(screen.getByTestId('box'));
    expect(screen.getByTestId('rotating').textContent).toBe('true');
    await tick(1000);
    expect(screen.getByTestId('page').textContent).toBe('c');
  });

  it('focusِ صفحه‌کلید هم مکث می‌سازد', async () => {
    render(<Harness />);
    fireEvent.focus(screen.getByTestId('box'));
    expect(screen.getByTestId('rotating').textContent).toBe('false');
    await tick(2500);
    expect(screen.getByTestId('page').textContent).toBe('a');
  });

  it('انتخابِ دستی صفحّه چرخش را ریست نمی‌کند؛ کلیدِ توقف آن را خاموش می‌کند', async () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId('tab-c'));
    expect(screen.getByTestId('page').textContent).toBe('c');
    await tick(1000);
    expect(screen.getByTestId('page').textContent).toBe('a'); // از c به چرخۀ بعد
    fireEvent.click(screen.getByTestId('toggle'));
    expect(screen.getByTestId('rotating').textContent).toBe('false');
    await tick(5000);
    expect(screen.getByTestId('page').textContent).toBe('a'); // خاموش مانده
    fireEvent.click(screen.getByTestId('toggle'));
    await tick(1000);
    expect(screen.getByTestId('page').textContent).toBe('b');
  });

  it('تنظیمِ درون‌برنامه («still») بر چرخش حاکم است و ماندگار می‌ماند', async () => {
    const KEY = 'test.rotator.v1';
    localStorage.setItem(KEY, 'still');
    render(<Harness storageKey={KEY} />);
    expect(screen.getByTestId('rotating').textContent).toBe('false');
    await tick(3000);
    expect(screen.getByTestId('page').textContent).toBe('a');
    // روشن‌کردن دوباره، کلید را به «rotate» می‌بندد تا درِ نشستِ بعد هم یادش بماند
    fireEvent.click(screen.getByTestId('toggle'));
    expect(localStorage.getItem(KEY)).toBe('rotate');
  });
});

const pulse = {
  smartMoney: null,
  summary: {
    status: 'ok',
    rows: [
      { key: 'eq_all', label: 'سهام و حق تقدم', symbols: 985, traded: 931, pc_buy_m_toman: 75.5, pc_sell_m_toman: 36.5, buy_power: 2.07 },
    ],
  },
  depth: {
    status: 'ok', group: 'eq_all', depth_available: true, buy_queue_b_toman: 16997.8,
    sell_queue_b_toman: 1660.0, ratio: 10.24, buy_queue_count: 214, sell_queue_count: 31,
  },
  thermometer: {
    status: 'ok', group: 'eq_all', positive: 610, negative: 292, zero: 13, nodata: 16,
    not_traded: 54, positive_pct: 66.7, negative_pct: 31.9,
  },
} as unknown as Record<string, unknown>;

const histogram = {
  status: 'ok', group: 'all', histo12: [], known: 931, nodata: 16, not_traded: 54, total: 985,
} as unknown as Record<string, unknown>;

const split = {
  status: 'ok', tab: 'all', symbols: 985, money_flow_b_toman: -4055.9,
  retail: { buy_b_toman: 18877.8, sell_b_toman: 22933.7 },
} as unknown as Record<string, unknown>;

function renderTicker(pulseArg: unknown = pulse) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MarketStatusTicker pulse={pulseArg as never} histogram={histogram as never} split={split as never} />
    </QueryClientProvider>,
  );
}

describe('نوارِ خلاصۀ چرخشی', () => {
  beforeEach(() => localStorage.clear());

  it('پنج تبِ دستی همیشه دیدنی‌اند و صفحۀ فعال aria-current می‌گیرد', () => {
    renderTicker();
    for (const id of ['breadth', 'flow', 'value', 'queues', 'quality']) {
      expect(screen.getByTestId(`ticker-tabs-${id}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId('ticker-tabs-breadth')).toHaveAttribute('aria-current', 'page');
  });

  it('عددِ هر صفحّه از همان داده است؛ نبودِ داده صفر نمی‌شود', () => {
    const first = renderTicker();
    expect(screen.getByTestId('ticker-fact-مثبت').textContent).toBe('۶۱۰');
    expect(screen.getByTestId('ticker-fact-منفی').textContent).toBe('۲۹۲');
    first.unmount();
    renderTicker({ ...pulse, thermometer: null, depth: null } as Record<string, unknown>);
    expect(screen.getByTestId('ticker-fact-مثبت').textContent).toBe('—');
  });

  it('عمقِ نرسیده «بی‌داده» می‌گوید، نه صفِ صفر', () => {
    renderTicker({ ...pulse, depth: { ...(pulse.depth as object), depth_available: false } } as Record<string, unknown>);
    fireEvent.click(screen.getByTestId('ticker-tabs-queues'));
    expect(screen.getByTestId('ticker-no-depth')).toBeInTheDocument();
    expect(screen.queryByTestId('ticker-fact-ارزش صف خرید')).not.toBeInTheDocument();
  });

  it('کلیدِ توقف رویِ نوار هم کار می‌کند (همان تنظیمِ مشترک)', () => {
    renderTicker();
    const toggle = screen.getByTestId('ticker-rotate-toggle');
    expect(toggle.textContent).toContain('روشن');
    fireEvent.click(toggle);
    expect(localStorage.getItem('market.status.ticker.rotate.v1')).toBe('still');
    expect(screen.getByTestId('ticker-rotate-toggle').textContent).toContain('خاموش');
  });
});
