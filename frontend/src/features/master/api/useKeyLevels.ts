// features/master/api/useKeyLevels.ts -- سطوحِ کلیدیِ همان نماد (ترازِ پشتیبان/مقاومت)
// Round L §4: `Support` درِ `/api/fts` نیست؛ منبعش همین اندپوینت است، پس اینجا
// خوانده می‌شود نه اینکه حدس زده شود. هیچ داوریِ تازه‌ای در این فایل نیست.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const Level = z.object({
  price: z.number(),
  kind: z.string().nullish(),
  strength: z.number().nullish(),
});

const KeyLevelsSchema = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  levels: z.array(Level).nullish(),
  // P0#1/#12: پیامِ «چرا سطحی نیست» با تعدادِ واقعی باید به رابط برسد؛ پیش از
  // این اسکیمایِ فرانت فقط status/symbol/levels را می‌خواند و message را
  // بی‌صدا دور می‌ریخت — «۰ سطح» با «۳۰ روز سابقه، ۶۰ لازم» یکی می‌شد.
  message: z.string().nullish(),
  insufficient_history: z.boolean().nullish(),
  bars_effective: z.number().nullish(),
  raw_rows: z.number().nullish(),
});

export type KeyLevelsFeed = z.infer<typeof KeyLevelsSchema>;

/** تنها متنِ مجازِ «بی‌سطح»: همان پیامی که سرور با تعدادِ واقعی نوشته. */
export function keyLevelsNote(feed: KeyLevelsFeed | null | undefined): string | null {
  if (!feed) return null;
  if (feed.status === 'ok' && (feed.levels?.length ?? 0) > 0) return null;
  return feed.message ?? null;
}

export function useKeyLevels(symbol: string) {
  return useQuery({
    queryKey: ['key-levels', symbol],
    queryFn: ({ signal }) =>
      http<KeyLevelsFeed>(`/api/chart/${encodeURIComponent(symbol)}/key-levels`, {
        schema: KeyLevelsSchema,
        signal,
      }),
    enabled: symbol.length > 0,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

/**
 * نزدیک‌ترین ترازِ زیرِ قیمت (پشتیبان) و بالایِ قیمت (مقاومت) — فقط مقایسه،
 * بی‌آستانه و بی‌وزن. `close` باید مثبت باشد وگرنه «—».
 */
export function supportResistance(
  levels: Array<{ price: number; kind?: string | null }> | null | undefined,
  close: number | null,
): { support: number | null; resistance: number | null } {
  if (!Array.isArray(levels) || close === null || !(close > 0)) {
    return { support: null, resistance: null };
  }
  const lows = levels.filter((l) => l.kind === 'low' && l.price < close).map((l) => l.price);
  const highs = levels.filter((l) => l.kind === 'high' && l.price > close).map((l) => l.price);
  return {
    support: lows.length ? Math.max(...lows) : null,
    resistance: highs.length ? Math.min(...highs) : null,
  };
}
