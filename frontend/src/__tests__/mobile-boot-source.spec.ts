// گاردِ منبعِ بستۀ داده درِ موبایل — سه قاعده‌ای که زمانِ «دریافت داده‌های
// آفلاین» را تعیین می‌کنند:
// ۱) بستۀ همراهِ APK خوانده می‌شود و درِ Cache API ذخیره نمی‌شود (یک‌برگِ
//    اضافه رویِ حافظهٔ گوشی که دورِ بعد کهنه می‌شود).
// ۲) کش فقط وقتی می‌ارزد که مهرش از APK تازه‌تر باشد — وگرنه دادۀ کهنه بر
//    APKِ تازه می‌برد و گوشی تا ریلیزِ بعدی دادهٔ قدیمی نشان می‌دهد.
// ۳) اگر APK نبود، ریلیز با درصدِ واقعیِ بایت می‌آید؛ اگر خودِ ریلیز هم به
//    دیوار خورد، درگاهِ بومی — و آن‌جا درصد ساخته نمی‌شود.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BootProgress } from '@shared/api/local/localData';

const h = vi.hoisted(() => ({
  nativeGetBytes: vi.fn(),
  match: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  fetchMock: vi.fn(),
}));

vi.mock('@shared/api/local/nativeHttp', () => ({
  nativeGetBytes: h.nativeGetBytes,
  nativeGetJson: vi.fn(async () => null),
}));

const STAMP_KEY = 'bors_snapshot_cached_stamp';
const GZ_URL = '/mobile_snapshot.db.gz';
const RELEASE_URL =
  'https://github.com/johnwarchief/BorsTerminal-src/releases/download/mobile-latest/mobile_snapshot.db.gz';

const gzBytes = (n = 1_048_576): ArrayBuffer => {
  const b = new Uint8Array(n);
  b[0] = 0x1f;
  b[1] = 0x8b;
  return b.buffer;
}

/** پاسخِ streaming با content-lengthِ اعلامی — همان چیزی که WebView می‌دهد. */
function streamed(bytes: ArrayBuffer, declareLength = true): Response {
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(new Uint8Array(bytes));
      c.close();
    },
  });
  const headers = declareLength ? { 'content-length': String(bytes.byteLength) } : undefined;
  return new Response(body, { status: 200, headers });
}

async function load(stamp: string | undefined): Promise<typeof import('@shared/api/local/localData')> {
  vi.resetModules();
  vi.stubEnv('VITE_SNAPSHOT_STAMP', stamp ?? '');
  return import('@shared/api/local/localData') as Promise<typeof import('@shared/api/local/localData')>;
}

function routeFetch(routes: Record<string, () => Response>) {
  h.fetchMock.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const hit = routes[url];
    if (!hit) return Promise.reject(new Error(`fetch بی‌مسیر: ${url}`));
    const res = hit();
    return Promise.resolve(res);
  });
}

type BootMod = typeof import('@shared/api/local/localData');

async function withProgress(mod: BootMod, run: () => Promise<unknown>): Promise<BootProgress[]> {
  const events: BootProgress[] = [];
  const off = mod.subscribeBootProgress((p) => events.push(p));
  try {
    await run();
  } finally {
    off();
  }
  return events;
}

describe('منبعِ بستۀ دادهٔ آفلاین', () => {
  let mod: BootMod;

  beforeEach(() => {
    localStorage.clear();
    h.match.mockReset();
    h.put.mockReset();
    h.del.mockReset();
    h.nativeGetBytes.mockReset();
    h.fetchMock.mockReset();
    vi.stubGlobal('fetch', h.fetchMock);
    vi.stubGlobal('caches', { open: async () => ({
      match: h.match, put: h.put, delete: h.del,
    }) });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('بستۀ APK را می‌خواند و آن را درِ کش ذخیره نمی‌کند', async () => {
    h.match.mockResolvedValue(undefined);
    routeFetch({ [GZ_URL]: () => streamed(gzBytes(2_097_152)) });
    mod = await load('2026-10-08T16:16:15');

    const events = await withProgress(mod, () => mod.__fetchSnapshotForTest());
    expect(mod.bootTiming.source).toBe('bundle');
    expect(h.put).not.toHaveBeenCalled();
    expect(h.del).not.toHaveBeenCalled(); // کش خالی بود — چیزی برای پاک کردن نبود
    expect(events.at(-1)?.percent).toBe(100);
    expect(events.every((e) => e.loadedBytes <= e.totalBytes)).toBe(true);
  });

  it('کشِ کهنه را به APK می‌بازد و همان‌جا پاکش می‌کند', async () => {
    localStorage.setItem(STAMP_KEY, '2026-10-01T09:00:00');
    h.match.mockResolvedValue(new Response(gzBytes(2_097_152)));
    routeFetch({ [GZ_URL]: () => streamed(gzBytes(1_048_576)) });
    mod = await load('2026-10-08T16:16:15');

    const buf = await mod.__fetchSnapshotForTest();
    expect(buf.byteLength).toBe(1_048_576); // بستۀ خودِ برنامه، نه کپیِ کهنه
    expect(mod.bootTiming.source).toBe('bundle');
    expect(h.del).toHaveBeenCalledWith(GZ_URL);
    expect(localStorage.getItem(STAMP_KEY)).toBeNull();
  });

  it('کشِ تازه‌تر از APK را بر بستۀ همراه ترجیح می‌دهد', async () => {
    localStorage.setItem(STAMP_KEY, '2026-10-09T07:30:00');
    h.match.mockResolvedValue(new Response(gzBytes(1_048_576)));
    routeFetch({});
    mod = await load('2026-10-08T16:16:15');

    const buf = await mod.__fetchSnapshotForTest();
    expect(buf.byteLength).toBe(1_048_576);
    expect(mod.bootTiming.source).toBe('cache');
    expect(h.fetchMock).not.toHaveBeenCalled();
  });

  it('اگر بستۀ APK باز نشد، ریلیز را با درصدِ واقعیِ بایت می‌گیرد', async () => {
    h.match.mockResolvedValue(undefined);
    routeFetch({
      [GZ_URL]: () => new Response(null, { status: 404 }),
      [RELEASE_URL]: () => streamed(gzBytes(4_194_304)),
    });
    mod = await load('2026-10-08T16:16:15');

    const events = await withProgress(mod, () => mod.__fetchSnapshotForTest());
    expect(mod.bootTiming.source).toBe('release');
    expect(h.put).toHaveBeenCalled();
    const download = events.filter((e) => e.phase === 'download');
    expect(download.some((e) => e.totalBytes === 4_194_304 && e.percent === 100)).toBe(true);
  });

  it('اگر ریلیز هم از fetch رد شد، درگاهِ بومی می‌آید و درصد نمی‌سازد', async () => {
    localStorage.setItem(STAMP_KEY, '2026-10-08T16:16:15'); // APK == کش ⇒ مهر تازۀ APK را می‌برد
    h.match.mockResolvedValue(undefined);
    routeFetch({ [GZ_URL]: () => new Response(null, { status: 500 }) });
    h.fetchMock.mockImplementation((input: RequestInfo | URL) =>
      String(input) === RELEASE_URL ? Promise.reject(new TypeError('CORS')) : Promise.resolve(new Response(null, { status: 500 })));
    h.nativeGetBytes.mockResolvedValue(gzBytes(2_097_152));
    mod = await load('2026-10-08T16:16:15');

    const events = await withProgress(mod, () => mod.__fetchSnapshotForTest());
    expect(h.nativeGetBytes).toHaveBeenCalledWith(RELEASE_URL);
    expect(mod.bootTiming.source).toBe('release');
    const first = events.find((e) => e.source === 'release');
    expect(first?.totalBytes).toBe(0);
    expect(first?.percent).toBeNull();
  });

  it('درصدِ آمادگی درِ سه مرحله عقب نمی‌رود', async () => {
    // قبلاً عددِ صفحه درصدِ دریافت بود و بعد percentِ کلی، پس رقم از ۱۰۰٪
    // به ۷۵٪ برمی‌گشت — کاربر آن را پس‌رفتِ دریافت می‌خواند.
    mod = await load('2026-10-08T16:16:15');
    const steps = [
      mod.__bootProgressForTest('download', 0, 16_179_264).overallPercent,
      mod.__bootProgressForTest('download', 8_089_632, 16_179_264).overallPercent,
      mod.__bootProgressForTest('download', 16_179_264, 16_179_264).overallPercent,
      mod.__bootProgressForTest('decompress', 0, 0).overallPercent,
      mod.__bootProgressForTest('database', 0, 0).overallPercent,
    ].filter((n): n is number => n !== null);
    expect(steps.every((n, i) => i === 0 || n >= steps[i - 1])).toBe(true);
    expect(steps).toEqual([0, 35, 70, 85, 95]);
  });

  it('صفحۀ پاسخِ HTML جایِ دیتابیس را نمی‌گیرد — حتی از خودِ برنامه', async () => {
    // سرورِ محلی/WebViewِ خرابه می‌تواند مسیرِ بسته را با ۲۰۰ و index.html
    // جواب بدهد؛ اگر آن «بسته» پذیرفته شود، sql.js بی‌معنی می‌سوزد و همه‌جا
    // «بی‌داده» می‌شود. پس gz نبود ⇒ ریلیز ⇒ و اگر آن هم/html بود ⇒ خطا.
    localStorage.setItem(STAMP_KEY, '2026-10-08T16:16:15');
    h.match.mockResolvedValue(undefined);
    const html = () => new Response('<html>not found</html>', { status: 200 });
    routeFetch({ [GZ_URL]: html, [RELEASE_URL]: html });
    h.nativeGetBytes.mockResolvedValue(new Response('<html>not found</html>').arrayBuffer());
    mod = await load('2026-10-08T16:16:15');

    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/بستهٔ دادهٔ آفلاین/);
    expect(h.nativeGetBytes).toHaveBeenCalledWith(RELEASE_URL);
    expect(h.put).not.toHaveBeenCalled();
    expect(mod.bootTiming.source).not.toBe('bundle');
  });
});
