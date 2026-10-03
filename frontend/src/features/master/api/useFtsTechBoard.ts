// features/master/api/useFtsTechBoard.ts -- رأیِ تکنیکالِ دو زمانه برایِ نامادهایِ قیف
//
// چرا این‌جا هست و نه در خودِ قیف: اسکرینرِ کدال تحلیلِ تکنیکال را فقط روی
// سقفِ `watchlist_max` ردیفِ اول (رتبه‌بندیِ بنیادی) اجرا می‌کند — سنجشِ زندهٔ
// 1405-07-06: از 128 نمادِ نشانه‌خوردهٔ تابلو فقط 1 نماد رأیِ تکنیکال داشت.
// قیفِ درخت استراتژی بدونِ رأیِ تکنیکال فقط «سنجیده نشد» می‌شمرد و درِ چارت
// (ستون T) هرگز بسته نمی‌شد. آدرسِ `/api/fts/{symbol}` همان موتورِ اسکرینر
// است، فقط برایِ یک نماد (اندازۀ پاسخ ~۳ کیلوبایت، ~۰٫۷ ثانیه).
//
// الگو از features/portfolio/api/useStopLossBoard.ts گرفته شده است: به ازای هر
// نماد یک کوئریِ سبک، نه یک fetchِ دسته‌ای — تا نمادِ تازه فقط خودش را بخواهد
// و پاسخ‌هایِ پیشین درِ کشِ TanStack بمانند. هم‌زمانیِ واقعی را سقفِ ۶ اتصالِ
// Chromium به ازای هر host تنظیم می‌کند، پس پولینگِ تابلو گرسنه نمی‌ماند.
import { useQueries } from '@tanstack/react-query';
import { useMemo, useRef } from 'react';
import { z } from 'zod';
import { http } from '@shared/api/http';

const Flag = z.object({ active: z.boolean().nullish(), bullish: z.boolean().nullish() });
const Zone = z.object({ in_zone: z.boolean().nullish() });

const FtsTechSchema = z.object({
  status: z.string(),
  fts: z
    .object({
      trend: z
        .object({
          D: z.object({ trend: z.string().nullish() }).nullish(),
          W: z.object({ trend: z.string().nullish() }).nullish(),
          matrix: z
            .object({
              decision: z.string().nullish(),
              setup: z.string().nullish(),
              desc: z.string().nullish(),
            })
            .nullish(),
        })
        .nullish(),
      jet: z
        .object({ active: z.boolean().nullish(), resistance: z.number().nullish(), pct_above_res: z.number().nullish() })
        .nullish(),
      choch: Flag.nullish(),
      double_bottom: Flag.nullish(),
      range_box: Flag.nullish(),
      hourglass: Flag.nullish(),
      point_hunt: Flag.nullish(),
      fib: z
        .object({
          zone_33_40: Zone.nullish(),
          zone_618_70: Zone.nullish(),
        })
        .nullish(),
    })
    .nullish(),
});

/** رأیِ نرمال‌شدۀ تکنیکال — همان چیزی که درِ T درِ چارت می‌خواند */
export type TechVerdict = {
  /** PERMITTED / REJECT / UNKNOWN — رأیِ خودِ `trend.matrix` درِ بک‌اند */
  decision: string | null;
  matrixDesc: string | null;
  trendW: string | null;
  trendD: string | null;
  jet: boolean;
  fibZone: string | null;
  chochBull: boolean;
  doubleBottom: boolean;
  rangeBreak: boolean;
  hourglass: boolean;
  /** `true`/`false` از خودِ موتور؛ این‌جا هیچ‌وقت از نبودِ داده ساخته نمی‌شود */
  pointHunt: boolean;
  /** شواهدِ ستاپِ جت از همان پاسخ — برایِ «فاصله تا ماشه»؛ نه فرمولِ فرانت */
  jetResistance: number | null;
  jetPctAbove: number | null;
};

export const TECH_QUERY_CAP = 60;

/**
 * `symbols` باید **از پیشِ مرتب** بیاید: `lib/ftsFunnel.ts::techQueryQueue` آن را
 * با رتبۀ رسمیِ بک‌اند (`screener.py:440`) می‌چیند. این‌جا دیگر `slice` رویِ
 * ترتیبِ تصادفیِ تابلو نمی‌شود — که با هر رفرش عوض می‌شد و «کی سنجیده شد» را
 * قمار می‌کرد. `requested` تعدادِ کلِ صف است تا UI بگوید چند نماد بیرونِ بودجه
 * مانده (`unavailable`، نه `reject`).
 */
export function useFtsTechBoard(symbols: string[]) {
  const all = [...new Set(symbols.filter(Boolean))];
  const uniq = all.slice(0, TECH_QUERY_CAP);
  const q = useQueries({
    queries: uniq.map((symbol) => ({
      queryKey: ['fts-tech', symbol],
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        http<z.infer<typeof FtsTechSchema>>(`/api/fts/${encodeURIComponent(symbol)}`, {
          schema: FtsTechSchema,
          signal,
          retries: 1,
        }),
      staleTime: 30 * 60_000,
      gcTime: 2 * 60 * 60_000,
      retry: false,
      refetchOnWindowFocus: false,
      enabled: uniq.length > 0,
    })),
  });
  const latest = useRef({ uniq, q });
  latest.current = { uniq, q };

  // امضایِ محتوا: نقشه فقط وقتی از نو ساخته می‌شود که رأیی واقعاً عوض شده باشد.
  // بی‌این هر رندرِ تابلو (1 تا 5 ثانیه) یک Mapِ نو می‌ساخت و قیفِ 5360
  // ردیفی دوباره حساب می‌شد — روی ماشینِ کند همین تفاوتِ روانی و پرش است.
  const sig = uniq
    .map((s, i) => {
      const f = q[i]?.data?.fts;
      if (!f) return `${s}:-`;
      return [
        s,
        f.trend?.matrix?.decision ?? '',
        f.trend?.W?.trend ?? '',
        f.trend?.D?.trend ?? '',
        f.jet?.active ? 1 : 0,
        f.jet?.resistance ?? '',
        f.fib?.zone_33_40?.in_zone ? 1 : 0,
        f.fib?.zone_618_70?.in_zone ? 1 : 0,
        f.choch?.bullish ? 1 : 0,
        f.double_bottom?.active ? 1 : 0,
        f.range_box?.active ? 1 : 0,
        f.hourglass?.active ? 1 : 0,
        f.point_hunt?.active ? 1 : 0,
      ].join(':');
    })
    .join('|');

  const map = useMemo(() => {
    const out = new Map<string, TechVerdict>();
    const { uniq: syms, q: results } = latest.current;
    syms.forEach((symbol, i) => {
      const f = results[i]?.data?.fts;
      if (!f) return;
      const fib33 = f.fib?.zone_33_40?.in_zone === true;
      const fib61 = f.fib?.zone_618_70?.in_zone === true;
      out.set(symbol, {
        decision: f.trend?.matrix?.decision ?? null,
        matrixDesc: f.trend?.matrix?.desc ?? null,
        trendW: f.trend?.W?.trend ?? null,
        trendD: f.trend?.D?.trend ?? null,
        jet: f.jet?.active === true,
        jetResistance: typeof f.jet?.resistance === 'number' ? f.jet.resistance : null,
        jetPctAbove: typeof f.jet?.pct_above_res === 'number' ? f.jet.pct_above_res : null,
        fibZone: fib33 ? '33-40' : fib61 ? '61.8-70' : null,
        chochBull: f.choch?.bullish === true,
        doubleBottom: f.double_bottom?.active === true,
        rangeBreak: f.range_box?.active === true,
        hourglass: f.hourglass?.active === true,
        pointHunt: f.point_hunt?.active === true,
      });
    });
    return out;
  }, [sig]);

  // تازگیِ رأیِ هر نماد (#16): زمانِ آخرینِ دریافتِ خودِ همین پاسخ، نه زمانِ رندر.
  // مثلِ `map` با امضایِ محتوا می‌سازد — وگرنه هر رندر یک Mapِ نو می‌داد و
  // useMemoهایِ پایینِ دست (قیفِ چندصدردیفی) دوباره حساب می‌شدند.
  const asOf = useMemo(() => {
    const out = new Map<string, number>();
    const { uniq: syms, q: results } = latest.current;
    syms.forEach((symbol, i) => {
      const d = results[i]?.dataUpdatedAt;
      if (d) out.set(symbol, d);
    });
    return out;
  }, [sig]);

  return {
    map,
    asOf,
    loading: q.some((r) => r.isPending),
    wanted: uniq.length,
    /** چند نماد در صف بودند — تفاوتِ `queued - wanted` بیرونِ بودجه مانده است */
    queued: all.length,
    beyondCap: Math.max(0, all.length - uniq.length),
    resolved: map.size,
  };
}
