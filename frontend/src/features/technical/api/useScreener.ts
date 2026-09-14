// features/technical/api/useScreener.ts -- سیگنال‌های FTS سایدبار راست (تب ۲)
// از اندپوینت /api/screener؛ فقط ستون‌های tech_* لازم است. اسکیمای بومیِ فیچر
// (مرز B1): هیچ importی از فیچر fundamental. ردیف بی‌سیگنال حذف می‌شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const flag = z.boolean().nullish();

export const ScreenerRowSchema = z.object({
  symbol: z.string().min(1),
  name: z.string().nullish(),
  symbol_norm: z.string().nullish(),
  sector_name: z.string().nullish(),
  score: z.number().nullish(),
  excluded: z.boolean().nullish(),
  watchlist: z.boolean().nullish(),
  tech_trend_d: z.string().nullish(),
  tech_trend_w: z.string().nullish(),
  tech_trend_m: z.string().nullish(),
  tech_alignment: z.string().nullish(),
  tech_jet: flag,
  tech_choch_bull: flag,
  tech_choch_bear: flag,
  tech_double_bottom: flag,
  tech_range_break: flag,
  tech_fib_zone: z.string().nullish(),
  tech_exit_verdict: z.string().nullish(),
  tech_exit_signals: z.array(z.string()).nullish(),
});
export type ScreenerRow = z.infer<typeof ScreenerRowSchema>;

export const ScreenerResponseSchema = z.object({
  status: z.string(),
  count: z.number().nullish(),
  data: z.array(ScreenerRowSchema),
});
export type ScreenerResponse = z.infer<typeof ScreenerResponseSchema>;

const DEFAULT_LIMIT = 60;

export function useFtsScreener() {
  return useQuery({
    queryKey: ['technical-fts-screener'],
    queryFn: ({ signal }) => http<ScreenerResponse>('/api/screener', { schema: ScreenerResponseSchema, signal }),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export type FtsSignalTag = { label: string; tone: 'green' | 'red' | 'blue' };

/** برچسب ستاپ‌های فعال از ستون‌های tech_* پاسخ اسکرینر */
export function ftsSignalTags(r: ScreenerRow): FtsSignalTag[] {
  const t: FtsSignalTag[] = [];
  if (r.tech_jet) t.push({ label: 'جت', tone: 'green' });
  if (r.tech_choch_bull) t.push({ label: 'CHoCH صعودی', tone: 'green' });
  if (r.tech_choch_bear) t.push({ label: 'CHoCH نزولی', tone: 'red' });
  if (r.tech_double_bottom) t.push({ label: 'کف دوقلو', tone: 'green' });
  if (r.tech_range_break) t.push({ label: 'خروج از انباشت', tone: 'green' });
  if (r.tech_fib_zone) t.push({ label: 'نقطه‌زنی فیبو', tone: 'blue' });
  return t;
}

/** فقط نمادهای دارای دست‌کم یک ستاپ/الگو؛ جستجو روی نماد و نام */
export function filterFtsSignals(rows: ScreenerRow[], q: string, limit = DEFAULT_LIMIT): ScreenerRow[] {
  const term = q.trim().toLowerCase();
  return rows
    .filter((r) => {
      if (ftsSignalTags(r).length === 0) return false;
      if (!term) return true;
      return r.symbol.toLowerCase().includes(term) || (r.name ?? '').toLowerCase().includes(term);
    })
    .slice(0, limit);
}
