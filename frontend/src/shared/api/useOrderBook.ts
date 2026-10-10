// shared/api/useOrderBook.ts -- تنها مصرف‌کنندۀ /api/order-book/{symbol}
//
// پیش از این دو کپی از این لایه بود (`features/technical/api/useOrderBook.ts` و
// `features/portfolio/api/useWatchOrderBook.ts`)؛ همان سؤال، دو پاسخ، دو
// queryKey و دو درخواستِ جدا برایِ یک نماد. این فایل هر دو را با هم جمع می‌کند:
//   • دامانۀِ پاسخِ جابه‌جا (echo) از نسخۀِ دیدۀبان،
//   • اعلانِ «این پنجره عمق را نگاه می‌کند» و ریتمِ نشست‌محور از هر دو.
// منبع: `api/chart.py:get_order_book` ← جدولِ `order_book` ← blDsِ خودِ تابلو.
// این لایه هیچ عددی نمی‌سازد: بی‌داده یعنی فهرستِ خالی و پیامِ خودِ سرور.
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

export type OrderBook = z.infer<typeof BookSchema>;
export type OrderBookLevel = z.infer<typeof LevelSchema>;

/** پاسخِ همان نمادِ خواسته‌شده؟ بی‌مهرۀِ سرور ⇒ بی‌رد (نسخۀِ کهنۀ API)، ولی
 *  اگر نمادِ دیگری echoed شد این پاسخ جابه‌جاست و هیچ‌جا نشین نمی‌شود. */
function echoMatches(echoed: string | null | undefined, want: string): boolean {
  if (!echoed) return true;
  return normalizeFa(echoed) === normalizeFa(want);
}

export function useOrderBook(symbol: string) {
  const paused = useMarketStore((s) => s.paused);
  // «این پنجره عمق را نگاه می‌کند» — درِ حالتِ داغ؛ نمادِ دیده‌شده را به
  // بک‌اند می‌گوید تا همان سطرِ order_book تازه بماند (نیشتنِ /api/order-book
  // نیست؛ فقط اعلامِ مصرف).
  useEffect(() => {
    if (!symbol) return;
    void http('/api/orderbook/watch', { method: 'POST', body: { ins_code: symbol } }).catch(() => {});
  }, [symbol]);
  return useQuery({
    queryKey: ['order-book', symbol],
    queryFn: ({ signal }) =>
      http<OrderBook>(`/api/order-book/${encodeURIComponent(symbol)}`, { schema: BookSchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 20_000,
    // order_book فقط وقتی عوض می‌شود که خودِ تابلو همگام شود (~۳۰ ثانیه)؛
    // بیرونِ نشست یا تبِ مخفی هیچ درخواستی زده نمی‌شود.
    refetchInterval: paused ? false : () => sessionPollMs(30_000),
    refetchIntervalInBackground: false,
    select: (d: OrderBook) => (echoMatches(d.symbol, symbol) ? d : null),
  });
}
