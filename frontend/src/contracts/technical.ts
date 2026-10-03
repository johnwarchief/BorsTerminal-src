// contracts/technical.ts -- ستاپ های v9.7.4 در قرارداد سیگنال
import { z } from 'zod';
import { DataQuality } from './signal';

export const Timeframe = z.enum(['daily', 'weekly', 'monthly']);
export type Timeframe = z.infer<typeof Timeframe>;

export const SetupKind = z.enum(['breakout', 'pullback', 'fibonacci', 'choch', 'bearish_div', 'range', 'trend']);
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
  setups: z.array(SetupKind).default([]),
  stopLossRef: StopLossRef.nullable().default(null),
  stopLossPrice: z.number().nullable().default(null),
  keyLevels: z.array(KeyLevel).default([]),
  /** کیفیت داده: تاریخچه کوتاه تر از 50 کندل یعنی partial (فاز 4) */
  dataQuality: DataQuality.default('complete'),
  weekly: WeeklyTrend.nullish(),
});
export type TechnicalPayload = z.infer<typeof TechnicalPayload>;
