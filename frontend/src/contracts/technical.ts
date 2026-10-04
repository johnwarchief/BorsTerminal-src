// contracts/technical.ts -- ستاپ های v9.7.4 در قرارداد سیگنال
import { z } from 'zod';
import { DataQuality } from './signal';

export const Timeframe = z.enum(['daily', 'weekly', 'monthly']);
export type Timeframe = z.infer<typeof Timeframe>;

/**
 * ستاپ‌ها = فقط «تریگرِ ورود» (taxonomyِ دورِ J، از `role` درِ خودِ موتور).
 * فیبو اینجا نیست: سنجهٔ تاریخی گفت داخلِ کمربند بودن edge ندارد، پس نقشش
 * `context` است و درِ `TechnicalPayload.context` منتشر می‌شود.
 */
export const SetupKind = z.enum(['breakout', 'pullback', 'choch', 'bearish_div', 'range', 'trend']);
export type SetupKind = z.infer<typeof SetupKind>;

/**
 * مبنایِ حد ضرر: رشتهٔ خامِ `stop_basis`ِ خودِ موتورِ خروج
 * (`api/chart.py::_fts_exit_layer1` ⇒ `exit_engine.l1.stop_basis`).
 * پیش از این اینجا یک enumِ سه‌تاییِ فرانتی (`ma14 | rising_low | swing_stop`)
 * بود که به «موتورِ دومِ» فرانت گره خورده بود؛ حالا که حد ضرر از سرور می‌آید،
 * enumِ فرانت واژۀ موتور را نمی‌پوشاند و ترجمه‌اش نمی‌کند.
 */
export const StopLossRef = z.string().min(1);
export type StopLossRef = z.infer<typeof StopLossRef>;

export const KeyLevel = z.object({
  type: z.string().min(1),
  price: z.number(),
});
export type KeyLevel = z.infer<typeof KeyLevel>;

/**
 * رأیِ هفتگیِ موتورِ FTSِ سرور (`/api/fts`) — تنها منبعِ گیتِ وتوی هفتگی.
 *
 * پیش‌تر هیچ تولیدکننده‌ای این بلوک را منتشر نمی‌کرد، پس `weeklyTrendFromSignal`
 * همیشه null می‌داد و گیت برای هر نمادی «در انتظار» می‌ماند ⇒ حکمِ
 * «توقف در فیلتر دوم» (شاهد: کايزد با ۱۵۲٪ صعودِ هفتگی).
 */
export const WeeklyTrend = z.object({
  /** روندِ هفتگی صعودی است؟ null یعنی ساختار کافی برای قضاوت نیست */
  uptrend: z.boolean().nullable().default(null),
  belowMa52: z.boolean().nullable().default(null),
  rsi: z.number().nullable().default(null),
  /** مبنایِ رأی: 'pivots' (سقف/کفِ تأییدشده) یا 'recent-window' (پیوتِ کهنه) */
  basis: z.string().nullable().default(null),
  /** دلیلِ فارسیِ رأی: کدام پیوت‌ها یا کدام بازه سنجیده شد */
  reason: z.string().nullable().default(null),
  matrixDecision: z.string().nullable().default(null),
});
export type WeeklyTrend = z.infer<typeof WeeklyTrend>;

export const TechnicalPayload = z.object({
  kind: z.literal('setup'),
  timeframe: Timeframe,
  setups: z.array(SetupKind).default([]),  stopLossRef: StopLossRef.nullable().default(null),
  stopLossPrice: z.number().nullable().default(null),
  keyLevels: z.array(KeyLevel).default([]),
  /** کیفیت داده: تاریخچه کوتاه تر از 50 کندل یعنی partial (فاز 4) */
  dataQuality: DataQuality.default('complete'),
  weekly: WeeklyTrend.nullish(),
  /**
   * وضعیتِ عمومیِ canonical، عینِ `_fts_status_block` درِ `api/chart.py`:
   * کد (با اولویتِ حدِ ضرر ← خروجِ تأییدشده ← وتوی هفتگی ← تریگرِ امروز ←
   * هشدار ← فقطِ زمینه ← بی‌سیگنال ← بی‌داده) و متنِ فارسیِ همان رأی.
   * کارتِ «وضعیت FTS» و بج‌ها این را می‌خوانند؛ هیچ کامپوننتی متنِ ثابتِ
   * خودش را جایِ رأیِ موتور نمی‌گذارد (باگِ «در انتظار شکست خط آبی» در همهٔ
   * حالت‌ها).
   */
  status: z
    .object({ code: z.string(), text: z.string() })
    .nullable()
    .nullish(),
  /** هرچه نقشش «زمینه» است (کمربند فیبو، هم‌راستاییِ روند) — بی‌امتیاز و بی‌«ستاپ» */
  context: z.array(z.string()).nullish(),
  /**
   * پرچم‌هایِ خامِ ستاپ، عینِ خروجیِ `_fts_analyze_candles` درِ `api/chart.py`.
   *
   * چرا لازم بود: `lib/ftsPipelineEvaluator.ts` گامِ ۲ را با همین کلیدها
   * (`jet_active`، `choch_bullish`، `point_hunt_active`، `double_bottom_active`)
   * می‌سنجد، ولی هیچ تولیدکننده‌ای آن‌ها را منتشر نمی‌کرد — پس آن گام درِ
   * برنامهٔ زنده همیشه به «در انتظار» می‌افتاد و فقط درِ تست‌هایی که payload
   * جعلی می‌دادند کار می‌کرد (دقیقاً همان باگِ بلوکِ `weekly` که بالا مستند شده).
   * هیچ تشخیصِ تازه‌ای این‌جا ساخته نمی‌شود: فقط رأیِ موتور منتقل می‌شود.
   *
   * سه‌حال است نه بولین: `true` = ستاپ فعال، `false` = صریحاً غیرفعال،
   * `null` = موتور **قضاوت نکرد** (تاریخچه/پیوت کافی نبود) — و `undefined`
   * = پاسخِ تکنیکال اصلاً نیامده. تبدیلِ null به false ممنوع (رأیِ مالک).
   */
  jet_active: z.boolean().nullable().optional(),
  choch_bullish: z.boolean().nullable().optional(),
  point_hunt_active: z.boolean().nullable().optional(),
  double_bottom_active: z.boolean().nullable().optional(),
  range_break_active: z.boolean().nullable().optional(),
  hourglass_active: z.boolean().nullable().optional(),
});
export type TechnicalPayload = z.infer<typeof TechnicalPayload>;
