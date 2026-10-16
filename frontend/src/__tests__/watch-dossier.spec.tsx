// __tests__/watch-dossier.spec.tsx — بندِ ۲ و ۳ مأموریت: پروندۀ یکپارچۀ نماد درِ دیدهبان
//
// سه ادعا:
//   ۱) فهرستِ هاب = اتحادِ ستارۀ سرور و دیدهبانِ محلی (نمادی که فقط ستاره دارد
//      هم درِ همان جدول می‌نشیند؛ «دو فهرستِ جدا» دیگر دلیلِ ندیدن نیست)
//   ۲) سابقۀ چندروزه از /api/tape-history خوانده می‌شود و سه حالت را جدا می‌گوید:
//      روشن (✓)، رصدشده-خاموش (—)، ثبت‌نشده (ستون ندارد) — و «از چه تاریخی
//      قابل‌اعتماد است» را صریح می‌نویسد
//   ۳) با تغییرِ نماد، پروندۀ نمادِ قبلی رویِ صفحه نمی‌ماند
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WatchMarketWorkspace from '@features/portfolio/components/WatchMarketWorkspace';
import { resetMarketFeedMirror } from '@shared/api/marketFeed';
import { useWatchSymbolsStore } from '@features/portfolio/stores/watchSymbolsStore';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const D1 = 20261011, D2 = 20261012;

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } });

const row = (symbol: string, ins_code: string) => ({
  symbol, name: `شرکت ${symbol}`, ins_code, p_last: 1025, p_closing: 1000, p_first: 990,
  p_max: 1040, p_min: 980, percent_change: 2.5, q_tot_tran: 5_000_000, z_tot_tran: 320,
  q_tot_cap: 5_125_000_000, buy_q1_px: 1024, buy_q1_vol: 44_600, sell_q1_px: 1026,
  sell_q1_vol: 9_846, row_h: 102335, is_live: true,
  f_susp: symbol === 'شپنا', f_jet: false, f_clock: false, f_roobi: false, f_noqteh: false,
  f_smart: false, f_legal: false,
});

beforeEach(() => {
  resetMarketFeedMirror();
  useWatchSymbolsStore.setState({ symbols: ['شپنا'] });
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    if (u.includes('/api/watchlist')) {
      return Promise.resolve(json({ status: 'success', count: 1, limit: 50,
        data: [{ norm: 'فولاد', symbol: 'فولاد', name: 'فولاد مبارکه', note: '', added_at: 'x' }] }));
    }
    if (u.includes('/api/tape-history')) {
      const onDay = { active: true, first_at: '2026-10-11 09:12:00', last_at: '2026-10-11 11:02:00',
                      passes: 3, evidence: { tvol: 4_000_000 } };
      const offDay = { active: false, first_at: null, last_at: null, passes: 0, evidence: {} };
      return Promise.resolve(json({
        status: 'success', days: [D1, D2], reliable_from: D1,
        flags: ['f_clock', 'f_susp'], write_error: null,
        by_symbol: { A1: { f_susp: { total: 1, last_seen_at: '2026-10-11 09:12:00',
                                     days: { [String(D1)]: onDay, [String(D2)]: offDay } } } },
      }));
    }
    if (u.includes('/api/fundamental')) {
      return Promise.resolve(json({ status: 'success', symbol: 'شپنا' }));
    }
    return Promise.resolve(json({ status: 'success', rev: 3, count: 2, live_count: 2,
      fossil_count: 0, meta: { d_even: D2, h_even: 102335 },
      data: [row('شپنا', 'A1'), row('فولاد', 'A2')] }));
  });
});

const renderHub = () => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <WatchMarketWorkspace />
  </QueryClientProvider>,
);

describe('پروندۀ نماد درِ دیدهبان', () => {
  it('ستارۀ سرور و دیدهبانِ محلی درِ یک فهرست یکی می‌شوند', async () => {
    renderHub();
    await waitFor(() => expect(screen.getByTestId('watch-row-شپنا')).toBeInTheDocument());
    // «فولاد» فقط درِ /api/watchlist است و درِ store محلی نیست — با این‌حال ردیفش
    // درِ هاب می‌نشیند، وگرنه انتخابِ دسته‌ای از جدول تحویل بی‌صدا گم می‌شد.
    await waitFor(() => expect(screen.getByTestId('watch-row-فولاد')).toBeInTheDocument());
    expect(screen.getByTestId('watch-server-note').textContent).toContain('اتحاد');
  });

  it('سابقۀ چندروزه: ✓، «—» و نبودِ ستون — سه حالتِ جدا', async () => {
    renderHub();
    await waitFor(() => expect(screen.getByTestId('tape-history-شپنا')).toBeInTheDocument());
    const panel = screen.getByTestId('tape-history-شپنا');
    const susp = screen.getByTestId('tape-history-row-شپنا-f_susp');
    expect(susp.textContent).toContain('✓');      // D1 روشن
    expect(susp.textContent).toContain('—');      // D2 رصد شد و خاموش بود
    // روزِ رصدنشده ستون نمی‌سازد (وگرنه «غیرفعالِ» ساختگی پرِ جدول می‌شد)
    expect(panel.querySelectorAll('thead th')).toHaveLength(1 + 2 + 2);  // فیلتر + دو روز + دفعات/روند
    expect(screen.getByTestId('tape-history-note-شپنا').textContent)
      .toContain('قابل‌اعتماد است');
  });

  it('با انتخابِ نمادِ دیگر، پرونده عوض می‌شود — اطلاعاتِ شپنا رویِ فولاد نمی‌ماند', async () => {
    renderHub();
    await waitFor(() => expect(screen.getByTestId('tape-history-شپنا')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('watch-row-فولاد'));
    await waitFor(() => expect(screen.getByTestId('tape-history-فولاد')).toBeInTheDocument());
    expect(screen.queryByTestId('tape-history-شپنا')).not.toBeInTheDocument();
    // فولاد درِ پاسخِ ساختگیِ بالا ردیفِ سابقه ندارد ⇒ «صفر روز» با «ثبت نشده»
    // distinguish می‌ماند و هیچ ✓ جعلی رسم نمی‌شود.
    expect(screen.getByTestId('tape-history-row-فولاد-f_susp').textContent).not.toContain('✓');
  });
});
