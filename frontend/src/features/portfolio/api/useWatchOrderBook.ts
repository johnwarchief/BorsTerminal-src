// features/portfolio/api/useWatchOrderBook.ts -- پنج سطرحِ واقعیِ صفِ خرید/فروشِ یک نماد
//
// چرا یک کپی درِ `features/portfolio`: قاعدۀِ FSD (eslint.config.js —
// boundaries/element-types) importِ بینِ featureها را ممنوع می‌کند؛
// `SidebarOrderBook`/`useOrderBook` درِ `features/technical` است و پرتفوی نمی‌تواند
// آن را بکشَد. قراردادِ پاسخ همان `api/chart.py` است:
// `GET /api/order-book/{symbol}` → {status, symbol, levels[], session, totals}.
//
// ضدِ «دادهٔ نمادِ قبلی زیرِ نمادِ جدید»: queryKey با نماد + `select` که اگر
// سرور نمادی جزِ نمادِ خواسته‌شده را برگرداند (پاسخِ جابه‌جا/کهنه) آن را null
// می‌کند. بی‌placeholderData، پس بینِ دو انتخاب هیچ دادهٔ نمادِ دیگر نمایش
// داده نمی‌شود.
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { sessionPollMs } from '@shared/lib/marketHours';
import { useMarketStore } from '@shared/stores/marketStore';

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
  session: z
    .object({
      d_even: z.number().nullish(),
      h_even: z.number().nullish(),
      updated_at: z.string().nullish(),
    })
    .nullish(),
  totals: z
    .object({
      buy_vol: z.number().nullish(),
      buy_cnt: z.number().nullish(),
      sell_vol: z.number().nullish(),
      sell_cnt: z.number().nullish(),
    })
    .nullish(),
});

export type WatchOrderBook = z.infer<typeof BookSchema>;
export type WatchOrderBookLevel = z.infer<typeof LevelSchema>;

/** پاسخِ همان نمادِ خواسته‌شده؟ بی‌مهرۀِ سرور (نسخۀِ قدیمی) ⇒ بی‌رد، ولی
 *  اگر نمادِ دیگری echoed شد این پاسخ کهنه/جابه‌جاست ⇒ null. */
function echoMatches(echoed: string | null | undefined, want: string): boolean {
  if (!echoed) return true;
  return normalizeFa(echoed) === normalizeFa(want);
}

export function useWatchOrderBook(symbol: string) {
  const paused = useMarketStore((s) => s.paused);
  // «این پنجره عمق را نگاه می‌کند» — درِ حالتِ داغ؛ همان اعلانِ مصرفیِ سایدبار
  // (نیشتنی‌شدۀِ /api/order-book نیست؛ فقط می‌گوید کدام نماد تماشا می‌شود).
  useEffect(() => {
    if (!symbol) return;
    void http('/api/orderbook/watch', { method: 'POST', body: { ins_code: symbol } }).catch(() => {});
  }, [symbol]);
  return useQuery({
    queryKey: ['watch-order-book', symbol],
    queryFn: ({ signal }) =>
      http<WatchOrderBook>(`/api/order-book/${encodeURIComponent(symbol)}`, { schema: BookSchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 20_000,
    // order_book فقط وقتی عوض می‌شود که خودِ تابلو همگام شود (~۳۰ ثانیه)؛
    // بیرونِ نشست و تبِ مخفی هیچ درخواستی زده نمی‌شود.
    refetchInterval: paused ? false : () => sessionPollMs(30_000),
    refetchIntervalInBackground: false,
    select: (d: WatchOrderBook) => (echoMatches(d.symbol, symbol) ? d : null),
  });
}
