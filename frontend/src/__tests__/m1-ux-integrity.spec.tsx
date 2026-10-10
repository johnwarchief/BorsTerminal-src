// تست‌هایِ M1/M2/M3 — تفکیکِ اتصال از تازگی، مصرفِ خطایِ قیف، فیدِ مشترکِ پالت،
// presetِ واحدِ درخت، داوریِ مشترکِ پنل، و ریتمِ پرتفوی/کندل.
// هیچ ادعایی از خودِ UI نمی‌آید: تابعِ خالصِ freshness را با ورودیِ کنترل‌شده
// می‌سنجیم و مصرف‌کننده‌ها را با fetchِ شمارش‌شده.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { computeFeedStatus } from '@shared/lib/feedFreshness';
import { CLOSED_POLL_MS } from '@shared/lib/marketHours';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { SuspiciousPanel } from '@features/market/components/SuspiciousPanel';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { FunnelErrorBanner } from '@features/master/ui/FunnelErrorBanner';
import type { MarketRow } from '@shared/types/marketRow';

const NOW = Date.UTC(2026, 9, 12, 6, 30); // ۱۰:۰۰ Tehran ≈ 06:30Z، دوشنبه

describe('computeFeedStatus — اتصال ≠ تازگی', () => {
  it('بازارِ باز + ردیفِ نشستِ جاری + تازه‌سازیِ روان ⇒ live', () => {
    const st = computeFeedStatus({ status: 'success', dataUpdatedAt: NOW - 2_000, liveCount: 500, totalCount: 600, now: NOW, marketOpen: true });
    expect(st.freshness).toBe('live');
    expect(st.connection).toBe('ok');
    expect(st.pulse).toBe(true);
  });

  it('بازارِ بسته ⇒ closed (نه «آنلاینِ متحرک»، نه کهنه، نه خطا)', () => {
    const st = computeFeedStatus({ status: 'success', dataUpdatedAt: NOW - 40 * 60_000, liveCount: 0, totalCount: 600, now: NOW, marketOpen: false });
    expect(st.freshness).toBe('closed');
    expect(st.connection).toBe('ok');
    expect(st.pulse).toBe(false);
    expect(st.label).toContain('بازار بسته');
  });

  it('خطا بر همه‌چیز غالب است و «خالی» نیست', () => {
    const st = computeFeedStatus({ status: 'error', dataUpdatedAt: NOW - 1000, liveCount: 0, totalCount: 0, now: NOW, marketOpen: true });
    expect(st.connection).toBe('error');
    expect(st.label).toContain('نمی‌رسد');
  });

  it('بازارِ باز ولی ردیفِ نشستِ جاری نیست ⇒ stale (نه live)', () => {
    const st = computeFeedStatus({ status: 'success', dataUpdatedAt: NOW - 2_000, liveCount: 0, totalCount: 600, now: NOW, marketOpen: true });
    expect(st.freshness).toBe('stale');
  });

  it('بازارِ باز ولی تازه‌سازی بیش از ریتمِ بسته خوابیده ⇒ stale', () => {
    const st = computeFeedStatus({ status: 'success', dataUpdatedAt: NOW - CLOSED_POLL_MS - 5_000, liveCount: 500, totalCount: 600, now: NOW, marketOpen: true });
    expect(st.freshness).toBe('stale');
    expect(st.label).toContain('متوقف');
  });

  // REV-AT-AGE: سنجشِ زندهٔ ۱۴۰۵-۰۷-۱۸ — `revision` نودوچهار و نیم دقیقه تکان
  // نخورد و نشانگر «(به‌روزرسانی: لحظاتی پیش)» می‌گفت، چون هر دورِ «unchanged»
  // هم `dataUpdatedAt` را نو می‌کند. تازگی باید از عوض‌شدنِ *داده* سنجیده شود.
  it('درخواست‌ها می‌رسند ولی هیچ عددی عوض نشده ⇒ stale، با گفتنِ هر دو سن', () => {
    const st = computeFeedStatus({
      status: 'success', dataUpdatedAt: NOW - 3_000, dataChangedAt: NOW - 945_000,
      liveCount: 2890, totalCount: 5865, now: NOW, marketOpen: true,
    });
    expect(st.freshness).toBe('stale');
    expect(st.connection).toBe('ok');       // اتصال سالم است؛ انکارش نکن
    expect(st.dataAgeMs).toBe(945_000);     // سنِ داده
    expect(st.ageMs).toBe(3_000);           // سنِ پاسخِ HTTP — دو مفهومِ جدا
    expect(st.label).toContain('عوض');
  });

  it('با عوض‌شدنِ اخیرِ داده، همان ورودی ⇒ live', () => {
    const st = computeFeedStatus({
      status: 'success', dataUpdatedAt: NOW - 3_000, dataChangedAt: NOW - 4_000,
      liveCount: 2890, totalCount: 5865, now: NOW, marketOpen: true,
    });
    expect(st.freshness).toBe('live');
  });

  it('بک‌اندِ بی‌`rev_at` (نسخۀ قدیمیِ نصبی) ⇒ رفتارِ پیشین، نه برچسبِ ساختگی', () => {
    const st = computeFeedStatus({
      status: 'success', dataUpdatedAt: NOW - 3_000, dataChangedAt: null,
      liveCount: 2890, totalCount: 5865, now: NOW, marketOpen: true,
    });
    expect(st.freshness).toBe('live');
    expect(st.label).not.toContain('عوض');
  });

  it('live_count گزارش نشده ⇒ unknown (تازگی را قطعی نمی‌کند)', () => {
    const st = computeFeedStatus({ status: 'success', dataUpdatedAt: NOW - 2_000, liveCount: null, totalCount: null, now: NOW, marketOpen: true });
    expect(st.freshness).toBe('unknown');
  });

  it('هنوز داده‌ای نیامده ⇒ connecting/idle، بدونِ سن', () => {
    const st = computeFeedStatus({ status: 'loading', dataUpdatedAt: 0, now: NOW, marketOpen: true });
    expect(st.connection).toBe('connecting');
    expect(st.ageMs).toBeNull();
  });
});

describe('usePortfolio — ریتمِ نشست‌محور، نه هر نفس', () => {
  it('درِ بازارِ باز poll می‌زند و بیرونِ نشست به ریتمِ آرام می‌نشیند', async () => {
    vi.useFakeTimers();
    try {
      // همان منطقِ refetchInterval درِ usePortfolio را مستقیم می‌سنجیم: تابعِ
      // نشست‌محور باید درِ باز ۳۰s و درِ بسته CLOSED_POLL_MS بدهد.
      const { sessionPollMs } = await import('@shared/lib/marketHours');
      const openDt = new Date(NOW);
      expect(sessionPollMs(30_000, openDt)).toBe(30_000);
      const closedDt = new Date(Date.UTC(2026, 9, 15, 4, 0)); // پنجشنبه ≈ تعطیل
      expect(sessionPollMs(30_000, closedDt)).toBe(CLOSED_POLL_MS);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('CommandPalette — فیدِ مشترک، بی‌fetchِ دوم', () => {
  const fetchSpy = vi.fn();
  beforeEach(() => {
    fetchSpy.mockReset();
    globalThis.fetch = fetchSpy;
    useSymbolStore.setState({ symbol: '', recent: [], pinned: ['فولاد'] });
  });

  it('نمادها از MARKET_FEED_KEY خوانده می‌شوند؛ درخواستِ /api/marketِ مستقل نیست', async () => {
    fetchSpy.mockImplementation(() => Promise.reject(new Error('شبکه خاموش')));
    const { CommandPalette } = await import('@app/components/CommandPalette');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(['market-feed'], {
      status: 'success',
      data: [{ ins_code: 'a', symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات' }],
      count: 1,
    });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><CommandPalette /></MemoryRouter>
      </QueryClientProvider>,
    );
    // Ctrl+K بازش می‌کند؛ «فولاد» سنجاق‌شده از همانِ cacheِ feed باید دیده شود
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }));
    await waitFor(() => expect(screen.getByText('فولاد')).toBeInTheDocument(), { timeout: 4000 });
    // پالت از همانِ feed خواند ⇒ هیچ درخواستِ مستقیمی به fetch نرفته (fetch خام)
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe('FunnelErrorBanner — خطا ≠ بازارِ خالی', () => {
  it('blocking و degraded دو متنِ جدا دارند و Retryِ واقعی صدا زده می‌شود', () => {
    const onRetry = vi.fn();
    const { unmount } = render(<FunnelErrorBanner onRetry={onRetry} blocking />);
    expect(screen.getByTestId('funnel-error').textContent).toContain('این «بازارِ خالی» نیست');
    fireEvent.click(screen.getByTestId('funnel-error-retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
    unmount();
    // حالتِ غیربلاکینگ (دادهٔ قبلی رویِ صفحه هست) ⇒ متنِ «تازه‌سازی ناموفق»
    render(<FunnelErrorBanner onRetry={vi.fn()} />);
    expect(screen.getByTestId('funnel-error').textContent).toContain('تازه‌سازیِ قیف ناموفق');
  });
});

describe('SuspiciousPanel — داوری از tapeFilterVerdict و configِ کاربر (#M2.3)', () => {
  // ردیفِ زندهٔ تابلو با ورودیِ فرمول (prior30_vol ⇒ hasTapeFormulaInputs) تا
  // داوریِ canonical راه بیفتد؛ multiple = tvol/prior30.
  const suspRow = (over: Partial<MarketRow> = {}): MarketRow => ({
    symbol: 'پرتویی', name: 'شرکت پرتویی', tvol: 5_000_000, prior30_vol: 1_000_000,
    vol_ratio_file: 5, z_tot_tran: 200, hist_sessions: 40, is_live: true,
    p_last: 1000, p_closing: 1000, ...over,
  } as MarketRow);

  it('با آستانۀ پیش‌فرض (minRatio=3) ردیفِ ۵ برابری درِ «حجم مشکوک» می‌آید', () => {
    useTapeStore.getState().resetTapeFilterConfig();
    render(<SuspiciousPanel rows={[suspRow()]} onSelect={() => {}} sections={['susp']} />);
    expect(screen.getByText('پرتویی')).toBeInTheDocument();
  });

  it('با بالا بردنِ آستانه به ۱۰، همان ردیف دیگر مشکوک نیست — پنل config را رعایت می‌کند', () => {
    useTapeStore.getState().setTapeFilterConfig({ suspiciousVolume: { minRatio: 10 } as never });
    render(<SuspiciousPanel rows={[suspRow()]} onSelect={() => {}} sections={['susp']} />);
    expect(screen.queryByText('پرتویی')).not.toBeInTheDocument();
    useTapeStore.getState().resetTapeFilterConfig();
  });
});

describe('useActiveFunnelPreset — تصمیمِ واحدِ preset (Master و درخت) (#M2.1)', () => {
  it('URL > انتخابِ ذخیره‌شده > افق؛ بی‌URL، savedPreset غالب بر horizon است', async () => {
    const { renderHook } = await import('@testing-library/react');
    const { useActiveFunnelPreset } = await import('@features/master/lib/useActiveFunnelPreset');
    const { useFunnelPrefsStore } = await import('@features/master/stores/funnelPrefsStore');
    const { useStrategyStore } = await import('@shared/stores/strategyStore');
    const { MemoryRouter } = await import('react-router');

    useFunnelPrefsStore.getState().setPreset('trend');
    useStrategyStore.setState({ horizon: 'swing' });

    const wrapper = (url: string) =>
      function W({ children }: { children: React.ReactNode }) {
        return <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>;
      };

    // بی‌URL ⇒ همان انتخابِ ذخیره‌شده، نه افق
    const a = renderHook(() => useActiveFunnelPreset('hourglass'), { wrapper: wrapper('/master') });
    expect(a.result.current).toBe('trend');

    // با URL ⇒ URL غالب است
    const b = renderHook(() => useActiveFunnelPreset('hourglass'), { wrapper: wrapper('/master?preset=custom') });
    expect(b.result.current).toBe('custom');

    useFunnelPrefsStore.getState().setPreset('custom');
  });
});
