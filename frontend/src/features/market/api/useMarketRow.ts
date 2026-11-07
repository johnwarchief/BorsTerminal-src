// features/market/api/useMarketRow.ts -- یک ردیفِ تابلو، نه کلِ فید
//
// سایدبارِ نماد پیش‌تر `useMarketFeed` را با enabled=true می‌خواند تا یک ردیف
// پیدا کند: ۶٫۸MB خام / ~۱٫۲MB gzip در هر انتخابِ نماد. مسیرِ سبکِ
// `/api/market/row` همان ردیفِ آینهٔ دلتا را می‌دهد؛ اسکیمایِ ردیف همان
// `MarketRowSchema` است، پس هیچ ستون/معنایی عوض نمی‌شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { MarketRowSchema, type MarketRow } from '@shared/types/marketRow';
import { sessionPollMs } from '@shared/lib/marketHours';

const MarketRowResponseSchema = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  row: MarketRowSchema.nullish(),
  rev: z.number().nullish(),
});

export type MarketRowResponse = z.infer<typeof MarketRowResponseSchema>;

export function marketRowQueryOptions(symbol: string) {
  return {
    queryKey: ['market-row', symbol] as const,
    queryFn: ({ signal }: { signal?: AbortSignal }) =>
      http<MarketRowResponse>(`/api/market/row?symbol=${encodeURIComponent(symbol)}`, {
        schema: MarketRowResponseSchema,
        signal,
      }),
  };
}

export function useMarketRow(
  symbol: string,
  enabled = true,
  opts: { poll?: boolean } = {},
) {
  return useQuery({
    ...marketRowQueryOptions(symbol),
    enabled: enabled && symbol.length > 0,
    staleTime: 4_000,
    gcTime: 5 * 60_000,
    refetchInterval: opts.poll === false ? false : () => sessionPollMs(5_000),
    refetchOnWindowFocus: false,
  });
}

/** هویت ثابت است؛ برایِ `ins_code` نباید هر ۵ثانیه پرسیده شود. */
export function useMarketRowIdentity(symbol: string, enabled = true) {
  return useQuery({
    ...marketRowQueryOptions(symbol),
    enabled: enabled && symbol.length > 0,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
}

export function marketRowOf(q: { data?: MarketRowResponse }): MarketRow | null {
  return q.data?.row ?? null;
}
