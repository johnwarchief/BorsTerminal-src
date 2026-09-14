// features/portfolio/api/useStopLossBoard.ts -- حد ضررهای سبد از اندپوینت چارت
// حد ضرر تکنیکال/فیبو فقط از /api/fts/{symbol} خوانده می‌شود (Circuit Breaker:
// غیب فیلد ⇒ «بدون داده»)؛ حد ضرر بنیادی از /api/fundamental/{symbol}.
// fetch درون batch انجام نمی‌شود — به ازای هر نمادِ نمای فعلی یک کوئری سبک.
import { useQueries } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const FibZone = z.object({ lo: z.number().nullish(), hi: z.number().nullish(), in_zone: z.boolean().nullish() });

const FtsStopSchema = z.object({
  status: z.string(),
  fts: z
    .object({
      fib: z
        .object({
          zone_33_40: FibZone.nullish(),
          zone_618_70: FibZone.nullish(),
        })
        .nullish(),
      jet: z.object({ active: z.boolean().nullish(), resistance: z.number().nullish() }).nullish(),
      exit_engine: z
        .object({
          l1: z
            .object({
              hard_stop: z.number().nullish(),
              stop_basis: z.string().nullish(),
              ma14: z.number().nullish(),
              ma14_exit_pending: z.boolean().nullish(),
            })
            .nullish(),
        })
        .nullish(),
    })
    .nullish(),
});

const FundStopSchema = z.object({
  status: z.string(),
  metrics: z
    .object({
      gross_margin: z.number().nullish(),
      growth_pct: z.number().nullish(),
      monetary_growth_pct: z.number().nullish(),
    })
    .nullish(),
});

export type StopCell = {
  symbol: string;
  /** حد ضرر تکنیکال: 5٪ زیر آخرین کف ماژور یا MA-14 */
  techStop: number | null;
  techBasis: string;
  /** تراز فیبو ۳۳-۴۰ پله اول */
  fib1: { lo: number | null; hi: number | null } | null;
  /** تراز فیبو ۶۱.۸-۷۰ پله دوم */
  fib2: { lo: number | null; hi: number | null } | null;
  /** ستاپ جت فعال است؟ */
  jetActive: boolean | null;
  /** حد ضرر بنیادی: افت فروش فصلی یا حاشیه سود زیر ۲۰٪ */
  fundStop: { margin: number | null; growth: number | null; hit: boolean | null };
};

const NO_STOP: Omit<StopCell, 'symbol'> = {
  techStop: null,
  techBasis: 'بدون داده',
  fib1: null,
  fib2: null,
  jetActive: null,
  fundStop: { margin: null, growth: null, hit: null },
};

/** قانون حد ضرر بنیادی: حاشیه سود ناخالص زیر ۲۰٪ یا افت فروش فصلی */
export function fundStopHit(margin: number | null, growth: number | null): boolean | null {
  if (margin == null && growth == null) return null;
  if (margin != null && margin < 20) return true;
  if (growth != null && growth < 0) return true;
  return false;
}

export function useStopLossBoard(symbols: string[]) {
  const uniq = [...new Set(symbols)].slice(0, 20);
  const ftsQ = useQueries({
    queries: uniq.map((symbol) => ({
      queryKey: ['stop-fts', symbol],
      queryFn: ({ signal }) =>
        http<z.infer<typeof FtsStopSchema>>(`/api/fts/${encodeURIComponent(symbol)}`, {
          schema: FtsStopSchema,
          signal,
          retries: 1,
        }),
      staleTime: 10 * 60_000,
      gcTime: 30 * 60_000,
      retry: false,
      refetchOnWindowFocus: false,
    })),
  });
  const fundQ = useQueries({
    queries: uniq.map((symbol) => ({
      queryKey: ['stop-fund', symbol],
      queryFn: ({ signal }) =>
        http<z.infer<typeof FundStopSchema>>(`/api/fundamental/${encodeURIComponent(symbol)}`, {
          schema: FundStopSchema,
          signal,
          retries: 1,
        }),
      staleTime: 30 * 60_000,
      gcTime: 60 * 60_000,
      retry: false,
      refetchOnWindowFocus: false,
    })),
  });

  const out = new Map<string, StopCell>();
  const loading = ftsQ.some((q) => q.isPending) || fundQ.some((q) => q.isPending);
  uniq.forEach((symbol, i) => {
    const fts = ftsQ[i]?.data;
    const fund = fundQ[i]?.data;
    const l1 = fts?.fts?.exit_engine?.l1 ?? null;
    const margin = fund?.metrics?.gross_margin ?? null;
    const growth = fund?.metrics?.monetary_growth_pct ?? fund?.metrics?.growth_pct ?? null;
    out.set(symbol, {
      symbol,
      techStop: l1?.hard_stop ?? l1?.ma14 ?? null,
      techBasis:
        l1?.stop_basis === 'swing_low'
          ? '۵٪ زیر آخرین کف ماژور'
          : l1?.stop_basis === 'entry'
            ? '۵٪ زیر کف ورود'
            : l1?.ma14 != null && l1?.hard_stop == null
              ? 'شکست MA-14'
              : 'بدون داده',
      fib1: fts?.fts?.fib?.zone_33_40
        ? { lo: fts.fts.fib.zone_33_40.lo ?? null, hi: fts.fts.fib.zone_33_40.hi ?? null }
        : null,
      fib2: fts?.fts?.fib?.zone_618_70
        ? { lo: fts.fts.fib.zone_618_70.lo ?? null, hi: fts.fts.fib.zone_618_70.hi ?? null }
        : null,
      jetActive: fts?.fts?.jet?.active ?? null,
      fundStop: { margin, growth, hit: fundStopHit(margin, growth) },
    });
  });
  return { map: out, loading, empty: { ...NO_STOP } };
}
