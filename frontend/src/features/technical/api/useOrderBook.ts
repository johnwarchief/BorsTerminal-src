// features/technical/api/useOrderBook.ts -- پنج خطِ واقعیِ صفِ خرید و فروشِ یک نماد
// منبع: /api/order-book/{symbol} ← جدولِ order_book ← blDsِ خودِ تابلو.
// این لایه هیچ عددی نمی‌سازد: بی‌داده یعنی فهرستِ خالی و پیامِ سرور.
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
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
  symbol: z.string(),
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

export function useOrderBook(symbol: string) {
  const paused = useMarketStore((s) => s.paused);
  // «این پنجره عمق را نگاه می‌کند» — درِ حالتِ داغ. بیرونِ نشست و درِ تبِ
  // مخفی هیچ درخواستی زده نمی‌شود (پایین‌تر)، پس اشتراک هم فقط درِ دید.
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
    // order_book فقط وقتی عوض می‌شود که خودِ تابلو همگام شود (~۳۰ ثانیه).
    // تندتر از آن فقط درخواستِ بی‌مصرفِ SQLite است؛ و بیرونِ ساعتِ بازار
    // اصلاً چیزی عوض نمی‌شود، پس ریتم به ۵ دقیقه می‌نشیند (#35 گیتِ نشست:
    // تا پیش از این این پولینگ تنها مصرف‌کنندۀ بازار بود که بی‌اعتبار به
    // نشست و بی‌اعتبار به paused، شب‌ها هم هر ۳۰ ثانیه می‌زد).
    refetchInterval: paused ? false : () => sessionPollMs(30_000),
    refetchIntervalInBackground: false,
  });
}
