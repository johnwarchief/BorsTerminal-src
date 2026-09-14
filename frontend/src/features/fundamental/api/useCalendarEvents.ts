// features/fundamental/api/useCalendarEvents.ts -- رویدادهای تقویم نماد (مجمع و…)
// منبع واقعیِ رویدادهای تقویم بک‌اند فیلد `events` در /api/ma/{symbol} است
// (خروجی _cal_events_for در api/chart.py). این endpoint نسبتاً سنگین است
// (سری MA را هم می‌فرستد)، برای همین با days=120 و staleTime بلند کش میشود؛
// endpoint سبک اختصاصی تقویم به هد بک‌اند پیشنهاد شده است.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

export const CalEventSchema = z.object({
  date: z.string(),
  ts: z.number().nullish(),
  title: z.string().nullish(),
  cat: z.string().nullish(),
});

export type CalEventRow = z.infer<typeof CalEventSchema>;

/** فقط فیلدهای لازم را مدل می‌کند؛ بقیهٔ پاسخ (سریهای MA) نادیده گرفته میشود */
const MaEventsSchema = z.object({
  status: z.string().nullish(),
  symbol: z.string().nullish(),
  events: z.array(CalEventSchema).nullish(),
});

export function useCalendarEvents(symbol: string) {
  return useQuery({
    queryKey: ['cal-events', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof MaEventsSchema>>(`/api/ma/${encodeURIComponent(symbol)}?days=120`, {
        schema: MaEventsSchema,
        signal,
      }),
    enabled: symbol.length > 0,
    /** تقویم مجمع دیر تغییر می‌کند — badge سبکِ کش‌شده، نه درخواست هر رندر */
    staleTime: 6 * 60 * 60_000,
    gcTime: 24 * 60 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}
