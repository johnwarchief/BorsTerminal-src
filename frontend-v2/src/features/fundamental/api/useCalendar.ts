import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const Str = z.string().nullish();
const Num = z.number().nullish();

const EventSchema = z.looseObject({
  date: z.string(),
  ts: Num,
  title: z.string(),
  cat: Str,
  date_source: Str,
  published_at: Str,
});

const SymbolPayload = z.looseObject({
  status: z.string(),
  symbol: z.string().nullish(),
  count: z.number().nullish(),
  events: z.array(EventSchema).default([]),
});

const UpcomingItemSchema = z.looseObject({
  symbol: z.string(),
  date: z.string(),
  cat: Str,
  title: z.string(),
  date_source: Str,
  published_at: Str,
});

const UpcomingPayload = z.looseObject({
  status: z.string(),
  days: z.number().nullish(),
  count: z.number().nullish(),
  items: z.array(UpcomingItemSchema).default([]),
  capital_count: z.number().nullish(),
  capital: z.array(UpcomingItemSchema).default([]),
});

export type CalendarEvent = z.infer<typeof EventSchema>;
export type UpcomingEvent = z.infer<typeof UpcomingItemSchema>;

export function useSymbolCalendar(symbol: string | null | undefined) {
  return useQuery({
    queryKey: ['calendar-symbol', symbol],
    queryFn: ({ signal }) => getJson(
      `/api/calendar/${encodeURIComponent(String(symbol))}`, SymbolPayload, signal),
    enabled: Boolean(symbol),
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useUpcomingCalendar(days = 30) {
  return useQuery({
    queryKey: ['calendar-upcoming', days],
    queryFn: ({ signal }) => getJson(`/api/calendar/upcoming?days=${days}`, UpcomingPayload, signal),
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
}
