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

const SNAPSHOT_URL =
  (import.meta.env.VITE_SNAPSHOT_URL as string | undefined) ?? '/mobile_snapshot.db.gz';
const CACHE_NAME = 'bors-mobile-snapshot-v1';

// --- بروزرسانی خودکار داده از GitHub Releases (بدون سرور، بدون هزینه) -----
// یک بار در روز metaی کوچک (~۲۰۰ بایت) چک می‌شود؛ اگر built_at جدیدتر بود،
// gz کامل در پس‌زمینه دانلود و در Cache API جایگزین می‌شود — از اجرای بعدی
// برنامه دادهٔ تازه بار می‌شود (اجرای جاری دست‌نخورده می‌ماند).
const REMOTE_BASE =
  (import.meta.env.VITE_SNAPSHOT_REMOTE as string | undefined) ??
  'https://github.com/johnwarchief/BorsTerminal-src/releases/latest/download';
const REMOTE_META_URL = `${REMOTE_BASE}/mobile_snapshot.db.meta.json`;
const REMOTE_GZ_URL = `${REMOTE_BASE}/mobile_snapshot.db.gz`;
const CHECK_KEY = 'bors_snapshot_check_at';
const CHECK_EVERY_MS = 24 * 3600 * 1000;

async function maybeRefreshSnapshot(): Promise<void> {
  try {
    const lastCheck = Number(localStorage.getItem(CHECK_KEY) ?? 0);
    if (Date.now() - lastCheck < CHECK_EVERY_MS) return;
    localStorage.setItem(CHECK_KEY, String(Date.now()));
    const metaRes = await fetch(REMOTE_META_URL);
    if (!metaRes.ok) return; // ریلیزی با بستهٔ داده هنوز منتشر نشده
    const meta = (await metaRes.json()) as { built_at?: string };
    const remoteBuilt = String(meta.built_at ?? '');
    if (!remoteBuilt) return;
    const localBuilt = (await metaValue('built_at')) ?? '';
    if (remoteBuilt <= localBuilt) return; // همین دادهٔ فعلی یا قدیمی‌تر
    const gzRes = await fetch(REMOTE_GZ_URL);
    if (!gzRes.ok) return;
    const buf = await gzRes.arrayBuffer();
    // sanity: gz معتبر و به‌قدر کافی بزرگ باشد (صفحهٔ خطای HTML جایگزین نشود)
    const head = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
    if (buf.byteLength < 1_000_000 || head[0] !== 0x1f || head[1] !== 0x8b) return;
    const cache = await caches.open(CACHE_NAME);
    await cache.put(SNAPSHOT_URL, new Response(buf));
  } catch { /* آفلاین/Cache API غایب — دفعهٔ بعد دوباره تلاش می‌شود */ }
}

async function fetchSnapshot(): Promise<ArrayBuffer> {
  // Cache API: دانلود ~۱۵MB فقط یک‌بار در عمر نصب؛ تازه‌سازی = پاک کردن کش
  // (دکمهٔ «بروزرسانی داده» بعداً همین کش را حذف و دوباره دانلود می‌کند).
  let cache: Cache | null = null;
  try {
    cache = await caches.open(CACHE_NAME);
    const hit = await cache.match(SNAPSHOT_URL);
    if (hit) return await hit.arrayBuffer();
  } catch {
    cache = null; // Cache API در برخی WebViewها نیست — مستقیم دانلود کن
  }
  const res = await fetch(SNAPSHOT_URL);
  if (!res.ok) {
    throw new HttpError(res.status, SNAPSHOT_URL, 'دانلود بستهٔ دادهٔ آفلاین ناموفق بود');
  }
  if (cache) {
    try {
      await cache.put(SNAPSHOT_URL, res.clone());
    } catch {
      /* جای کافی نبود — فقط از همین پاسخ استفاده کن */
    }
  }
  return res.arrayBuffer();
}

async function gunzip(buf: ArrayBuffer): Promise<Uint8Array> {
  const head = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
  // اگر CDN/سرور خودش Content-Encoding زده باشد، مرورگر از قبل بازش کرده و
  // بایت‌ها دیگر gzip نیستند (جادویی 1f 8b) — دوباره باز کردن یعنی خطا.
  if (head.length < 2 || head[0] !== 0x1f || head[1] !== 0x8b) {
    return new Uint8Array(buf);
  }
  const ds = new DecompressionStream('gzip');
  const decompressed = new Response(new Blob([buf]).stream().pipeThrough(ds));
  return new Uint8Array(await decompressed.arrayBuffer());
}

let dbPromise: Promise<Database> | null = null;

/** دیتابیس اسنپ‌شات — singleton؛ اولین فراخوانی دانلود/بازگشایی می‌کند */
export function getDb(): Promise<Database> {
  dbPromise ??= (async () => {
    const [SQL, gz] = await Promise.all([
      initSqlJs({ locateFile: () => wasmUrl }),
      fetchSnapshot(),
    ]);
    const bytes = await gunzip(gz);
    const db = new SQL.Database(bytes);
    // چکِ بروزرسانی در پس‌زمینه — نه await می‌شود نه خطایش به UI می‌رسد
    setTimeout(() => { void maybeRefreshSnapshot(); }, 15000);
    return db;
  })();
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
