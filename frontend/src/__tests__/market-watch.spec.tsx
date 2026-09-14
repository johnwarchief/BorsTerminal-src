// تست دیده‌بان‌ها: جدول تمام‌عرض است و سه پنل کناری به دراور تب‌دار رفته‌اند
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { WatchDrawer } from '@features/market/components/WatchDrawer';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    percent_change: 2.5,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 5,
    buyer_power: 2.1,
    p_last: 1000,
    p_closing: 1030,
    z_tot_tran: 120,
    is_live: true,
    ...patch,
  } as MarketRow;
}

// صنایع داخل تب «صنایع داغ» از fetch استفاده می‌کند؛ بقیه ردیف-محورند
const fetchMock = vi.fn(() => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response));
vi.stubGlobal('fetch', fetchMock);

describe('دراور دیده‌بان‌های تابلو', () => {
  it('بسته است تا یک تب فعال نشود؛ سه تریگر سریع دیده می‌شوند', () => {
    render(<WatchDrawer rows={[row()]} onSelect={() => {}} />);
    expect(screen.getByRole('tab', { name: 'دیده‌بان ساعت' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'دیده‌بان حجم مشکوک' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'صنایع داغ' })).toBeInTheDocument();
    expect(screen.queryByTestId('watch-body')).not.toBeInTheDocument();
  });

  it('کلیک «دیده‌بان ساعت» فقط بخش الگوی ساعت را بازنشانی می‌کند', () => {
    const rows = [row({ symbol: 'قوی', p_closing: 950, p_last: 1010, price_yesterday: 1000 })];
    render(<WatchDrawer rows={rows} onSelect={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: 'دیده‌بان ساعت' }));
    expect(screen.getByTestId('watch-body')).toBeInTheDocument();
    expect(screen.getByText(/الگوی ساعت/)).toBeInTheDocument();
    // بخش‌های حجم مشکوک/کف‌روبی در این تب پنه‌اند
    expect(screen.queryByText(/حجم مشکوک \(/)).not.toBeInTheDocument();
    expect(screen.queryByText(/کف‌روبی \(/)).not.toBeInTheDocument();
  });

  it('کلیک «دیده‌بان حجم مشکوک» هر دو بخش حجم و کف‌روبی را نشان می‌دهد', () => {
    render(<WatchDrawer rows={[row({ symbol: 'خودرو' })]} onSelect={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: 'دیده‌بان حجم مشکوک' }));
    expect(screen.getByText(/حجم مشکوک \(/)).toBeInTheDocument();
    expect(screen.getByText(/کف‌روبی \(/)).toBeInTheDocument();
  });

  it('تب فعال aria-selected دارد و دکمهٔ بستن دراور را می‌بندد', () => {
    render(<WatchDrawer rows={[row()]} onSelect={() => {}} />);
    const clockTab = screen.getByRole('tab', { name: 'دیده‌بان ساعت' });
    fireEvent.click(clockTab);
    expect(screen.getByRole('tab', { name: 'دیده‌بان ساعت' })).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByTestId('watch-close'));
    expect(screen.queryByTestId('watch-body')).not.toBeInTheDocument();
  });
});
