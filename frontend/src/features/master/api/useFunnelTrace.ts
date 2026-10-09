// features/master/api/useFunnelTrace.ts — ردپایِ غربالگریِ یک نماد
//
// موتور درِ هر اجرا برایِ هر نماد می‌نویسد کدام فیلترِ تابلو، با چه شمارۀ
// ترتیبی، با چه دلیلی و با چه ورودی/خروجی‌ای رد یا قبولش کرد. این همان
// `timeline` است که درِ پاسخِ `/api/funnel` برایِ *فهرست* نمی‌آید و فقط با
// `GET /api/funnel/trace?symbol=` می‌رسد. تا پیش از این سایدبار فقط «ایستاده
// در مرحلۀ X» را می‌گفت؛ این هوک همان پاسخ را می‌آورد که کاربر *بدون* حدس
// بفهمد فیلتر به‌فیلتر چه شد.
//
// منبعِ داوری اینجا نیست: هیچ وضعیتی درِ فرانت محاسبه نمی‌شود، فقط نمایش
// داده می‌شود (همان قاعدۀ `funnelView.ts`).
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

export const TraceStepSchema = z.object({
  stage: z.string(),
  seq: z.number().nullish(),
  status: z.string(),
  reason_code: z.string().nullish(),
  human_reason: z.string().nullish(),
  input_count: z.number().nullish(),
  output_count: z.number().nullish(),
  source: z.string().nullish(),
  timestamp: z.string().nullish(),
});

const TraceSchema = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  as_of: z.number().nullish(),
  engine_version: z.string().nullish(),
  ruleset_version: z.string().nullish(),
  timeline: z.array(TraceStepSchema).nullish(),
  matrix: z.unknown().nullish(),
  message: z.string().nullish(),
  universe: z.unknown().nullish(),
});

export type TraceStep = z.infer<typeof TraceStepSchema>;
export type FunnelTrace = z.infer<typeof TraceSchema>;

/** همان پارامترهایی که `useFtsFunnel` به `/api/funnel` می‌فرستد. ردپا باید
 *  زیرِ *همان* درخواست حساب شود، وگرنه سایدبار و جدول غربالگری دو حکمِ
 *  متفاوت برایِ یک نماد نشان می‌دهند (و کشِ بک‌اند هم با کلیدِ همین است). */
export interface TraceRequest {
  preset: string;
  chain: readonly string[];
  fundMode: string;
  exceptions: Record<string, string[]>;
}

export function useFunnelTrace(symbol: string | null | undefined, req: TraceRequest) {
  const sym = String(symbol ?? '').trim();
  const qs = `preset=${encodeURIComponent(req.preset)}`
    + `&chain=${encodeURIComponent(req.chain.join(','))}`
    + `&fund_mode=${encodeURIComponent(req.fundMode)}`
    + `&exceptions=${encodeURIComponent(JSON.stringify(req.exceptions ?? {}))}`;
  return useQuery({
    queryKey: ['funnel-trace', sym, req.preset, req.chain.join(','), req.fundMode,
               JSON.stringify(req.exceptions ?? {})],
    queryFn: ({ signal }) =>
      http<FunnelTrace>(`/api/funnel/trace?symbol=${encodeURIComponent(sym)}&${qs}`, {
        schema: TraceSchema,
        signal,
      }),
    enabled: sym.length > 0,
    // ردپا از همان کشِ هشت‌ثانیه‌ایِ موتور می‌آید؛ ده دقیقه برایِ یک پنلِ
    // تفصیلی کافی است و بی‌هزینه نیست (هر miss یک اجرایِ کاملِ ۵٫۸ هزار ردیف).
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}
