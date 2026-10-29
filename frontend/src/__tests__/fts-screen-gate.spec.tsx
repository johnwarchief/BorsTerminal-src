// __tests__/fts-screen-gate.spec.tsx — بند ۷.۱: چیپِ قیف درِ جدول
// جدول هیچ گامی را حساب نمی‌کند؛ چیپ شمارشِ گام‌ها را از خودِ `/api/screener`
// می‌خواند. از Task 9 به بعد بجِ «کاندیدِ قیف» رویِ ردیف رندر نمی‌شود (بجِ
// تکنیکال است و جای آن تبِ تکنیکال است) — این فایل حالا هم چیپ را می‌سنجد و
// هم نبودِ بج را. دو حالتِ چیپ جدا می‌ماند: قیفِ applied و قیفِ نرسیده که
// علتش را می‌گوید.
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import type { FtsScreenRow, FtsFunnelGate } from '@features/fundamental/api/useFtsScreen';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  /** jsdom اندازه ندارد؛ پنجرهٔ ۱۲ ردیفی مثل پنجرهٔ مرورگر (۷۰vh/۴۶px) شبیه‌سازی می‌شود */
  const WINDOW = 12;
  let lastVirtualOptions: { count: number; overscan?: number; estimateSize?: (i: number) => number } | null = null;
  return {
    ...mod,
    useVirtualizer: (opts: { count: number; overscan?: number; estimateSize?: (i: number) => number }) => {
      lastVirtualOptions = opts;
      const { count } = opts;
      return {
        getTotalSize: () => count * 46,
        getVirtualItems: () =>
          Array.from({ length: Math.min(count, WINDOW) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
      };
    },
    __virtualOptions: () => lastVirtualOptions,
  };
});

vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('شبکه در تست خاموش است'))));

const row = (over: Partial<FtsScreenRow>): FtsScreenRow =>
  ({ symbol: 'شپنا', name: 'پالایش', score: 4, primary_score: 4, ...over }) as FtsScreenRow;

const gate = (over: Record<string, unknown> = {}): FtsFunnelGate =>
  ({
    state: 'applied', preset: 'trend', chain: ['f_roobi', 'f_noqteh'],
    stages: { tape: { input: 2781, matched: 1 }, technical: { input: 1, matched: 0 },
              fundamental: { input: 0, matched: 0 } },
    ...over,
  }) as unknown as FtsFunnelGate;

const table = (rows: FtsScreenRow[], funnelGate: FtsFunnelGate | null) =>
  render(
    <MemoryRouter>
      <FtsScreenTable rows={rows} onSelect={() => {}} thresholds={null} funnelGate={funnelGate} />
    </MemoryRouter>,
  );

const chip = () => screen.getByTestId('fts-funnel-gate').textContent ?? '';

describe('چیپ و بجِ قیف درِ جدول غربالگری', () => {
  it('چیپ شمارشِ گام‌ها را از بک‌اند می‌نویسد (نه از شمارشِ ردیف‌هایِ خودِ جدول)', () => {
    table([row({})], gate());
    const t = chip();
    expect(t).toContain('۲۷۸۱');   // inputِ تابلوخوانی
    expect(t).toContain('قیف trend');
    // ۲۷۱ ردیف درِ جدول نیست؛ عدد را جدول نمی‌شمارد
    expect(document.querySelectorAll('[data-testid="fts-screen-row"]').length).toBeLessThan(5);
  });

  it('ردیفِ کاندیدِ قیف بج نمی‌گیرد (بجِ تکنیکال در این تب رندر نمی‌شود)', () => {
    // ردیفِ سوم همهٔ محرک‌هایِ چهار بجِ تکنیکال را دارد — از جمله
    // `tech_matrix_decision: 'REJECT'` که تنها محرکِ «وتوی روند» بود. اگر یکی
    // از آن بج‌ها برگردد، همین ردیف باید در تست قرمز شود (نه ردیفی که محرک ندارد).
    table([row({ symbol: 'شپنا', funnel_candidate: true, tech_jet: true, tech_hourglass_active: true }),
           row({ symbol: 'فولاد', funnel_candidate: false, technical_status: 'reject' }),
           row({
             symbol: 'خساپا',
             funnel_candidate: true,
             tech_jet: true,
             tech_hourglass_active: true,
             tech_matrix_decision: 'REJECT',
             tech_matrix_desc: 'شکستِ ساختارِ روند',
           })], gate());
    expect(screen.queryByTestId('row-funnel-candidate')).toBeNull();
    expect(screen.queryByText('کاندیدِ قیف')).toBeNull();
    expect(screen.queryByText('جت')).toBeNull();
    expect(screen.queryByText('ساعت شنی')).toBeNull();
    expect(screen.queryByText('وتوی روند')).toBeNull();
    // خودِ ردیفِ «REJECT» رندر می‌شود، ولی هیچ‌یک از چهار بجِ تکنیکال رویش نیست
    const rejectRow = screen
      .getAllByTestId('fts-screen-row')
      .find((el) => el.textContent?.includes('خساپا'));
    expect(rejectRow).toBeDefined();
    expect(within(rejectRow as HTMLElement).queryByTestId('row-funnel-candidate')).toBeNull();
    expect(within(rejectRow as HTMLElement).queryByText('کاندیدِ قیف')).toBeNull();
    expect(within(rejectRow as HTMLElement).queryByText('جت')).toBeNull();
    expect(within(rejectRow as HTMLElement).queryByText('ساعت شنی')).toBeNull();
    expect(within(rejectRow as HTMLElement).queryByText('وتوی روند')).toBeNull();
    // چیپِ قیف (خلاصهٔ گیتِ بک‌اند) همچنان هست
    expect(chip()).toContain('قیف trend');
  });

  it('قیفِ نرسیده ⇒ چیپ علت را قرمز می‌گوید', () => {
    table([row({ symbol: 'شپنا', funnel_candidate: false, gate_state: 'unavailable' })],
          gate({ state: 'unavailable', message: 'تابلو ساخته نشده', stages: undefined }));
    expect(chip()).toContain('قیف نرسید');
    expect(screen.getByTestId('fts-funnel-gate').getAttribute('data-state')).toBe('unavailable');
  });

  it('بی‌`funnel_gate` درِ پاسخ (سرورِ کهنه) ⇒ چیپ نیست، جدول نمی‌شکند', () => {
    table([row({})], null);
    expect(screen.queryByTestId('fts-funnel-gate')).toBeNull();
    expect(screen.getAllByTestId('fts-screen-row').length).toBeGreaterThan(0);
  });
});
