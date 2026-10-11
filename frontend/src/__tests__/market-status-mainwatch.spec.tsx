// __tests__/market-status-mainwatch.spec.tsx — ستون «نشان» درِ «نمادهای زیرِ نظر»
//
// رأیِ مالک (۱۴۰۵-۰۷-۲۲): این جدول تنها پرچمِ «الگوی ساعت» را می‌دید؛ حجمِ مشکوک،
// ورودِ پولِ هوشمند و کد به کد هم باید دیده شوند. داوری درِ `tape_flags.py` است و
// `api/market_status.py` آن را از فیدِ تابلو منتقل می‌کند — پس اینجا سه حالت
// سنجیده می‌شود: پرچم روشن، پرچم خاموش، و «منبع نرسید». هیچ‌کدام «صفر» نیست.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MainWatchTable } from '@features/market/components/MarketStatusTables';

let restore = () => {};

function feed(payload: unknown) {
  const real = globalThis.fetch;
  globalThis.fetch = async () =>
    ({ ok: true, status: 200, json: () => Promise.resolve(payload) }) as unknown as Response;
  restore = () => { globalThis.fetch = real; };
}

const ASOF = { d_even: 20261010, h_even: 102343 };
const row = (symbol: string, tape_flags: Record<string, boolean> | null,
             ohlc: { first?: number; high?: number; low?: number } = { first: 980, high: 1010, low: 970 }) => ({
  symbol, ins_code: `c-${symbol}`, name: symbol, industry: 'فلزات', cls: 'سهامی', kind: 'stock',
  vol_b_shares: 100, trades: 60, val_b_toman: 42, p_last: 1000, p_closing: 990,
  p_first: ohlc.first ?? null, p_max: ohlc.high ?? null, p_min: ohlc.low ?? null,
  pct_last: 1, pct_close: 1, clock_pct: 2.5, pc_buy: 5, pc_sell: 4, power: 1.6,
  flow_b_toman: 3, tape_flags,
});

const payload = (rows: unknown[], source: string | null | undefined = 'api/market') => ({
  status: 'ok', asof: ASOF, group: 'eq_all', industry: '', sort: 'clock', sort_col: 'clock_pct',
  desc: true, total: rows.length, clock_hits: rows.length,
  clock_rule: { min_pct: 2, min_trades: 30, min_price: 200 },
  rows, source: 'local:market.db',
  // `null` = کلید هرگز درِ پاسخ نمی‌نشیند (پاسخِ بک‌اندِ بی‌منبع)، و `undefined`
  // پیش‌فرضِ خودِ helper است — با هم یکی نباشند، وگرنه این بند کور تست می‌شود.
  ...(source === null ? {} : { tape_flags_source: source }),
});

function renderTable() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MainWatchTable /></QueryClientProvider>);
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => restore());

describe('ستون نشان در نمادهای زیرِ نظر', () => {
  it('پرچم‌هایِ روشن با نامِ خودِ تابلو دیده می‌شوند؛ خاموش‌ها نمی‌آیند', async () => {
    feed(payload([row('فولاد', {
      f_clock: true, f_susp: true, f_jet: false, f_roobi: false,
      f_noqteh: false, f_smart: true, f_legal: false,
    })]));
    renderTable();
    await waitFor(() => expect(screen.getByTestId('mainwatch-row-فولاد')).toBeInTheDocument());
    expect(screen.getByTestId('mainwatch-flag-f_susp-فولاد')).toHaveTextContent('مشکوک');
    expect(screen.getByTestId('mainwatch-flag-f_smart-فولاد')).toHaveTextContent('پول هوشمند');
    expect(screen.queryByTestId('mainwatch-flag-f_legal-فولاد')).not.toBeInTheDocument();
    // نامِ کاملِ هر پرچم درِ title است — همان واژگانِ جزوه، نه مخففِ بی‌معنا
    expect(screen.getByTestId('mainwatch-flag-f_susp-فولاد')).toHaveAttribute('title', 'حجم مشکوک');
    expect(screen.getByTestId('mainwatch-flag-f_smart-فولاد')).toHaveAttribute('title', 'ورود پول هوشمند');
  });

  it('ردیفی که پرچمی ندارد «—» است، نه صفر و نه بج', async () => {
    feed(payload([row('شپنا', {
      f_clock: false, f_susp: false, f_jet: false, f_roobi: false,
      f_noqteh: false, f_smart: false, f_legal: false,
    })]));
    renderTable();
    await waitFor(() => expect(screen.getByTestId('mainwatch-row-شپنا')).toBeInTheDocument());
    expect(screen.queryAllByTestId(/^mainwatch-flag-/)).toHaveLength(0);
  });

  it('بی‌منبع، ستون بی‌صدا خالی نمی‌ماند: پاورقی «پرچم از فیدِ تابلو نرسید» می‌گوید', async () => {
    feed(payload([row('همراه', null)], null));
    renderTable();
    await waitFor(() => expect(screen.getByTestId('mainwatch-row-همراه')).toBeInTheDocument());
    expect(screen.queryAllByTestId(/^mainwatch-flag-/)).toHaveLength(0);
    expect(screen.getByTestId('status-mainwatch').textContent).toContain('پرچم از فیدِ تابلو نرسید');
  });

  it('کندلِ همین نشست رسم می‌شود، و بی‌OHLC «—» است نه کندلِ ساختگی', async () => {
    feed(payload([row('فولاد', null, { first: 980, high: 1010, low: 960 }),
                  row('شپنا', null, { first: undefined, high: undefined, low: undefined })]));
    renderTable();
    await waitFor(() => expect(screen.getByTestId('mainwatch-row-فولاد')).toBeInTheDocument());
    const up = screen.getByTestId('mainwatch-candle-فولاد');
    expect(up.getAttribute('data-state')).toBe('up');   // آخرین ۱۰۰۰ بالایِ اولین ۹۸۰
    expect(screen.getByTestId('mainwatch-candle-شپنا').getAttribute('data-state')).toBe('incomplete');
    expect(screen.getByTestId('mainwatch-candle-شپنا').textContent).toBe('—');
  });

  it('نمادی که درِ فیدِ تابلو نبود صریح «بی‌پرچم» است — با «پرچمی ندارد» یکی نیست', async () => {
    feed(payload([row('ولرز', null)]));
    renderTable();
    await waitFor(() => expect(screen.getByTestId('mainwatch-row-ولرز')).toBeInTheDocument());
    expect(screen.getByText('بی‌پرچم')).toBeInTheDocument();
  });
});
