// shared/api/local/localData.ts — موتور دادهٔ محلی (حالت موبایل/بدون بک‌اند)
//
// اسنپ‌شات پخته‌شده (mobile_snapshot.db.gz، خروجی scripts/build_mobile_snapshot.py)
// را دانلود، با DecompressionStream بومی مرورگر باز، و با sql.js (WASM) باز
// می‌کند. دو سرویس به resolvers می‌دهد:
//   baked(key)  — بسته‌های JSON از-پیش-پخته (بنیادی/FTS/اسکرینر/…)
//   query(sql)  — کوئری مستقیم روی جدول‌های خام (price_history/instruments/…)
//
// این ماژول فقط وقتی بارگذاری می‌شود که VITE_LOCAL_DATA='1' باشد (ایمپورت
// داینامیک در http.ts) — بیلد دسکتاپ/وب هیچ بایتی از آن ندارد.
import initSqlJs, { type Database } from 'sql.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';
import { HttpError } from '../http';
import { nativeGetBytes } from './nativeHttp';
import {
  parseManifest, parsePointer, verifyBytes, validateDatabase, versionAtLeast, sha256Hex,
  type ActivePointer, type DbProbe, type SnapshotManifest,
} from './snapshotPackage';
import { bundledManifestPublicKey, verifyManifestSignature } from './manifestSignature';

/** نسخۀ خودِ برنامه. `npm_package_version` را vite از package.json برمی‌دارد و
 *  `dev/version_anchor_guard.py` همان عدد را بهِ `bors_config.APP_VERSION` قفل
 *  می‌کند ⇒ یکِ منبعِ واحد، بی‌عددِ تازه. اگر روزی نبود، دروازۀِ «حداقلِ نسخه»
 *  بسته می‌ماند (رد، نه پذیرشِ بی‌آزمون). */
const APP_VERSION = (import.meta.env.VITE_APP_VERSION as string | undefined)
  ?? (import.meta.env as unknown as { npm_package_version?: string }).npm_package_version ?? '';

const SNAPSHOT_URL =
  (import.meta.env.VITE_SNAPSHOT_URL as string | undefined) ?? '/mobile_snapshot.db.gz';
const CACHE_NAME = 'bors-mobile-snapshot-v1';

// بستۀ همراهِ APK تا چه تاریخِ پختی است. CI آن را از meta.json کنارِ همان gz
// می‌خواند و به vite می‌دهد؛ بی‌این مهر، کشِ دورِ پیش (دادۀ APKِ کهنه) در اولین
// اجرای نصبِ تازه بر بستۀ جدیدِ همراهِ برنامه می‌برد و گوشی دادهٔ کهنه نشان
// می‌داد. نبودش (بیلد محلی) = رفتارِ قبلی: هرچه درِ کش بود خوانده می‌شود.
const BUNDLE_STAMP = (import.meta.env.VITE_SNAPSHOT_STAMP as string | undefined) ?? '';
const STAMP_KEY = 'bors_snapshot_cached_stamp';

export type BootProgressPhase = 'download' | 'decompress' | 'database';

export type BootProgress = {
  phase: BootProgressPhase;
  source: 'cache' | 'bundle' | 'release' | '';
  loadedBytes: number;
  totalBytes: number;
  percent: number | null;
  overallPercent: number | null;
};

type BootProgressListener = (progress: BootProgress) => void;
const bootProgressListeners = new Set<BootProgressListener>();

/** ثبت listener برای صفحهٔ آماده‌سازی اولیهٔ موبایل. */
export function subscribeBootProgress(listener: BootProgressListener): () => void {
  bootProgressListeners.add(listener);
  return () => bootProgressListeners.delete(listener);
}

function emitBootProgress(progress: BootProgress): void {
  for (const listener of bootProgressListeners) {
    try { listener(progress); } catch { /* UI listener نباید boot را متوقف کند */ }
  }
}

function makeBootProgress(
  phase: BootProgressPhase,
  source: BootProgress['source'],
  loadedBytes: number,
  totalBytes: number,
): BootProgress {
  const percent = totalBytes > 0
    ? Math.min(100, Math.max(0, Math.round((loadedBytes / totalBytes) * 100)))
    : null;

  let overallPercent: number | null = null;
  if (phase === 'download' && percent !== null) {
    // ۷۰٪ از آمادگی به دریافت بسته است، بازگشایی تا ۸۵٪ و ساخت دیتابیس تا
    // ۹۵٪. همین عددِ پیوسته نمایش داده می‌شود: اگر درصدِ دریافت و بعد
    // درصدِ کلی نشان داده می‌شد، رقم از ۱۰۰٪ به ۷۵٪ برمی‌گشت و کاربر آن را
    // پس‌رفت می‌خواند. این درصد کلّی است و زمانِ واقعی را ادعا نمی‌کند.
    overallPercent = Math.round(percent * 0.7);
  } else if (phase === 'decompress') {
    overallPercent = 85;
  } else if (phase === 'database') {
    overallPercent = 95;
  }

  return { phase, source, loadedBytes, totalBytes, percent, overallPercent };
}

function emitDownloadProgress(
  source: BootProgress['source'],
  loadedBytes: number,
  totalBytes: number,
): void {
  emitBootProgress(makeBootProgress('download', source, loadedBytes, totalBytes));
}

/**
 * Response را به ArrayBuffer تبدیل می‌کند و هنگام خواندن، پیشرفت را گزارش می‌دهد.
 * اگر content-length در WebView در دسترس نباشد، درصد null می‌ماند تا عدد جعلی نسازیم.
 */
async function responseArrayBufferWithProgress(
  response: Response,
  source: BootProgress['source'],
): Promise<ArrayBuffer> {
  const total = Number(response.headers.get('content-length') ?? 0);
  emitDownloadProgress(source, 0, total);

  if (!response.body || typeof response.body.pipeThrough !== 'function') {
    const buf = await response.arrayBuffer();
    emitDownloadProgress(source, buf.byteLength, total || buf.byteLength);
    return buf;
  }

  let loaded = 0;
  const counted = response.body.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        loaded += chunk.byteLength;
        emitDownloadProgress(source, loaded, total);
        controller.enqueue(chunk);
      },
    }),
  );

  const buf = await new Response(counted).arrayBuffer();
  emitDownloadProgress(source, buf.byteLength, total || buf.byteLength);
  return buf;
}


// --- بروزرسانی خودکار داده از GitHub Releases (بدون سرور، بدون هزینه) -----
// manifestِ کوچک چک می‌شود؛ اگر built_at تازه‌تر بود، gz کامل در **فضای موقت**
// (staging cache) دانلود می‌شود و تنها پس از اندازه + SHA-256 + gunzip + بازگشایی
// SQLite، با نوشتنِ یکِ **pointer** در آخرین گام فعال می‌شود. تا آن لحظه نسخهٔ سالم
// قبلی مرجع است، و هر شکستی همان نسخه را باقی می‌گذارد.
// تگ ثابت «mobile-latest» (pre-release غلتان که CI با هر بیلد تازه می‌کند) —
// عمداً نه releases/latest، تا ریلیزهای رسمی دسکتاپ مالک دست‌نخورده بمانند.
const REMOTE_BASE =
  (import.meta.env.VITE_SNAPSHOT_REMOTE as string | undefined) ??
  'https://github.com/johnwarchief/BorsTerminal-src/releases/download/mobile-latest';
const REMOTE_META_URL = `${REMOTE_BASE}/mobile_snapshot.db.meta.json`;
const REMOTE_GZ_URL = `${REMOTE_BASE}/mobile_snapshot.db.gz`;
/** امضا **کنارِ** manifest، نه داخلِ آن (`scripts/sign_mobile_manifest.py`) — تا
 *  بایت‌هایِ امضاشده همان بایت‌هایِ دانلودی بمانند و دورِ باطلی نسازیم. */
const REMOTE_SIG_URL = `${REMOTE_META_URL}.sig`;

/** manifest را فقط با امضایِ معتبر می‌خواند: بایتِ خام ← .sig ← parseManifest.
 *  ترتیب عمدی است: **هیچ فیلدی از manifest پیش از تأییدِ اصالت خوانده نمی‌شود.**
 *  بی‌کلیدِ عمومی درِ بیلد، همه‌چیز رد می‌شود (fail-closed) — نه پذیرشِ بی‌آزمون. */
async function fetchSignedManifest():
  Promise<{ ok: true; value: SnapshotManifest } | { ok: false; reason: string; detail: string }> {
  const pubkey = bundledManifestPublicKey();
  if (!pubkey) {
    return { ok: false, reason: 'signing-key-unconfigured',
             detail: 'کلیدِ عمومیِ امضا درِ این بیلد نیست؛ manifest بی‌امضا پذیرفته نمی‌شود' };
  }
  let mb: ArrayBuffer | null = null;
  try { mb = await nativeGetBytes(REMOTE_META_URL); }
  catch (e) {
    return { ok: false, reason: 'manifest-missing',
             detail: `دریافتِ manifest: ${e instanceof Error ? e.message : String(e)}` };
  }
  if (!mb || !mb.byteLength) return { ok: false, reason: 'manifest-missing', detail: 'manifest خالی بود' };
  let sigText = '';
  try {
    const sb = await nativeGetBytes(REMOTE_SIG_URL);
    sigText = sb ? new TextDecoder().decode(sb) : '';
  } catch { sigText = ''; }   // نبودِ .sig ⇒ امضایِ مفقود، پایین رد می‌کند
  const v = await verifyManifestSignature(mb, sigText, pubkey);
  if (!v.ok) return { ok: false, reason: v.reason, detail: v.detail };
  let json: unknown;
  try { json = JSON.parse(new TextDecoder().decode(mb)); }
  catch (e) {
    return { ok: false, reason: 'manifest-unparsable',
             detail: `پس ازِ امضایِ معتبر، JSON تجزیه نشد: ${e instanceof Error ? e.message : String(e)}` };
  }
  return parseManifest(json);
}

// کلیدهایِ وضعیت. جدا بودنشان عمدی است: «کی آخرین بار **موفق** بررسی شد» با
// «آخرین بار **تلاش** شد» یکی نیست — پیش‌ازِ این همان CHECK_KEY پیش از دانلود
// نوشته می‌شد و هر شکست، بررسیِ بعدی را ۲۴ ساعت عقب می‌انداخت.
const CHECK_KEY = 'bors_snapshot_check_at';          // legacy: آخرین تلاش (برایِ خواندنِ دادهٔ کهنه)
const LAST_OK_KEY = 'bors_snapshot_last_ok_at';      // آخرین **فعال‌سازیِ** موفق
const NEXT_TRY_KEY = 'bors_snapshot_next_try_at';    // سقفِ زمانیِ تلاشِ بعدی (backoff)
const FAILS_KEY = 'bors_snapshot_fail_streak';       // شمارشِ شکست‌هایِ پی‌درپی
const POINTER_KEY = 'bors_snapshot_active_v2';       // مرجعِ نسخۀِ فعال (آخرین گامِ فعال‌سازی)
const PREV_POINTER_KEY = 'bors_snapshot_previous_v2'; // نسخۀِ پیشینِ **اعتبارسنجی‌شده** (نامزدِ rollback)
const STAGING_CACHE_NAME = 'bors-mobile-snapshot-staging-v2';

/** پس ازِ فعال‌سازیِ موفق، حداکثر دو بسته می‌ماند: فعال + آخرینِ معتبرِ پیشین. */
const KEEP_PACKAGES = 2;

const CHECK_EVERY_MS = 24 * 3600 * 1000;             // ریتمِ عادیِ بررسی (تغییر نکرد)
const BACKOFF_BASE_MS = 5 * 60 * 1000;               // اولینِ فاصلۀِ پس ازِ شکست
const BACKOFF_CAP_MS = CHECK_EVERY_MS;               // سقفِ فاصل ⇒ هرگز بهِ pollingِ پرتکرار برنمی‌گردد

/** آیا اتصال سنجه‌دار (دادهٔ همراه) یا کاربر «صرفه‌جویی» خواسته است؟
 *
 *  بستهٔ داده ۲۲ مگابایت است. دانلودِ خودکارِ آن رویِ دادهٔ همراه، بی‌آنکه
 *  کاربر خواسته باشد، هم هزینه است هم بی‌ادبی — مخصوصاً که اپ با بستهٔ
 *  فعلی کاملاً کار می‌کند و این فقط «تازه‌تر» است، نه «لازم».
 *  نبودِ این API (WebViewِ قدیمی) یعنی محافظه‌کار باشیم؟ نه — آنجا رفتارِ
 *  قبلی می‌ماند، وگرنه رویِ وای‌فای هم هرگز تازه نمی‌شد.
 */
function isMeteredConnection(): boolean {
  const c = (navigator as unknown as {
    connection?: { saveData?: boolean; type?: string; effectiveType?: string };
  }).connection;
  if (!c) return false;
  if (c.saveData === true) return true;
  if (c.type === 'cellular') return true;
  // 2g/3g تقریباً همیشه همراه است؛ 4g ممکن است وای‌فای باشد، پس رد نمی‌شود.
  return c.effectiveType === 'slow-2g' || c.effectiveType === '2g' || c.effectiveType === '3g';
}

// ── وضعیتِ زمان‌بندی (موفق ≠ تلاش) ────────────────────────────────────────
function lsGet(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } }
function lsSet(k: string, v: string): void { try { localStorage.setItem(k, v); } catch { /* بی‌حافظه */ } }
function lsDel(k: string): void { try { localStorage.removeItem(k); } catch { /* بی‌حافظه */ } }

function readPointer(): ActivePointer | null {
  return parsePointer(lsGet(POINTER_KEY));
}

async function openCache(name: string): Promise<Cache | null> {
  try { return await caches.open(name); } catch { return null; } // Cache API درِ برخی WebViewها نیست
}

/** فاصلۀِ تلاشِ بعدی: ۵ دقیقه، دو‌برابرِ هرِ شکست، سقفِ یکِ روز. با موفقیت صفر می‌شود. */
export function backoffMs(failStreak: number): number {
  if (failStreak <= 0) return 0;
  return Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** Math.min(failStreak - 1, 10));
}

function noteFailure(detail: string): void {
  const n = Number(lsGet(FAILS_KEY) ?? 0) + 1;
  lsSet(FAILS_KEY, String(n));
  lsSet(NEXT_TRY_KEY, String(Date.now() + backoffMs(n)));
  lsSet(CHECK_KEY, String(Date.now())); // legacy: «تلاش شد» — موفقیت نیست
  lastOutcome = { at: Date.now(), ok: false, detail: detail.slice(0, 200) };
}

function noteSuccess(detail: string): void {
  lsSet(FAILS_KEY, '0');
  lsSet(LAST_OK_KEY, String(Date.now()));
  lsSet(NEXT_TRY_KEY, '0');
  lsSet(CHECK_KEY, String(Date.now()));
  lastOutcome = { at: Date.now(), ok: true, detail: detail.slice(0, 200) };
}

export type SnapshotOutcome = { at: number; ok: boolean; detail: string };
let lastOutcome: SnapshotOutcome | null = null;
let inFlight: Promise<SnapshotOutcome | null> | null = null;

/** وضعیتِ بسته برایِ پنلِ 🛠 و دکمۀِ «بررسی دستی». */
export function snapshotStatus(): {
  source: string; builtAt: string; packageId: string; activatedAt: number | null;
  previousPackageId: string;
  failStreak: number; nextTryAt: number; lastOkAt: number; lastOutcome: SnapshotOutcome | null;
  checking: boolean;
} {
  const p = readPointer();
  return {
    source: bootTiming.source || p ? (bootTiming.source || 'pointer') : '—',
    builtAt: p?.builtAt ?? '',
    packageId: p?.packageId ?? '',
    activatedAt: p?.activatedAt ?? null,
    previousPackageId: readPreviousPointers()[0]?.packageId ?? '',
    failStreak: Number(lsGet(FAILS_KEY) ?? 0),
    nextTryAt: Number(lsGet(NEXT_TRY_KEY) ?? 0),
    lastOkAt: Number(lsGet(LAST_OK_KEY) ?? 0),
    lastOutcome,
    checking: inFlight !== null,
  };
}

/** یکِ دورِ بررسی: manifest ← مقایسهٔ built_at ← staging ← اعتبارسنجی ← فعال‌سازی.
 *  هرگز دو دورِ هم‌زمان نمی‌دود (دکمهٔ دستی و تایمرِ پس‌زمینه یکی را شریک می‌شوند). */
async function runCheck(opts: { manual: boolean }): Promise<SnapshotOutcome | null> {
  if (inFlight) return inFlight;
  inFlight = (async (): Promise<SnapshotOutcome | null> => {
    const now = Date.now();
    if (!opts.manual && now < Number(lsGet(NEXT_TRY_KEY) ?? 0)) return null; // backoff
    if (!opts.manual && now - Number(lsGet(CHECK_KEY) ?? 0) < CHECK_EVERY_MS) return null;
    if (!opts.manual && isMeteredConnection()) {
      // مُهرِ موفقیت جلو نمی‌رود: وای‌فایِ بعدی باید دوباره بتواند بررسی کند.
      return null;
    }
    try {
      const mf = await fetchSignedManifest();
      if (!mf.ok) {
        // نخواندنِ manifest یکِ «بستۀِ خراب» نیست؛ فقط نمی‌توان تازه شد.
        noteFailure(`manifest: ${mf.reason} — ${mf.detail}`);
        return lastOutcome;
      }
      // مقایسه از روی pointer/مُهر، نه با بازکردنِ دیتابیس: بی‌این، هرِ بررسیِ
      // پس‌زمینه یعنی گشودنِ ۲۲ مگابایت درِ حافظه فقط برایِ خواندنِ یکِ تاریخ.
      const localBuilt = readPointer()?.builtAt ?? lsGet(STAMP_KEY) ?? '';
      if (localBuilt && mf.value.built_at <= localBuilt) {
        noteSuccess('بستۀِ فعلی تازه‌تر یا هم‌سطح است');
        return lastOutcome;
      }
      const got = await downloadToStaging(mf.value);
      if (!got.ok) {
        await dropRejectedCandidate(mf.value);
        noteFailure(got.detail); return lastOutcome;
      }
      const act = await activate(got.key, mf.value);
      if (!act.ok) { noteFailure(act.detail); return lastOutcome; }
      noteSuccess(`فعال شد: ${mf.value.package_id}`);
      // نگهداشتِ «فعال + پیشین» — فقط **پس از** فعال‌سازیِ موفق. انتظارش
      // می‌دهیم تا وضعیتِ کش درِ همانِ لحظه تعیین باشد (آزمونِ شمارشِ بسته‌ها)؛
      // retainPackages خودش خطا را می‌خورد، پس شکستِ آن اعتبارِ فعال را نمی‌کُشد.
      await retainPackages();
      return lastOutcome;
    } catch (e) {
      noteFailure(e instanceof Error ? `${e.name}: ${e.message}` : String(e));
      return lastOutcome;
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

/** «بررسی دستی» برایِ کاربر: بی‌پاک‌کردنِ کش، بی‌انتظار‌ماندنِ پنجرۀِ ۲۴ ساعته. */
export function requestManualCheck(): Promise<SnapshotOutcome | null> {
  return runCheck({ manual: true });
}

/** دانلود درِ فضایِ موقت؛ کلیدِ فعالِ `SNAPSHOT_URL` هنوز دست‌نخورده است. */
/** کلیدِ staging از package_id است، پس هر نامزدِ ردشدهٔ تازه یکِ ردیفِ جدا می‌گیرد. */
const stagingKey = (m: SnapshotManifest): string => `pkg/${m.package_id}.gz`;

/** بستۀِ **ردشده** نباید رویِ گوشی بماند: هر دورِ بررسیِ ناموفق با package_idِ
 *  تازه ~۲۲ مگابایتِ بی‌مصرف می‌آورد. فعال و پیشینِ سالم هرگز اینجا حذف نمی‌شوند —
 *  این فقط همان نامزدی است که خودِ اعتبارسنجی رد کرده است. */
async function dropRejectedCandidate(m: SnapshotManifest): Promise<void> {
  const key = stagingKey(m);
  const active = readPointer();
  if (active && active.cacheKey === key) return;
  if (readPreviousPointers().some((p) => p.cacheKey === key)) return;
  try {
    const c = await openCache(STAGING_CACHE_NAME);
    await c?.delete(key);
  } catch { /* ماندنِ نامزدِ ردشده اعتبارِ نسخۀِ فعال را کم نمی‌کند */ }
}

async function downloadToStaging(m: SnapshotManifest):
  Promise<{ ok: true; key: string } | { ok: false; detail: string }> {
  // دروازۀ سازگاری: هر مسیری که بخواهد بستۀ بیرونی را بپذیرد (هم بررسیِ
  // پس‌زمینه و هم پشتیبانِ راه‌اندازی) از همین‌جا می‌گذرد. پیش‌ازِ این فقطِ مسیرِ
  // بررسی آن را داشت و پشتیبانِ راه‌اندازی می‌توانست بستۀ ناسازگار را بیاورد.
  if (!APP_VERSION) {
    return { ok: false, detail: 'app-version-unknown: نسخۀ برنامه معلوم نیست؛ فعال نمی‌شود' };
  }
  if (!versionAtLeast(APP_VERSION, m.min_app_version)) {
    return { ok: false, detail: `app-version-too-low: بسته به ${m.min_app_version} می‌خواهد، برنامه ${APP_VERSION} است` };
  }
  const key = stagingKey(m);
  // اول fetchِ معمولی — پاسخِ streaming درصدِ واقعیِ بایت می‌دهد؛ اگر WebView به
  // دیوارِ CORS خورد درگاهِ بومی می‌آید و آن‌جا یکجا است، پس درصد نمی‌سازیم.
  let buf: ArrayBuffer | null = null;
  try {
    const r = await fetch(REMOTE_GZ_URL);
    if (r.ok) buf = await responseArrayBufferWithProgress(r, 'release');
  } catch { /* CORS/شبکه — درگاهِ بومی */ }
  if (!isGz(buf)) {
    emitDownloadProgress('release', 0, 0);
    try {
      buf = await nativeGetBytes(REMOTE_GZ_URL);
    } catch (e) {
      return { ok: false, detail: `دریافت بسته شکست خورد: ${e instanceof Error ? e.message : String(e)}` };
    }
  }
  if (!buf) return { ok: false, detail: 'storage-unavailable: هیچ مسیری بایتی برنگرداند' };
  const v = await verifyBytes(buf, m);
  if (!v.ok) return { ok: false, detail: `${v.reason}: ${v.detail}` };
  const staging = await openCache(STAGING_CACHE_NAME);
  if (!staging) return { ok: false, detail: 'storage-unavailable: Cache API در دسترس نیست' };
  try {
    await staging.put(key, new Response(buf.slice(0))); // کپی: buf بعداً درِ بازگشایی مصرف می‌شود
  } catch (e) {
    return { ok: false, detail: `storage-full: نوشتنِ فضایِ موقت ناموفق بود (${e instanceof Error ? e.message : String(e)})` };
  }
  // اعتبارسنجیِ **از روی همان چیزی که درِ کش نشست** — نه بایتی که درِ حافظه بود،
  // تا نوشتنِ نصفه‌نیمه هم گرفته شود.
  const back = await staging.match(key);
  if (!back) return { ok: false, detail: 'storage: نوشتنِ موقت تأیید نشد (بازخوانی نشد)' };
  const stored = await back.arrayBuffer();
  const vv = await verifyBytes(stored, m);
  if (!vv.ok) return { ok: false, detail: `${vv.reason} پس از ذخیره: ${vv.detail}` };
  const db = await validateStoredPackage(stored, m);
  if (!db.ok) return { ok: false, detail: db.detail };
  return { ok: true, key };
}

/** بازگشاییِ واقعی با همان sql.js که مصرفِ برنامه است (نه یک شبیه‌سازِ دیگر). */
async function validateStoredPackage(gzBuf: ArrayBuffer, m: SnapshotManifest):
  Promise<{ ok: true } | { ok: false; detail: string }> {
  try {
    const raw = await gunzip(gzBuf);
    const r = await validateDatabase(raw, m, activeProbe());
    return r.ok ? { ok: true } : { ok: false, detail: `${r.reason}: ${r.detail}` };
  } catch (e) {
    return { ok: false, detail: `gunzip/db: ${e instanceof Error ? e.message : String(e)}` };
  }
}

/** آخرین گام: نوشتنِ pointer. تا این خط اجرا نشده، نسخهٔ قبلی مرجع است.
 *  pointerِ کهنه به PREV_POINTER_KEY منتقل می‌شود — همان چیزی که بعداً نامزدِ
 *  rollback است؛ پس «بستۀِ پیشین» فقط بستۀِ **فعال‌شدۀِ قبلی** است، نه هر چیزی
 *  که درِ staging مانده باشد. */
async function activate(stagingKey: string, m: SnapshotManifest): Promise<{ ok: boolean; detail: string }> {
  const staging = await openCache(STAGING_CACHE_NAME);
  const hit = staging ? await staging.match(stagingKey) : undefined;
  if (!hit) return { ok: false, detail: 'staging گم شد (پیش از فعال‌سازی)' };
  const before = readPointer();
  const p: ActivePointer = {
    cacheKey: stagingKey, packageId: m.package_id, builtAt: m.built_at,
    sha256: m.gz_sha256, activatedAt: Date.now(), schema: m.schema_version,
  };
  lsSet(POINTER_KEY, JSON.stringify(p));
  lsSet(STAMP_KEY, m.built_at); // سازگاری: مسیرهایِ کهنه همین مُهر را می‌خوانند
  if (before && before.cacheKey !== stagingKey) {
    // اگر نسخۀِ پیشین واقعاً درِ حافظه هست، به‌عنوانِ نامزدِ rollback می‌ماند
    const stillThere = await staging?.match(before.cacheKey);
    if (stillThere) {
      const prevs = readPreviousPointers().filter((x) => x.cacheKey !== stagingKey);
      lsSet(PREV_POINTER_KEY, JSON.stringify([before, ...prevs].slice(0, KEEP_PACKAGES - 1)));
    } else {
      lsSet(PREV_POINTER_KEY, '[]');
    }
  }
  return { ok: true, detail: m.package_id };
}

/** فهرستِ بسته‌هایِ **فعال‌شده** (فعال + پیشین‌ها). هرکدام یک‌بار کامل
 *  اعتبارسنجی از راهِ دورِ فعال‌سازی گذشته‌اند؛ ردیفِ stagingِ بی‌فعال‌سازی اینجا نیست. */
function readPreviousPointers(): ActivePointer[] {
  try {
    const raw = JSON.parse(lsGet(PREV_POINTER_KEY) ?? '[]');
    if (!Array.isArray(raw)) return [];
    return raw.map((x) => parsePointer(JSON.stringify(x))).filter((x): x is ActivePointer => !!x);
  } catch { return []; }
}

/** کلیدِ `Cache` درِ مرورگر **آدرسِ مطلق** است (`put('pkg/x.gz')` آن را به
 *  `<origin>/pkg/x.gz` حل می‌کند) ولی pointer همان رشتهٔ نسبی را نگه می‌دارد.
 *  بی‌این حلِّ یکی‌به‌دیگری، فهرستِ «محفوظ‌ها» هیچ‌وقت با `keys()` نمی‌خواند و
 *  پاک‌سازی دقیقاً همان بستۀِ پیشینِ سالم را می‌کَند — درِ Chromiumِ واقعی دیدیم. */
function absCacheKey(k: string): string {
  try { return new URL(k, location.href).href; } catch { return k; }
}

/** نگهداشتِ «فعال + آخرینِ معتبرِ پیشین». **فقط** پس ازِ فعال‌سازیِ موفق صدا زده
 *  می‌شود؛ هیچ پاک‌سازیِ پیش‌دستانه‌ای (کمبودِ فضا، شکستِ دانلود) انجام نمی‌دهد،
 *  چون باید نسخهٔ سالمِ قبلی بماند. شکستِ خودش اعتبارِ نسخۀِ فعال را نمی‌کُشد. */
async function retainPackages(): Promise<{ kept: string[]; deleted: number; error: string }> {
  const out = { kept: [] as string[], deleted: 0, error: '' };
  try {
    const staging = await openCache(STAGING_CACHE_NAME);
    if (!staging) return { ...out, error: 'cache-unavailable' };
    const active = readPointer();
    const protectedKeys = new Set<string>();
    if (active) protectedKeys.add(absCacheKey(active.cacheKey));
    for (const p of readPreviousPointers()) protectedKeys.add(absCacheKey(p.cacheKey));
    const urls = (await staging.keys()).map((r) => r.url);
    // محافظتِ اضافی: اگر دوِ محافظ‌شده کمتر از KEEP_PACKAGES بود، تازه‌ترینِ
    // package_idها (ساختارِ pkg/<YYYYMMDDThhmmss>-<sha8>.gz ⇒ مرتب‌شدنی) می‌ماند.
    const others = urls.filter((u) => !protectedKeys.has(u)).sort();
    const room = Math.max(0, KEEP_PACKAGES - protectedKeys.size);
    const keepExtras = others.slice(Math.max(0, others.length - room));
    for (const u of urls) {
      if (protectedKeys.has(u) || keepExtras.includes(u)) { out.kept.push(u); continue; }
      try { await staging.delete(u); out.deleted++; } catch { /* حذفِ یکِ ردیفِ قدیمی کلِ نگهداشت را نمی‌خواباند */ }
    }
    const legacy = await openCache(CACHE_NAME);
    if (legacy) await legacy.delete(SNAPSHOT_URL); // کشِ دورِ پیش، حالا بی‌مصرف
    return out;
  } catch (e) {
    return { ...out, error: e instanceof Error ? e.message : String(e) };
  }
}

/** بازگشتِ صریح به آخرین بستۀِ **فعال‌شدۀِ معتبر** (نامزدِ rollback). بی‌بستۀِ سالم،
 *  pointer تکان نمی‌خورد — حتی اگر ردیفِ stagingاش مانده باشد. */
export async function rollbackToPreviousPackage():
  Promise<{ ok: boolean; detail: string }> {
  const active = readPointer();
  const prev = readPreviousPointers()[0];
  if (!prev) return { ok: false, detail: 'no-previous-package' };
  const staging = await openCache(STAGING_CACHE_NAME);
  const hit = staging ? await staging.match(prev.cacheKey) : undefined;
  if (!hit) return { ok: false, detail: 'previous-package-missing-from-storage' };
  const buf = await hit.arrayBuffer();
  const got = await sha256Hex(buf);
  if (!got) return { ok: false, detail: 'digest-missing-on-device' };
  if (got.toLowerCase() !== prev.sha256.toLowerCase()) {
    return { ok: false, detail: `digest-mismatch: ${got.slice(0, 12)} ≠ ${prev.sha256.slice(0, 12)}` };
  }
  if (active) lsSet(PREV_POINTER_KEY, JSON.stringify([active, ...readPreviousPointers()
    .filter((x) => x.cacheKey !== active.cacheKey && x.cacheKey !== prev.cacheKey)]
    .slice(0, KEEP_PACKAGES - 1)));
  lsSet(POINTER_KEY, JSON.stringify(prev));
  lsSet(STAMP_KEY, prev.builtAt);
  // دیتابیسِ بازِ فعلی متعلق به بستۀِ ردشده است؛ بازنشسته می‌شود تا گامِ بعدی
  // (reload یا خواندنِ بعدی) همان بستۀِ پیشینِ معتبر را باز کند.
  dbPromise = null;
  return { ok: true, detail: prev.packageId };
}

async function maybeRefreshSnapshot(): Promise<void> {
  await runCheck({ manual: false });
}

/** فقط برایِ تست — مسیرِ بارگذاریِ بسته و راهِ دومش. */
export const __isMeteredForTest = (): boolean => isMeteredConnection();

/** فقط برایِ تست — دورۀ خودکار (همانِ setTimeoutِ راه‌اندازی). */
export const __maybeRefreshForTest = (): Promise<void> => maybeRefreshSnapshot();

export const __fetchSnapshotForTest = (): Promise<ArrayBuffer> => fetchSnapshot();

/** فقط برایِ تست — وزن‌هایِ درصدِ آمادگی درِ سه مرحله. */
export const __bootProgressForTest = (phase: BootProgressPhase, loaded: number, total: number) =>
  makeBootProgress(phase, 'bundle', loaded, total);

/** کشِ بسته را با مهرِ آن پاک می‌کند — همان‌جا که بستۀ خودِ برنامه مرجع است. */
async function dropCachedSnapshot(cache: Cache | null): Promise<void> {
  try { await cache?.delete(SNAPSHOT_URL); } catch { /* کش نبود */ }
  try { localStorage.removeItem(STAMP_KEY); } catch { /* مهم نیست */ }
}

/** وارسیِ gz. کفِ حجم برایِ مسیرهایِ شبکه است (صفحهٔ خطایِ HTML جایِ
 *  دیتابیس را نگیرد)؛ برایِ بستۀ خودِ برنامه همین دو بایتِ اول کافی است —
 *  سرورِ محلی می‌تواند مسیرِ ناشناخته را با ۲۰۰ و index.html جواب بدهد. */
function isGz(buf: ArrayBuffer | null, minBytes = 1_000_000): buf is ArrayBuffer {
  if (!buf || buf.byteLength < minBytes) return false;
  const h = new Uint8Array(buf, 0, 2);
  return h[0] === 0x1f && h[1] === 0x8b;
}

async function fetchSnapshot(): Promise<ArrayBuffer> {
  // ترتیب: ۱) نسخۀ **فعال** (pointer) اگر از بستۀ خودِ APK تازه‌تر باشد
  //        ۲) بستۀ همراهِ APK (مسیر عادی — بی‌نیاز به شبکه)
  //        ۳) ریلیزِ mobile-latest ← فضایِ موقت ← اعتبارسنجی ← فعال‌سازی
  // در همۀِ مسیرها اگر گامی شکست بخورد، همان چیزی که پیش‌تر سالم بود باقی می‌ماند؛
  // هیچ‌جا نسخهٔ سالم **پیش از** تأییدِ نسخۀِ جدید حذف نمی‌شود.
  const pointer = readPointer();
  if (pointer && (!BUNDLE_STAMP || pointer.builtAt > BUNDLE_STAMP)) {
    const staging = await openCache(STAGING_CACHE_NAME);
    const hit = staging ? await staging.match(pointer.cacheKey) : undefined;
    if (hit) {
      bootTiming.source = 'cache';
      const buf = await hit.arrayBuffer();
      emitDownloadProgress('cache', buf.byteLength, buf.byteLength);
      return buf;
    }
    // pointer هست و بسته‌اش نیست (کشِ پاک‌شده/میانِ راه‌اندازیِ نیمه) ⇒ pointer را
    // برمی‌داریم تا همین اجرایِ برنامه بهِ بستۀِ APK برگردد، نه بهِ خطایِ بی‌بسته.
    lsDel(POINTER_KEY);
  }
  // مهاجرت: دورهای که فقط مُهرِ کهنه و کشِ `SNAPSHOT_URL` داشتند (schema v1، بی‌digest).
  const legacyCache = await openCache(CACHE_NAME);
  const legacyStamp = lsGet(STAMP_KEY) ?? '';
  if (!pointer && legacyCache && legacyStamp && (!BUNDLE_STAMP || legacyStamp > BUNDLE_STAMP)) {
    const hit = await legacyCache.match(SNAPSHOT_URL);
    if (hit) {
      bootTiming.source = 'cache';
      const buf = await hit.arrayBuffer();
      emitDownloadProgress('cache', buf.byteLength, buf.byteLength);
      return buf;
    }
    // مهر هست و بسته نیست (کشِ دورِ پیش پاک شده) — مهر را هم بردار
    await dropCachedSnapshot(legacyCache);
  }

  // ۲) بستۀ همراهِ APK. دیگر درِ Cache API ذخیره نمی‌شود: رویِ گوشی هست،
  // خواندنش از asset بی‌شبکه است، و یک‌برگِ ۱۵ مگابایتیِ اضافه فقط حافظه
  // وِ گوشی را می‌گیرد و بعداً دادهٔ کهنه می‌شود.
  let local: Response | null = null;
  let localWhy = '';
  try {
    local = await fetch(SNAPSHOT_URL);
    if (!local.ok) { localWhy = `HTTP ${local.status}`; local = null; }
  } catch (e) {
    localWhy = e instanceof Error ? e.message : String(e);
  }

  if (local) {
    const buf = await responseArrayBufferWithProgress(local, 'bundle');
    if (isGz(buf, 2)) {
      bootTiming.source = 'bundle';
      // اگر دورِ پیش چیزی درِ کشِ کهنه بود، حالا خودِ برنامه مرجع است و برگۀ
      // کهنه‌اش باید برود — هم ۱۵ مگابایتِ حافظه آزاد می‌شود هم دادهٔ کهنه.
      if (legacyCache && legacyStamp) await dropCachedSnapshot(legacyCache);
      return buf;
    }
    localWhy = 'بستۀ همراهِ برنامه gz نبود';
  }

  // ۳) پشتیبان: ریلیز، ولی از همۀِ گام‌هایِ اعتبارسنجیِ یکِ «بررسی» می‌گذرد:
  // manifest ← staging ← اندازه+digest ← gunzip+بازگشایی SQLite ← pointer.
  // اگر همان لحظه بسته لازم است (نصبِ بی‌بسته)، پس از فعال‌سازی از staging خوانده
  // می‌شود؛ اگر هر گام شکست بخورد، پیامِ زیر می‌آید و هیچ نسخۀِ سالمی حذف نشده.
  const mf = await fetchSignedManifest();
  if (!mf.ok) {
    throw new HttpError(
      0,
      SNAPSHOT_URL,
      `بستهٔ دادهٔ آفلاین درِ برنامه نبود و manifest هم خوانده نشد (${localWhy || mf.detail}). `
      + 'یک‌بار با اینترنتِ متصل باز کنید.',
    );
  }
  emitDownloadProgress('release', 0, 0);
  const staged = await downloadToStaging(mf.value);
  if (!staged.ok) {
    await dropRejectedCandidate(mf.value);
    throw new HttpError(0, SNAPSHOT_URL,
      `بستۀِ داده رد شد: ${staged.detail}. نسخهٔ پیشینِ برنامه دست‌نخورده مانده است.`);
  }
  const act = await activate(staged.key, mf.value);
  if (!act.ok) {
    throw new HttpError(0, SNAPSHOT_URL, `فعال‌سازی نشد: ${act.detail}`);
  }
  noteSuccess(`فعال شد (راه‌اندازی): ${mf.value.package_id}`);
  await retainPackages();
  const staging = await openCache(STAGING_CACHE_NAME);
  const again = staging ? await staging.match(staged.key) : undefined;
  if (!again) {
    throw new HttpError(0, SNAPSHOT_URL, 'بستۀ فعال‌شده درِ حافظهٔ موقت پیدا نشد');
  }
  const buf = await again.arrayBuffer();
  bootTiming.source = 'release';
  emitDownloadProgress('release', buf.byteLength, buf.byteLength);
  return buf;
}

async function gunzip(buf: ArrayBuffer): Promise<Uint8Array> {
  const head = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
  // اگر CDN/سرور خودش Content-Encoding زده باشد، مرورگر از قبل بازش کرده و
  // بایت‌ها دیگر gzip نیستند (جادویی 1f 8b) — دوباره باز کردن یعنی خطا.
  if (head.length < 2 || head[0] !== 0x1f || head[1] !== 0x8b) {
    return new Uint8Array(buf);
  }
  // WebViewهای قدیمی‌تر (کروم < ۸۰) DecompressionStream ندارند — بدون این
  // جایگزین، دیتابیس هرگز باز نمی‌شد و همهٔ تب‌ها خالی می‌ماند.
  if (typeof DecompressionStream === 'function') {
    const ds = new DecompressionStream('gzip');
    const decompressed = new Response(new Blob([buf]).stream().pipeThrough(ds));
    return new Uint8Array(await decompressed.arrayBuffer());
  }
  const { gunzipSync } = await import('fflate');
  return gunzipSync(new Uint8Array(buf));
}

/**
 * خطای مرگبار بارگذاری داده را به‌جای صفحهٔ بی‌صدا خالی، به کاربر نشان می‌دهد
 * (برای عیب‌یابی نصب اول روی گوشی حیاتی است — «همه بدون داده» یعنی همین‌جا).
 */
export const __showFatalBannerForTest = (m: string): void => showFatalBanner(m);

function showFatalBanner(message: string): void {
  try {
    if (document.getElementById('bors-fatal-banner')) return;
    const el = document.createElement('div');
    el.id = 'bors-fatal-banner';
    el.dir = 'rtl';
    // چیدمان در mobile.css است، نه inline — مهم‌ترینش padding-topِ
    // safe-area: بی‌آن بنر زیرِ نوارِ وضعیتِ اندروید می‌رود و متنش با ساعت
    // و باتری قاطی می‌شود، دقیقاً چیزی که رویِ گوشیِ مالک دیده شد.
    el.className = 'bors-fatal-banner';
    const txt = document.createElement('span');
    txt.textContent = `⛔ بارگذاری بستهٔ دادهٔ آفلاین شکست خورد: ${message}`;
    el.appendChild(txt);

    // دکمهٔ تلاشِ دوباره. بی‌این، تنها راهِ کاربر بستن و بازکردنِ اپ بود —
    // و چون dbPromise کش شده، حتی آن هم همیشه جواب نمی‌داد.
    // این‌جا دیگر **کلِ کش پاک نمی‌شود**: پاک‌کردنِ کشِ کامل، تنها نسخۀِ سالم را
    // هم از بین می‌برد و بستۀِ ۲۲ مگابایتی را دوباره دانلود می‌کرد. فقط promise
    // بازنشسته می‌شود و شمارندهٔ backoff آزاد می‌گردد تا تلاشِ واقعی تکرار شود.
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'تلاش دوباره';
    btn.onclick = () => {
      btn.disabled = true;
      btn.textContent = 'در حال تلاش…';
      void (async () => {
        try { localStorage.removeItem(FAILS_KEY); } catch { /* مهم نیست */ }
        try { localStorage.removeItem(NEXT_TRY_KEY); } catch { /* مهم نیست */ }
        dbPromise = null;
        location.reload();
      })();
    };
    el.appendChild(btn);
    document.body.appendChild(el);
  } catch { /* حتی بنر هم نشد — دستِ‌کم خطا در کنسول هست */ }
}

/** زمان‌بندیِ راه‌اندازی — پنلِ عیب‌یابیِ 🛠 نشانش می‌دهد.
 *
 *  چرا ثبت می‌شود: هر بار باز کردنِ اپ یعنی گشودنِ ۲۲ مگابایت gzip و
 *  ساختنِ یک دیتابیسِ چندده‌مگابایتی در حافظه. کدامش گران است را از
 *  اینجا نمی‌شود حدس زد — گوشیِ کاربر باید بگوید. بی‌عدد، هر
 *  «بهینه‌سازی»ای تیر در تاریکی است.
 */
export const bootTiming: {
  source: 'cache' | 'bundle' | 'release' | '';
  gzBytes: number;
  rawBytes: number;
  fetchMs: number;
  gunzipMs: number;
  openMs: number;
  totalMs: number;
} = { source: '', gzBytes: 0, rawBytes: 0, fetchMs: 0, gunzipMs: 0, openMs: 0, totalMs: 0 };

let dbPromise: Promise<Database> | null = null;
let sqlPromise: Promise<Awaited<ReturnType<typeof initSqlJs>>> | null = null;

/** همان sql.js که مصرف‌کنندهٔ واقعی استفاده می‌کند — اعتبارسنجیِ بسته با
 *  **همین** موتور انجام می‌شود، نه با یک شبیه‌سازِ دیگر. */
function getSql() {
  sqlPromise ??= initSqlJs({ locateFile: () => wasmUrl });
  return sqlPromise;
}

/** شیارِ آزمون: کاوشگرِ واقعی sql.js درِ jsdom سنگین و بی‌نیاز است؛ تست‌ها کاوشگرِ
 *  خودشان را می‌گذارند تا «بازگشاییِ ناموفق/جدولِ کم» را بسنجند. درِ تولید این هرگز
 *  صدا زده نمی‌شود و sqlProbe باقی می‌ماند. */
export const __setDbProbeForTest = (p: DbProbe | null): void => { probeOverride = p; };
let probeOverride: DbProbe | null = null;
const activeProbe = (): DbProbe => probeOverride ?? sqlProbe;

/** کاوشگرِ ساختار: جدول‌ها، کلیدهایِ پختۀِ لازم، و meta. هیچِ آستانۀِ ردیفی ندارد. */
const sqlProbe: DbProbe = async (bytes) => {
  const SQL = await getSql();
  const db = new SQL.Database(bytes);
  const tables = new Set<string>(
    (db.exec("SELECT name FROM sqlite_master WHERE type='table'")[0]?.values ?? [])
      .map((r) => String(r[0])),
  );
  return {
    tables,
    hasRow(table, keyColumn, key) {
      if (!tables.has(table)) return false;
      const r = db.exec(`SELECT 1 FROM "${table}" WHERE ${keyColumn} = ? LIMIT 1`, [key]);
      return (r[0]?.values?.length ?? 0) > 0;
    },
    metaValue(key) {
      if (!tables.has('meta')) return null;
      const r = db.exec('SELECT value FROM meta WHERE key = ? LIMIT 1', [key]);
      const v = r[0]?.values?.[0]?.[0];
      return typeof v === 'string' ? v : null;
    },
    close() { db.close(); },
  };
};

/** دیتابیس اسنپ‌شات — singleton؛ اولین فراخوانی دانلود/بازگشایی می‌کند */
export function getDb(): Promise<Database> {
  dbPromise ??= (async () => {
    const t0 = performance.now();
    const [SQL, gz] = await Promise.all([
      getSql(),
      fetchSnapshot(),
    ]);
    const t1 = performance.now();
    const gzSource = bootTiming.source;
    emitBootProgress(makeBootProgress('decompress', gzSource, 0, 0));
    const bytes = await gunzip(gz);
    emitBootProgress(makeBootProgress('decompress', gzSource, 1, 1));
    const t2 = performance.now();
    emitBootProgress(makeBootProgress('database', gzSource, 0, 0));
    const db = new SQL.Database(bytes);
    emitBootProgress(makeBootProgress('database', gzSource, 1, 1));
    const t3 = performance.now();
    bootTiming.gzBytes = gz.byteLength;
    bootTiming.rawBytes = bytes.byteLength;
    bootTiming.fetchMs = Math.round(t1 - t0);
    bootTiming.gunzipMs = Math.round(t2 - t1);
    bootTiming.openMs = Math.round(t3 - t2);
    bootTiming.totalMs = Math.round(t3 - t0);
    Object.assign(window, { bootTiming });
    // اگر بسته از ریلیز آمد و درِ کش نشست، مهرش را از خودِ دیتابیس خواندن:
    // اجرایِ بعدی باید بداند کش از بستۀ همراهِ APK تازه‌تر است.
    if (bootTiming.source === 'release') {
      const built = db.exec("SELECT value FROM meta WHERE key='built_at'")[0]?.values?.[0]?.[0];
      if (typeof built === 'string' && built) {
        try { localStorage.setItem(STAMP_KEY, built); } catch { /* مهم نیست */ }
      }
    }
    // چکِ بروزرسانی در پس‌زمینه — نه await می‌شود نه خطایش به UI می‌رسد
    setTimeout(() => { void maybeRefreshSnapshot(); }, 15000);
    return db;
  })().catch((e: unknown) => {
    // بدون این بنر، هر تب فقط «بی‌داده» می‌ماند و کاربر سرنخی ندارد؛
    // dbPromise هم ریست می‌شود تا اجرای بعدیِ برنامه دوباره تلاش کند.
    // بازیابیِ امن: اگر خواندن از **pointerِ فعال** شکست خورد (کشِ نیمه، نوشتنِ
    // قطع‌شده، SQLite خراب)، pointer برداشته می‌شود تا راه‌اندازیِ بعدی بهِ بستۀِ
    // همراهِ APK برگردد. هیچ‌گاه بستۀِ APK یا stagingِ سالمِ دیگر پاک نمی‌شود.
    if (readPointer()) {
      lsDel(POINTER_KEY);
      lsDel(STAMP_KEY);
    }
    showFatalBanner(e instanceof Error ? `${e.name}: ${e.message}` : String(e));
    dbPromise = null;
    throw e;
  });
  return dbPromise;
}

/** کوئری خام — خروجی: آرایهٔ آبجکت (نام ستون → مقدار) */
export async function query(
  sql: string,
  params: (string | number)[] = [],
): Promise<Record<string, unknown>[]> {
  const db = await getDb();
  const stmt = db.prepare(sql);
  try {
    stmt.bind(params);
    const rows: Record<string, unknown>[] = [];
    while (stmt.step()) rows.push(stmt.getAsObject());
    return rows;
  } finally {
    stmt.free();
  }
}

/** بستهٔ JSON پخته‌شده؛ null یعنی این کلید در اسنپ‌شات نیست */
export async function baked(key: string): Promise<unknown | null> {
  const rows = await query('SELECT json FROM baked WHERE key = ?', [key]);
  const raw = rows[0]?.json;
  if (typeof raw !== 'string') return null;
  return JSON.parse(raw) as unknown;
}

/** متادیتای اسنپ‌شات (app_version / built_at / …) */
export async function metaValue(key: string): Promise<string | null> {
  const rows = await query('SELECT value FROM meta WHERE key = ?', [key]);
  const v = rows[0]?.value;
  return typeof v === 'string' ? v : null;
}

/** نرمال‌سازی نویسه‌های عربی↔فارسی — همتای sym_pred بک‌اند (ك→ک، ي→ی) */
export function normFa(s: string): string {
  return s.replace(/ي/g, 'ی').replace(/ك/g, 'ک').trim();
}
