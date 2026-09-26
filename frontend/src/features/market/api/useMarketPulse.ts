// features/market/api/useMarketPulse.ts -- نبض بازار FTS (سه اندپوینت mstat در یک کوئری)
// الگوی اسکیمای محلی از useFtsScreen.ts: هر عدد nullable/nullish تا شکاف داده
// کرش نسازد؛ هر اندپوینت به‌تنهایی می‌میرد و چیپ خودش «بدون داده» می‌خورد.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const num = z.number().nullish();

/**
 * «nodata» حالتِ چهارم است، نه خطا: مоторِ کلان وقتی هیچ نمادی در نشستِ جاری
 * معامله نشده (نشستِ پیش از بازگشایی یا روزِ تعطیل) داوری نمی‌کند. پیش از این
 * نبودنِ داده را «نامساعد» می‌خواندیم — رأیِ مالک: هیچ‌چیز نباید از نبودِ داده
 * سبز یا قرمز بسازد. این رشته در اسکیماست، وگرنه اعتبارسنجی کل پاسخ می‌شکند.
 */
export const HematStateSchema = z.enum(['good', 'mid', 'bad', 'nodata']);
export type HematState = z.infer<typeof HematStateSchema>;

/** آستانه‌های سلامت کلان (سند FTS صفحهٔ ۳ -- آینهٔ mstat_engine.HEMAT_GOOD/BAD) */
export const HEMAT_GOOD = 20;
export const HEMAT_BAD = 10;
export const HEMAT_LABELS: Record<HematState, string> = {
  good: 'مساعد', mid: 'متوسط', bad: 'نامساعد', nodata: 'بدون داده',
};

/** دماسنج همت: ≥۲۰ سبز / میان ۱۰ و ۲۰ زرد / ≤۱۰ قرمز؛ عدد غایب یعنی null */
export function hematState(v: number | null | undefined): HematState | null {
  if (typeof v !== 'number' || !Number.isFinite(v)) return null;
  if (v >= HEMAT_GOOD) return 'good';
  if (v <= HEMAT_BAD) return 'bad';
  return 'mid';
}

export const SmartMoneySchema = z.object({
  status: z.string(),
  macro: z
    .object({
      value_hemat: num,
      state: HematStateSchema.nullish(),
      label: z.string().nullish(),
      good_min: num,
      bad_max: num,
      trade_value_all_market_hemat: num,
      market_value_hemat: num,
      market_value_source: z.string().nullish(),
      // شاخصِ رسمیِ همان نشست (GetMarketOverview بورس) — غایب = null، نه صفر
      index: z
        .object({
          d_even: num,
          last: num,
          change: num,
          pct: num,
          ew_last: num,
          ew_change: num,
          ew_pct: num,
        })
        .nullish(),
    })
    .nullish(),
  watch_entry: z
    .object({
      active: z.boolean().nullish(),
      bearish_pct: num,
      rule_pct: num,
      bearish: num,
      known: num,
    })
    .nullish(),
  flow: z
    .object({
      ideal_fts: z.boolean().nullish(),
      eq_inflow: z.boolean().nullish(),
      fixed_outflow: z.boolean().nullish(),
      eq_flow_b_toman: num,
      fixed_flow_b_toman: num,
    })
    .nullish(),
});
export type SmartMoney = z.infer<typeof SmartMoneySchema>;

export const SummaryRowSchema = z.object({
  key: z.string(),
  label: z.string().nullish(),
  symbols: num,
  traded: num,
  pc_buy_m_toman: num,
  pc_sell_m_toman: num,
  buy_power: num,
  buy_power_up: z.boolean().nullish(),
  money_flow_b_toman: num,
});

export const SummarySchema = z.object({
  status: z.string(),
  rows: z.array(SummaryRowSchema).nullish(),
  health: z
    .object({
      value_hemat: num,
      state: HematStateSchema.nullish(),
      label: z.string().nullish(),
      trade_value_all_market_hemat: num,
      market_value_hemat: num,
      market_value_source: z.string().nullish(),
    })
    .nullish(),
});
export type SummaryFeed = z.infer<typeof SummarySchema>;

export const DepthSchema = z.object({
  status: z.string(),
  depth_available: z.boolean().nullish(),
  symbols_with_depth: num,
  buy_queue_b_toman: num,
  sell_queue_b_toman: num,
  ratio: num,
  buy_queue_count: num,
  sell_queue_count: num,
});
export type DepthFeed = z.infer<typeof DepthSchema>;

export const ThermometerSchema = z.object({
  status: z.string(),
  group: z.string().nullish(),
  positive: num,
  negative: num,
  zero: num,
  nodata: num,
  not_traded: num,
  positive_pct: num,
  negative_pct: num,
  entry_opportunity: z.boolean().nullish(),
  entry_rule_pct: num,
});
export type Thermometer = z.infer<typeof ThermometerSchema>;

export type MarketPulseData = {
  smartMoney: SmartMoney | null;
  summary: SummaryFeed | null;
  depth: DepthFeed | null;
  thermometer: Thermometer | null;
};

/** دماسنج همت: اول macro اندپوینت پول هوشمند،fallback به healthِ خلاصه */
export function pulseHemat(d: MarketPulseData | null | undefined) {
  const src = d?.smartMoney?.macro ?? d?.summary?.health ?? null;
  if (!src) return null;
  const value = typeof src.value_hemat === 'number' && Number.isFinite(src.value_hemat) ? src.value_hemat : null;
  const state = src.state ?? hematState(value);
  return { value, state, label: state ? HEMAT_LABELS[state] : null };
}

/**
 * گردشِ روزِ کل بازار (همت) — ارزشِ معاملات، نه ارزشِ بازار.
 * نبود عدد = null تا کارت «بدون داده» بخورد، نه صفر ساختگی.
 */
export function pulseTradeValueAllMarketHemat(d: MarketPulseData | null | undefined): number | null {
  const v = (d?.smartMoney?.macro ?? d?.summary?.health)?.trade_value_all_market_hemat;
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * کل ارزش بازار (همت) — همان عددی که TSETMC ذیلِ «ارزش بازار» نشان می‌دهد و
 * همان مبنای «سهم از کل بازار» در شاخص ۵ است. تا پیش از این، نبض بازار
 * گردشِ روز را با همین تیتر نمایش می‌داد و عددِ FTS از جمعِ ردیف‌های تابلو
 * ساخته می‌شد (۲.۸ برابرِ واقعیت) — دو عددِ بی‌ربط، یک نام.
 */
export function pulseMarketValueHemat(d: MarketPulseData | null | undefined): number | null {
  const v = (d?.smartMoney?.macro ?? d?.summary?.health)?.market_value_hemat;
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * شاخصِ کل و هموزن — عددِ خامِ TSETMC، بدونِ هیچ بازسازی‌ای در لایهٔ نمایش.
 * null یعنی هنوز در این پایگاه ذخیره نشده (نصبِ تازه/پایگاهِ کهنه).
 */
export function pulseIndex(d: MarketPulseData | null | undefined) {
  const ix = d?.smartMoney?.macro?.index ?? null;
  if (!ix) return null;
  const n = (v: number | null | undefined) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  return {
    dEven: n(ix.d_even),
    last: n(ix.last),
    change: n(ix.change),
    pct: n(ix.pct),
    ewLast: n(ix.ew_last),
    ewChange: n(ix.ew_change),
    ewPct: n(ix.ew_pct),
  };
}

/** ردیف «سهام، حق تقدم و ص.سهامی» از جدول خلاصه -- سرانهٔ حقیقی و قدرت خرید */
export function pulseEqAll(d: MarketPulseData | null | undefined) {
  const row = d?.summary?.rows?.find((r) => r.key === 'eq_all') ?? null;
  if (!row) return null;
  return {
    pcBuy: typeof row.pc_buy_m_toman === 'number' ? row.pc_buy_m_toman : null,
    pcSell: typeof row.pc_sell_m_toman === 'number' ? row.pc_sell_m_toman : null,
    power: typeof row.buy_power === 'number' ? row.buy_power : null,
    symbols: typeof row.symbols === 'number' ? row.symbols : null,
    traded: typeof row.traded === 'number' ? row.traded : null,
  };
}

/** گروه‌های دارایی که در جدول خلاصه هستند — برای ردیف‌های مقایسهٔ قدرت خریدار */
export function pulseGroupRows(d: MarketPulseData | null | undefined, keys: string[]) {
  const rows = d?.summary?.rows ?? [];
  const n = (v: number | null | undefined) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  return keys
    .map((k) => rows.find((r) => r.key === k) ?? null)
    .filter((r): r is NonNullable<typeof r> => r != null)
    .map((r) => ({
      key: r.key,
      label: r.label ?? r.key,
      power: n(r.buy_power),
      pcBuy: n(r.pc_buy_m_toman),
      pcSell: n(r.pc_sell_m_toman),
    }));
}

/** تعادل صف‌ها: فقط وقتی depth_available درست است عدد معتبر است */
export function pulseDepth(d: MarketPulseData | null | undefined) {
  const dep = d?.depth ?? null;
  if (!dep || dep.depth_available !== true) return null;
  return {
    buyBt: typeof dep.buy_queue_b_toman === 'number' ? dep.buy_queue_b_toman : null,
    sellBt: typeof dep.sell_queue_b_toman === 'number' ? dep.sell_queue_b_toman : null,
    buyCount: typeof dep.buy_queue_count === 'number' ? dep.buy_queue_count : null,
    sellCount: typeof dep.sell_queue_count === 'number' ? dep.sell_queue_count : null,
    ratio: typeof dep.ratio === 'number' ? dep.ratio : null,
  };
}

/** آستانه‌های رنگِ برتری سرانه: ≥۱.۵× سبز، <۰.۸× قرمز، میانه کهربایی */
export const POWER_GOOD = 1.5;
export const POWER_BAD = 0.8;
export function powerTone(power: number | null | undefined): 'good' | 'mid' | 'bad' | null {
  if (typeof power !== 'number' || !Number.isFinite(power)) return null;
  if (power >= POWER_GOOD) return 'good';
  if (power < POWER_BAD) return 'bad';
  return 'mid';
}

/** جریان طلا (میلیارد تومان) از ردیف gold_fund خلاصه؛ نبود داده = null */
export function pulseGoldFlowB(d: MarketPulseData | null | undefined): number | null {
  const row = d?.summary?.rows?.find((r) => r.key === 'gold_fund') ?? null;
  const v = row?.money_flow_b_toman;
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

export const GOLD_WINDOW_LABEL = 'پنجرهٔ طلایی طلا ۱۲:۰۰–۱۲:۳۰';
export const ALPHA_TRIO_LABEL = 'ایده‌آل‌ترین شرایط ورود نوسانی';

export type AlphaTrio = {
  eqInflow: boolean;
  fixedOutflow: boolean;
  /** null یعنی دادهٔ طلا نداریم -- در این حالت شرط طلا لغو الزام می‌شود */
  goldOutflow: boolean | null;
  active: boolean;
};

/**
 * برچسب طلایی Alpha Trio: خروج از درآمد ثابت + خروج از طلا (فقط اگر داده باشد)
 * + ورود به سهام حقیقی -> «ایده‌آل‌ترین شرایط ورود نوسانی».
 */
export function computeAlphaTrio(d: MarketPulseData | null | undefined): AlphaTrio | null {
  const flow = d?.smartMoney?.flow ?? null;
  if (!flow) return null;
  const eqInflow = flow.eq_inflow ?? (typeof flow.eq_flow_b_toman === 'number' ? flow.eq_flow_b_toman > 0 : false);
  const fixedOutflow =
    flow.fixed_outflow ?? (typeof flow.fixed_flow_b_toman === 'number' ? flow.fixed_flow_b_toman < 0 : false);
  const gold = pulseGoldFlowB(d);
  const goldOutflow = gold == null ? null : gold < 0;
  return { eqInflow, fixedOutflow, goldOutflow, active: eqInflow && fixedOutflow && goldOutflow !== false };
}

export function useMarketPulse() {
  return useQuery({
    queryKey: ['market-pulse'],
    queryFn: async ({ signal }): Promise<MarketPulseData> => {
      const [smartMoney, summary, depth, thermometer] = await Promise.all([
        http<SmartMoney>('/api/mstat/smart-money', { schema: SmartMoneySchema, signal }).catch(() => null),
        http<SummaryFeed>('/api/mstat/summary', { schema: SummarySchema, signal }).catch(() => null),
        http<DepthFeed>('/api/mstat/depth', { schema: DepthSchema, signal }).catch(() => null),
        http<Thermometer>('/api/mstat/thermometer', { schema: ThermometerSchema, signal }).catch(() => null),
      ]);
      return { smartMoney, summary, depth, thermometer };
    },
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}
