// features/portfolio/api/useSymbolBasket.ts -- CRUD وضعیت نماد در سبد تصمیم
// قرارداد بک‌اند (فقط مصرف؛ ساخت نزن):
//   GET    /api/selection/portfolio            → همهٔ تصمیم‌ها (accept/reject/monitor)
//   POST   /api/selection/decision             → ثبت/بروزرسانی (upsert با کلید نماد؛
//                                                status=pending یعنی بازگشت به «بررسی‌نشده» = پاک شدن رکورد)
//   DELETE /api/selection/decision/{symbol}    → حذف کامل تصمیم
// اصل Circuit Breaker: دادهٔ غایب/خطا ⇒ state صادقانه برمی‌گردد؛ هرگز عدد ساختگی.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { http, HttpError } from '@shared/api/http';
import { PORTFOLIO_QUERY_KEY } from './usePortfolio';

export const BASKET_STATUSES = ['accept', 'monitor', 'reject', 'pending'] as const;
export type BasketStatus = (typeof BASKET_STATUSES)[number];

/** رکورد تصمیم — فیلدهای اختیاری نال‌پذیرند تا پاسخ ناقص هرگز UI را نکشدد */
export const BasketDecisionSchema = z.object({
  symbol: z.string().min(1),
  name: z.string().nullish(),
  status: z.string().nullish(),
  reason: z.string().nullish(),
  note: z.string().nullish(),
  stop_loss: z.union([z.number(), z.string()]).nullish(),
  asset_kind: z.string().nullish(),
  weight_pct: z.number().nullish(),
  price: z.number().nullish(),
  /** تعدادِ دارایی — با قیمت ضرب می‌شود تا وزن خودکار بیاید (#106 PORT-1) */
  qty: z.number().nullish(),
  score: z.number().nullish(),
  pricing_mode: z.string().nullish(),
  sector: z.string().nullish(),
  updated_at: z.string().nullish(),
  // فیلدهای محاسبه‌شدهٔ بک‌اند برای ردیف‌های accept
  value_toman: z.number().nullish(),
  weight_eff_pct: z.number().nullish(),
  weight_manual: z.boolean().nullish(),
  /** منشأ وزن: 'value' (قیمت×تعداد) · 'manual' · 'equal' — «حدس» را از «داده» جدا می‌کند */
  weight_source: z.enum(['value', 'manual', 'equal']).nullish(),
  over_cap: z.boolean().nullish(),
  /** طبقهٔ دارایی از classifyِ بک‌اند؛ null یعنی نمی‌دانیم (نه «سهام») */
  asset_class: z
    .object({ cls: z.string(), kind: z.string().nullish(), sector_name: z.string().nullish() })
    .nullish(),
});
export type BasketDecision = z.infer<typeof BasketDecisionSchema>;

const BasketFeedSchema = z.object({
  status: z.string(),
  decisions: z.array(BasketDecisionSchema).nullish(),
  counts: z.record(z.string(), z.number()).nullish(),
});
export type BasketFeed = z.infer<typeof BasketFeedSchema>;

const DecisionSaveSchema = z.object({
  status: z.string(),
  message: z.string().nullish(),
  symbol: z.string().nullish(),
  saved_status: z.string().nullish(),
});

const DecisionDeleteSchema = z.object({
  status: z.string(),
  message: z.string().nullish(),
  deleted: z.number().nullish(),
});

export const BASKET_QUERY_KEY = ['selection-basket'] as const;

/** هر نوشتن روی تصمیم باید هر دو خوانندهٔ همان اندپوینت را بی‌اعتبار کند. */
function invalidateDecisionFeeds(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: BASKET_QUERY_KEY });
  void qc.invalidateQueries({ queryKey: PORTFOLIO_QUERY_KEY });
}

/** فید مشترک همهٔ تصمیم‌ها — یک کوئری برای هر تعداد نماد در هر تب */
export function useBasketFeed() {
  return useQuery({
    queryKey: BASKET_QUERY_KEY,
    queryFn: ({ signal }) =>
      http<BasketFeed>('/api/selection/portfolio', { schema: BasketFeedSchema, signal }),
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export type BasketState = 'accept' | 'monitor' | 'reject' | 'none';

/** وضعیت یک نماد از روی فید — تابع خالص و قابل تست؛ pending/نامشخص ⇒ none */
export function deriveBasketState(feed: BasketFeed | undefined, symbol: string): BasketState {
  if (!feed || !symbol) return 'none';
  const sym = symbol.trim();
  const row = (feed.decisions ?? []).find((d) => d.symbol === sym);
  const s = (row?.status ?? '').trim().toLowerCase();
  if (s === 'accept' || s === 'monitor' || s === 'reject') return s;
  return 'none';
}

/** هوک خودکفا برای یک نماد — در هر تب قابل نصب */
export function useSymbolBasket(symbol: string) {
  const feed = useBasketFeed();
  const state = deriveBasketState(feed.data, symbol);
  const decision =
    (feed.data?.decisions ?? []).find((d) => d.symbol === symbol.trim()) ?? null;
  return {
    state,
    decision,
    /** همهٔ تصمیم‌ها — برای برآوردِ وزنِ یک ردیفِ تازه پیش از ذخیره (#106) */
    decisions: feed.data?.decisions ?? [],
    isLoading: feed.isLoading,
    isError: feed.isError,
    error: feed.error,
    refetch: feed.refetch,
  };
}

export type BasketDecisionInput = {
  symbol: string;
  status: BasketStatus;
  /** وزن درصدی ۰..۱۰۰ — فقط وقتی معنا دارد که ارزشِ ردیف معلوم نباشد */
  weightPct?: number | null;
  /** حد ضرر قیمت — عدد یا رشتهٔ عددی */
  stopLoss?: number | string | null;
  note?: string;
  reason?: string;
  name?: string;
  sector?: string;
  price?: number | null;
  /** تعداد دارایی؛ null یعنی «بفرست، مقدارِ ذخیره‌شده حفظ شود» (#106) */
  qty?: number | null;
};

/** ثبت/بروزرسانی تصمیم نماد (status=pending ⇒ بک‌اند رکورد را پاک می‌کند) */
export function useSaveBasketDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: BasketDecisionInput) => {
      const symbol = (input.symbol ?? '').trim();
      if (!symbol) throw new HttpError(0, '/api/selection/decision', 'نماد خالی است');
      const body: Record<string, unknown> = {
        symbol,
        status: input.status,
        note: input.note ?? '',
        reason: input.reason ?? '',
        stop_loss: input.stopLoss ?? '',
        weight_pct: input.weightPct ?? 0,
      };
      // فیلدهایِ اختیاری فرستاده نمی‌شوند مگر معلوم باشند: بک‌اند کلیدِ غایب را
      // از رکوردِ موجود برمی‌دارد، پس «ویرایشِ یادداشت» قیمت/تعداد را صفر نمی‌کند.
      if (input.name != null) body.name = input.name;
      if (input.sector != null) body.sector = input.sector;
      if (input.price != null) body.price = input.price;
      if (input.qty != null) body.qty = input.qty;
      const res = await http<z.infer<typeof DecisionSaveSchema>>('/api/selection/decision', {
        schema: DecisionSaveSchema,
        method: 'POST',
        body,
      });
      if (res.status !== 'success') {
        throw new HttpError(0, '/api/selection/decision', res.message || 'ثبت تصمیم ناموفق بود');
      }
      return res;
    },
    onSuccess: () => invalidateDecisionFeeds(qc),
  });
}

/** حذف کامل تصمیم نماد (بازگشت به «بررسی‌نشده») */
export function useRemoveBasketDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (symbol: string) => {
      const sym = (symbol ?? '').trim();
      if (!sym) throw new HttpError(0, '/api/selection/decision/', 'نماد خالی است');
      const url = `/api/selection/decision/${encodeURIComponent(sym)}`;
      // DELETE از همان `http()` می‌رود: روی گوشی `resolveLocal` حتماً باید ببیندش
      // (همین‌جا حذفِ تصمیم در localStorage پیاده شده) — با fetchِ خام WebView
      // آدرس را ۴۰۴ می‌داد و «بررسی‌نشده» شدن هرگز ذخیره نمی‌شد.
      const data = DecisionDeleteSchema.parse(await http<unknown>(url, { method: 'DELETE' }));
      if (data.status !== 'success') {
        throw new HttpError(0, url, data.message || 'حذف تصمیم ناموفق بود');
      }
      return data;
    },
    onSuccess: () => invalidateDecisionFeeds(qc),
  });
}
