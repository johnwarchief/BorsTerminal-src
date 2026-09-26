// features/portfolio/api/useSymbolSearch.ts -- جستجوی نماد برای «افزودن دارایی»
// #106 (PORT-1): نام و قیمتِ دارایی باید از سرور بیاید، نه از تایپِ کاربر؛
// کاربر فقط «تعداد» را می‌داند. بک‌اند فیلتر می‌کند (سهام و صندوق) و طبقه را از
// همان classifyِ جدولِ بازار می‌دهد — نگاشتِ دومِ «طلا/نقره/…» در فرانت ممنوع.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

export const SymbolHitSchema = z.object({
  symbol: z.string().min(1),
  name: z.string().default(''),
  sector_name: z.string().default(''),
  /** 'stock' | 'fund' — طبقهٔ ابزار */
  cls: z.string().default(''),
  /** زیرگونهٔ صندوق: gold / silver / fixed / equity / … */
  kind: z.string().default(''),
  /** قیمتِ جاری؛ null یعنی تابلو قیمتی ندارد و کاربر باید خودش وارد کند */
  price: z.number().nullable().default(null),
});
export type SymbolHit = z.infer<typeof SymbolHitSchema>;

const SearchFeedSchema = z.object({
  status: z.string(),
  count: z.number().nullish(),
  query: z.string().nullish(),
  data: z.array(SymbolHitSchema).nullish(),
});

export const SYMBOL_SEARCH_KEY = ['portfolio-symbol-search'] as const;

/** حداقلِ دو نویسه؛ با یک نویسه ده‌ها نتیجه بی‌فایده برگردانده می‌شود */
export const SYMBOL_SEARCH_MIN = 2;

export function useSymbolSearch(raw: string) {
  const q = (raw ?? '').trim();
  return useQuery({
    queryKey: [...SYMBOL_SEARCH_KEY, q],
    queryFn: ({ signal }) =>
      http<z.infer<typeof SearchFeedSchema>>(
        `/api/selection/symbols?q=${encodeURIComponent(q)}`,
        { schema: SearchFeedSchema, signal },
      ),
    enabled: q.length >= SYMBOL_SEARCH_MIN,
    staleTime: 5 * 60_000,
    gcTime: 10 * 60_000,
  });
}
