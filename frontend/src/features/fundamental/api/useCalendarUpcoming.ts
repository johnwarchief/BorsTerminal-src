// features/fundamental/api/useCalendarUpcoming.ts -- تقویم مجمعِ همهٔ نمادها در یک درخواست
// ردیف‌های جدول بنیادی شش‌صدتایی‌اند؛ `/api/calendar/{symbol}` به‌ازای هر ردیف
// یک درخواست می‌خواست. این مسیر انبوه برمی‌گرداند و یک‌بار کش می‌شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import type { CalEvent } from '../lib/assemblyEvent';

const UpcomingItemSchema = z.object({
  symbol: z.string(),
  date: z.string(),
  cat: z.string().nullish(),
  title: z.string().nullish(),
});

const UpcomingSchema = z.object({
  status: z.string(),
  days: z.number().nullish(),
  count: z.number().nullish(),
  items: z.array(UpcomingItemSchema).nullish(),
});

export type UpcomingAssembly = z.infer<typeof UpcomingItemSchema>;

export function useCalendarUpcoming(days = 14, enabled = true) {
  return useQuery({
    queryKey: ['cal-upcoming', days],
    queryFn: ({ signal }) =>
      http<z.infer<typeof UpcomingSchema>>(`/api/calendar/upcoming?days=${days}`, {
        schema: UpcomingSchema,
        signal,
      }),
    enabled,
    staleTime: 6 * 60 * 60_000,
    gcTime: 24 * 60 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

/** آیتم‌های تختِ پاسخِ انبوه → نقشهٔ نماد به رویداد، تا منطقِ آزمون‌شدهٔ
 *  `pickAssemblyBadge` بدونِ تغییر دوباره استفاده شود. */
export function groupBySymbol(
  items: UpcomingAssembly[] | null | undefined,
): Record<string, CalEvent[]> {
  const out: Record<string, CalEvent[]> = {};
  for (const it of items ?? []) {
    const sym = String(it.symbol ?? '').trim();
    if (!sym) continue;
    (out[sym] ??= []).push({ date: it.date, title: it.title ?? null, cat: it.cat ?? null });
  }
  return out;
}
