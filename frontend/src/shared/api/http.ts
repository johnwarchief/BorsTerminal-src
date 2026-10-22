import type { ZodType } from 'zod';

/** خطای یکدست HTTP — همیشه فارسی و قابل نمایش در UI */
export class HttpError extends Error {
  constructor(
    public status: number,
    public url: string,
    message?: string,
  ) {
    super(message ?? `خطای ${status} در دریافت ${url}`);
    this.name = 'HttpError';
  }
}

export interface HttpOptions {
  /** اعتبارسنجی پاسخ با اسکیمای Zod — سیگنال خراب هرگز به UI نمی رسد */
  schema?: ZodType;
  /** تعداد تلاش مجدد (فقط روی 429/403/5xx و خطای شبکه) */
  retries?: number;
  /** تاخیر پایهٔ backoff نمایی (میلی ثانیه) */
  baseDelayMs?: number;
  signal?: AbortSignal;
  /** متد HTTP — پیش‌فرض GET؛ POST برای ذخیرهٔ تنظیمات (B5 داخل http.ts مجاز است) */
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  /** بدنهٔ درخواست — همراه با method: 'POST' به صورت JSON ارسال می‌شود */
  body?: unknown;
  /**
   * بدینهٔ خام (Blob/ArrayBuffer/string) — مستقیماً و بدونِ JSON.stringify به
   * fetch داده می‌شود. کاربرد: بارگذاریِ باینری مثل نصب‌کنندهٔ آفلاین روی
   * /api/update/install-local (بدون نیاز به python-multipart).
   */
  rawBody?: BodyInit;
  /** هدرهای اضافه یا رونویسی (مثلاً Content-Type برای rawBody) */
  headers?: Record<string, string>;
  /**
   * بی‌کشِ اعتبارسنجی. برایِ آدرسهایی که *هر سیکل نویشان* دارند:
   * `/api/market/delta?since=REV` با کلیدِ آدرس‌محور درِ `conditional` یک
   * ورودیِ تازه می‌سازد و هیچ‌وقت به کار نمی‌آید (۳۰۴ ندارد) — یعنی نشتِ
   * حافظه‌ای که درِ نشستِ چهارساعته هزاران ردیفِ ۲۰۰-تایی نگه می‌دارد.
   */
  noCache?: boolean;
}

const RETRYABLE = new Set([403, 429, 500, 502, 503, 504]);

/**
 * کشِ اعتبارسنجیِ خودِ اپ (نه کشِ مرورگر): etagِ پاسخ + همان آبجکتِ تجزیه‌شده.
 * چرا: /api/market بدنهٔ ۷٫۳ مگابایتی دارد و تابلو در ساعتِ بازار هر ۵ ثانیه
 * آن را می‌خواهد، ولی سینکِ داده هر ~۳۰ ثانیه یک‌بار چیزی عوض می‌کند — یعنی
 * بیشترِ درخواست‌ها بدنهٔ *عیناً* قبلی را برمی‌گردانند. با If-None-Match سرور
 * ۳۰ می‌دهد (صفر بایت، صفر gzip) و اینجا همان آبجکتِ قبلی را برمی‌گرداند؛
 * چون مرجعِ داده عوض نمی‌شود، TanStack Query هیچ رندرِ تازه‌ای نسازد.
 * `cache: 'no-store'` لازم است وگرنه کشِ Chromium خودش پاسخِ ۲۰۰ِ کامل را
 * از دیسک بیرون می‌دهد و ما هیچ‌وقت ۳۰۴ را نمی‌بینیم.
 *
 * کلید این کش **آدرس + هویتِ اسکیمای zod** است، نه خودِ آدرس. یک URL را چند
 * مصرف‌کننده با چند اسکیمای مختلف می‌خواند (`/api/market` را تابلو کامل
 * می‌خواهد و `useMarketCloses` فقط {symbol, p_closing}); اسکیمای zod کلیدهای
 * ناشناخته را می‌کاهد، پس با کلیدِ فقط-آدرس، ۳۰۴ِ یک مصرف‌کننده آبجکتِ
 * *چروکیدهٔ* مصرف‌کنندۀ دیگر را برمی‌گرداند. شاهدِ زندهٔ ۱۴۰۵-۰۷-۰۶: درِ تبِ
 * درخت استراتژی، قیف «1193 نماد زنده ← 0 نشانه» می‌داد و همان لحظه
 * /api/market پرچم‌ها را با 128 ردیف می‌فرستاد — چون `useMarketCloses` زودتر
 * از `useMarketFeed` کوئری می‌زد و ردیف‌های دوفیلدیِ او به کشِ تابلو نشت می‌کرد.
 */
const conditional = new Map<string, { etag: string; data: unknown }>();
/** سقفِ کشِ شرطی. کلید شاملِ URL است و مسیرهایِ نمادمحور (`/api/chart/<sym>`)
 *  هر کدام یک ورودیِ تازه می‌سازند؛ بی‌سقف، یک نشستِ طولانی با صدها نماد
 *  صدها بدنهٔ پارس‌شده (چارت ~۱MB) را تا بستنِ تب نگه می‌داشت. ۳۲ ورودیِ
 *  آخر (LRU) همان سودِ ۳۰۴ را برایِ مسیرهایِ پرتکرار نگه می‌دارد و حافظه را
 *  کران‌دار می‌کند. اخراج فقط «۳۰۴ِ بعدی» را از دست می‌دهد، نه داده یا درخواست. */
const CONDITIONAL_MAX = 32;

function conditionalGet(key: string) {
  const hit = conditional.get(key);
  if (hit) {
    // تازه‌سازیِ ترتیب: ورودیِ پرتکرار آخر می‌رود، نه اول.
    conditional.delete(key);
    conditional.set(key, hit);
  }
  return hit;
}

function conditionalSet(key: string, value: { etag: string; data: unknown }) {
  conditional.delete(key);
  conditional.set(key, value);
  while (conditional.size > CONDITIONAL_MAX) {
    const oldest = conditional.keys().next().value as string | undefined;
    if (oldest === undefined) break;
    conditional.delete(oldest);
  }
}

const schemaIds = new WeakMap<ZodType, number>();
let schemaSeq = 0;

/** هویتِ پایدارِ هر آبجکتِ اسکیمای zod (اسکیمای مشترکِ ما همه ماژول-سطحی‌اند) */
function schemaId(schema: ZodType | undefined): number {
  if (!schema) return 0;
  let id = schemaIds.get(schema);
  if (id === undefined) {
    id = ++schemaSeq;
    schemaIds.set(schema, id);
  }
  return id;
}

const conditionalKey = (url: string, schema?: ZodType) => `${url}\u0000${schemaId(schema)}`;

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(t);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

export type BlobReply = { blob: Blob; filename: string | null };

function dispositionFilename(header: string): string | null {
  // RFC 5987: filename*=UTF-8''… (نامِ فارسی) و اگر نبود filename="…"ِ ASCII
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      return star[1];
    }
  }
  const plain = /filename="([^"]+)"/i.exec(header);
  return plain?.[1] ?? null;
}

/**
 * POSTِ JSON → فایلی که سرور ساخته (Excel/PDF/DOCX). `http` پاسخ را `res.json()`
 * می‌کند، پس باینری از آن رد نمی‌شود؛ این تنها مسیرِ مجازِ `fetch` برایِ دانلودِ
 * فایل است (گاردِ no-restricted-syntax همان `shared/api/http.ts` را می‌پذیرد).
 */
export async function httpBlob(url: string, body: unknown, signal?: AbortSignal): Promise<BlobReply> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/octet-stream' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let message: string | undefined;
    try {
      const j = (await res.json()) as { detail?: unknown; message?: unknown };
      const d = typeof j?.detail === 'string' ? j.detail
        : typeof j?.message === 'string' ? j.message : undefined;
      message = d ? `خطای ${res.status}: ${d}` : undefined;
    } catch {
      /* بدنهٔ غیرِ JSON = همان خطایِ بی‌توضیح */
    }
    throw new HttpError(res.status, url, message);
  }
  return {
    blob: await res.blob(),
    filename: dispositionFilename(res.headers?.get?.('content-disposition') ?? ''),
  };
}

/** fetch با retry نمایی + Zod parse — الگوی codal_fetcher (backoff روی 429/403) */
export async function http<T>(url: string, opts: HttpOptions = {}): Promise<T> {
  const { schema, retries = 2, baseDelayMs = 800, signal, method = 'GET',
          body, rawBody, headers, noCache } = opts;
  let lastErr: unknown;

  // JSON body فقط وقتی build می‌شود که بدنهٔ خام نیامده باشد (rawBody اولویت دارد).
  const payload: BodyInit | undefined = rawBody ?? (body != null ? JSON.stringify(body) : undefined);
  const cKey = conditionalKey(url, schema);

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const revalidate = method === 'GET' && !noCache ? conditionalGet(cKey) : undefined;
      const res = await fetch(url, {
        headers: {
          Accept: 'application/json',
          // برای بدینهٔ خام، Content-Type را فراخواننده تعیین می‌کند (در headers).
          ...(payload && rawBody == null ? { 'Content-Type': 'application/json' } : {}),
          ...(revalidate ? { 'If-None-Match': revalidate.etag } : {}),
          ...headers,
        },
        ...(revalidate ? { cache: 'no-store' as RequestCache } : {}),
        method,
        ...(payload != null ? { body: payload } : {}),
        signal,
      });
      // ۳۰۴ پیش از !res.ok بررسی می‌شود: statusِ ۳۰۴ با ok=false می‌آید و
      // اگر همین‌جا رد شود، کاربر «خطایِ شبکه» می‌بیند در حالی که داده سالم است.
      if (res.status === 304 && revalidate) return revalidate.data as T;
      if (!res.ok) {
        const err = new HttpError(res.status, url);
        if (RETRYABLE.has(res.status) && attempt < retries) {
          await sleep(baseDelayMs * 2 ** attempt, signal);
          lastErr = err;
          continue;
        }
        throw err;
      }
      const data: unknown = await res.json();
      if (!schema) return data as T;
      const parsed = schema.safeParse(data);
      if (!parsed.success) {
        throw new HttpError(0, url, `پاسخ API با قرارداد نمی خواند: ${parsed.error.message}`);
      }
      // `?.` چون پاسخ‌هایِ ماک‌شدهٔ تست‌ها ممکن است Responseِ کامل نباشند؛
      // نبودِ هدر فقط یعنی «این پاسخ قابلِ اعتبارسنجیِ مجدد نیست».
      const etag = res.headers?.get?.('etag') ?? null;
      if (method === 'GET' && etag && !noCache) conditionalSet(cKey, { etag, data: parsed.data });
      return parsed.data as T;
    } catch (e) {
      if (e instanceof HttpError) throw e;
      if (e instanceof DOMException && e.name === 'AbortError') throw e;
      lastErr = e;
      if (attempt < retries) {
        await sleep(baseDelayMs * 2 ** attempt, signal);
        continue;
      }
    }
  }
  throw lastErr instanceof Error
    ? lastErr
    : new HttpError(0, url, 'خطای نامشخص شبکه');
}
