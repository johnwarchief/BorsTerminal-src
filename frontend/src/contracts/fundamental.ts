// contracts/fundamental.ts -- بازتاب FTS v10 در قرارداد سیگنال
import { z } from 'zod';
import { DataQuality as SignalQuality } from './signal';

export const RiskGateId = z.enum(['m141', 'mcap_floor', 'liquidity', 'industry']);
export type RiskGateId = z.infer<typeof RiskGateId>;

export const RiskGateState = z.enum(['pass', 'warn', 'fail', 'nodata']);
export type RiskGateState = z.infer<typeof RiskGateState>;

export const RiskGate = z.object({
  id: RiskGateId,
  state: RiskGateState,
  note: z.string().default(''),
});
export type RiskGate = z.infer<typeof RiskGate>;

export const DataGap = z.object({
  layer: z.string().min(1),
  why: z.string().min(1),
  fix: z.string().min(1),
});
export type DataGap = z.infer<typeof DataGap>;

export const FundamentalPayload = z.object({
  kind: z.literal('fts_card'),
  /** امتیاز 5 لایه FTS */
  score: z.number().min(0).max(5),
  passes: z.record(z.string(), z.boolean()),
  riskGates: z.array(RiskGate).default([]),
  /** نردبان EPS -- مقدار null یعنی دوره بدون داده */
  epsSeries: z.array(z.number().nullable()).default([]),
  dataGaps: z.array(DataGap).default([]),
  /** کهنگی: فاصله آخرین صورت مالی بیش از 120 روز (فاز 3) */
  staleness: z.boolean().default(false),
  /** سن آخرین صورت مالی به روز -- null یعنی نامشخص */
  statementAgeDays: z.number().nullable().default(null),
  /** کیفیت داده: ناقص یعنی سیگنال خنثی احتیاطی (قرارداد مشترک signal) */
  dataQuality: SignalQuality.default('complete'),
  /** نسبت P/E سهم به میانه صنعت -- null یعنی قابل محاسبه نبود */
  peVsSector: z.number().nullable().default(null),
  /** رشد سود خالص فصل جاری به فصل مشابه پارسال (درصد) */
  profitYoY: z.number().nullable().default(null),
  /** رأی ۱۵: پنج‌شاخصه برای صندوق معنا ندارد — داوری صادر نمی‌شود، نه رد.
   *  غایب = نامعلوم ⇒ «می‌گنجد» (ftsApplicable همان‌جا تفسیر می‌کند). */
  applicable: z.boolean().optional(),
});
export type FundamentalPayload = z.infer<typeof FundamentalPayload>;

/**
 * امتیاز ۰ تا ۵ «شمار شاخص‌های تاییدشده FTS» از سیگنال بنیادی.
 *
 * دو نمره در سیگنال بنیادی وجود دارد و اشتباه گرفتنشان باگ زا است:
 * - `signal.score` → ۰ تا ۱۰۰: اعتماد ترکیبی (مخصوص `AgentSignal`، مصرف در masterMath/گیت‌ها).
 * - `signal.payload.score` → ۰ تا ۵: تعداد شاخص‌های بنیادی تاییدشده (مصرف در FTS/«از ۵»).
 * هر جا منطق «امتیاز از ۵» یا سوپربنیادیِ «۵ از ۵» می‌خواهید، از این تابع بخوانید نه `signal.score`.
 */
/** آیا اصلاً ارزیابی FTS بر این نماد می‌گنجد؟ (صندوق ⇒ خیر) */
export function ftsApplicable(fund: { payload?: unknown } | null | undefined): boolean {
  return (fund?.payload as { applicable?: unknown } | undefined)?.applicable !== false;
}

export function ftsScoreOf(fund: { payload?: unknown } | null | undefined): number | null {
  const p = fund?.payload as { score?: unknown } | null | undefined;
  return typeof p?.score === 'number' ? p.score : null;
}
