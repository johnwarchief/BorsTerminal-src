import type { ZodType } from 'zod';

/** تنها درِ شبکه در کلِ اپ — هیچ کامپوننتی مستقیم fetch نمی‌زند. */
export class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function requestJson<T>(
  path: string,
  schema: ZodType<T>,
  options: { method?: 'GET' | 'POST' | 'DELETE'; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const { method = 'GET', body, signal } = options;
  const res = await fetch(path, {
    method,
    signal,
    headers: {
      Accept: 'application/json',
      // The SPA authenticates with the local API cookie the server sets on the
      // first static request; cookie-authenticated writes need this marker.
      ...(method !== 'GET' ? { 'X-OC-CSRF': '1' } : {}),
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) throw new HttpError(res.status, `${path} → ${res.status}`);
  return schema.parse(await res.json());
}

export async function getJson<T>(path: string, schema: ZodType<T>, signal?: AbortSignal): Promise<T> {
  return requestJson(path, schema, { signal });
}
