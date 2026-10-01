// بارگذاریِ بستهٔ دادهٔ آفلاین: راهِ دوم وقتی فایلِ همراهِ APK نیاید.
//
// انگیزه: اسکرین‌شاتِ مالک رویِ گوشی — نوارِ قرمزِ «بارگذاری بستهٔ دادهٔ
// آفلاین شکست خورد» و همهٔ کارت‌ها «بدون داده». علت: اگر fetchِ فایلِ
// درونِ APK شکست می‌خورد، هیچ راهِ دومی نبود، در حالی که همان بسته روی
// ریلیزِ mobile-latest هست و کدِ دانلودش هم برایِ بروزرسانیِ روزانه از
// قبل نوشته شده بود — فقط به مسیرِ بارگذاریِ اول وصل نبود.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('sql.js/dist/sql-wasm.wasm?url', () => ({ default: 'wasm:stub' }));
const nativeGetBytes = vi.fn();
vi.mock('@shared/api/local/nativeHttp', () => ({
  nativeGetBytes: (...a: unknown[]) => nativeGetBytes(...a),
  nativeGetJson: vi.fn(async () => null),
}));

/** gz معتبرِ ساختگی: دو بایتِ جادویی + پرکننده تا از آستانهٔ ۱MB رد شود. */
function fakeGz(bytes = 1_200_000): ArrayBuffer {
  const u = new Uint8Array(bytes);
  u[0] = 0x1f; u[1] = 0x8b;
  return u.buffer;
}

describe('پشتیبانِ بستهٔ دادهٔ آفلاین', () => {
  beforeEach(() => {
    nativeGetBytes.mockReset();
    vi.stubGlobal('caches', undefined);
    vi.stubGlobal('localStorage', {
      getItem: () => String(Date.now()), setItem: () => {},
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('وقتی فایلِ درونِ APK ۴۰۴ می‌دهد، از ریلیز می‌گیرد', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })));
    nativeGetBytes.mockResolvedValue(fakeGz());
    const { __fetchSnapshotForTest } = await import('@shared/api/local/localData');
    const buf = await __fetchSnapshotForTest();
    expect(buf.byteLength).toBeGreaterThan(1_000_000);
    expect(nativeGetBytes).toHaveBeenCalledTimes(1);
  });

  it('وقتی fetch استثنا پرتاب می‌کند هم سراغِ ریلیز می‌رود', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('WebView نداد'); }));
    nativeGetBytes.mockResolvedValue(fakeGz());
    const { __fetchSnapshotForTest } = await import('@shared/api/local/localData');
    await expect(__fetchSnapshotForTest()).resolves.toBeTruthy();
  });

  it('پاسخِ کوچک یا بی‌امضای gz را نمی‌پذیرد — صفحهٔ خطایِ HTML دیتابیس نشود', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })));
    nativeGetBytes.mockResolvedValue(new TextEncoder().encode('<html>503</html>').buffer);
    const { __fetchSnapshotForTest } = await import('@shared/api/local/localData');
    await expect(__fetchSnapshotForTest()).rejects.toThrow(/بستهٔ دادهٔ آفلاین/);
  });

  it('پیامِ خطا به کاربر می‌گوید چه کند، نه فقط کدِ خطا', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })));
    nativeGetBytes.mockResolvedValue(null);
    const { __fetchSnapshotForTest } = await import('@shared/api/local/localData');
    await expect(__fetchSnapshotForTest()).rejects.toThrow(/اینترنتِ متصل/);
  });

  it('مسیرِ عادی دست‌نخورده است: فایلِ APK که بیاید، شبکه اصلاً صدا نمی‌شود', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(fakeGz(), { status: 200 })));
    const { __fetchSnapshotForTest } = await import('@shared/api/local/localData');
    await __fetchSnapshotForTest();
    expect(nativeGetBytes).not.toHaveBeenCalled();
  });
});
