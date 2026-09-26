// features/updater/api/diagnostics.ts -- شبکهٔ فیچرِ بروزرسانی فقط از این‌جا
// قاعدهٔ ESLint: fetchِ خام بیرونِ shared/api/http.ts یا api/ِ فیچر ممنوع است.
import { z } from 'zod';
import { http } from '@shared/api/http';

const LogOpenSchema = z.object({
  status: z.string(),
  path: z.string().nullish(),
  message: z.string().nullish(),
});
export type LogOpenResult = z.infer<typeof LogOpenSchema>;

/** فایلِ لاگ را با ادیتورِ پیش‌فرضِ ویندوز باز می‌کند (درخواستِ دستیِ کاربر) */
export function openAppLog(signal?: AbortSignal): Promise<LogOpenResult> {
  return http<LogOpenResult>('/api/diagnostics/log/open', {
    method: 'POST',
    schema: LogOpenSchema,
    retries: 0,
    signal,
  });
}
