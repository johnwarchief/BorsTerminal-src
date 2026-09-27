// features/technical/api/useFtsAnalysis.ts -- تحلیل FTS سمت سرور (بدج استریپ)
// موازی با بج های tech_rtv.js قدیمی: روند D/W/M، فیبو، جت، CHoCH، شکار نقطه، موتور خروج.
// پاسخ empty (نماد بدون تاریخچه) حالت مشروع است و ماسک نمی شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const TrendLeg = z.object({
  trend: z.string(),
  hh: z.boolean().nullish(),
  hl: z.boolean().nullish(),
  last_high: z.number().nullish(),
  prev_high: z.number().nullish(),
  last_low: z.number().nullish(),
  prev_low: z.number().nullish(),
});

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
    // سطوحِ کاملِ ابزارِ فیبو (۰ تا ۱) و خودِ موجِ لنگر — چارت این‌ها را رسم
    // می‌کند و هیچ‌چیز را دوباره حساب نمی‌کند.
    levels: z.array(z.object({ ratio: z.number(), price: z.number() })).nullish(),
    leg: z
      .object({
        direction: z.string().nullish(),
        start: z.string().nullish(),
        end: z.string().nullish(),
        high: z.number().nullish(),
        low: z.number().nullish(),
      })
      .nullish(),
  })
  .nullish();

const Setup = z.object({
  date: z.string(),
  kind: z.string(),
  label: z.string(),
  price: z.number(),
  side: z.string().nullish(),
});

const Jet = z.object({
  active: z.boolean().nullish(),
  resistance: z.number().nullish(),
  ath: z.boolean().nullish(),
  close: z.number().nullish(),
  pct_above_res: z.number().nullish(),
});

const Choch = z.object({
  bearish: z.boolean().nullish(),
  bullish: z.boolean().nullish(),
  level: z.number().nullish(),
  label: z.string().nullish(),
});

const PointHunt = z.object({
  touches: z.number().nullish(),
  floor_price: z.number().nullish(),
  active: z.boolean().nullish(),
  floor_idx: z.number().nullish(),
  // تاریخِ کندلِ لنگر — چارت فقط با این می‌تواند نشانگر را رویِ کندلِ درست
  // بگذارد؛ اندیسِ آرایۀِ سرور با ردیف‌هایِ دیدۀِ مرورگر یکی نیست (#193).
  floor_date: z.string().nullish(),
});

const DoubleBottom = z.object({
  active: z.boolean().nullish(),
  neckline: z.number().nullish(),
  pct_above_neck: z.number().nullish(),
});

const RangeBox = z.object({
  active: z.boolean().nullish(),
  top: z.number().nullish(),
  bottom: z.number().nullish(),
  pct_above_top: z.number().nullish(),
});

const ExitEngine = z.object({
  verdict: z.string(),
  signals: z.array(z.string()).nullish(),
  l1: z
    .object({
      hard_stop: z.number().nullish(),
      stop_basis: z.string().nullish(),
      stop_hit: z.boolean().nullish(),
      ma14_exit: z.boolean().nullish(),
      ma14_exit_pending: z.boolean().nullish(),
      ma14: z.number().nullish(),
      close: z.number().nullish(),
    })
    .nullish(),
  l2: z
    .object({
      choch_break: z.boolean().nullish(),
      channel_break: z.boolean().nullish(),
      level: z.number().nullish(),
      touches: z.number().nullish(),
    })
    .nullish(),
  l3: z
    .object({
      third_peak: z.boolean().nullish(),
      third_peak_level: z.number().nullish(),
      double_top: z.boolean().nullish(),
      hs_break: z.boolean().nullish(),
      neckline: z.number().nullish(),
      level: z.number().nullish(),
    })
    .nullish(),
  l4: z
    .object({
      rsi_divergence: z.boolean().nullish(),
      rsi_rollover: z.boolean().nullish(),
      rsi: z.number().nullish(),
      rsi_prev_peak: z.number().nullish(),
    })
    .nullish(),
});

const MatrixDecision = z.object({
  decision: z.string().nullish(),
  setup: z.string().nullish(),
  desc: z.string().nullish(),
});

const HourglassStrategy = z.object({
  active: z.boolean().nullish(),
  weekly_close: z.number().nullable().nullish(),
  ma52: z.number().nullable().nullish(),
  weekly_rsi5: z.number().nullable().nullish(),
  action: z.string().nullish(),
  desc: z.string().nullish(),
});

export const FtsAnalysis = z.object({
  trend: z
    .object({
      D: TrendLeg.nullish(),
      W: TrendLeg.nullish(),
      M: TrendLeg.nullish(),
      alignment: z.string().nullish(),
      matrix: MatrixDecision.nullish(),
    })
    .nullish(),
  fib: Fib,
  jet: Jet.nullish(),
  choch: Choch.nullish(),
  point_hunt: PointHunt.nullish(),
  double_bottom: DoubleBottom.nullish(),
  range_box: RangeBox.nullish(),
  exit_engine: ExitEngine.nullish(),
  hourglass: HourglassStrategy.nullish(),
  setups: z.array(Setup).nullish(),
});

export type FtsAnalysisData = z.infer<typeof FtsAnalysis>;

const FtsResponse = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  fts: FtsAnalysis.nullish(),
});

export type FtsResponseData = z.infer<typeof FtsResponse>;

export function useFtsAnalysis(symbol: string) {
  return useQuery({
    queryKey: ['fts-analysis', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof FtsResponse>>(`/api/fts/${encodeURIComponent(symbol)}`, {
        schema: FtsResponse,
        signal,
      }),
    enabled: symbol.length > 0,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
