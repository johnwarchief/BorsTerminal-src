// تست دیده‌بان‌ها: جدول تمام‌عرض است و سه پنل کناری به دراور تب‌دار رفته‌اند
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

/** تب صنایع داغ را باز می‌کند و بدنهٔ پاسخ /api/mstat/industries را می‌چسباند */
async function openHotIndustryPanel(body: unknown): Promise<string[]> {
  fetchMock.mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as unknown as Response),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const picked: string[] = [];
  render(
    <QueryClientProvider client={qc}>
      <WatchDrawer rows={[row()]} onSelect={() => {}} onPickSector={(s) => picked.push(s)} />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole('tab', { name: 'صنایع داغ' }));
  await waitFor(() => expect(screen.getByTestId('sector-inflow')).toBeInTheDocument());
  await waitFor(() => expect(screen.queryAllByRole('listitem').length).toBeGreaterThan(0));
  return picked;
}

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

describe('تب صنایع داغ — RTL و منطق رتبه‌بندی', () => {
  it('RTL: فقط عدد در .num ایزولهٔ LTR است؛ واحدِ «ب.ت» و ٪ بیرون از آن می‌مانند', async () => {
    await openHotIndustryPanel({
      status: 'ok',
      leader: 'فولاد',
      rows: [{ industry: 'فولاد', symbols: 10, positive: 5, negative: 2, avg_pct: 2.34, value_b_toman: 100, flow_b_toman: 520.4 }],
    });
    // جریان: ظرفِ بیرونی نباید کلاس num (direction:ltr) بگیرد، وگرنه «ب.ت» پشت عدد می‌پرد
    const flow = screen.getByTestId('industry-flow-فولاد');
    expect(flow.className).not.toContain('num');
    const flowNum = flow.querySelector('.num');
    expect(flowNum?.textContent).toBe('۵۲۰'); // fmtInt(round(520.4)) — جدا و بدون واحدِ فارسی
    expect(flowNum?.textContent).not.toContain('ب.ت');
    expect(flow.textContent).toContain('ب.ت'); // واحد در جریانِ RTL باقی می‌ماند
    // درصد: عدد ایزوله + علامتِ ٪ در span جدا
    const pct = screen.getByTestId('industry-pct-فولاد');
    expect(pct.className).not.toContain('num');
    const pctNum = pct.querySelector('.num');
    expect(pctNum?.textContent).toBe('۲.۳'); // fa1(2.34)
    expect(pctNum?.textContent).not.toContain('٪');
    expect(pct.textContent).toContain('٪');
  });

  it('بی‌داده هیچ‌وقت صفرِ سبز/قرمز نیست: نبودِ هر سنجه جداگانه خالی می‌ماند', async () => {
    await openHotIndustryPanel({
      status: 'ok',
      rows: [
        { industry: 'گاز', avg_pct: null, flow_b_toman: 40, value_b_toman: 1 }, // درصد ندارد
        { industry: 'زغال', avg_pct: 6, flow_b_toman: null, value_b_toman: 0 }, // جریان ندارد
      ],
    });
    // حالت «ورود پول»: گاز رتبه می‌گیرد ولی درصدش خالی است — نه صفرِ درصد
    const gasPct = screen.getByTestId('industry-pct-گاز');
    expect(gasPct.textContent).toBe('—');
    expect(gasPct.textContent).not.toMatch(/[۰٪]/);
    expect(gasPct.querySelector('.num')).toBeNull();
    // حالت «بیشترین درصد»: زغال رتبه می‌گیرد ولی جریان پولش نبود داده است — نه ▲ ۰ سبز
    fireEvent.click(screen.getByRole('button', { name: 'بیشترین درصد' }));
    const zFlow = screen.getByTestId('industry-flow-زغال');
    expect(zFlow.textContent).toBe('بدون داده');
    expect(zFlow.textContent).not.toMatch(/[▲▼۰]/);
    expect(zFlow.querySelector('.num')).toBeNull();
  });

  it('رتبه‌بندی: پیش‌فرض «ورود پول» نزولی؛ صنعتِ بدونِ سنجه هرگز رتبه نمی‌گیرد', async () => {
    await openHotIndustryPanel({
      status: 'ok',
      leader: 'فولاد',
      rows: [
        { industry: 'سیمان', avg_pct: 5, flow_b_toman: 10, value_b_toman: 1 },
        { industry: 'فولاد', avg_pct: 9, flow_b_toman: 20, value_b_toman: 1 },
        { industry: 'پتروشیمی', avg_pct: 7, flow_b_toman: 30, value_b_toman: 1 },
        { industry: 'زغال', avg_pct: null, flow_b_toman: null, value_b_toman: 0 },
      ],
    });
    const items = () => screen.getAllByRole('listitem').map((li) => li.textContent ?? '');
    expect(items()).toHaveLength(3); // زغال (flow=null) حذف
    expect(items()[0]).toContain('پتروشیمی'); // flow 30
    expect(items()[1]).toContain('فولاد'); // flow 20
    expect(items()[2]).toContain('سیمان'); // flow 10
    expect(items().join('|')).not.toContain('زغال');
    // سَرجُا روی «بیشترین درصد»: فولاد(9) > پتروشیمی(7) > سیمان(5)؛ زغال همچنان حذف
    fireEvent.click(screen.getByRole('button', { name: 'بیشترین درصد' }));
    expect(items()[0]).toContain('فولاد');
    expect(items()[1]).toContain('پتروشیمی');
    expect(items()[2]).toContain('سیمان');
    expect(items().join('|')).not.toContain('زغال');
  });

  it('کلیک روی صنعت، جدول تابلو را روی همان صنعت فیلتر می‌کند (onPickSector)', async () => {
    const picked = await openHotIndustryPanel({
      status: 'ok',
      rows: [{ industry: 'فولاد', avg_pct: 3, flow_b_toman: 40, value_b_toman: 5 }],
    });
    fireEvent.click(screen.getByTestId('industry-pick-فولاد'));
    expect(picked).toContain('فولاد');
  });
});
