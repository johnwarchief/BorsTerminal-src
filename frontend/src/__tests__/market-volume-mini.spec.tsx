// تست مینی‌چارت جریان حجم (P-03/#49): منبع = دلتای خوراک تابلو، بدون داده صادقانه،
// هایلایت پنجره‌های FTS، و هیچ درخواستی به اندپوینتِ درون‌روزهٔ ساختگی نمی‌رود.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  FTS_WINDOWS,
  MARKET_CLOSE,
  MARKET_OPEN,
  VolumeFlowMini,
  inFtsWindow,
} from '@features/market/components/VolumeFlowMini';
import { recordFlow } from '@features/market/lib/symbolFlow';
import { toEnDigits } from '@shared/lib/fmt';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

/** عددِ فارسیِ داخلِ title ⇒ عددِ قابلِ مقایسه */
function titleValue(el: HTMLElement): number {
  const afterDash = toEnDigits(el.getAttribute('title') ?? '').split('—')[1] ?? '';
  const m = /([\d.]+)/.exec(afterDash.replace(/,/g, ''));
  return m ? Number(m[1]) : NaN;
}

function json(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}

/** پاسخ /api/market با حجمِ انباشته و قیمتِ دلخواه */
function feed(cumVol: number, price: number) {
  return {
    status: 'success',
    count: 1,
    data: [{ symbol: 'شپنا', name: 'پتروشیمی پارس', q_tot_tran: cumVol, p_last: price }],
  };
}

function renderMini(symbol: string, compact = false) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = render(
    <QueryClientProvider client={qc}>
      <VolumeFlowMini symbol={symbol} compact={compact} />
    </QueryClientProvider>,
  );
  return { ...ui, qc };
}

describe('پنجره‌های حساس FTS', () => {
  it('بازهٔ معاملات و دو پنجرهٔ FTS', () => {
    expect(MARKET_OPEN).toBe('08:45');
    expect(MARKET_CLOSE).toBe('12:30');
    expect(FTS_WINDOWS).toEqual([
      ['09:00', '09:30'],
      ['12:00', '12:30'],
    ]);
  });

  it('inFtsWindow فقط داخل پنجره‌ها درست است', () => {
    expect(inFtsWindow('09:00')).toBe(true);
    expect(inFtsWindow('09:15')).toBe(true);
    expect(inFtsWindow('09:30')).toBe(true);
    expect(inFtsWindow('12:15')).toBe(true);
    expect(inFtsWindow('10:00')).toBe(false);
    expect(inFtsWindow('08:45')).toBe(false);
    expect(inFtsWindow('13:00')).toBe(false);
  });
});

describe('مینی‌چارت جریان حجم', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    localStorage.clear();
    // چهارشنبه ۰۹:۲۰ — داخل ساعتِ بازار، وگرنه چیزی ثبت نمی‌شود
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 8, 30, 9, 20));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('بدون نماد انتخابی چیزی رندر نمی‌شود', () => {
    const { container } = renderMini('');
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId('volume-flow-mini')).not.toBeInTheDocument();
  });

  it('خالی بودنِ سری ⇒ «بدون داده» صادقانه، نه میلهٔ ساختگی', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json(feed(1000, 100))));
    renderMini('فولاد');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(await screen.findByTestId('volume-mini-empty')).toHaveTextContent('بدون داده');
    expect(screen.queryByTestId('volume-mini-chart')).not.toBeInTheDocument();
  });

  it('سریِ جمع‌شده در همین نشست ⇒ میله‌ها با هایلایت پنجرهٔ FTS', () => {
    recordFlow('شپنا', { t: '09:14', cumVol: 1000, price: 100 }, undefined, localStorage);
    recordFlow('شپنا', { t: '09:15', cumVol: 1600, price: 101 }, undefined, localStorage);
    recordFlow('شپنا', { t: '10:00', cumVol: 1900, price: 99 }, undefined, localStorage);
    recordFlow('شپنا', { t: '12:15', cumVol: 2900, price: 100 }, undefined, localStorage);
    fetchMock.mockImplementation(() => Promise.resolve(json(feed(2900, 100))));
    renderMini('شپنا');
    expect(screen.getByTestId('volume-mini-chart')).toBeInTheDocument();
    expect(titleValue(screen.getByTestId('volume-mini-bar-09:15'))).toBe(600);
    expect(screen.getByTestId('volume-mini-bar-09:15')).toHaveAttribute('data-fts-window', 'true');
    expect(screen.getByTestId('volume-mini-bar-12:15')).toHaveAttribute('data-fts-window', 'true');
    expect(screen.getByTestId('volume-mini-bar-10:00')).not.toHaveAttribute('data-fts-window');
  });

  it('هر پولینگِ تازه دلتای حجم را به سری اضافه می‌کند', async () => {
    let cum = 1000;
    fetchMock.mockImplementation(() => Promise.resolve(json(feed(cum, 100))));
    const { qc } = renderMini('شپنا');
    // نمونۀ اول پایه است و حجمی نمی‌گوید؛ باید نشسته باشد تا دلتای دوم معنا داشته باشد
    await screen.findByTestId('volume-mini-empty');
    expect(screen.queryByTestId('volume-mini-chart')).not.toBeInTheDocument();

    cum = 2500;
    vi.setSystemTime(new Date(2026, 8, 30, 9, 21));
    await act(async () => {
      await qc.invalidateQueries();
    });
    await waitFor(() =>
      expect(screen.getByTestId('volume-mini-bar-09:21')).toBeInTheDocument(),
    );
    expect(titleValue(screen.getByTestId('volume-mini-bar-09:21'))).toBe(1500);
  });

  it('هیچ درخواستی به مسیر درون‌روزهٔ بک‌اند نمی‌رود', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json(feed(1000, 100))));
    renderMini('شپنا');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.every((u) => !u.includes('/intraday/'))).toBe(true);
    expect(urls.some((u) => u.includes('/api/market'))).toBe(true);
  });
});
