// shared/api/local/snapshotPackage.ts — قراردادِ بستهٔ دادهٔ آفلاین (Stage 3)
//
// چرا فایلِ جدا: «چه چیزی یکِ بسته را سالم می‌کند» باید یکِ جایِ قابل‌آزمون باشد،
// نه پخش‌شده درِ جریانِ دانلودِ localData.ts. localData تصمیمِ *زمان‌بندی* می‌گیرد و
// این فایل تصمیمِ *صحت* را.
//
// سه تضمین، سه چیزِ متفاوت (نباید یکی خوانده شوند):
//   ۱) `verifyBytes()`  — اندازه و SHA-256 ⇒ تشخیصِ خرابیِ تصادفی و انتقالِ ناقص.
//   ۲) `validateDatabase()` — بازگشایی SQLite، جدول‌ها، کلیدهایِ پختۀِ لازم ⇒ ساختار
//      و قراردادِ نسخه.
//   ۳) اصالتِ ناشر — **این‌جا هیچ ادعایی نیست**. SHA-256 بی‌کلیدِ عمومیِ مستقل امضا
//      نیست؛ هرکس که مسیرِ دانلود را عوض کند می‌تواند manifest را هم با بستهٔ خودش
//      بسازد. افزودنِ امضا یکِ تصمیمِ معماری است (گزارشِ Stage 3)، نه چیزی که اینجا
//      ساکت اضافه شود.
//
// digest بی‌دورِ باطل: manifest فایلِ **جدا**یی است (`mobile_snapshot.db.meta.json`)
// و sha256 روی بایت‌های همان `mobile_snapshot.db.gz` گرفته می‌شود؛ پس هیچ فایلی
// خودش را هش نمی‌کند. ترتیبِ مصرف: دانلود ← اندازه+digest ← gunzip/بازگشایی ← فعال‌سازی.

/** نسخۀ قراردادی که این کلاینت می‌پذیرد. هر چیزِ دیگر ⇒ رد (نه پذیرشِ بی‌آزمون). */
export const ACCEPTED_MANIFEST_SCHEMA = 2;

export type SnapshotManifest = {
  schema_version: number;
  package_id: string;
  app_version: string;
  min_app_version: string;
  built_at: string;
  gz_bytes: number;
  gz_sha256: string;
  db_bytes?: number;
  baked_ok?: number;
  baked_fail?: number;
  tables?: string[];
  required_baked_keys?: string[];
  /** چیدمانِ دیتابیسِ بسته (درِ جدول `meta` به‌همین نام نوشته می‌شود). با
   *  `schema_version` یکی نیست: آن نسخۀ *قراردادِ manifest* است، این نسخۀ *فایلِ
   *  SQLite*. اگر سازنده هر دو را بفرستد، کلاینت مقایسه می‌کند. */
  db_schema?: number;
  /** سریِ انتشاری که این بسته برایش پخته شده (`mobile-latest` = کهنه،
   *  `mobile-latest-v2` = سریِ امضاشدۀ v2). انتخابِ سری باید **صریح** باشد، نه
   *  حدس از URL یا نسخۀ مبهم: کلاینتی که برای یک سری بیلد شده، بستۀ سریِ دیگر
   *  را رد می‌کند — وگرنه یکِ اشتباه درِ مسیرِ ریلیز، دادۀِ نسلِ دیگر را رویِ
   *  گوشی می‌نشاند. */
  series?: string;
};

export type RejectReason =
  | 'manifest-missing' | 'manifest-unparsable' | 'manifest-schema-unknown'
  | 'manifest-field-missing' | 'app-version-too-low'
  | 'size-mismatch' | 'digest-missing-on-device' | 'digest-mismatch'
  | 'not-gzip' | 'gunzip-failed' | 'db-open-failed' | 'table-missing'
  | 'baked-key-missing' | 'meta-missing' | 'storage-unavailable' | 'storage-full'
  | 'db-schema-mismatch' | 'series-mismatch' | 'series-unknown';

export type Check<T> = { ok: true; value: T } | { ok: false; reason: RejectReason; detail: string };

const bad = (reason: RejectReason, detail: string): Check<never> => ({ ok: false, reason, detail });

/** manifest را می‌خواند و *ساختارِ* لازم را می‌سنجد. هیچ فیلدِ غایبی جایگزین نمی‌شود. */
export function parseManifest(raw: unknown): Check<SnapshotManifest> {
  if (raw === null || raw === undefined) return bad('manifest-missing', 'پاسخِ manifest خالی بود');
  if (typeof raw !== 'object') return bad('manifest-unparsable', `نوعِ manifest: ${typeof raw}`);
  const m = raw as Record<string, unknown>;
  const sv = Number(m.schema_version);
  if (!Number.isFinite(sv)) return bad('manifest-field-missing', 'schema_version نیست');
  if (sv !== ACCEPTED_MANIFEST_SCHEMA) {
    return bad('manifest-schema-unknown', `schema_version=${sv}؛ این کلاینت ${ACCEPTED_MANIFEST_SCHEMA} می‌خواهد`);
  }
  for (const k of ['package_id', 'built_at', 'gz_sha256', 'app_version', 'min_app_version'] as const) {
    if (typeof m[k] !== 'string' || !m[k]) return bad('manifest-field-missing', `${k} نیست`);
  }
  const gzBytes = Number(m.gz_bytes);
  if (!Number.isInteger(gzBytes) || gzBytes <= 0) return bad('manifest-field-missing', 'gz_bytes درست نیست');
  if (!/^[0-9a-f]{64}$/i.test(String(m.gz_sha256))) return bad('manifest-field-missing', 'gz_sha256 شکلِ sha256 ندارد');
  return { ok: true, value: m as unknown as SnapshotManifest };
}

/** بسته باید برای همين سریِ انتشاری باشد که کلاینت برایش بیلد شده.
 *  `bakedSeries` خالی = بیلد محلی/بی‌سری ⇒ داوری نمی‌شود (نه پذیرشِ بی‌معنای
 *  هر چیزِ دیگر: سازنده هم همیشه سری را می‌نویسد، پس بسته‌ای که سری ندارد از
 *  سازندۀ کهنه آمده و با `series-unknown` رد می‌شود). */
export function checkSeries(m: SnapshotManifest, bakedSeries: string):
  Check<SnapshotManifest> {
  if (!bakedSeries) return { ok: true, value: m };
  if (typeof m.series !== 'string' || !m.series) {
    return bad('series-unknown', 'manifest سریِ انتشار را ندارد؛ این بسته از '
      + 'سازندۀ بی‌قراردادِ v2 آمده و برای این بیلد تأیید نشده است');
  }
  if (m.series !== bakedSeries) {
    return bad('series-mismatch', `series=${m.series} در برابرِ سریِ همراهِ برنامه (${bakedSeries})`);
  }
  return { ok: true, value: m };
}

/** مقایسۀ نسخۀ جلالیِ «۱۴۵/۰/۱۳…» نه — نسخه‌های نقطه‌چینِ اپ (APP_VERSION). */
export function versionAtLeast(have: string, need: string): boolean {
  const p = (s: string) => String(s || '').split('.').map((x) => parseInt(x, 10)).filter((x) => Number.isFinite(x));
  const a = p(have); const b = p(need);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] ?? 0; const y = b[i] ?? 0;
    if (x > y) return true;
    if (x < y) return false;
  }
  return true;
}

/** SHA-256 با WebCrypto. اگر نبود، `null` — و فراخوان **باید** رد کند (fail-closed). */
export async function sha256Hex(buf: ArrayBuffer): Promise<string | null> {
  const subtle = (globalThis.crypto as Crypto | undefined)?.subtle;
  if (!subtle) return null;
  try {
    const d = await subtle.digest('SHA-256', buf);
    return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
  } catch {
    return null;
  }
}

/** تضمینِ ۱: اندازه و digest روی همان بایت‌هایی که دانلود/ذخیره شده‌اند. */
export async function verifyBytes(buf: ArrayBuffer, m: SnapshotManifest): Promise<Check<ArrayBuffer>> {
  if (buf.byteLength !== m.gz_bytes) {
    return bad('size-mismatch', `انتظار ${m.gz_bytes}، دریافت ${buf.byteLength} بایت`);
  }
  const head = new Uint8Array(buf, 0, 2);
  if (head.length < 2 || head[0] !== 0x1f || head[1] !== 0x8b) {
    return bad('not-gzip', 'دو بایتِ اول امضای gzip نیست (صفحهٔ خطا/HTML جای بسته را گرفته؟)');
  }
  const got = await sha256Hex(buf);
  if (got === null) {
    return bad('digest-missing-on-device', 'crypto.subtle در دسترس نیست؛ بی‌digest فعال نمی‌شود');
  }
  if (got.toLowerCase() !== m.gz_sha256.toLowerCase()) {
    return bad('digest-mismatch', `sha256 نخواند: ${got.slice(0, 12)}… در برابرِ ${m.gz_sha256.slice(0, 12)}…`);
  }
  return { ok: true, value: buf };
}

/** چیزی که یکِ SQLite بازِ سالم را برایِ مصرفِ واقعیِ گوشی تعریف می‌کند.
 *  جدول‌ها و کلیدها از `resolvers.ts` و `build_mobile_snapshot.py` گرفته شده‌اند،
 *  نه از حدس: تعدادِ ردیف یا آستانهٔ حجمی اینجا هیچ نقشی ندارد. */
export type DbProbe = (bytes: Uint8Array) => Promise<{
  tables: Set<string>;
  hasRow(table: string, keyColumn: string, key: string): boolean;
  metaValue(key: string): string | null;
  close?(): void;
}>;

/** تضمینِ ۲: ساختار و قراردادِ نسخه. */
export async function validateDatabase(bytes: Uint8Array, m: SnapshotManifest, probe: DbProbe):
  Promise<Check<{ built_at: string }>> {
  let db: Awaited<ReturnType<DbProbe>>;
  try {
    db = await probe(bytes);
  } catch (e) {
    return bad('db-open-failed', e instanceof Error ? e.message : String(e));
  }
  try {
    const want = m.tables?.length ? m.tables : ['baked', 'meta', 'instruments', 'price_history'];
    for (const t of want) {
      if (!db.tables.has(t)) return bad('table-missing', `جدولِ ${t} در بسته نیست`);
    }
    for (const k of m.required_baked_keys ?? ['market_board']) {
      if (!db.hasRow('baked', 'key', k)) return bad('baked-key-missing', `کلیدِ پختۀ ${k} در بسته نیست`);
    }
    const built = db.metaValue('built_at');
    if (!built) return bad('meta-missing', 'meta.built_at نیست');
    // چیدمانِ فایلِ SQLite با چیزی که manifest می‌گوید باید یکی باشد. بی‌این،
    // «contract v2» می‌توانست بسته‌ای با چیدمانِ دیگری را بپذیرد و گوشی تا
    // بازگشاییِ بعدی بفهمد. نبودش (بستۀ سازندۀ کهنه) داوری را عوض نمی‌کند.
    const schema = db.metaValue('schema');
    if (m.db_schema !== undefined && schema !== null
        && String(m.db_schema) !== String(schema)) {
      return bad('db-schema-mismatch',
        `meta.schema=${schema} در برابرِ db_schema=${m.db_schema} درِ manifest`);
    }
    if (schema !== null && m.schema_version && Number(schema) > 99) {
      return bad('manifest-schema-unknown', `meta.schema=${schema} غیرمنتظره است`);
    }
    return { ok: true, value: { built_at: built } };
  } finally {
    try { db.close?.(); } catch { /* بستن نشد، رأیِ اعتبارسنجی عوض نمی‌شود */ }
  }
}

/** وضعیتِ فعال‌شده — همان چیزی که درِ localStorage به‌عنوان «مرجع» می‌نشیند. */
export type ActivePointer = {
  cacheKey: string;
  packageId: string;
  builtAt: string;
  sha256: string;
  activatedAt: number;
  schema: number;
};

export function parsePointer(raw: string | null): ActivePointer | null {
  if (!raw) return null;
  try {
    const p = JSON.parse(raw) as Partial<ActivePointer>;
    if (typeof p.cacheKey !== 'string' || !p.cacheKey) return null;
    if (typeof p.sha256 !== 'string' || !/^[0-9a-f]{64}$/i.test(p.sha256)) return null;
    if (typeof p.builtAt !== 'string' || !p.builtAt) return null;
    if (p.schema !== ACCEPTED_MANIFEST_SCHEMA) return null;   // pointerِ دورۀ پیشین ⇒ بازنشستگی
    return p as ActivePointer;
  } catch {
    return null;
  }
}
