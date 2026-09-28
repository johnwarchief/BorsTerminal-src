// __tests__/http-conditional.spec.ts — اعتبارسنجیِ مجددِ پاسخ‌هایِ تکراری (#175)
// /api/market بدنهٔ ۷٫۳ مگابایتی دارد و در ساعتِ بازار هر ۵ ثانیه خواسته می‌شود،
// ولی داده هر ~۳۰ ثانیه یک‌بار عوض می‌شود. اگر هر poll بدنهٔ کامل بیاید، همان
// حجم هر بار decompress + JSON.parse + zod می‌شود (اندازه‌گیری: ۵۷۲ms از نخِ
// اصلی). با If-None-Match سرور ۳۰۴ِ صفر‌بایتی می‌دهد (۳ms) و http() همان
// آبجکتِ قبلی را برمی‌گرداند — پس TanStack Query هیچ رندرِ تازه‌ای نمی‌سازد.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { http, HttpError } from '@shared/api/http';

const Schema = z.object({ status: z.string(), count: z.number() });

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' }, ...init });

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('http() با ETag', () => {
  it('پاسخِ ۳۰۴ خطا نیست: همان آبجکتِ قبلی (با همان مرجع) برمی‌گردد', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: 'success', count: 5322 }, { headers: { ETag: '"abc"' } }))
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    vi.stubGlobal('fetch', fetchMock);

    const first = await http('/api/market', { schema: Schema });
    const second = await http('/api/market', { schema: Schema });

    expect(first).toEqual({ status: 'success', count: 5322 });
    // مرجعِ یکسان = هیچ رندرِ تازه‌ای در UI
    expect(second).toBe(first);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(new Headers(init.headers).get('if-none-match')).toBe('"abc"');
    // cache: 'no-store' لازم است، وگرنه کشِ خودِ مرورگر پاسخِ ۲۰۰ِ کامل را
    // از دیسک می‌دهد و ما هیچ‌وقت ۳۰۴ را نمی‌بینیم
    expect(init.cache).toBe('no-store');
  });

  it('بدونِ هدرِ ETag هیچ اعتبارسنجیِ تازه‌ای فرستاده نمی‌شود', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse({ status: 'success', count: 1 }));
    vi.stubGlobal('fetch', fetchMock);

    await http('/api/mstat/summary', { schema: Schema });
    await http('/api/mstat/summary', { schema: Schema });

    const init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(new Headers(init.headers).get('if-none-match')).toBeNull();
    expect(init.cache).toBeUndefined();
  });

  it('پس‌زمینهٔ ۳۰۴ فقط برای GETِ همان URL معتبر است؛ ۵۰۰ همچنان خطاست', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: 'success', count: 2 }, { headers: { ETag: '"x"' } }))
      .mockResolvedValueOnce(new Response('boom', { status: 500 }));
    vi.stubGlobal('fetch', fetchMock);
    await http('/api/other', { schema: Schema, retries: 0 });
    await expect(http('/api/other', { schema: Schema, retries: 0 })).rejects.toBeInstanceOf(HttpError);
  });

  // مسمومیتِ کشِ چنداسکیمایی: همان URL را دو مصرف‌کننده با دو اسکیمای متفاوت
  // می‌خوانند. zod کلیدهای ناشناخته را می‌کاهد، پس اگر ۳۰۴ به آبجکتِ چروکیدهٔ
  // دیگری اشاره کند، تابلو ردیف‌های دوفیلدی تحویل می‌گیرد (قیفِ درخت استراتژی:
  // «1193 نماد زنده ← 0 نشانه» در حالی که پرچم‌ها فرستاده شده بودند).
  it('اسکیمای دیگرِ همان URL آبجکتِ چروکیدهٔ او را نمی‌گیرد', async () => {
    const Rich = z.object({
      status: z.string(),
      data: z.array(z.object({ symbol: z.string(), f_clock: z.boolean().nullish() })),
    });
    const Narrow = z.object({
      status: z.string(),
      data: z.array(z.object({ symbol: z.string() })),
    });
    const body = { status: 'success', data: [{ symbol: 'شينا', f_clock: true }] };
    const fetchMock = vi
      .fn()
      // نخست `useMarketCloses`-مان می‌آید و فقط symbol نگه می‌دارد
      .mockResolvedValueOnce(jsonResponse(body, { headers: { ETag: '"v1"' } }))
      // سپس تابلو: باید *بدنهٔ کامل* بگیرد، نه ۳۰۴ِ آبجکتِ دوفیلدی
      .mockResolvedValueOnce(jsonResponse(body, { headers: { ETag: '"v1"' } }));
    vi.stubGlobal('fetch', fetchMock);

    const narrow = await http<{ data: { symbol: string }[] }>('/api/market', { schema: Narrow });
    const rich = await http<{ data: { symbol: string; f_clock?: boolean | null }[] }>('/api/market', { schema: Rich });

    expect(narrow.data[0]).toEqual({ symbol: 'شينا' });
    expect(rich.data[0]).toEqual({ symbol: 'شينا', f_clock: true });
    // هیچ If-None-Match‌ای از اسکیمای دیگر نشت نمی‌کند
    const h2 = new Headers((fetchMock.mock.calls[1][1] as RequestInit).headers);
    expect(h2.get('if-none-match')).toBeNull();
  });

  it('همان اسکیمای همان URL همچنان از ۳۰۴ و یک مرجع استفاده می‌کند', async () => {
    const Rich = z.object({ status: z.string(), data: z.array(z.object({ symbol: z.string() })) });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: 'success', data: [{ symbol: 'شينا' }] }, { headers: { ETag: '"v2"' } }))
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    vi.stubGlobal('fetch', fetchMock);

    const first = await http('/api/market', { schema: Rich });
    const second = await http('/api/market', { schema: Rich });

    expect(second).toBe(first);
    expect(new Headers((fetchMock.mock.calls[1][1] as RequestInit).headers).get('if-none-match')).toBe('"v2"');
  });
});
