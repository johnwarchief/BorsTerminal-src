// shared/api/userWatchlist.ts — واچ‌لیستِ کاربر = همان جدولِ `user_watchlists` بک‌اند
//
// چرا درِ `shared`: ستارۀ واچ‌لیست درِ تابلو، بنیادی، غربالگری، پرتفوی و جست‌وجو
// یک چیز باید باشد (§۳۱: «هیچ duplicate watchlist storage در frontend نساز»).
// `features/*` فقط می‌تواند `shared` و `contracts` را وارد کند
// (`eslint.config.js:40`)، پس تنها جایِ ممکن همین است.
//
// هیچ storageِ تازه‌ای اینجا نیست: GET/POST/DELETEِ `/api/watchlist` از قبل
// هست و کلیدش `norm_fa(نماد)` است (`watchlist_store.py:31-45`,
// `api/watchlist.py:17,33,70`). افزودن/حذف optimistic است و فقط همان کوئری را
// عوض می‌کند — نه رفرشِ کلِ تابلو، نه کلِ پرتفوی (§۸).
import { useContext } from 'react';
import {
  QueryClient, QueryClientContext, useMutation, useQuery,
} from '@tanstack/react-query';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { http } from '@shared/api/http';

/** `watchlist_store._row` کلیدِ نرمال را `norm` می‌فرستد (نه `symbol_norm`) —
 *  همان‌طور که درِ پاسخِ زندهٔ `GET /api/watchlist` دیده شد. */
export type WatchlistRow = {
  norm: string; symbol: string; name: string; note: string; added_at: string;
};

export type WatchlistPayload = {
  status: string; count: number; data?: WatchlistRow[]; limit?: number | null;
  message?: string; watch?: WatchlistRow; deleted?: number;
};

export const WATCHLIST_QUERY_KEY = ['user-watchlist'];

/** ستارۀ واچ‌لیست درِ **هر** جدولی می‌نشیند — از جمله ردیفِ تابلو و اسکرینر که
 *  ده‌ها تستِ موجودشان آن را بی‌`QueryClientProvider` رندر می‌کنند. بی‌این
 *  fallback، هر یک از آن تست‌ها با «No QueryClient set» می‌شکست. درِ اپِ واقعی
 *  همیشه provider هست و همان کلاینتِ مشترکِ برنامه مصرف می‌شود (§۳۱: یکِ منبعِ
 *  حقیقت)؛ کلاینتِ یتیم فقط سرپناهِ رندرِ بی‌provider است. */
const ORPHAN_CLIENT = new QueryClient({
  defaultOptions: { queries: { retry: 0 }, mutations: { retry: 0 } },
});

function useWatchlistClient(): QueryClient {
  return useContext(QueryClientContext) ?? ORPHAN_CLIENT;
}

async function fetchWatchlist(): Promise<WatchlistPayload> {
  return http<WatchlistPayload>('/api/watchlist');
}

/** فهرستِ واچ‌لیست + سقفِ ظرفیت (USER_WATCHLIST_MAX، نه سقفِ غربالگری — §۹/§۱۰) */
export function useUserWatchlist() {
  const q = useQuery<WatchlistPayload>({
    queryKey: WATCHLIST_QUERY_KEY,
    queryFn: fetchWatchlist,
    staleTime: 30_000,
  }, useWatchlistClient());
  const rows = q.data?.data ?? [];
  return {
    rows,
    count: q.data?.count ?? rows.length,
    limit: q.data?.limit ?? null,
    ready: !!q.data && q.data.status === 'success',
    failed: !!q.data && q.data.status === 'error',
    message: q.data?.message ?? null,
    loading: q.isPending,
    refresh: () => void q.refetch(),
  };
}

/** عضویتِ یک نماد — با `select` تا فقط یک بولین برگردد و هر ردیفِ جدول با
 *  عوض شدنِ فهرست دوباره رندر نشود. */
export function useIsWatchlisted(symbol: string | null | undefined): boolean {
  const norm = normalizeFa(symbol ?? '');
  const { data } = useQuery<WatchlistPayload, Error, boolean>({
    queryKey: WATCHLIST_QUERY_KEY,
    queryFn: fetchWatchlist,
    staleTime: 30_000,
    enabled: !!norm,
    select: (p) => {
      if (!norm) return false;
      return (p.data ?? []).some((r) => normalizeFa(r.symbol) === norm);
    },
  }, useWatchlistClient());
  return data === true;
}

export type ToggleArgs = { symbol: string; name?: string; remove?: boolean };

function optimistic(prev: WatchlistPayload | undefined, { symbol, name = '', remove }: ToggleArgs): WatchlistPayload {
  const rows = prev?.data ?? [];
  const norm = normalizeFa(symbol);
  const rest = rows.filter((r) => normalizeFa(r.symbol) !== norm);
  const data = remove ? rest
    : [{ norm, symbol, name, note: '', added_at: new Date().toISOString() } as WatchlistRow, ...rest];
  return { status: 'success', count: data.length, data, limit: prev?.limit ?? null };
}

/** افزودن/حذفِ واچ‌لیست — optimistic، بی‌refetchِ صفحه‌هایِ دیگر */
export function useWatchlistToggle() {
  const qc = useWatchlistClient();
  return useMutation<WatchlistPayload, Error, ToggleArgs, { prev?: WatchlistPayload }>({
    mutationFn: ({ symbol, name = '', remove }) =>
      remove
        ? http<WatchlistPayload>(`/api/watchlist/${encodeURIComponent(symbol)}`, { method: 'DELETE' })
        : http<WatchlistPayload>('/api/watchlist', { method: 'POST', body: { symbol, name } }),
    onMutate: async (vars) => {
      await qc.cancelQueries({ queryKey: WATCHLIST_QUERY_KEY });
      const prev = qc.getQueryData<WatchlistPayload>(WATCHLIST_QUERY_KEY);
      qc.setQueryData<WatchlistPayload>(WATCHLIST_QUERY_KEY, optimistic(prev, vars));
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      // واخوردنِ حدسِ محلی: اگر سرور نپذیرفت (سقف/خطا)، همان فهرستِ قبلی برمی‌گردد
      if (ctx?.prev) qc.setQueryData(WATCHLIST_QUERY_KEY, ctx.prev);
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: WATCHLIST_QUERY_KEY }); },
  }, qc);
}

/** متنِ یک جا، تا ستاره درِ پنج سطح دو حرفِ متفاوت نزند */
export function watchlistLabel(symbol: string, inList: boolean): string {
  return inList
    ? `«${symbol}» درِ واچ‌لیست است — کلیک برایِ حذف`
    : `«${symbol}» را به واچ‌لیست اضافه کن (ماندگار، برایِ رصدِ روزهایِ بعد)`;
}
