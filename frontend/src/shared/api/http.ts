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
  /** کش شرطی را برای همین درخواست خاموش می‌کند. */
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

/** fetch با retry نمایی + Zod parse — الگوی codal_fetcher (backoff روی 429/403) */
export async function http<T>(url: string, opts: HttpOptions = {}): Promise<T> {
  const { schema, retries = 2, baseDelayMs = 800, signal, method = 'GET',
          body, rawBody, headers, noCache } = opts;

  // حالت موبایل/آفلاین (VITE_LOCAL_DATA='1'): مسیرهای /api/* به‌جای شبکه از
  // اسنپ‌شات روی دستگاه پاسخ می‌گیرند (shared/api/local). ایمپورت داینامیک
  // است تا در بیلد دسکتاپ (بدون این متغیر) کل شاخه dead-code حذف شود و
  // قانون «fetch فقط در http.ts» هم سر جایش بماند.
  if (import.meta.env.VITE_LOCAL_DATA === '1' && url.startsWith('/api/')) {
    const { resolveLocal } = await import('./local');
    const data: unknown = await resolveLocal(url, method as 'GET' | 'POST' | 'PUT' | 'DELETE', body);
    if (!schema) return data as T;
    const parsed = schema.safeParse(data);
    if (!parsed.success) {
      throw new HttpError(0, url, `پاسخ آفلاین با قرارداد نمی خواند: ${parsed.error.message}`);
    }
    return parsed.data as T;
  }
  let lastErr: unknown;

  // JSON body فقط وقتی build می‌شود که بدنهٔ خام نیامده باشد (rawBody اولویت دارد).
  const payload: BodyInit | undefined = rawBody ?? (body != null ? JSON.stringify(body) : undefined);
  const cKey = conditionalKey(url, schema);

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const revalidate = method === 'GET' && !noCache ? conditional.get(cKey) : undefined;
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
      if (method === 'GET' && etag && !noCache) conditional.set(cKey, { etag, data: parsed.data });
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
