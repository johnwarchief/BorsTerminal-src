// تست ماتریس تخصیص صنایع سهام (سند FTS §۴): بازه‌ها، نگاشت صنعت، وزن فعلی و هشدار Overweight
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SectorMatrix } from '@features/portfolio/components/SectorMatrix';
import {
  SECTOR_BANDS,
  bandRangeLabel,
  computeSectorAllocation,
  matchSectorBand,
  normalizeSector,
  overweightAlerts,
} from '@features/portfolio/model/sectorAllocation';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function ok(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}

function renderMatrix() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SectorMatrix />
    </QueryClientProvider>,
  );
}

function mockFeed(decisions: unknown[]) {
  return {
    status: 'success',
    decisions,
    portfolio: decisions,
    monitor: [],
    counts: { accept: decisions.length, reject: 0, monitor: 0, pending: 0 },
    limits: { min: 5, max: 7, weight_cap_pct: 20 },
  };
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    if (String(url) === '/api/selection/portfolio') return Promise.resolve(ok(mockFeed([])));
    return Promise.resolve(ok({ status: 'error' }));
  });
});

describe('مدل ماتریس صنایع (خالص)', () => {
  it('سند FTS §۴ هفت طبقه با بازهٔ درست دارد', () => {
    expect(SECTOR_BANDS.map((b) => b.label)).toEqual([
      'فلزات اساسی',
      'سیمان',
      'پتروپالایشی',
      'بانکی',
      'دارویی منتخب',
      'زراعت',
      'ضدبحران / متفرقه',
    ]);
    const petro = SECTOR_BANDS.find((b) => b.id === 'petro')!;
    expect([petro.min, petro.max]).toEqual([15, 20]);
    // بازهٔ تک‌نقطه‌ای فقط یک عدد نشان می‌دهد
    expect(bandRangeLabel(SECTOR_BANDS.find((b) => b.id === 'bank')!)).toBe('۱۰٪');
  });

  it('نگاشت نام صنعت تابلو به طبقهٔ سند با یکدست‌سازی ي/ك و نیم‌فاصله', () => {
    expect(normalizeSector('پتروشيمي')).toBe('پتروشیمی');
    expect(matchSectorBand('فلزات اساسي')).toBe('metals');
    expect(matchSectorBand('سيمان، آهك و گچ')).toBe('cement');
    expect(matchSectorBand('بانكها و موسسات اعتباري')).toBe('bank');
    expect(matchSectorBand('مواد و محصولات دارويي')).toBe('pharma');
    expect(matchSectorBand('زراعت و خدمات وابسته')).toBe('agri');
    expect(matchSectorBand('رايانه و فعاليت‌هاي وابسته به آن')).toBe('defensive');
    expect(matchSectorBand('')).toBeNull();
  });

  it('فقط تصمیم‌های accept وزن می‌گیرند و عبور از سقف هشدار می‌سازد', () => {
    const alloc = computeSectorAllocation([
      { symbol: 'فملی', status: 'accept', weight_eff_pct: 10, sector: 'فلزات اساسي' },
      { symbol: 'فسبزوار', status: 'accept', weight_eff_pct: 8, sector: 'فلزات اساسي' },
      { symbol: 'وبملت', status: 'accept', weight_eff_pct: 6, sector: 'بانكها و موسسات اعتباري' },
      { symbol: 'شپنا', status: 'monitor', weight_eff_pct: 9, sector: 'فلزات اساسي' },
      { symbol: 'دزاگرس', status: 'accept', weight_eff_pct: 0, sector: 'مواد و محصولات دارويي' },
    ]);
    expect(alloc.hasData).toBe(true);
    const metals = alloc.rows.find((r) => r.band.id === 'metals')!;
    expect(metals.actualPct).toBe(18);
    expect(metals.overweight).toBe(true);
    expect(metals.overByPct).toBe(3);
    expect(metals.members.map((m) => m.symbol)).toEqual(['فملی', 'فسبزوار']);
    // monitor وزن نمی‌گیرد
    const bank = alloc.rows.find((r) => r.band.id === 'bank')!;
    expect(bank.actualPct).toBe(6);
    expect(bank.overweight).toBe(false);
    // نماد با وزن صفر شمرده می‌شود
    expect(alloc.zeroWeightCount).toBe(1);

    const alerts = overweightAlerts(alloc.rows);
    expect(alerts).toHaveLength(1);
    expect(alerts[0].label).toBe('فلزات اساسی');
    expect(alerts[0].reason).toContain('۱۸٪');
    expect(alerts[0].reason).toContain('سقف سند');
  });

  it('بدون داده هیچ هشداری ساخته نمی‌شود و وزن‌ها صفر می‌مانند', () => {
    const alloc = computeSectorAllocation([]);
    expect(alloc.hasData).toBe(false);
    expect(alloc.mappedTotalPct).toBe(0);
    expect(alloc.rows.every((r) => r.actualPct === 0)).toBe(true);
    expect(overweightAlerts(alloc.rows)).toEqual([]);
  });
});

describe('کامپوننت ماتریس صنایع', () => {
  it('در نبود تصمیم، «بدون داده» نشان می‌دهد و هشدار نمی‌زند', async () => {
    renderMatrix();
    expect(await screen.findByText('تفکیک صنایع سهام (سند FTS)')).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText('بدون داده').length).toBeGreaterThan(0));
    expect(screen.queryByText(/نقض تنوع‌بخشی/)).toBeNull();
    // همهٔ هفت طبقه با بازهٔ سند دیده می‌شوند
    for (const b of SECTOR_BANDS) {
      expect(screen.getAllByText(b.label).length).toBeGreaterThanOrEqual(1);
    }
  });

  it('صنعت عبورکرده از سقف، هشدار Overweight علت‌محور می‌دهد', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (String(url) === '/api/selection/portfolio')
        return Promise.resolve(
          ok(
            mockFeed([
              { symbol: 'فملی', status: 'accept', weight_eff_pct: 10, sector: 'فلزات اساسي' },
              { symbol: 'فسبزوار', status: 'accept', weight_eff_pct: 8, sector: 'فلزات اساسي' },
            ]),
          ),
        );
      return Promise.resolve(ok({ status: 'error' }));
    });
    renderMatrix();
    expect(await screen.findByText(/نقض تنوع‌بخشی \(Overweight\)/)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('فلزات اساسی');
    expect(screen.getByRole('alert')).toHaveTextContent('۱۸٪');
    expect(screen.getAllByText(/Overweight · ۳٪\+/).length).toBeGreaterThan(0);
  });

  it('خطای بک‌اند ⇒ پیام صادقانه و بدون هشدار ساختگی', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 400, json: () => Promise.resolve({}) } as unknown as Response),
    );
    renderMatrix();
    expect(await screen.findByText('خطای دریافت سبد')).toBeInTheDocument();
    expect(screen.getByText(/دریافت تصمیم‌های سبد ناموفق بود/)).toBeInTheDocument();
    expect(screen.queryByText(/نقض تنوع‌بخشی/)).toBeNull();
  });
});
