// shared/types/marketRow.ts -- شکل پاسخ /api/market
// فیلدها از کوئری api/market.py استخراج شده اند. عددها ممکن است null باشند.
//
// این فهرست **همان چیزی است که سرور می‌فرستد**، نه همهٔ ستون‌هایِ بانک. کارِ #73
// (حالتِ داغ) بیست‌وشش کلید را از سریال‌سازی بیرون گذاشت، چون inventoryِ
// frontend/src نشان داد هیچ‌جا خوانده نمی‌شوند: eps، price_max/price_min،
// p_max/p_min، buy_n_vol/sell_n_vol، aggregates‌هایِ صف
// (buy_q_vol/val/cnt، sell_q_vol/val/cnt، buy_q1_px، sell_q1_vol/sell_q1_px)،
// prev_day_vol، d1_vol، max30_high، tmax، vol_trend،
// sell_power_i، suspicious_vol، d_even، resistance_59، dist_min30_pct.
// آن‌ها هنوز درِ `market_watch` و درِ کوئریِ تابلو هستند؛ فقط رویِ سیم نمی‌آیند:
// ۷٫۵MB → ۴٫۲MB و gzip ۹۱۳KB → ۵۶۵KB. `month_avg_vol` فرستاده می‌شود، چون
// typeِ همین فایل آن را اعلام می‌کند — قراردادِ دو طرف باید یکی بماند.
//
// همه کلیدها `.nullish()`‌اند، پس «نیامدن» و «null» برایِ UI یکی است — و این
// شرطِ درستِ کارِ حالتِ داغ است: سرور کلیدهایِ null را هم حذف می‌کند.
import { z } from 'zod';

const num = z.number().nullish();
const flag = z.boolean().nullish();

export const MarketRowSchema = z.object({
  ins_code: z.string().nullish(),
  symbol: z.string().min(1),
  name: z.string().nullish(),
  sector_name: z.string().nullish(),
  board: z.union([z.number(), z.string()]).nullish(),
  p_closing: num,
  p_last: num,
  price_yesterday: num,
  percent_change: num,
  q_tot_tran: num,
  z_tot_tran: num,
  q_tot_cap: num,
  tvol: num,
  vol_ratio: num,
  pe: num,
  // تابلویِ ۵ مظنه: از بانک می‌آید؛ «عمق بازار» دیگر چیزی نمی‌سازد.
  // فقط سطرِ اولِ صف خرید درِ پنج فیلترِ جزوه است (qd1/zd1)، پس همان می‌ماند.
  buy_q1_vol: num,
  buy_q1_cnt: num,
  // (tmin) درِ فیلترنویسِ TSETMC = آستانۀ مجاز، نه کفِ همین نشست.
  tmin: num,
  buy_i_vol: num,
  sell_i_vol: num,
  buy_count_i: num,
  sell_count_i: num,
  month_avg_vol: num,
  // مبنایِ حجمِ پنج فیلتر: Σ[ih][0..29]/۳۰ — میانگینِ سی **نشستِ** آخر.
  // null = پنجره کامل نیست، که یعنی **سنجیده نمی‌شود**.
  vol_ratio_file: num,
  prior30_vol: num,
  // چند نشست از عمرِ نماد می‌دانیم (سقفِ پنجره ۶۰). شمارۀِ **نشست** است نه
  // شمارۀِ ردیفِ ذخیره‌شده؛ نشستِ بی‌معامله درِ سایت صفر است و درِ بانکِ ما
  // ردیفی ندارد، پس همین عدد مرزِ «سنجش ممکن است یا نه» را می‌سازد.
  hist_sessions: num,
  // کمینۀِ خامِ [ih][0..28].PriceMin — صفر می‌ماند، چون فایل خودِ صفر را
  // دلیلِ رد می‌خواهد (`MinPriceOfMonth() != 0`) نه حذف‌شدنی.
  min_low_29: num,
  // (zd1) = تعدادِ سفارشِ **سطرِ اولِ صف خرید** (blDs[0]).
  vol_dod: num,
  buyer_power: num,
  buyer_power_raw: num,
  buy_power_i: num,
  // درصدِ «آخرین» نسبت به دیروز: percent_change پایانی را می‌سنجد، این آخرین را.
  percent_last: num,
  f_roobi: flag,
  f_susp: flag,
  f_clock: flag,
  f_jet: flag,
  f_noqteh: flag,
  // دو فیلترِ جزوۀِ تازه — داوری‌شان درِ tape_flags.py است؛ رابط فقط پرچم را
  // می‌خواند (بی‌آینۀِ منطقیِ دوم).
  f_smart: flag,
  f_legal: flag,
  is_live: flag,
  // سقفِ تک‌روزیِ kامین نشستِ آخر — [ih][k].PriceMax در فرمول‌هایِ TSETMC.
  // نبودنش یعنی آن نشست بی‌معامله بوده و سایت همان‌جا صفر می‌گذارد؛ «پلکانِ
  // غایب» از این تفکیک نمی‌آید، از `hist_sessions` می‌آید.
  h2_max: num,
  h5_max: num,
  h9_max: num,
  h19_max: num,
  h29_max: num,
  h39_max: num,
  h49_max: num,
  h59_max: num,
  min30_low: num,
  // ── P0-3: وضعیتِ معاملاتی/نظارتی از TSETMC (canonical، بی‌محاسبۀ رابط) ──
  // سه حالت جدا هستند و رابط حق ندارد یکی را جای دیگری بگذارد:
  //   کلید نیامده/null = «موردی ثبت نشده»   ≠   «سالم» ≠ «متوقف» ≠ «خطا»
  // خطایِ فید را `inspector-feed-error` جدا می‌گوید، نه این کلیدها.
  // cEtaval/عنوانِ وضعیتِ آخرینِ تغییرِ ثبت‌شده (instrument_state)
  st_code: z.string().nullish(),
  st_title: z.string().nullish(),
  // حضور در فهرست نظارت (supervision_state)؛ خودِ ستونِ under_supervision درِ
  // پاسخِ واقعی حتی برایِ نمادهای زیرِ نظر صفر است، پس برچسب از «ردیف هست»
  // می‌آید — نه از آن عدد.
  sup_flag: num,
  sup_title: z.string().nullish(),
  sup_reason_count: num,
  // علتِ توقف (webgw CompanyState → dalils)؛ متنِ کامل فقط درِ Inspector
  // خوانده می‌شود، درِ تابلو تنها همین که «چرا» هست کافی است.
  stop_state: z.string().nullish(),
  stop_since: z.string().nullish(),
  stop_reasons: z.string().nullish(),
  // مبدأِ ارزشِ حقیقی/حقوقی: native | mixed | reconstructed. یک‌بار درِ نویسنده
  // حساب شده و همین‌جا خوانده می‌شود؛ رابط حق ندارد از خودِ عددها بازسازیش کند.
  // فقط درِ «جزئیات» نشان داده می‌شود — نه بج، نه ستونِ تابلو، و هرگز وارد
  // داوری/FTS نمی‌شود.
  ctv_kind: z.string().nullish(),
});

export type MarketRow = z.infer<typeof MarketRowSchema>;

export const MarketMetaSchema = z.object({
  d_even: num,
  h_even: num,
  last_sync: z.string().nullish(),
});

export type MarketMeta = z.infer<typeof MarketMetaSchema>;

export const MarketFeedSchema = z.object({
  status: z.string(),
  /** ویرایشِ حالتِ داغِ این بدنه — پولینگِ بعدی `?since=rev` می‌شود. */
  rev: z.number().nullish(),
  count: z.number().nullish(),
  data: z.array(MarketRowSchema),
  meta: MarketMetaSchema.nullish(),
  live_count: z.number().nullish(),
  fossil_count: z.number().nullish(),
});

export type MarketFeed = z.infer<typeof MarketFeedSchema>;

/**
 * پاسخ /api/market/delta?since=REV — همان تابلو، بی‌بدنۀ کامل.
 *
 * سه حالتِ ممکن و صریح (هیچ‌کدام «نصفه» نیست):
 *   • unchanged : سرور همان ویرایشِ ماست ⇒ صفر ردیف، صفر parse؛
 *   • delta     : فقط ردیف‌هایِ تغییریافته از ویرایشِ ما تا `rev`؛
 *   • full      : سرور نمی‌تواند دلتا را اثبات کند (ژورنال چرخیده، کلاینت
 *                 عقب/جلو مانده، نمادی جابه‌جا شده) ⇒ `/api/market` کامل.
 * `count` در دو حالتِ اول می‌آید و **باید** با تعدادِ ردیف‌هایِ ما برابر باشد؛
 * اگر نبود، یعنی چیزی از چشمِ دلتا دور مانده و merge را رها می‌کنیم.
 */
const counts = {
  count: z.number().nullish(),
  live_count: z.number().nullish(),
  fossil_count: z.number().nullish(),
};

export const MarketDeltaSchema = z.discriminatedUnion('status', [
  z.object({ status: z.literal('unchanged'), rev: z.number(), meta: MarketMetaSchema.nullish(), ...counts }),
  z.object({ status: z.literal('delta'), rev: z.number(), rows: z.array(MarketRowSchema),
             meta: MarketMetaSchema.nullish(), ...counts }),
  z.object({ status: z.literal('full'), rev: z.number().nullish(), reason: z.string().nullish() }),
]);

export type MarketDelta = z.infer<typeof MarketDeltaSchema>;
