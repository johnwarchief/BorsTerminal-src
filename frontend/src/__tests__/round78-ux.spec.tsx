// __tests__/round78-ux.spec.tsx -- گاردِ Task #78 (باقی‌ماندۀ UX جهانی)
// چهار قراردادِ تازه درِ همین دور بسته شد و همین‌جا میخ می‌خورد:
//   1) هوک مشترکِ دیالوگ: Escape/تلهٔ Tab/focus اولیه/بازگردانی focus/قفل اسکرول
//   2) سطرِ تعاملیِ FtsScreenTable با کیبورد کار می‌کند (Enter/Space)، سطرِ حذف‌شده نه
//   3) خطا دکمۀ «تلاش دوباره» دارد و همان refetch را صدا می‌زند (دکمهٔ fake ممنوع)
//   4) نقطۀ وضعیتِ Topbar از سیگنالِ واقعیِ کوئری تابلو می‌آید، نه از رنگِ ثابت
import type { ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { Modal } from '@shared/components/Modal';
import { MARKET_FEED_KEY } from '@shared/api/marketFeed';
import { Topbar } from '@app/components/Topbar';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { FtsBadgeStrip } from '@features/technical/components/FtsBadgeStrip';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

// jsdom اندازه ندارد -- virtualizer را به رندر کامل وادار می‌کنیم (الگوی fts-screen)
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 12;
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => {
      const { count } = opts;
      return {
        getTotalSize: () => count * 46,
        getVirtualItems: () =>
          Array.from({ length: Math.min(count, WINDOW) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
      };
    },
  };
});

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'شپنا',
    symbol_norm: 'شپنا',
    name: 'پالایش نفت اصفهان',
    sector_name: 'محصولات نفتی',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_last: 150,
    eps_data_gap: false,
    ...patch,
  } as FtsScreenRow;
}

describe('۱) هوک مشترکِ دیالوگ (Modal)', () => {
  it('focus اولیه داخل پنل، قفل اسکرول، تلهٔ Tab دورِ پنل و Escape می‌بندد', () => {
    const onClose = vi.fn();
    render(
      <Modal title="پنجرۀ تست" onClose={onClose}>
        <input aria-label="ورودیِ پنل" />
      </Modal>,
    );
    // اولین عنصرِ قابل‌فوکوسِ پنل دکمۀ «✕ / بستن» است
    expect(document.activeElement?.getAttribute('aria-label')).toBe('بستن');
    expect(document.body.style.overflow).toBe('hidden');

    const input = screen.getByLabelText('ورودیِ پنل');
    input.focus();
    // Tab از آخرین عنصرِ پنل → به اولین برمی‌گردد (بیرون زدنی وجود ندارد)
    fireEvent.keyDown(input, { key: 'Tab' });
    expect(document.activeElement?.getAttribute('aria-label')).toBe('بستن');
    // Shift+Tab از اولین → به آخرین
    fireEvent.keyDown(screen.getByRole('button', { name: 'بستن' }), { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(input);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('بازگردانی focus به تریگر + آزادسازی قفل اسکرول پس از بسته شدن', () => {
    const trigger = document.createElement('button');
    document.body.appendChild(trigger);
    trigger.focus();
    const { unmount } = render(
      <Modal title="پنجرۀ دوم" onClose={() => {}}>
        <span>بدنه</span>
      </Modal>,
    );
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('');
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});

describe('۲) سطرِ کیبورد-پذیرِ غربالگری FTS', () => {
  it('Enter و Space همان onSelect را صدا می‌زنند', () => {
    const onSelect = vi.fn();
    render(<FtsScreenTable rows={[row()]} thresholds={null} onSelect={onSelect} />);
    const tr = screen.getByTestId('fts-screen-row');
    expect(tr.getAttribute('tabindex')).toBe('0');
    fireEvent.keyDown(tr, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('شپنا');
    fireEvent.keyDown(tr, { key: ' ' });
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it('سطرِ حذف‌شده (excluded) در جدول رسم نمی‌شود تا کیبورد هم نگیرد', () => {
    const onSelect = vi.fn();
    render(
      <FtsScreenTable
        rows={[row(), row({ symbol: 'پترو', symbol_norm: 'پترو', excluded: true })]}
        thresholds={null}
        onSelect={onSelect}
      />,
    );
    const trs = screen.getAllByTestId('fts-screen-row');
    expect(trs).toHaveLength(1);
    expect(trs[0].getAttribute('tabindex')).toBe('0');
    fireEvent.keyDown(trs[0], { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('شپنا');
  });
});

describe('۳) تلاشِ دوباره روی خطای نشانِ تحلیل', () => {
  it('در حالتِ خطا دکمه هست و کلیک همان onRetry است', () => {
    const onRetry = vi.fn();
    render(<FtsBadgeStrip data={null} empty={false} error="تحلیل از سرور گرفته نشد" onRetry={onRetry} />);
    fireEvent.click(screen.getByTestId('fts-strip-retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('بی‌خطا هیچ دکمهٔ تلاشی رسم نمی‌شود', () => {
    render(<FtsBadgeStrip data={null} empty onRetry={() => {}} />);
    expect(screen.queryByTestId('fts-strip-retry')).toBeNull();
  });
});

describe('۴) نقطۀ وضعیتِ تاپ‌بار از سیگنالِ واقعی', () => {
  function FeedProbe({ ok }: { ok: boolean }) {
    useQuery({
      queryKey: MARKET_FEED_KEY,
      queryFn: () => (ok ? Promise.resolve({ rows: [] }) : Promise.reject(new Error('down'))),
      retry: false,
    });
    return null;
  }
  const withBar = (ui: ReactNode) => (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );

  it('بی‌کوئریِ اجراشده «در انتظار» است — ادعای آنلاین بی‌سیگنال ممنوع', () => {
    render(withBar(<Topbar />));
    expect(screen.getByRole('status').getAttribute('aria-label')).toContain('در انتظار');
  });

  it('خطای خوراکِ تابلو ⇒ قرمز و صادق', async () => {
    render(withBar(<><FeedProbe ok={false} /><Topbar /></>));
    await waitFor(() =>
      expect(screen.getByRole('status').getAttribute('aria-label')).toContain('دادهٔ تابلو نمی‌رسد'),
    );
  });

  it('خوراکِ سالم ⇒ سبزِ «سیستم آنلاین و متصل»', async () => {
    render(withBar(<><FeedProbe ok /><Topbar /></>));
    await waitFor(() =>
      expect(screen.getByRole('status').getAttribute('aria-label')).toBe('سیستم آنلاین و متصل'),
    );
  });
});
