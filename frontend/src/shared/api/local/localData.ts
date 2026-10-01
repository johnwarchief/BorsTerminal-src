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
import { nativeGetBytes, nativeGetJson } from './nativeHttp';

const SNAPSHOT_URL =
  (import.meta.env.VITE_SNAPSHOT_URL as string | undefined) ?? '/mobile_snapshot.db.gz';
const CACHE_NAME = 'bors-mobile-snapshot-v1';

// --- بروزرسانی خودکار داده از GitHub Releases (بدون سرور، بدون هزینه) -----
// یک بار در روز metaی کوچک (~۲۰۰ بایت) چک می‌شود؛ اگر built_at جدیدتر بود،
// gz کامل در پس‌زمینه دانلود و در Cache API جایگزین می‌شود — از اجرای بعدی
// برنامه دادهٔ تازه بار می‌شود (اجرای جاری دست‌نخورده می‌ماند).
// تگ ثابت «mobile-latest» (pre-release غلتان که CI با هر بیلد تازه می‌کند) —
// عمداً نه releases/latest، تا ریلیزهای رسمی دسکتاپ مالک دست‌نخورده بمانند.
const REMOTE_BASE =
  (import.meta.env.VITE_SNAPSHOT_REMOTE as string | undefined) ??
  'https://github.com/johnwarchief/BorsTerminal-src/releases/download/mobile-latest';
const REMOTE_META_URL = `${REMOTE_BASE}/mobile_snapshot.db.meta.json`;
const REMOTE_GZ_URL = `${REMOTE_BASE}/mobile_snapshot.db.gz`;
const CHECK_KEY = 'bors_snapshot_check_at';
const CHECK_EVERY_MS = 24 * 3600 * 1000;

async function maybeRefreshSnapshot(): Promise<void> {
  try {
    const lastCheck = Number(localStorage.getItem(CHECK_KEY) ?? 0);
    if (Date.now() - lastCheck < CHECK_EVERY_MS) return;
    localStorage.setItem(CHECK_KEY, String(Date.now()));
    // درگاه بومی: داخل اپ اندروید بدون دیوار CORS؛ در مرورگر fetch معمولی
    const meta = (await nativeGetJson(REMOTE_META_URL)) as { built_at?: string } | null;
    if (!meta) return; // ریلیزی با بستهٔ داده هنوز منتشر نشده / آفلاین
    const remoteBuilt = String(meta.built_at ?? '');
    if (!remoteBuilt) return;
    const localBuilt = (await metaValue('built_at')) ?? '';
    if (remoteBuilt <= localBuilt) return; // همین دادهٔ فعلی یا قدیمی‌تر
    const buf = await nativeGetBytes(REMOTE_GZ_URL);
    if (!buf) return;
    // sanity: gz معتبر و به‌قدر کافی بزرگ باشد (صفحهٔ خطای HTML جایگزین نشود)
    const head = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
    if (buf.byteLength < 1_000_000 || head[0] !== 0x1f || head[1] !== 0x8b) return;
    const cache = await caches.open(CACHE_NAME);
    await cache.put(SNAPSHOT_URL, new Response(buf));
  } catch { /* آفلاین/Cache API غایب — دفعهٔ بعد دوباره تلاش می‌شود */ }
}

/** فقط برایِ تست — مسیرِ بارگذاریِ بسته و راهِ دومش. */
export const __fetchSnapshotForTest = (): Promise<ArrayBuffer> => fetchSnapshot();

async function fetchSnapshot(): Promise<ArrayBuffer> {
  // Cache API: دانلود ~۱۵MB فقط یک‌بار در عمر نصب؛ تازه‌سازی = پاک کردن کش
  // (دکمهٔ «بروزرسانی داده» بعداً همین کش را حذف و دوباره دانلود می‌کند).
  let cache: Cache | null = null;
  try {
    cache = await caches.open(CACHE_NAME);
    const hit = await cache.match(SNAPSHOT_URL);
    if (hit) { bootTiming.source = 'cache'; return await hit.arrayBuffer(); }
  } catch {
    cache = null; // Cache API در برخی WebViewها نیست — مستقیم دانلود کن
  }
  // ۱) بستهٔ همراهِ APK (مسیر عادی — بی‌نیاز به شبکه)
  let local: Response | null = null;
  let localWhy = '';
  try {
    local = await fetch(SNAPSHOT_URL);
    if (!local.ok) { localWhy = `HTTP ${local.status}`; local = null; }
  } catch (e) {
    localWhy = e instanceof Error ? e.message : String(e);
  }

  // ۲) پشتیبان: همان بسته از ریلیزِ mobile-latest.
  //
  // چرا لازم شد: تا پیش از این اگر فایلِ درونِ APK به هر دلیلی باز نمی‌شد —
  // بیلدی که بسته در آن جا نیفتاده، نصبِ ناقص، یا WebViewای که فایلِ ۲۲
  // مگابایتی را از سرورِ مجازیِ خودش نمی‌دهد — اپ کاملاً می‌مرد: یک نوارِ
  // قرمز و همهٔ کارت‌ها «بدون داده». در حالی که همان بسته روی ریلیز هست و
  // کدِ دانلودش (nativeGetBytes) هم از قبل برای بروزرسانیِ روزانه نوشته
  // شده بود؛ فقط به‌عنوانِ راهِ دومِ بارگذاریِ اول وصل نبود.
  if (!local) {
    try {
      const buf = await nativeGetBytes(REMOTE_GZ_URL);
      // همان وارسیِ بروزرسانیِ روزانه: gz معتبر و به‌قدرِ کافی بزرگ، تا
      // صفحهٔ خطایِ HTML به‌جایِ دیتابیس ذخیره نشود.
      if (buf && buf.byteLength >= 1_000_000) {
        const h = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
        if (h[0] === 0x1f && h[1] === 0x8b) {
          if (cache) {
            try { await cache.put(SNAPSHOT_URL, new Response(buf.slice(0))); } catch { /* جا نبود */ }
          }
          bootTiming.source = 'release';
          return buf;
        }
      }
    } catch { /* شبکه هم نبود — پیامِ زیر را می‌دهیم */ }
    throw new HttpError(
      0,
      SNAPSHOT_URL,
      `بستهٔ دادهٔ آفلاین نه در برنامه بود نه از اینترنت آمد (${localWhy || 'بدون پاسخ'}). `
      + 'یک‌بار با اینترنتِ متصل باز کنید تا بسته دانلود شود.',
    );
  }

  if (cache) {
    try {
      await cache.put(SNAPSHOT_URL, local.clone());
    } catch {
      /* جای کافی نبود — فقط از همین پاسخ استفاده کن */
    }
  }
  bootTiming.source = 'bundle';
  return local.arrayBuffer();
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
    // و چون dbPromise کش شده، حتی آن هم همیشه جواب نمی‌داد. اینجا کشِ بسته
    // و خودِ promise پاک می‌شوند تا واقعاً از نو تلاش شود.
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'تلاش دوباره';
    btn.onclick = () => {
      btn.disabled = true;
      btn.textContent = 'در حال تلاش…';
      void (async () => {
        try { await caches.delete(CACHE_NAME); } catch { /* کش نبود */ }
        try { localStorage.removeItem(CHECK_KEY); } catch { /* مهم نیست */ }
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

/** دیتابیس اسنپ‌شات — singleton؛ اولین فراخوانی دانلود/بازگشایی می‌کند */
export function getDb(): Promise<Database> {
  dbPromise ??= (async () => {
    const t0 = performance.now();
    const [SQL, gz] = await Promise.all([
      initSqlJs({ locateFile: () => wasmUrl }),
      fetchSnapshot(),
    ]);
    const t1 = performance.now();
    const bytes = await gunzip(gz);
    const t2 = performance.now();
    const db = new SQL.Database(bytes);
    const t3 = performance.now();
    bootTiming.gzBytes = gz.byteLength;
    bootTiming.rawBytes = bytes.byteLength;
    bootTiming.fetchMs = Math.round(t1 - t0);
    bootTiming.gunzipMs = Math.round(t2 - t1);
    bootTiming.openMs = Math.round(t3 - t2);
    bootTiming.totalMs = Math.round(t3 - t0);
    // چکِ بروزرسانی در پس‌زمینه — نه await می‌شود نه خطایش به UI می‌رسد
    setTimeout(() => { void maybeRefreshSnapshot(); }, 15000);
    return db;
  })().catch((e: unknown) => {
    // بدون این بنر، هر تب فقط «بی‌داده» می‌ماند و کاربر سرنخی ندارد؛
    // dbPromise هم ریست می‌شود تا اجرای بعدیِ برنامه دوباره تلاش کند.
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
