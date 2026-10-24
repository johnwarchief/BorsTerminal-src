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

function feed(rows: MarketRow[], rev: number, count = rows.length, gen?: number): MarketFeed {
  return {
    status: 'success',
    rev,
    gen,
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
    expect(marketFeedMirrorSize()).toEqual({ rows: 1, rev: 7, gen: null, revAt: expect.any(Number) });
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

  // پنلِ «وضعیت بازار»: «عوض‌شدنِ عدد» از `rev_at`ِ پاسخ خوانده می‌شود. سرور هیچ‌وقت
  // این خانۀ را نمی‌فرستد، پس اگر adopt خودِ بدنه را برگرداند، هر بارگذاریِ کامل
  // (اولین بار، خطایِ دلتا، سرورِ بی‌دلتا) «نامعلوم» می‌شد — نقصِ ثبت‌شدۀ
  // ۱۴۰۵-۰۷-۱۸ِ همین برنامه.
  it('بدنۀ کامل هم rev_at دارد؛ بدنۀ هم‌revِ دوباره آن را جلو نمی‌برد', async () => {
    let t = 2_000_000;
    const spy = vi.spyOn(Date, 'now').mockImplementation(() => t);
    try {
      httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1000 })], 7));
      const first = await call();
      expect(first.rev_at).toBe(2_000_000);
      // «دلتا نشد» (سرور می‌گوید کامل بخواه) و بدنه همان ویرایش است ⇒ داده
      // نچرخیده، پس سنّش هم نباید جلو برود.
      httpMock.mockResolvedValueOnce({ status: 'full', rev: 7 });
      httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1000 })], 7));
      t = 2_090_000;
      const again = await call();
      expect(again.rev_at).toBe(2_000_000);
      // ویرایشِ نو ⇒ سن از لحظۀِ خودِ تغییر
      httpMock.mockResolvedValueOnce({ status: 'full', rev: 8 });
      httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1010 })], 8));
      t = 2_120_000;
      const moved = await call();
      expect(moved.rev_at).toBe(2_120_000);
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

  // STATIC-GEN: تغییرِ client_type_value (درصد حقیقی/حقوقی) یا پنجره‌هایِ تاریخ
  // revisionِ زنده را تکان نمی‌دهد. کلاینت باید نسلِ ایستا را همراهِ delta
  // بفرستد؛ سرور با ناهم‌خوانی می‌فهمد ردیف‌هایِ دلتا کافی نیستند و بدنۀ کامل
  // می‌دهد — وگرنه تابلو تا ابد عددِ قدیمی را با برچسبِ «زنده» نگه می‌داشت.
  it('gen از بدنۀ کامل می‌آید و با delta می‌رود', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1000 })], 7, 1, 3));
    await call();
    expect(marketFeedMirrorSize().gen).toBe(3);
    httpMock.mockResolvedValueOnce({
      status: 'delta', rev: 8, gen: 3, count: 1,
      rows: [row('A', 'شپنا', { p_closing: 1010 })],
    });
    await call();
    expect(httpMock.mock.calls[1][0]).toBe('/api/market/delta?since=7&gen=3');
  });

  it('تغییرِ ایستا با revِ ثابت ⇒ ژنِ نو، بدنۀ کامل و revAtِ تازه', async () => {
    let t = 3_000_000;
    const spy = vi.spyOn(Date, 'now').mockImplementation(() => t);
    try {
      httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { retail_buy_pct: 33.3 })], 10, 1, 4));
      const first = await call();
      expect(first.gen).toBe(4);
      t = 3_030_000;
      // سرور می‌گوید نسلِ تو کهنه است؛ ردیف‌هایِ دلتا کافی نیستند.
      httpMock.mockResolvedValueOnce({ status: 'full', rev: 10, gen: 5, reason: 'board-changed' });
      httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { retail_buy_pct: 98.9 })], 10, 1, 5));
      const second = await call();
      expect(httpMock.mock.calls[1][0]).toBe('/api/market/delta?since=10&gen=4');
      expect(httpMock.mock.calls[2][0]).toBe('/api/market');
      expect(second.data[0].retail_buy_pct).toBe(98.9);
      expect(second.rev).toBe(10);
      expect(second.gen).toBe(5);
      expect(second.rev_at).toBe(3_030_000);
    } finally {
      spy.mockRestore();
    }
  });

  it('دلتایِ ناگهان‌باژن رد می‌شود؛ mergeِ ناقص جایِ بدنۀ کامل نمی‌نشیند', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1000 })], 5, 1, 2));
    await call();
    httpMock.mockResolvedValueOnce({
      status: 'delta', rev: 6, gen: 3, count: 1,
      rows: [row('A', 'شپنا', { p_closing: 1100 })],
    });
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 1200 })], 6, 1, 3));
    const f = await call();
    expect(httpMock.mock.calls[2][0]).toBe('/api/market');
    expect(f.data[0].p_closing).toBe(1200);
    expect(f.gen).toBe(3);
  });

  it('unchangedِ ناگهان‌باژن هم به بدنۀ کامل برمی‌گردد، نه بی‌تفاوتی', async () => {
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا')], 5, 1, 2));
    await call();
    httpMock.mockResolvedValueOnce({ status: 'unchanged', rev: 5, gen: 3, count: 1 });
    httpMock.mockResolvedValueOnce(feed([row('A', 'شپنا', { p_closing: 900 })], 5, 1, 3));
    const f = await call();
    expect(httpMock.mock.calls[2][0]).toBe('/api/market');
    expect(f.data[0].p_closing).toBe(900);
    expect(f.gen).toBe(3);
  });
});
