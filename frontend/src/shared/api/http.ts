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
  method?: 'GET' | 'POST' | 'PUT';
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
}

const RETRYABLE = new Set([403, 429, 500, 502, 503, 504]);

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
          body, rawBody, headers } = opts;
  let lastErr: unknown;

  // JSON body فقط وقتی build می‌شود که بدنهٔ خام نیامده باشد (rawBody اولویت دارد).
  const payload: BodyInit | undefined = rawBody ?? (body != null ? JSON.stringify(body) : undefined);

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, {
        headers: {
          Accept: 'application/json',
          // برای بدینهٔ خام، Content-Type را فراخواننده تعیین می‌کند (در headers).
          ...(payload && rawBody == null ? { 'Content-Type': 'application/json' } : {}),
          ...headers,
        },
        method,
        ...(payload != null ? { body: payload } : {}),
        signal,
      });
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
