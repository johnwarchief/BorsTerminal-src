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

export async function getJson<T>(path: string, schema: ZodType<T>, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: 'application/json' } });
  if (!res.ok) throw new HttpError(res.status, `${path} → ${res.status}`);
  return schema.parse(await res.json());
}
