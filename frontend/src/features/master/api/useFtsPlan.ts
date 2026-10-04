// features/master/api/useFtsPlan.ts -- پارامترهای قیمتی برنامه معاملاتی
// فقط‌خواندنی از /api/fts/{symbol} (مالک م hosted تب تکنیکال است) —
// fib_zones و range_box و exit_engine را fetch می‌کند و در فرانت بازتولید نمی‌کند.
// Circuit Breaker: نبود فیلد ⇒ null + برچسب «بدون داده»، نه خطای UI.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const FibZone = z.object({
  lo: z.number().nullish(),
  hi: z.number().nullish(),
  in_zone: z.boolean().nullish(),
});

const Fib = z
  .object({
    retrace_base_high: z.number().nullish(),
    retrace_base_low: z.number().nullish(),
    zone_33_40: FibZone.nullish(),
    zone_618_70: FibZone.nullish(),
  })
  .nullish();

const Jet = z.object({
  active: z.boolean().nullish(),
  resistance: z.number().nullish(),
  /** سقفِ تاریخیِ منتشرشده — اگر `null` باشد عددِ `resistance` فقط
   *  بالاترینِ دیدِ ماست و برآیندِ مستر آن را «سقفِ تاریخی» نمی‌نویسد */
  ceiling: z.number().nullish(),
  ath: z.boolean().nullish(),
  close: z.number().nullish(),
  pct_above_res: z.number().nullish(),
});

const ExitL1 = z
  .object({
    hard_stop: z.number().nullish(),
    stop_basis: z.string().nullish(),
    stop_hit: z.boolean().nullish(),
    ma14_exit: z.boolean().nullish(),
    ma14_exit_pending: z.boolean().nullish(),
    ma14: z.number().nullish(),
    close: z.number().nullish(),
  })
  .nullish();

const ExitEngine = z.object({ verdict: z.string().nullish(), l1: ExitL1 }).nullish();

// ── داوریِ موتور، نه فقط عددِ سطوح ──
// Round L: برآیندِ مستر باید همان `status` و گیتِ هفتگی/روزانه را بخواند؛ تا پیش
// از این این فایل فقط سطح‌ها را می‌گرفت و Master مجبور بود حکم را جای دیگری بسازد.
const TrendLeg = z.object({ trend: z.string().nullish() }).nullish();

const StatusTrigger = z
  .object({
    kind: z.string().nullish(),
    label: z.string().nullish(),
    price: z.number().nullish(),
    date: z.string().nullish(),
    role: z.string().nullish(),
  })
  .nullish();

const FtsStatus = z
  .object({
    code: z.string().nullish(),
    text: z.string().nullish(),
    trigger: StatusTrigger,
    vetoed: z.boolean().nullish(),
  })
  .nullish();

const Hourglass = z
  .object({
    active: z.boolean().nullish(),
    action: z.string().nullish(),
    ma52: z.number().nullish(),
    weekly_rsi5: z.number().nullish(),
    desc: z.string().nullish(),
  })
  .nullish();

const FtsPlanSchema = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  analysis_basis: z.string().nullish(),
  fts: z
    .object({
      fib: Fib,
      jet: Jet.nullish(),
      exit_engine: ExitEngine,
      status: FtsStatus,
      hourglass: Hourglass,
      trend: z
        .object({
          D: TrendLeg,
          W: TrendLeg,
          matrix: z
            .object({
              decision: z.string().nullish(),
              setup: z.string().nullish(),
              desc: z.string().nullish(),
            })
            .nullish(),
        })
        .nullish(),
    })
    .nullish(),
});

export type FtsPlanFeed = z.infer<typeof FtsPlanSchema>;

export function useFtsPlan(symbol: string) {
  return useQuery({
    queryKey: ['fts-plan', symbol],
    queryFn: ({ signal }) =>
      http<FtsPlanFeed>(`/api/fts/${encodeURIComponent(symbol)}`, { schema: FtsPlanSchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
