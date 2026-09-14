// features/fundamental/api/useCalendarEvents.ts -- رویدادهای تقویم نماد (مجمع و…)
// منبع: endpoint سبک اختصاصی `GET /api/calendar/{symbol}` بک‌اند —
// خروجی `_cal_events_for` در api/chart.py:
// {status, symbol, count, events:[{date, ts, title, cat}]}
// با cat ∈ assembly | assemblyExtra | assemblyChange | dividend | capitalIncrease | ipo | bondMaturity | other.
// (قبلاً از events در /api/ma/{symbol} می‌آمد که سری MA سنگین را هم می‌فرستد.)
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

/** فقط فیلدهای لازم را مدل می‌کند؛ فیلدهای اضافی پاسخ نادیده گرفته میشود */
const MaEventsSchema = z.object({
  status: z.string().nullish(),
  symbol: z.string().nullish(),
  events: z.array(CalEventSchema).nullish(),
});

export function useCalendarEvents(symbol: string) {
  return useQuery({
    queryKey: ['cal-events', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof MaEventsSchema>>(`/api/calendar/${encodeURIComponent(symbol)}`, {
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
