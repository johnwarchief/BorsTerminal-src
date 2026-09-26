// features/fundamental/api/useFtsConfig.ts -- پیش‌شرط‌های fts_thresholds.json
// GET/POST /api/fts/config — همان کلیدهایی که پنل تنظیمات کدال می‌نویسد.
// بازنشانی (Reset) = ارسال کل پیش‌فرض‌های جزوه؛ کلیدهای غایب در سرور
// مقدار کهنهٔ فایل را نگه می‌دارند، پس Reset باید همهٔ کلیدها را صریح بفرستد.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

export const FtsConfigPayloadSchema = z.object({
  growth_min: z.number(),
  eps_years: z.number(),
  margin_min: z.number(),
  margin_optimal: z.number(),
  sales_to_mcap_min: z.number(),
  profit_potential_min: z.number(),
  industry_mode: z.string(),
  watchlist_max: z.number(),
  mcap_min_hmt: z.number(),
  suspended_max_stale_sessions: z.number(),
  filter_m141: z.boolean(),
  min_trade_val: z.number(),
  mandatory_sectors: z.array(z.string()),
  free_sectors: z.array(z.string()),
  include_industries: z.array(z.string()).nullish(),
  exclude_industries: z.array(z.string()).nullish(),
  v10_monetary_growth_min: z.number().nullish(),
  v10_volume_growth_min: z.number().nullish(),
  v10_volume_breadth_min: z.number().nullish(),
  v10_eps_years: z.number().nullish(),
  v10_margin_min: z.number().nullish(),
  v10_margin_ideal: z.number().nullish(),
  v10_sales_to_mcap_min: z.number().nullish(),
  v10_potential_min: z.number().nullish(),
  v10_inflation_basis: z.number().nullish(),
});

export const FtsConfigSchema = z.object({
  status: z.string(),
  config: FtsConfigPayloadSchema.nullish(),
  message: z.string().nullish(),
  errors: z.record(z.string(), z.string()).nullish(),
});
export type FtsConfig = z.infer<typeof FtsConfigPayloadSchema>;

/** پیش‌فرض‌های جزوهٔ FTS — مرجع Reset و seed اسلایدرها */
export const FTS_GUIDE_DEFAULTS = {
  growth_min: 40.0,
  eps_years: 3,
  margin_min: 20.0,
  margin_optimal: 30.0,
  sales_to_mcap_min: 0.33,
  profit_potential_min: 40.0,
  industry_mode: 'Exclude_Mandatory_Pricing',
  watchlist_max: 50,
  mcap_min_hmt: 0.0,
  suspended_max_stale_sessions: 3,
  filter_m141: false,
  min_trade_val: 0.0,
  /** فهرستِ **سخت‌گیرانه**: کلید «همهٔ صنایعِ دستوری» همین را POST می‌کند و «صنایع مجاز با جهش نرخ» دارو/غذا را از آن کم می‌کند. به همین دلیل با پیش‌فرضِ سرور (که دارو/غذا را ندارد) برابر نیست — گاردِ parity همین یک کلید را به‌جای برابری، زیرمجموعه‌بودنِ سرور بررسی می‌کند. */
  mandatory_sectors: ['خودرو', 'دارو', 'نیروگاه', 'قند و شکر', 'غذا', 'لاستیک', 'شوینده', 'بیمه'],
  free_sectors: ['سیمان', 'پتروشیمی', 'شیمیایی', 'فلزات', 'کانی', 'کاشی', 'سرامیک', 'شیشه', 'کانه', 'معادن', 'نفت', 'محصولات فلزی'],
  include_industries: [] as string[],
  exclude_industries: [] as string[],
  v10_monetary_growth_min: 60,
  v10_volume_growth_min: 0,
  v10_volume_breadth_min: 0.6,
  v10_eps_years: 3,
  v10_margin_min: 20,
  v10_margin_ideal: 30,
  /** کف نسبت فروش سالانه‌شده به ارزش بازار — ۰.۳۳ = ۳۳٪ (تصمیمِ مالک؛ مطلوب ۱.۰) */
  v10_sales_to_mcap_min: 0.33,
  v10_potential_min: 40,
  /** مبنای تورمِ داخلِ فرمولِ ۱ب (٪). مالک ۱۴۰۵-۰۷-۰۴ خواست این عدد درِ دستِ کاربر باشد؛ پیش‌فرض = هدفِ ۶۰٪ جزوه. */
  v10_inflation_basis: 60,
} as const;

/** پیش‌فرضِ کشوی تنظیمات: کف فروش/ارزش بازار ۳۳٪ (مطلوب ۱۰۰٪) */
export const SALES_TO_MCAP_GUIDE_DEFAULT = 0.33;

export function useFtsConfig() {
  return useQuery({
    queryKey: ['fts-config'],
    queryFn: ({ signal }) => http<z.infer<typeof FtsConfigSchema>>('/api/fts/config', { schema: FtsConfigSchema, signal }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export type FtsConfigSaveResult = { ok: boolean; errors?: Record<string, string>; message?: string };

/** ذخیرهٔ پیش‌شرط‌ها — payload کامل (نه دلتا) تا سرور مقدار کهنه نگه ندارد */
export function useSaveFtsConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>): Promise<FtsConfigSaveResult> => {
      const res = await http<z.infer<typeof FtsConfigSchema>>('/api/fts/config', {
        method: 'POST',
        body: payload,
        retries: 0,
      });
      if (res.status !== 'success') {
        return { ok: false, errors: res.errors ?? undefined, message: res.message ?? 'ذخیره نشد' };
      }
      return { ok: true };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fts-config'] });
      qc.invalidateQueries({ queryKey: ['fts-screen'] });
      qc.invalidateQueries({ queryKey: ['fts-card'] });
    },
  });
}
