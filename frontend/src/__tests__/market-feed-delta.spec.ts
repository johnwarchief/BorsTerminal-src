// تستِ mergeِ دلتا در shared/api/marketFeed.ts — بی‌React، بی‌شبکه
//
// چرا: این لایه «سرعتِ تابلو» را می‌سازد و اگر یک ردیف را جا بیندازد یا
// ردیفِ کهنه را نگه دارد، کاربر عددِ غلط می‌بیند. پس ادعاهایِ دقیق:
//   • جایِ ردیفِ تغییریافته *درِ همان ترتیب* می‌نشیند (نه append، نه جا‌به‌جا);
//   • «unchanged» همان ارجاعِ قبلی را برمی‌گرداند (یعنی بی‌رندر);
//   • هر حالتِ غیرقابل‌اثبات (countِ ناهمخوان، ۴۰۴، پاسخِ ناشناخته) به بدنۀ
//     کامل برمی‌گردد، نه به دلتایِ نصفه.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const httpMock = vi.fn();
vi.mock('@shared/api/http', () => ({
  http: (...a: unknown[]) => httpMock(...a),
  HttpError: class HttpError extends Error {
    constructor(public status: number, public url: string, message?: string) {
      super(message ?? `خطای ${status}`);
    }
  },
}));

import { HttpError } from '@shared/api/http';
import {
  marketFeedOptions,
  resetMarketFeedMirror,
  marketFeedMirrorSize,
} from '@shared/api/marketFeed';
import type { MarketFeed, MarketRow } from '@shared/types/marketRow';

function row(code: string, symbol: string, patch: Partial<MarketRow> = {}): MarketRow {
  return { ins_code: code, symbol, ...patch } as MarketRow;
}

function feed(rows: MarketRow[], rev: number, count = rows.length): MarketFeed {
  return {
    status: 'success',
    rev,
    count,
    live_count: rows.length,
    fossil_count: 0,
    meta: { d_even: 20260930, h_even: 125959, last_sync: '2026-09-30 12:59:59' },
    data: rows,
  };
}

const call = () =>
  (marketFeedOptions(5_000, false).queryFn as (c: { signal?: AbortSignal }) => Promise<MarketFeed>)({});

describe('marketFeed — حالتِ داغ در کلاینت', () => {
  beforeEach(() => {
    httpMock.mockReset();
    resetMarketFeedMirror();
  });

  it('اولین کوئری بدنۀ کامل است و rev از همان بدنه جا می‌افتد', async () => {
    httpMock.mockResolvedValue(feed([row('A', 'شپنا', { p_closing: 1000 })], 7));
    const f = await call();
    expect(httpMock.mock.calls[0][0]).toBe('/api/market');
    expect(f.data[0].p_closing).toBe(1000);
    expect(marketFeedMirrorSize()).toEqual({ rows: 1, rev: 7, revAt: expect.any(Number) });
  });

  it('دومین کوئری دلتاست، همان‌جا از همان rev', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1000 }),
                                        row('B', 'فولاد', { p_closing: 2000 })], 7));
    await call();
    httpMock.mockResolvedValueOnce({ status: 'delta', rev: 9, count: 2, rows: [row('B', 'فولاد', { p_closing: 2100 })] });
    const f2 = await call();
    expect(httpMock.mock.calls[1][0]).toBe('/api/market/delta?since=7');
    expect(f2.data.map((r) => r.p_closing)).toEqual([1000, 2100]);
    expect(f2.data[0].symbol).toBe('شپنا');
  });

  it('unchanged ⇒ دقیقاً همان آرایه (مرجعِ یکسان، بی‌رندرِ تازه)', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا')], 3));
    const f1 = await call();
    httpMock.mockResolvedValueOnce({ status: 'unchanged', rev: 3, count: 1, rows: undefined });
    const f2 = await call();
    expect(f2.data).toBe(f1.data);
    // Phase پرفورمنس: ادعای «بی‌رندر» یعنی خودِ wrapper هم باید همان مرجع باشد؛
    // تا پیش از این هر poll آبجکتِ تازه می‌ساخت و fan-outِ ۸-observerه می‌زد.
    httpMock.mockResolvedValueOnce({ status: 'unchanged', rev: 3, count: 1, rows: undefined });
    const f3 = await call();
    expect(f3).toBe(f2);
    expect(httpMock).toHaveBeenCalledTimes(3);
  });

  // REV-AT: «زمانِ عوض‌شدنِ داده» باید از «زمانِ رسیدنِ پاسخ» جدا باشد — باگِ
  // اثبات‌شدۀ زنده: نودوچهار دقیقه بی‌revision و نشانگر «لحظاتی پیش».
  it('دلتایِ واقعی revAt را جلو می‌برد و «unchanged» آن را تکان نمی‌دهد', async () => {
    let t = 1_000_000;
    const spy = vi.spyOn(Date, 'now').mockImplementation(() => t);
    try {
      httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1000 })], 4));
      await call();
      expect(marketFeedMirrorSize().revAt).toBe(1_000_000);
      httpMock.mockResolvedValueOnce({ status: 'unchanged', rev: 4, count: 1, rows: undefined });
      t = 1_060_000;
      await call();
      expect(marketFeedMirrorSize().revAt).toBe(1_000_000);   // هیچ عددی عوض نشده
      expect(marketFeedMirrorSize().rev).toBe(4);
      httpMock.mockResolvedValueOnce({ status: 'delta', rev: 5, count: 1,
                                       rows: [row('A', 'شپنا', { p_closing: 1010 })] });
      t = 1_110_000;
      await call();
      expect(marketFeedMirrorSize().revAt).toBe(1_110_000);   // داده عوض شد
      expect(marketFeedMirrorSize().rev).toBe(5);
    } finally {
      spy.mockRestore();
    }
  });

  it('countِ ناهمخوان ⇒ بدنۀ کامل، نه mergeِ ناقص (ردیفِ کم/زیاد از دلتا پنهان می‌ماند)', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا'), row('B', 'فولاد')], 4));
    await call();
    // سرور می‌گوید تابلو ۳ ردیف است ولی دلتا فقط یکی از دو ردیفِ *معلومِ ما* را
    // فرستاده ⇒ ردیفِ سوم از چشمِ ما دور مانده؛ merge رها و بدنۀ کامل می‌آید.
    httpMock.mockResolvedValueOnce({ status: 'delta', rev: 5, count: 3, rows: [row('B', 'فولاد', { p_closing: 2100 })] });
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا'), row('B', 'فولاد'), row('C', 'مبارکه')], 6));
    const f = await call();
    expect(httpMock.mock.calls[2][0]).toBe('/api/market');
    expect(f.data.map((r) => r.ins_code)).toEqual(['A', 'B', 'C']);
  });

  it('سرورِ بی‌دلتا (۴۰۴) ⇒ تا پایانِ همین پروسه بدنۀ کامل، بی‌خطا', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا')], 1));
    await call();
    httpMock.mockImplementationOnce(async () => {
      throw new HttpError(404, '/api/market/delta');
    });
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1100 })], 2));
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1200 })], 3));
    const f1 = await call();
    const f2 = await call();
    expect(f1.data[0].p_closing).toBe(1100);
    expect(f2.data[0].p_closing).toBe(1200);
    // دیگر هیچ درخواستِ دلتا نمی‌رود:
    expect(httpMock.mock.calls.map((c) => c[0]).filter((u) => String(u).includes('delta')).length).toBe(1);
  });

  it('پاسخِ ناشناخته هم به بدنۀ کامل برمی‌گردد (بی‌ساختنِ عدد از نبودِ داده)', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا')], 1));
    await call();
    httpMock.mockResolvedValueOnce({ status: 'journal-gap' });
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 900 })], 2));
    const f = await call();
    expect(f.data[0].p_closing).toBe(900);
  });
});
