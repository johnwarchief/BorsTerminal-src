// shared/api/local/nativeHttp.ts — درگاه HTTP بومی برای دامنه‌های بیرونی (موبایل)
//
// چرا این ماژول: پچ سراسری CapacitorHttp (enabled:true) همهٔ fetchها — از جمله
// دانلود اسنپ‌شات و sql-wasm از سرور مجازی WebView (https://localhost/…) — را به
// لایهٔ بومی می‌برد که آن سرور را نمی‌بیند؛ نتیجه دیتابیس باز نمی‌شد و همهٔ
// تب‌ها خالی می‌ماند. پس پچ سراسری خاموش است و فقط این‌جا، صریح و فقط برای
// URLهای مطلق بیرونی (TSETMC / GitHub)، از پلاگین بومی استفاده می‌شود:
//   - داخل اپ اندروید: CapacitorHttp.get → درخواست بومی، بدون دیوار CORS،
//     با هدرهای Referer/Origin که مرورگر اجازه نمی‌دهد.
//   - در مرورگر/پیش‌نمایش: fetch معمولی (CORS ممکن است بگیرد ⇒ null و
//     مصرف‌کننده به دادهٔ اسنپ‌شات برمی‌گردد — اصل صداقت داده).
//
// این ماژول فقط در بیلد موبایل بار می‌شود (زنجیرهٔ ایمپورتِ shared/api/local
// پشت پرچم VITE_LOCAL_DATA است) — بیلد دسکتاپ هیچ بایتی از آن ندارد.
import { Capacitor, CapacitorHttp } from '@capacitor/core';

export type NativeHttpResult<T> = {
  status: number;
  data: T | null;
  headers: Record<string, string>;
  error?: string;
};

function isNative(): boolean {
  try {
    return Capacitor.isNativePlatform();
  } catch {
    return false;
  }
}

/** GET با پاسخ JSON؛ null اگر شبکه/وضعیت غیر ۲xx */
export async function nativeGetJson(
  url: string,
  headers: Record<string, string> = {},
): Promise<unknown | null> {
  if (isNative()) {
    const res = await CapacitorHttp.get({ url, headers, responseType: 'json',
                                          connectTimeout: 15000, readTimeout: 20000 });
    if (res.status < 200 || res.status >= 300) return null;
    // بعضی سرورها JSON را text/plain می‌دهند ⇒ data رشته می‌ماند
    return typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
  }
  const res = await fetch(url, { headers });
  if (!res.ok) return null;
  return res.json();
}

/** GET با پاسخ متنی (CSV چارت)؛ null اگر شبکه/وضعیت غیر ۲xx */
export async function nativeGetText(
  url: string,
  headers: Record<string, string> = {},
): Promise<string | null> {
  if (isNative()) {
    const res = await CapacitorHttp.get({ url, headers, responseType: 'text',
                                          connectTimeout: 15000, readTimeout: 30000 });
    if (res.status < 200 || res.status >= 300) return null;
    return typeof res.data === 'string' ? res.data : JSON.stringify(res.data);
  }
  const res = await fetch(url, { headers: { ...headers, Accept: 'text/plain' } });
  if (!res.ok) return null;
  return res.text();
}

function normalizeHeaders(value: unknown): Record<string, string> {
  if (!value || typeof value !== 'object') return {};
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key.toLowerCase(), String(item)]));
}

/** GET that preserves HTTP status and transport failures for bounded sync jobs. */
export async function nativeGetJsonResult(
  url: string,
  headers: Record<string, string> = {},
): Promise<NativeHttpResult<unknown>> {
  try {
    if (isNative()) {
      const res = await CapacitorHttp.get({ url, headers, responseType: 'json',
                                            connectTimeout: 15000, readTimeout: 30000 });
      const responseHeaders = normalizeHeaders(res.headers);
      if (res.status < 200 || res.status >= 300) {
        return { status: res.status, data: null, headers: responseHeaders };
      }
      const data = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
      return { status: res.status, data: data ?? null, headers: responseHeaders };
    }
    const res = await fetch(url, { headers });
    const responseHeaders = Object.fromEntries(res.headers.entries());
    if (!res.ok) return { status: res.status, data: null, headers: responseHeaders };
    return { status: res.status, data: await res.json(), headers: responseHeaders };
  } catch (error) {
    return { status: 0, data: null, headers: {},
      error: error instanceof Error ? error.message : String(error) };
  }
}

/** Text counterpart of nativeGetJsonResult. */
export async function nativeGetTextResult(
  url: string,
  headers: Record<string, string> = {},
): Promise<NativeHttpResult<string>> {
  try {
    if (isNative()) {
      const res = await CapacitorHttp.get({ url, headers, responseType: 'text',
                                            connectTimeout: 15000, readTimeout: 60000 });
      const responseHeaders = normalizeHeaders(res.headers);
      if (res.status < 200 || res.status >= 300) {
        return { status: res.status, data: null, headers: responseHeaders };
      }
      return { status: res.status,
        data: typeof res.data === 'string' ? res.data : JSON.stringify(res.data),
        headers: responseHeaders };
    }
    const res = await fetch(url, { headers: { ...headers, Accept: 'text/html,text/plain' } });
    const responseHeaders = Object.fromEntries(res.headers.entries());
    if (!res.ok) return { status: res.status, data: null, headers: responseHeaders };
    return { status: res.status, data: await res.text(), headers: responseHeaders };
  } catch (error) {
    return { status: 0, data: null, headers: {},
      error: error instanceof Error ? error.message : String(error) };
  }
}

/** base64 → بایت. حلقۀ بایت‌به‌بایت رویِ بستۀ چندده‌مگابایتیِ داده رویِ گوشی
 *  دقیقه‌ها می‌برد و WebView را از حافظه می‌اندازد؛ data: URL درِ خودِ موتور
 *  رمزگشایی می‌شود. مسیرِ دستی فقط درازگشت است، نه راهِ عادی. */
async function base64ToBytes(b64: string): Promise<ArrayBuffer> {
  try {
    const r = await fetch(`data:application/octet-stream;base64,${b64}`);
    if (r.ok) return await r.arrayBuffer();
  } catch { /* موتورِ قدیمی data: را از fetch رد می‌کند */ }
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

/** GET باینری (بستهٔ دادهٔ GitHub)؛ null اگر شبکه/وضعیت غیر ۲xx */
export async function nativeGetBytes(url: string): Promise<ArrayBuffer | null> {
  if (isNative()) {
    const res = await CapacitorHttp.get({ url, responseType: 'blob',
                                          connectTimeout: 15000, readTimeout: 120000 });
    if (res.status < 200 || res.status >= 300 || typeof res.data !== 'string') return null;
    // پل بومی باینری را base64 می‌دهد
    return base64ToBytes(res.data);
  }
  const res = await fetch(url);
  if (!res.ok) return null;
  return res.arrayBuffer();
}
