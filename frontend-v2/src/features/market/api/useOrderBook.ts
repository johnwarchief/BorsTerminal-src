import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson, requestJson } from '@shared/api/http';
import { normalizeFa } from '@shared/lib/faSearch';
import { sessionPollMs } from '@shared/lib/marketHours';

const LevelSchema = z.object({
  buy_px: z.number(),
  buy_vol: z.number(),
  buy_cnt: z.number(),
  sell_px: z.number(),
  sell_vol: z.number(),
  sell_cnt: z.number(),
});

const BookSchema = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  levels: z.array(LevelSchema).default([]),
  message: z.string().nullish(),
  session: z.object({
    d_even: z.number().nullish(),
    h_even: z.number().nullish(),
    updated_at: z.string().nullish(),
  }).nullish(),
  totals: z.object({
    buy_vol: z.number().nullish(),
    buy_cnt: z.number().nullish(),
    sell_vol: z.number().nullish(),
    sell_cnt: z.number().nullish(),
  }).nullish(),
});

const WatchSchema = z.looseObject({ status: z.string() });

export type OrderBook = z.infer<typeof BookSchema>;
export type OrderBookLevel = z.infer<typeof LevelSchema>;

function echoMatches(echoed: string | null | undefined, wanted: string): boolean {
  if (!echoed) return true;
  return normalizeFa(echoed) === normalizeFa(wanted);
}

export function useOrderBook(symbol: string, insCode?: string | null) {
  useEffect(() => {
    const code = insCode?.trim();
    if (!code) return;
    void requestJson('/api/orderbook/watch', WatchSchema, {
      method: 'POST', body: { ins_code: code },
    }).catch(() => undefined);
  }, [insCode]);

  return useQuery({
    queryKey: ['order-book', symbol],
    queryFn: ({ signal }) => getJson(`/api/order-book/${encodeURIComponent(symbol)}`, BookSchema, signal),
    enabled: symbol.length > 0,
    staleTime: 20_000,
    refetchInterval: () => sessionPollMs(30_000),
    refetchIntervalInBackground: false,
    select: (data: OrderBook) => (echoMatches(data.symbol, symbol) ? data : null),
  });
}
