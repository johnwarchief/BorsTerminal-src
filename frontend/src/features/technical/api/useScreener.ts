// features/technical/api/useScreener.ts -- سیگنال‌های FTS سایدبار راست (تب ۲)
// از اندپوینت /api/screener؛ فقط ستون‌های tech_* لازم است. اسکیمای بومیِ فیچر
// (مرز B1): هیچ importی از فیچر fundamental. ردیف بی‌سیگنال حذف می‌شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { matchFa } from '@shared/lib/normalizeFa';

const flag = z.boolean().nullish();

export const ScreenerRowSchema = z.object({
  symbol: z.string().min(1),
  name: z.string().nullish(),
  symbol_norm: z.string().nullish(),
  sector_name: z.string().nullish(),
  score: z.number().nullish(),
  excluded: z.boolean().nullish(),
  watchlist: z.boolean().nullish(),
  weekly_veto: z.boolean().nullish(),
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
  tech_matrix_decision: z.string().nullish(),
  tech_matrix_setup: z.string().nullish(),
  tech_hourglass_active: flag,
  tech_hourglass_action: z.string().nullish(),
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

export type FtsSignalTag = { label: string; tone: 'green' | 'red' | 'blue' | 'gray'; role: 'signal' | 'context' };

/** برچسب ستاپ‌های فعال از ستون‌های tech_* پاسخ اسکرینر.
 *  taxonomyِ دورِ J: `role: 'context'` هیچ‌وقت «ستاپ» حساب نمی‌شود — کمربندِ فیبو
 *  جایِ ایستادن را می‌گوید، نه اینکه بخر (سنجش: داخلِ باند edge ندارد). */
export function ftsSignalTags(r: ScreenerRow): FtsSignalTag[] {
  const t: FtsSignalTag[] = [];
  if (r.tech_hourglass_active) t.push({ label: 'ساعت شنی (۲x-۴x)', tone: 'green', role: 'signal' });
  if (r.tech_jet) t.push({ label: 'جت', tone: 'green', role: 'signal' });
  if (r.tech_choch_bull) t.push({ label: 'CHoCH صعودی', tone: 'green', role: 'signal' });
  if (r.tech_choch_bear) t.push({ label: 'CHoCH نزولی', tone: 'red', role: 'signal' });
  if (r.tech_double_bottom) t.push({ label: 'کف دوقلو', tone: 'green', role: 'signal' });
  if (r.tech_range_break) t.push({ label: 'خروج از انباشت', tone: 'green', role: 'signal' });
  if (r.tech_fib_zone) t.push({ label: `موقعیت فیبو ${r.tech_fib_zone}`, tone: 'gray', role: 'context' });
  if (r.tech_matrix_decision === 'REJECT') t.push({ label: 'وتوی هفتگی', tone: 'red', role: 'signal' });
  return t;
}

/** فقط نمادهای دارای دست‌کم یک ستاپ/الگو؛ جستجو روی نماد و نام */
export function filterFtsSignals(rows: ScreenerRow[], q: string, limit = DEFAULT_LIMIT): ScreenerRow[] {
  const term = q.trim();
  const hasSignal = (r: ScreenerRow) => ftsSignalTags(r).some((tag) => tag.role === 'signal');
  return rows
    .filter((r) => {
      if (!hasSignal(r)) return false;
      if (!term) return true;
      return matchFa(r.symbol, term) || matchFa(r.name, term);
    })
    .slice(0, limit);
}

/**
 * نماد پیش‌فرض (fallback) وقتی نمادی انتخاب نشده: اولین ردیف واچ‌لیست اسکرینر،
 * وگرنه اولین ردیف غیرمردود. null یعنی اسکرینر خالی است.
 */
export function firstScreenerSymbol(rows: ScreenerRow[]): string | null {
  const wl = rows.find((r) => r.watchlist && !r.excluded && r.symbol);
  if (wl) return wl.symbol;
  const any = rows.find((r) => !r.excluded && r.symbol);
  return any ? any.symbol : null;
}
