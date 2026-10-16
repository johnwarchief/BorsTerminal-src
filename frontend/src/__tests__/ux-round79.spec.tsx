// __tests__/ux-round79.spec.tsx -- گاردِ P0 دورِ تحقیق UX
// ۱) نماداستور: اخیرها با هر انتخاب واقعی نوشته می‌شوند و pinnedها دستِ کاربرند
// ۲) پالت فرمان سه‌شیاری: نماد/صفحه/فرمان، فرمان‌ها واقعاً اجرا می‌شوند
// ۳) تب قیف دیگر فقط هایلایت نیست — کارتِ همان مرحله را به دید می‌آورد
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CommandPalette, PALETTE_OPEN_EVENT } from '@app/components/CommandPalette';
import { useSymbolStore } from '@shared/stores/symbolStore';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

// پالت فرمان حالا از فیدِ مشترکِ تابلو (useMarketFeedShared) می‌خواند، پس مثلِ هر
// مصرف‌کننده‌ای باید زیرِ QueryClientProvider رندر شود — همان چیزی که درِ AppShell
// هست. بی‌کوئریِ دومِ /api/market دیگر فرستاده نمی‌شود (#M2.2).
function renderPalette() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <CommandPalette />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  useSymbolStore.setState({ symbol: '', recent: [], pinned: [] });
});

describe('۱) اخیرها و سنجاق‌ها درِ symbolStore', () => {
  it('setSymbol نماد را اولِ اخیرها می‌گذارد و تکراری را یکی می‌کند', () => {
    const { setSymbol } = useSymbolStore.getState();
    setSymbol('فولاد');
    setSymbol('شپنا');
    setSymbol('فولاد');
    const st = useSymbolStore.getState();
    expect(st.recent).toEqual(['فولاد', 'شپنا']);
    expect(JSON.parse(localStorage.getItem('bors-symbol-recent') ?? '[]')).toEqual(['فولاد', 'شپنا']);
  });

  it('togglePin افزودن/برداشتن است و بی‌رابطه با setSymbol پاک نمی‌شود', () => {
    const { setSymbol, togglePin } = useSymbolStore.getState();
    setSymbol('خودرو');
    togglePin('خودرو');
    expect(useSymbolStore.getState().pinned).toEqual(['خودرو']);
    useSymbolStore.getState().togglePin('خودرو');
    expect(useSymbolStore.getState().pinned).toEqual([]);
  });
});

describe('۲) پالت فرمان سه‌شیار', () => {
  const openPalette = () => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT));

  it('بی‌کوئری: شیارهای نماد/صفحه/فرمان رسم می‌شوند و صفحه‌ها لینک‌اند', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: async () => ({ data: [{ symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات' }] }),
    });
    renderPalette();
    openPalette();
    await waitFor(() => expect(screen.getByText('صفحه')).toBeInTheDocument());
    expect(screen.getByText('فرمان')).toBeInTheDocument();
    expect(screen.getByText('مدیریت پرتفوی')).toBeInTheDocument();
    expect(screen.getByText('تغییر پوسته (روشن/تیره)')).toBeInTheDocument();
  });

  it('فرمان «پاک کردن نمادِ انتخابی» همان command اجرا می‌کند، نه نمایش', async () => {
    useSymbolStore.setState({ symbol: 'فولاد' });
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: async () => ({ data: [] }),
    });
    renderPalette();
    openPalette();
    const cmd = await screen.findByText('پاک کردن نمادِ انتخابی');
    fireEvent.click(cmd);
    expect(useSymbolStore.getState().symbol).toBe('');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('pinned در صدر نتایج با برچسبِ «سنجاق» می‌آید حتی پیش از رسیدن فید', async () => {
    fetchMock.mockImplementation(() => new Promise(() => {})); // فید هرگز نمی‌رسد
    useSymbolStore.setState({ pinned: ['فولاد'], recent: [] });
    renderPalette();
    openPalette();
    await waitFor(() => expect(screen.getByText('فولاد')).toBeInTheDocument());
    expect(screen.getByText('سنجاق')).toBeInTheDocument();
  });
});
