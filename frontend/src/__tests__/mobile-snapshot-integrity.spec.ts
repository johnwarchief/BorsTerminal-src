// __tests__/mobile-snapshot-integrity.spec.ts — Stage 3: هیچ شکستی نسخۀ سالم را
// از دسترس بیرون نمی‌اندازد؛ هیچ نسخۀ جدیدی پیش از کامل شدن اعتبارسنجی فعال نمی‌شود؛
// هیچ شکستی به‌حساب «بررسی موفق» ثبت نمی‌شود.
//
// آینهٔ سناریوهای مرحلۀ ۴ مأموریت. سه چیز در هر آزمون دیده می‌شود، نه فقط پیام:
//   • `bors_snapshot_active_v2` (pointerِ فعال) — کی نوشته می‌شود و کی نه
//   • محتوای cache staging و cache کهنه (SNAPSHOT_URL) — چه چیزی روی دیسک مانده
//   • دادهٔ کاربر (`bors_mobile_decisions_v1`) — باید دست‌نخورده بماند
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { makeTestSigner } from './minisignTestKey';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DbProbe } from '@shared/api/local/snapshotPackage';

const h = vi.hoisted(() => ({
  nativeGetBytes: vi.fn(),
  fetchMock: vi.fn(),
}));

vi.mock('@shared/api/local/nativeHttp', () => ({
  nativeGetBytes: h.nativeGetBytes,
}));

const POINTER_KEY = 'bors_snapshot_active_v2';
const STAMP_KEY = 'bors_snapshot_cached_stamp';
const CHECK_KEY = 'bors_snapshot_check_at';
const FAILS_KEY = 'bors_snapshot_fail_streak';
const NEXT_TRY_KEY = 'bors_snapshot_next_try_at';
const LAST_OK_KEY = 'bors_snapshot_last_ok_at';
const SNAP_PATH = '/mobile_snapshot.db.gz';
/** کلاینت کشِ واقعی کلید را به URLِ مطلق حل می‌کند؛ درِ مرورگر `cache.keys()` هرگز
 *  'pkg/…' نمی‌دهد. بی‌این تقلید، آزمونِ نگهداشت (۱۸) باگِ مقایسهٔ کلیدِ ناهمسنج
 *  را ندید و سبز بود. */
const ABS = (u: string): string => new URL(u, globalThis.location?.href ?? 'http://localhost/').href;
const GZ_URL = ABS(SNAP_PATH);
const STAGING = 'bors-mobile-snapshot-staging-v2';
const LEGACY = 'bors-mobile-snapshot-v1';
const RELEASE_GZ = 'https://github.com/johnwarchief/BorsTerminal-src/releases/download/mobile-latest/mobile_snapshot.db.gz';
const RELEASE_META = 'https://github.com/johnwarchief/BorsTerminal-src/releases/download/mobile-latest/mobile_snapshot.db.meta.json';
const RELEASE_SIG = RELEASE_META + '.sig';
// کلیدِ آزمایشیِ همین اجرا — امضا/بررسی درِ آزمون‌هایِ چرخه از همین می‌آید
const SIGNER = makeTestSigner();
const META_TEXT = (m: unknown): string => JSON.stringify(m, null, 1);

const USER_DATA_KEY = 'bors_mobile_decisions_v1';

type Mod = typeof import('@shared/api/local/localData');

// ── Cache APIِ درونِ حافظه، کلیدشده به‌اسمِ cache ───────────────────────────
const stores = new Map<string, Map<string, ArrayBuffer>>();
function cacheOf(name: string): Map<string, ArrayBuffer> {
  if (!stores.has(name)) stores.set(name, new Map());
  return stores.get(name)!;
}
function installCaches(overrides: { put?: (k: string) => void } = {}) {
  vi.stubGlobal('caches', {
    open: async (name: string) => {
      const store = cacheOf(name);
      return {
        match: async (req: string) => {
          const v = store.get(ABS(req));
          return v ? new Response(v.slice(0)) : undefined;
        },
        put: async (req: string, res: Response) => {
          const k = ABS(req);
          if (overrides.put) overrides.put(k);
          store.set(k, await res.arrayBuffer());
        },
        delete: async (req: string) => store.delete(ABS(req)),
        keys: async () => [...store.keys()].map((u) => ({ url: u } as Request)),
      };
    },
    delete: async (name: string) => stores.delete(name),
  });
}

// ── ساختِ بستۀ واقعیِ قابل‌هش (gzipِ سبکِ خودِ Node) ────────────────────────
import { gzipSync } from 'node:zlib';
const RAW_DB = new Uint8Array(64 * 1024).fill(7);
const GZ = () => new Uint8Array(gzipSync(Buffer.from(RAW_DB))).buffer as ArrayBuffer;

async function sha256(buf: ArrayBuffer): Promise<string> {
  const d = await webcrypto.subtle.digest('SHA-256', buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** manifestِ درست‌وسازمان‌دهندۀ همان بایت‌ها. `over` برای خراب‌کردن عمدی. */
/** manifest + بایت‌هایِ همان manifest + امضایِ «Ed» رویِ همان بایت‌ها. */
async function makeManifest(over: Record<string, unknown> = {}) {
  const bytes = GZ();
  const base = {
    schema_version: 2,
    package_id: '20261012T090000-abcd1234',
    app_version: '1.0.79',
    min_app_version: '1.0.70',
    built_at: '2026-10-12T09:00:00',
    gz_bytes: bytes.byteLength,
    gz_sha256: await sha256(bytes),
    db_bytes: RAW_DB.byteLength,
    tables: ['baked', 'meta', 'instruments', 'price_history'],
    required_baked_keys: ['market_board'],
  };
  const manifest = { ...base, ...over };
  const text = META_TEXT(manifest);
  const mb = new TextEncoder().encode(text).slice().buffer as ArrayBuffer;
  return { manifest, bytes: GZ(), manifestBytes: mb, manifestText: text,
           sigText: SIGNER.signBlock(mb) };
}

/** کاوشگرِ ساختارِ قابل‌کنترل: «بسته» را سالم یا جدول‌کم/بازگشایی‌خراب می‌کند. */
function probeWith(state: { tables?: string[]; bakedKeys?: string[]; meta?: Record<string, string>; throwOnOpen?: boolean }): DbProbe {
  return async () => {
    if (state.throwOnOpen) throw new Error('SQLite is not a database');
    const tables = new Set(state.tables ?? ['baked', 'meta', 'instruments', 'price_history']);
    const bakedKeys = new Set(state.bakedKeys ?? ['market_board']);
    const meta = state.meta ?? { built_at: '2026-10-12T09:00:00', schema: '1' };
    return {
      tables,
      hasRow: (_t: string, _c: string, k: string) => bakedKeys.has(k),
      metaValue: (k: string) => meta[k] ?? null,
      close: () => undefined,
    };
  };
}

async function load(stamp = '2026-10-08T16:16:15'): Promise<Mod> {
  vi.resetModules();
  vi.stubEnv('VITE_SNAPSHOT_STAMP', stamp);
  vi.stubEnv('VITE_APP_VERSION', '1.0.79');
  // کلیدِ عمومیِ build-time: همان چیزی که CI از public keyِ انتشار می‌سازد
  vi.stubEnv('VITE_MOBILE_MANIFEST_PUBKEY', SIGNER.pubB64);
  const m = await import('@shared/api/local/localData') as Mod;
  m.__setDbProbeForTest(probeWith({}));
  return m;
}

/** مسیرِ APK را می‌بندیم تا ریلیز آزموده شود؛ `bytes` همان چیزی که شبکه می‌دهد. */
/** مسیرِ APK بسته؛ manifest و .sig از درگاهِ بومی می‌آیند (کلاینت بایتِ خام می‌خواند). */
function serveRelease(bytes: ArrayBuffer | null, manifest: unknown,
                      opts: { sig?: string | null; manifestBytes?: ArrayBuffer | null } = {}) {
  const mb = opts.manifestBytes ?? (manifest === null ? null
    : new TextEncoder().encode(META_TEXT(manifest)).slice().buffer as ArrayBuffer);
  const sig = opts.sig === undefined ? (mb ? SIGNER.signBlock(mb) : null) : opts.sig;
  h.nativeGetBytes.mockImplementation(async (url: string) => {
    if (url === RELEASE_GZ) return bytes ? bytes.slice(0) : null;
    if (url === RELEASE_META) return mb ? mb.slice(0) : null;
    if (url === RELEASE_SIG) return sig ? new TextEncoder().encode(sig).slice().buffer as ArrayBuffer : null;
    return null;
  });
  h.fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const u = String(input);
    if (u === SNAP_PATH) return new Response(null, { status: 404 });   // بی‌بستۀ APK
    return new Response(null, { status: 500 });
  });
  vi.stubGlobal('fetch', h.fetchMock);
}

describe('چرخۀ بستهٔ آفلاین: staging، اعتبارسنجی، فعال‌سازی، backoff', () => {
  let mod: Mod;
  beforeEach(() => {
    stores.clear();
    localStorage.clear();
    localStorage.setItem(USER_DATA_KEY, JSON.stringify({ decisions: ['شپنا'] }));
    h.nativeGetBytes.mockReset();
    h.fetchMock.mockReset();
    vi.stubGlobal('crypto', webcrypto);
    // jsdom بی‌Blob.stream است؛ WebView دارد. gunzipِ تولید بهِ آن تکیه می‌کند، پس
    // آزمون همان تواناییِ مرورگر را می‌دهد (این جایگزینیِ محیط است، نه تغییرِ کد).
    vi.stubGlobal('Blob', NodeBlob);
    installCaches();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('۱) بستۀ سالم: دانلود، اعتبارسنجی، فعال‌سازی — و pointer در آخرین گام', async () => {
    mod = await load();
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);

    const buf = await mod.__fetchSnapshotForTest();
    expect(buf.byteLength).toBe(bytes.byteLength);
    expect(mod.bootTiming.source).toBe('release');
    const p = JSON.parse(localStorage.getItem(POINTER_KEY) ?? 'null');
    expect(p?.packageId).toBe(manifest.package_id);
    expect(p?.sha256).toBe(manifest.gz_sha256);
    expect(cacheOf(STAGING).size).toBe(1);          // یک نسخۀ فعال در staging
    expect(cacheOf(LEGACY).has(GZ_URL)).toBe(false); // کش کهنه نوشته نشد
    expect(JSON.parse(localStorage.getItem(USER_DATA_KEY)!).decisions).toEqual(['شپنا']);
  });

  it('۲) دانلود ناقص (طول ناسازگار): رد، و نسخۀ APKِ پیشین دست‌نخورده می‌ماند', async () => {
    localStorage.setItem(STAMP_KEY, '2026-10-09T07:30:00');   // نسخۀ کشیِ معتبرِ پیشین
    cacheOf(LEGACY).set(GZ_URL, GZ());
    mod = await load();
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes.slice(0, bytes.byteLength - 11), manifest); // ۱۱ بایت کم

    const out = await mod.requestManualCheck();
    expect(out?.ok, out?.detail).toBe(false);
    expect(out?.detail).toMatch(/size-mismatch/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();          // فعال نشد
    expect(Number(localStorage.getItem(FAILS_KEY))).toBe(1);
    expect(localStorage.getItem(LAST_OK_KEY)).toBeNull();          // «موفق» ثبت نشد
    // و راه‌اندازی: همان نسخۀ پیشین سرو می‌شود (نه خطا، نه دادهٔ نیمه)
    const kept = await mod.__fetchSnapshotForTest();
    expect(kept.byteLength).toBe(GZ().byteLength);
    expect(mod.bootTiming.source).toBe('cache');
    expect(cacheOf(LEGACY).has(GZ_URL)).toBe(true);
  });

  it('۳) SHA-256 نامعتبر: رد و حفظ پیشین؛ staging پاک نمی‌شود ولی فعال هم نمی‌شود', async () => {
    cacheOf(LEGACY).set(GZ_URL, GZ());
    localStorage.setItem(STAMP_KEY, '2026-10-09T07:30:00');
    mod = await load();
    const { manifest, bytes } = await makeManifest({ gz_sha256: '0'.repeat(64) });
    serveRelease(bytes, manifest);

    const out = await mod.requestManualCheck();
    expect(out?.detail).toMatch(/digest-mismatch/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
    expect(cacheOf(LEGACY).has(GZ_URL)).toBe(true);
    expect((await mod.__fetchSnapshotForTest()).byteLength).toBe(GZ().byteLength);
  });

  it('۴) gzip غیرقابل‌بازگشایی: رد در گامِ gunzip، نه در راه‌اندازی', async () => {
    mod = await load();
    const { manifest } = await makeManifest();
    const junk = new Uint8Array(manifest.gz_bytes).fill(0x5a);     // هم‌طول، بی‌معنی
    expect(new Uint8Array(junk)[0]).not.toBe(0x1f);
    serveRelease(junk.buffer as ArrayBuffer, manifest);
    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/not-gzip/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
  });

  it('۵) gz سالم با SQLite خراب: رد؛ cache فعال و pointer خراب نمی‌شوند', async () => {
    cacheOf(LEGACY).set(GZ_URL, GZ());
    localStorage.setItem(STAMP_KEY, '2026-10-09T07:30:00');
    mod = await load();
    mod.__setDbProbeForTest(probeWith({ throwOnOpen: true }));
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);

    const out = await mod.requestManualCheck();
    expect(out?.detail).toMatch(/db-open-failed/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
    expect(cacheOf(LEGACY).has(GZ_URL)).toBe(true);
    expect((await mod.__fetchSnapshotForTest()).byteLength).toBe(GZ().byteLength);
  });

  it('۵ت) db_schemaِ manifest با meta.schemaِ بسته نمی‌خواند ⇒ رد', async () => {
    mod = await load();
    mod.__setDbProbeForTest(probeWith({ meta: { built_at: '2026-10-12T09:00:00', schema: '1' } }));
    const { manifest, bytes } = await makeManifest({ db_schema: 2 });
    serveRelease(bytes, manifest);
    const out = await mod.requestManualCheck();
    expect(out?.ok).toBe(false);
    expect(out?.detail).toMatch(/db-schema-mismatch/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
  });

  it('۵ث) db_schemaِ همخوان و نبودش (بستۀ سازندۀ کهنه): هر دو پذیرفته می‌شوند', async () => {
    mod = await load();
    mod.__setDbProbeForTest(probeWith({ meta: { built_at: '2026-10-12T09:00:00', schema: '1' } }));
    const a = await makeManifest({ db_schema: 1 });
    serveRelease(a.bytes, a.manifest);
    expect((await mod.requestManualCheck())?.ok).toBe(true);
    localStorage.removeItem(POINTER_KEY);
    mod.__setDbProbeForTest(probeWith({ meta: { built_at: '2026-10-12T09:00:00', schema: '9' } }));
    const b = await makeManifest({ package_id: '20261012T090001-old-build',
                                   built_at: '2026-10-12T09:00:01' });
    serveRelease(b.bytes, b.manifest);
    expect((await mod.requestManualCheck())?.detail, 'بی‌db_schema داوریِ تازه اعمال نمی‌شود')
      .toMatch(/فعال شد|تازه‌تر/);
  });

  it('۵ب) جدولِ لازمِ غایب: رد با نامِ همان جدول', async () => {
    mod = await load();
    mod.__setDbProbeForTest(probeWith({ tables: ['baked', 'meta', 'instruments'] }));
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);
    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/table-missing.*price_history/);
  });

  it('۵پ) کلیدِ پختۀ لازمِ غایب: رد (بیستۀ بی‌تابلو پذیرفته نمی‌شود)', async () => {
    mod = await load();
    mod.__setDbProbeForTest(probeWith({ bakedKeys: ['screener'] }));
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);
    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/baked-key-missing.*market_board/);
  });

  it.each([
    ['schema_version ناشناخته', { schema_version: 3 }],
    ['sha256 نیست', { gz_sha256: undefined }],
    ['اندازه نیست', { gz_bytes: undefined }],
    ['package_id نیست', { package_id: undefined }],
  ])('۶) manifestِ نامعتبر ⇒ ردِ کنترل‌شده، بدونِ فعال‌سازی: %s', async (_name, over) => {
    mod = await load();
    const { manifest, bytes } = await makeManifest(over as Record<string, unknown>);
    serveRelease(bytes, manifest);
    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/manifest هم خوانده نشد|بستۀِ داده رد شد/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
  });

  it('۶ب) نسخۀ برنامه از حداقلِ خواستۀ بسته پایین‌تر ⇒ رد', async () => {
    mod = await load();
    const { manifest, bytes } = await makeManifest({ min_app_version: '9.9.9' });
    serveRelease(bytes, manifest);
    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/بستۀِ داده رد شد/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
  });

  it('۷) کمبود فضا در نوشتنِ staging: خطا بلعیده نمی‌شود؛ پیشین می‌ماند', async () => {
    cacheOf(LEGACY).set(GZ_URL, GZ());
    localStorage.setItem(STAMP_KEY, '2026-10-09T07:30:00');
    installCaches({ put: (k) => { if (k.includes('/pkg/')) throw new Error('QuotaExceededError'); } });
    mod = await load();
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);
    const out = await mod.requestManualCheck();
    expect(out?.detail, out?.detail).toMatch(/QuotaExceededError|storage-full|storage/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
    expect(cacheOf(LEGACY).has(GZ_URL)).toBe(true);
    expect((await mod.__fetchSnapshotForTest()).byteLength).toBe(GZ().byteLength);
  });

  it('۸) شکست پس از نوشتن staging و پیش از pointer: راه‌اندازیِ بعدی APK را می‌گیرد', async () => {
    mod = await load();
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);
    // staging نوشته می‌شود، بعدِ آن فعال‌سازی می‌شکند (pointer نوشته نمی‌شود)
    const realPut = cacheOf(STAGING).set.bind(cacheOf(STAGING));
    cacheOf(STAGING).set = (k: string, v: ArrayBuffer) => { realPut(k, v); throw new Error('crash before activate'); };
    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/crash before activate/);
    cacheOf(STAGING).set = realPut;
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();

    // «راه‌اندازیِ بعدی»: pointer نیست ⇒ بستۀ APK خوانده می‌شود، stagingِ یتیم آزار نمی‌دهد
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) =>
      String(input) === SNAP_PATH ? new Response(new Uint8Array(GZ())) : new Response(null, { status: 500 })));
    const m2 = await load();
    const got = await m2.__fetchSnapshotForTest();
    expect(got.byteLength).toBeGreaterThan(0);
    expect(m2.bootTiming.source).toBe('bundle');
  });

  it('۹) فعال‌سازی موفق و شکست پاک‌سازی: هر دو نسخۀ قابل‌بازیابی می‌مانند', async () => {
    mod = await load();
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);
    const staging = cacheOf(STAGING);
    const realDelete = staging.delete.bind(staging);
    staging.delete = () => { throw new Error('delete failed'); };
    const buf = await mod.__fetchSnapshotForTest();
    staging.delete = realDelete;
    expect(buf.byteLength).toBe(bytes.byteLength);
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe(manifest.package_id);
    expect(staging.size).toBeGreaterThanOrEqual(1);   // پاک‌سازی نشد ⇒ داده نه‌فقط سالم که موجود
  });

  it('۱۰) شکست دانلود، پنجرۀ بررسی بعدی را ۲۴ ساعت جلو نمی‌اندازد', async () => {
    mod = await load();
    const { manifest } = await makeManifest();
    serveRelease(null, manifest);
    h.nativeGetBytes.mockRejectedValue(new Error('offline'));
    await mod.requestManualCheck();
    const nextTry = Number(localStorage.getItem(NEXT_TRY_KEY));
    expect(nextTry - Date.now()).toBeLessThan(10 * 60_000);   // ≈۵ دقیقه، نه ۲۴ ساعت
    expect(Number(localStorage.getItem(CHECK_KEY))).toBeGreaterThan(0); // «تلاش شد» ثبت است
    expect(localStorage.getItem(LAST_OK_KEY)).toBeNull();               // و «موفق» نیست
  });

  it('۱۱) backoff دو‌برابر می‌شود، سقفِ یک روز دارد، و با موفقیت صفر می‌شود', async () => {
    mod = await load();
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes.slice(0, 5), manifest);            // طول غلط ⇒ شکست
    const waits: number[] = [];
    for (let i = 0; i < 6; i++) {
      await mod.requestManualCheck();
      waits.push(Number(localStorage.getItem(NEXT_TRY_KEY)) - Date.now());
    }
    expect(Number(localStorage.getItem(FAILS_KEY))).toBe(6);
    expect(waits[0]).toBeLessThan(waits[2]!);
    expect(Math.max(...waits)).toBeLessThanOrEqual(24 * 3600_000 + 5000);
    // موفقیت ⇒ شمارنده و backoff صفر
    serveRelease(bytes, manifest);
    await mod.requestManualCheck();
    expect(Number(localStorage.getItem(FAILS_KEY))).toBe(0);
    expect(Number(localStorage.getItem(NEXT_TRY_KEY))).toBe(0);
    expect(Number(localStorage.getItem(LAST_OK_KEY))).toBeGreaterThan(0);
  });

  it('۱۱ب) بررسی دستی هم‌زمان یک دانلود می‌سازد، و بی‌دستورِ دستی پنجرۀ ۲۴ ساعته محترم است', async () => {
    mod = await load();
    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);
    const both = await Promise.all([mod.requestManualCheck(), mod.requestManualCheck()]);
    expect(h.nativeGetBytes.mock.calls.filter((c) => c[0] === RELEASE_META).length).toBe(1);
    expect(both[0]).toBe(both[1]);
    // بعد از موفقیت، چرخۀ خودکار تا ۲۴ ساعت نباید دوباره manifest بخواند
    const before = h.nativeGetBytes.mock.calls.length;
    await (mod as unknown as { __maybeRefreshForTest?: () => Promise<void> }).__maybeRefreshForTest?.();
    expect(h.nativeGetBytes.mock.calls.length).toBe(before);
  });

  it('۱۲) مهاجرت از کشِ کهنه: خوانده می‌شود، دادهٔ کاربر می‌ماند، و فعال‌سازیِ تازه بازش می‌کند', async () => {
    cacheOf(LEGACY).set(GZ_URL, GZ());
    localStorage.setItem(STAMP_KEY, '2026-10-09T07:30:00');
    mod = await load('2026-10-08T16:16:15');
    const buf = await mod.__fetchSnapshotForTest();
    expect(buf.byteLength).toBeGreaterThan(0);
    expect(mod.bootTiming.source).toBe('cache');
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();  // هنوز چیزی فعال نشده

    const { manifest, bytes } = await makeManifest();
    serveRelease(bytes, manifest);
    const out = await mod.requestManualCheck();
    expect(out?.ok, out?.detail).toBe(true);
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe(manifest.package_id);
    expect(JSON.parse(localStorage.getItem(USER_DATA_KEY)!).decisions).toEqual(['شپنا']);
  });

  it('۱۳) regression: سه منبع و درصدِ یکنوا و «HTML جای دیتابیس را نمی‌گیرد» پابرجاست', async () => {
    mod = await load();
    const steps = [
      mod.__bootProgressForTest('download', 0, 16_179_264).overallPercent,
      mod.__bootProgressForTest('download', 8_089_632, 16_179_264).overallPercent,
      mod.__bootProgressForTest('decompress', 0, 0).overallPercent,
      mod.__bootProgressForTest('database', 0, 0).overallPercent,
    ].filter((n): n is number => n !== null);
    expect(steps.every((n, i) => i === 0 || n >= steps[i - 1]!)).toBe(true);

    const html = new TextEncoder().encode('<html>not found</html>').buffer as ArrayBuffer;
    const { manifest } = await makeManifest();
    serveRelease(html, { ...manifest, gz_bytes: html.byteLength, gz_sha256: await sha256(html) });
    await expect(mod.__fetchSnapshotForTest()).rejects.toThrow(/not-gzip|بستۀِ داده رد شد/);
    expect(mod.bootTiming.source).not.toBe('bundle');
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
  });

  it('۱۳ب) بنرِ «تلاش دوباره» کلِ کش را پاک نمی‌کند و پیامِ فارسی دارد', async () => {
    cacheOf(LEGACY).set(GZ_URL, GZ());
    localStorage.setItem(STAMP_KEY, '2026-10-09T07:30:00');
    mod = await load();
    localStorage.setItem(FAILS_KEY, '4');
    localStorage.setItem(NEXT_TRY_KEY, String(Date.now() + 10_000));
    mod.__showFatalBannerForTest('تست');
    const banner = document.getElementById('bors-fatal-banner');
    expect(banner?.textContent ?? '').toContain('بارگذاری بستهٔ دادهٔ آفلاین شکست خورد');
    const btn = banner?.querySelector('button');
    expect(btn?.textContent).toBe('تلاش دوباره');
    // پاک‌کردنِ کشِ کامل ممنوع ⇒ تنها کاری که دکمه می‌کند آزادکردنِ backoff است
    btn?.click();
    expect(cacheOf(LEGACY).has(GZ_URL)).toBe(true);
    expect(localStorage.getItem(FAILS_KEY)).toBeNull();
    expect(localStorage.getItem(NEXT_TRY_KEY)).toBeNull();
  });
  // ── مرحلۀ ۲ (دور ۴): لایۀ اصالت — بی‌امضا هیچ بسته‌ای فعال نمی‌شود ──────
  it('۱۴) امضایِ مفقود: رد، و نسخۀ فعالِ پیشین دست‌نخورده می‌ماند', async () => {
    mod = await load();
    const m1 = await makeManifest({ built_at: '2026-10-12T09:00:00' });
    serveRelease(m1.bytes, m1.manifest);
    expect((await mod.requestManualCheck())?.ok).toBe(true);
    const activePkg = JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId;
    const legacyBytesBefore = cacheOf(STAGING).size;
    const m2 = await makeManifest({ built_at: '2026-10-13T09:00:00',
                                    package_id: '20261013T090000-bbbb1111' });
    serveRelease(m2.bytes, m2.manifest, { sig: null });          // .sig نیست
    const out = await mod.requestManualCheck();
    expect(out?.ok).toBe(false);
    expect(out?.detail).toMatch(/signature-missing/);
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe(activePkg);
    expect(cacheOf(STAGING).size).toBe(legacyBytesBefore);        // هیچ پاک‌سازیِ پیش‌دستانه‌ای نه
    expect(JSON.parse(localStorage.getItem(USER_DATA_KEY)!).decisions).toEqual(['شپنا']);
  });

  it('۱۵) manifestِ دستکاری‌شده (امضا رویِ بایتِ دیگر) ⇒ signature-invalid', async () => {
    mod = await load();
    const m = await makeManifest();
    const signedOver = new TextEncoder().encode(META_TEXT({ ...m.manifest, gz_bytes: 1 }))
      .slice().buffer as ArrayBuffer;
    serveRelease(m.bytes, m.manifest, { sig: SIGNER.signBlock(signedOver) });
    const out = await mod.requestManualCheck();
    expect(out?.ok).toBe(false);
    expect(out?.detail).toMatch(/signature-invalid/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
  });

  it('۱۶) امضایِ کلیدِ دیگر ⇒ signature-key-mismatch، حتی با بایت‌هایِ درست', async () => {
    mod = await load();
    const m = await makeManifest();
    const other = makeTestSigner();
    serveRelease(m.bytes, m.manifest, { sig: other.signBlock(m.manifestBytes) });
    const out = await mod.requestManualCheck();
    expect(out?.ok).toBe(false);
    expect(out?.detail).toMatch(/signature-key-mismatch/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
  });

  it('۱۷) بی‌کلیدِ عمومی درِ بیلد ⇒ fail-closed (کلید از جایِ نامطمئن خوانده نمی‌شود)', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_SNAPSHOT_STAMP', '2026-10-08T16:16:15');
    vi.stubEnv('VITE_APP_VERSION', '1.0.79');
    vi.stubEnv('VITE_MOBILE_MANIFEST_PUBKEY', '');
    const m0 = await import('@shared/api/local/localData') as Mod;
    m0.__setDbProbeForTest(probeWith({}));
    const m = await makeManifest();
    serveRelease(m.bytes, m.manifest);
    const out = await m0.requestManualCheck();
    expect(out?.ok).toBe(false);
    expect(out?.detail).toMatch(/signing-key-unconfigured/);
    expect(localStorage.getItem(POINTER_KEY)).toBeNull();
    vi.stubEnv('VITE_MOBILE_MANIFEST_PUBKEY', SIGNER.pubB64);
  });

  // ── مرحلۀ ۴ (دور ۴): دو بسته می‌ماند؛ rollback فقط به فعال‌شدۀ معتبر ─────
  it('۱۸) سه فعال‌سازی پیاپی ⇒ دقیقاً دو بسته می‌ماند (فعال + آخرین معتبرِ پیشین)', async () => {
    mod = await load();
    for (const [pid, at] of ([['20261010T090000-aaaa0001', '2026-10-10T09:00:00'], ['20261011T090000-aaaa0002', '2026-10-11T09:00:00'], ['20261012T090000-aaaa0003', '2026-10-12T09:00:00']] as Array<[string, string]>)) {
      const m = await makeManifest({ package_id: pid, built_at: at });
      serveRelease(m.bytes, m.manifest);
      const out = await mod.requestManualCheck();
      expect(out?.ok, pid + ': ' + out?.detail).toBe(true);
    }
    const keys = [...cacheOf(STAGING).keys()];
    expect(keys.length).toBe(2);
    expect(keys.some((k) => k.includes('aaaa0003'))).toBe(true);
    expect(keys.some((k) => k.includes('aaaa0002'))).toBe(true);
    expect(keys.some((k) => k.includes('aaaa0001'))).toBe(false);
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe('20261012T090000-aaaa0003');
    expect(JSON.parse(localStorage.getItem(USER_DATA_KEY)!).decisions).toEqual(['شپنا']);
  });

  it('۱۹) اجرایِ دوبارهِ نگهداشت پایدار است و فعال/پیشین را تصادفاً نمی‌کَند', async () => {
    mod = await load();
    for (const [pid, at] of ([['20261011T090000-bb02', '2026-10-11T09:00:00'], ['20261012T090000-bb03', '2026-10-12T09:00:00']] as Array<[string, string]>)) {
      const m = await makeManifest({ package_id: pid, built_at: at });
      serveRelease(m.bytes, m.manifest);
      expect((await mod.requestManualCheck())?.ok).toBe(true);
    }
    const before = [...cacheOf(STAGING).keys()].sort();
    expect(before.length).toBe(2);
    for (let i = 0; i < 3; i++) {
      expect((await mod.requestManualCheck())?.ok).toBe(true);   // همان built_at ⇒ فعال‌سازیِ دوباره نیست
    }
    expect([...cacheOf(STAGING).keys()].sort()).toEqual(before);
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe('20261012T090000-bb03');
  });

  it('۲۰) rollback به آخرین فعال‌شدۀ معتبر؛ ردیفِ stagingِ یتیم نامزد نیست', async () => {
    mod = await load();
    for (const [pid, at] of ([['20261011T090000-cc01', '2026-10-11T09:00:00'], ['20261012T090000-cc02', '2026-10-12T09:00:00']] as Array<[string, string]>)) {
      const m = await makeManifest({ package_id: pid, built_at: at });
      serveRelease(m.bytes, m.manifest);
      expect((await mod.requestManualCheck())?.ok).toBe(true);
    }
    cacheOf(STAGING).set(ABS('pkg/20261013T090000-orph3n.gz'), GZ());   // هرگز فعال نشده
    const rb = await mod.rollbackToPreviousPackage();
    expect(rb.ok, rb.detail).toBe(true);
    expect(rb.detail).toBe('20261011T090000-cc01');
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe('20261011T090000-cc01');
    expect(String(JSON.parse(localStorage.getItem(POINTER_KEY)!).cacheKey).includes('orph3n')).toBe(false);
    const back = await mod.rollbackToPreviousPackage();            // رفت‌وبرگشتِ متقابل
    expect(back.ok).toBe(true);
    expect(back.detail).toBe('20261012T090000-cc02');
  });

  it('۲۱) بستۀ پیشینی که digestش درِ حافظه نمی‌خواند، rollback نمی‌شود', async () => {
    mod = await load();
    for (const [pid, at] of ([['20261011T090000-dd01', '2026-10-11T09:00:00'], ['20261012T090000-dd02', '2026-10-12T09:00:00']] as Array<[string, string]>)) {
      const m = await makeManifest({ package_id: pid, built_at: at });
      serveRelease(m.bytes, m.manifest);
      expect((await mod.requestManualCheck())?.ok).toBe(true);
    }
    const victim = [...cacheOf(STAGING).keys()].find((k) => k.includes('dd01'))!;
    cacheOf(STAGING).set(victim, new Uint8Array(64 * 1024).fill(9).buffer as ArrayBuffer);
    const before = JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId;
    const rb = await mod.rollbackToPreviousPackage();
    expect(rb.ok).toBe(false);
    expect(rb.detail).toMatch(/digest-mismatch/);
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe(before);
  });

  it('۲۲) کمبودِ فضا درِ نگهداشتِ پس ازِ فعال‌سازی، معتبرها را نمی‌کَشد و فعال را بی‌اعتبار نمی‌کند', async () => {
    mod = await load();
    const m = await makeManifest({ package_id: '20261012T090000-ee01',
                                   built_at: '2026-10-12T09:00:00' });
    serveRelease(m.bytes, m.manifest);
    expect((await mod.requestManualCheck())?.ok).toBe(true);
    const staging = cacheOf(STAGING);
    const realDelete = staging.delete.bind(staging);
    staging.delete = () => { throw new Error('QuotaExceededError on delete'); };
    const m2 = await makeManifest({ package_id: '20261013T090000-ee02',
                                    built_at: '2026-10-13T09:00:00' });
    serveRelease(m2.bytes, m2.manifest);
    expect((await mod.requestManualCheck())?.ok).toBe(true);       // فعال شد
    staging.delete = realDelete;
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe('20261013T090000-ee02');
    expect(staging.size).toBeGreaterThanOrEqual(1);                // دادهٔ فعال هنوز رویِ دستگاه است
    expect((await mod.__fetchSnapshotForTest()).byteLength).toBe(m2.bytes.byteLength);
  });

  it('۲۳) بستۀِ ردشده درِ staging نمی‌ماند؛ فعال و پیشینِ سالم می‌مانند', async () => {
    mod = await load();
    for (const [pid, at] of ([['20261011T090000-gg01', '2026-10-11T09:00:00'], ['20261012T090000-gg02', '2026-10-12T09:00:00']] as Array<[string, string]>)) {
      const m = await makeManifest({ package_id: pid, built_at: at });
      serveRelease(m.bytes, m.manifest);
      expect((await mod.requestManualCheck())?.ok).toBe(true);
    }
    expect(cacheOf(STAGING).size).toBe(2);
    // نامزدِ تازه: امضا، اندازه و digest سالم، ولی SQLite باز نمی‌شود ⇒ ردِ فعال‌سازی
    mod.__setDbProbeForTest(probeWith({ throwOnOpen: true }));
    const bad = await makeManifest({ package_id: '20261013T090000-gg03',
                                     built_at: '2026-10-13T09:00:00' });
    serveRelease(bad.bytes, bad.manifest);
    const out = await mod.requestManualCheck();
    expect(out?.ok).toBe(false);
    expect(out?.detail).toMatch(/db-open-failed/);
    const keys = [...cacheOf(STAGING).keys()];
    expect(keys.some((k) => k.includes('gg03'))).toBe(false);      // ردیفِ نامزدِ ردشده نماند
    expect(keys.length).toBe(2);
    expect(JSON.parse(localStorage.getItem(POINTER_KEY)!).packageId).toBe('20261012T090000-gg02');
    expect(JSON.parse(localStorage.getItem(USER_DATA_KEY)!).decisions).toEqual(['شپنا']);
  });
});
