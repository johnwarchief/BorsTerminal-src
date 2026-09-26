// features/market/api/useFtsFunnel.ts -- قیفِ پنج‌محوریِ FTS رویِ کلِ بازار
// سرِبراههٔ جزوه: FTS قیف است، نه پنج نمرهٔ جدا. این آمار را خودِ سرور از همان
// کشِ /api/screener می‌شمارد (api/fundamental.py:api_fundamental_funnel) — لایهٔ
// نمایش هیچ امتیازی دوباره نمی‌سازد.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const num = z.number().nullish();

export const FtsFunnelSchema = z.object({
  status: z.string(),
  total: num,
  tested: num,
  not_applicable: num,
  vetoed: num,
  axes: z.array(z.object({ key: z.string(), column: z.string(), pass: num })).nullish(),
  verdicts: z.record(z.string(), z.number()).nullish(),
});

export type FtsFunnel = z.infer<typeof FtsFunnelSchema>;

/** شمارۀ محور → تعدادِ ردشدگان؛ -۱ یعنی سرور این محور را نفرستاده (بدون داده) */
export function funnelPass(funnel: FtsFunnel | null | undefined, column: string): number {
  const hit = funnel?.axes?.find((a) => a.column === column) ?? null;
  return typeof hit?.pass === 'number' ? hit.pass : -1;
}

export function useFtsFunnel() {
  return useQuery({
    queryKey: ['fts-funnel'],
    queryFn: ({ signal }): Promise<FtsFunnel> =>
      http<FtsFunnel>('/api/fundamental/funnel', { schema: FtsFunnelSchema, signal }),
    // قیف با هر اسکنِ کدال عوض می‌شود، نه با هر تیکِ تابلو — کشِ طولانی بی‌ضرر است.
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
}
