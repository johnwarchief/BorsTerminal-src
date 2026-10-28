import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson, requestJson } from '@shared/api/http';
import { normalizeFa } from '@shared/lib/faSearch';

const WatchlistRowSchema = z.looseObject({
  norm: z.string(),
  symbol: z.string(),
  name: z.string().default(''),
  note: z.string().default(''),
  added_at: z.string().default(''),
});

const WatchlistPayloadSchema = z.looseObject({
  status: z.string(),
  count: z.number().nullish(),
  data: z.array(WatchlistRowSchema).nullish(),
  limit: z.number().nullish(),
  message: z.string().nullish(),
  watch: WatchlistRowSchema.nullish(),
  deleted: z.number().nullish(),
  existed: z.boolean().nullish(),
});

export type WatchlistRow = z.infer<typeof WatchlistRowSchema>;
export type WatchlistPayload = z.infer<typeof WatchlistPayloadSchema>;
export type ToggleWatchArgs = { symbol: string; name?: string; remove?: boolean };

export const WATCHLIST_QUERY_KEY = ['user-watchlist'] as const;

function accepted(payload: WatchlistPayload): WatchlistPayload {
  if (payload.status !== 'success') {
    throw new Error(payload.message || 'واچ‌لیست درخواست را نپذیرفت');
  }
  return payload;
}

async function fetchWatchlist(signal?: AbortSignal): Promise<WatchlistPayload> {
  return accepted(await getJson('/api/watchlist', WatchlistPayloadSchema, signal));
}

export function useUserWatchlist() {
  return useQuery({
    queryKey: WATCHLIST_QUERY_KEY,
    queryFn: ({ signal }) => fetchWatchlist(signal),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

function optimistic(prev: WatchlistPayload | undefined, args: ToggleWatchArgs): WatchlistPayload {
  const rows = prev?.data ?? [];
  const norm = normalizeFa(args.symbol);
  const rest = rows.filter((row) => normalizeFa(row.symbol) !== norm);
  const data = args.remove ? rest : [{
    norm,
    symbol: args.symbol,
    name: args.name ?? '',
    note: '',
    added_at: new Date().toISOString(),
  }, ...rest];
  return { status: 'success', count: data.length, data, limit: prev?.limit };
}

export function useWatchlistToggle() {
  const queryClient = useQueryClient();
  return useMutation<WatchlistPayload, Error, ToggleWatchArgs, { prev?: WatchlistPayload }>({
    mutationFn: async ({ symbol, name = '', remove }) => accepted(await requestJson(
      remove ? `/api/watchlist/${encodeURIComponent(symbol)}` : '/api/watchlist',
      WatchlistPayloadSchema,
      remove ? { method: 'DELETE' } : { method: 'POST', body: { symbol, name } },
    )),
    onMutate: async (args) => {
      await queryClient.cancelQueries({ queryKey: WATCHLIST_QUERY_KEY });
      const prev = queryClient.getQueryData<WatchlistPayload>(WATCHLIST_QUERY_KEY);
      queryClient.setQueryData(WATCHLIST_QUERY_KEY, optimistic(prev, args));
      return { prev };
    },
    onError: (_error, _args, context) => {
      queryClient.setQueryData(WATCHLIST_QUERY_KEY, context?.prev);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: WATCHLIST_QUERY_KEY }),
  });
}
