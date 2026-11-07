// features/technical/api/useStructure3.ts -- قراردادِ دادهٔ موتورِ سوم (مستقل، بی‌رأی)
// `/api/structure3/{symbol}` تنها مسیرِ این لایه است: نه چیزی از `/api/fts`
// بازتفسیر می‌شود، نه داوریِ سوم درِ فرانت ساخته می‌شود. آستانه‌ها (`params`)
// از خودِ موتور خوانده می‌شوند و درِ رابط فقط نمایش داده می‌شوند.
// `official=false` و `voting=false` درِ payload یعنی این خروجی درِ رأیِ FTS
// مشارکت ندارد؛ پس هیچ‌وقت با نقاطِ ساختاریِ موتورِ اول قاطی نمی‌شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

export const Structure3Point = z.object({
  idx: z.number(),
  /** 'YYYY-MM-DD' وقوعِ پیوت (کِی رخ داد) */
  time: z.string(),
  price: z.number(),
  kind: z.enum(['high', 'low']),
  confirm_idx: z.number(),
  /** کِی فهمیدیم -- بی‌این، ضدِ repaintِ موتورِ سوم بی‌اثبات می‌ماند */
  confirm_time: z.string().nullish(),
  threshold_pct: z.number().nullish(),
  atr_used: z.boolean().nullish(),
  label: z.enum(['HH', 'HL', 'LH', 'LL']).nullish(),
});

export const Structure3Choch = z.object({
  kind: z.enum(['high', 'low']),
  direction: z.enum(['bullish', 'bearish']),
  idx: z.number(),
  time: z.string(),
  confirm_idx: z.number(),
  confirm_time: z.string().nullish(),
  level: z.number(),
});

export const Structure3Meta = z.object({
  bars: z.number().nullish(),
  atr_period: z.number().nullish(),
  atr_mult: z.number().nullish(),
  floor_pct: z.number().nullish(),
  /** تأییدهایی که آستانه‌شان از ATR آمد -- نه از کفِ ۳٪ */
  confirmed_atr: z.number().nullish(),
  confirmed_floor_only: z.number().nullish(),
  atr_missing_bars: z.number().nullish(),
  /** ساختارِ تأییدنشده: درِ شواهد خوانده می‌شود، هرگز رسم نمی‌شود */
  pending: z
    .object({
      idx: z.number().nullish(),
      time: z.string().nullish(),
      price: z.number().nullish(),
      kind: z.string().nullish(),
      confirmed: z.boolean().nullish(),
    })
    .nullish(),
});

export const Structure3Response = z.object({
  status: z.enum(['success', 'empty', 'insufficient', 'error']),
  symbol: z.string().nullish(),
  engine: z.string().nullish(),
  engine_label: z.string().nullish(),
  official: z.boolean().nullish(),
  voting: z.boolean().nullish(),
  rule_source: z.string().nullish(),
  /** بی‌مرجعِ بیرونیِ تأییدشدنی؛ همان «تنها مانعِ مرحلۀ ۲» درِ گزارشِ مأموریت */
  reference_status: z.string().nullish(),
  params: z
    .object({ atr_period: z.number(), atr_mult: z.number(), floor_pct: z.number() })
    .nullish(),
  tf: z.string().nullish(),
  basis: z.string().nullish(),
  bars: z.number().nullish(),
  ref_close: z.number().nullish(),
  as_of: z.string().nullish(),
  message: z.string().nullish(),
  points: z.array(Structure3Point).nullish(),
  choch: z.array(Structure3Choch).nullish(),
  meta: Structure3Meta.nullish(),
});

export type Structure3Data = z.infer<typeof Structure3Response>;
export type Structure3PointData = z.infer<typeof Structure3Point>;

/** لایه پیش‌فرض خاموش است، پس درخواستِ بی‌مصرف هم نمی‌شود (`enabled`) */
export function useStructure3(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: ['structure3', symbol],
    queryFn: ({ signal }) =>
      http<Structure3Data>(`/api/structure3/${encodeURIComponent(symbol)}`, {
        schema: Structure3Response,
        signal,
      }),
    enabled: enabled && symbol.length > 0,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
