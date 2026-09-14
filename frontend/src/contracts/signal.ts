// contracts/signal.ts -- تایپ پایه AgentSignal (ماده 3.3 سند معماری)
// تنها منبع حقیقت قراردادها. بدون نیم فاصله نوشته شده است.
import { z } from 'zod';

/** جهت سیگنال -- کنوانسیون سراسری */
export const Direction = z.enum(['bullish', 'bearish', 'neutral']);
export type Direction = z.infer<typeof Direction>;

/** حالت اعتماد داده -- هم راستا با واژگان موتور FTS */
export const Confidence = z.enum(['high', 'medium', 'low', 'nodata']);
export type Confidence = z.infer<typeof Confidence>;

/** هویت تولیدکننده سیگنال -- تنها 4 مقدار مجاز ساب ایجنت */
export const AgentId = z.enum(['fundamental', 'technical', 'tape', 'portfolio']);
export type AgentId = z.infer<typeof AgentId>;

/** فیچری که سیگنال از آن نشات گرفت -- برای deep-link در UI */
export const SourceView = z.enum(['fundamental', 'technical', 'market', 'portfolio']);
export type SourceView = z.infer<typeof SourceView>;

/** اهمیت سیگنال در تصمیم نهایی مستر */
export const SignalWeight = z.enum(['critical', 'major', 'minor', 'info']);
export type SignalWeight = z.infer<typeof SignalWeight>;

export const SIGNAL_CONTRACT_VERSION = 1 as const;

/** سیگنال پایه مشترک همه ایجنت ها */
export const BaseSignal = z.object({
  /** شناسه یکتا: ${agentId}:${symbol}:${kind}:${ts} */
  id: z.string().min(8),
  agentId: AgentId,
  symbol: z.string().min(1),
  /** epoch ms -- لحظه صدور سیگنال */
  ts: z.number().int().positive(),
  direction: Direction,
  confidence: Confidence,
  weight: SignalWeight.default('major'),
  /** عنوان فارسی کوتاه برای UI */
  title: z.string().min(2),
  /** توضیح کامل فارسی: استدلال و اعداد و منبع */
  rationale: z.string().min(4),
  /** نمره داوری 0 تا 100 -- null مجاز */
  score: z.number().min(0).max(100).nullable().default(null),
  /** عمق پشتیبان برای مسیریابی UI مستر */
  evidence: z.array(z.string()).default([]),
  /** لینک به فیچر مبدا */
  sourceView: SourceView,
  /** منبع داده پشتیبان سیگنال */
  sourceRef: z.array(z.string()).default([]),
  /** ابطال خودکار: سیگنال قدیمی تر از این مهلت کنار گذاشته می شود.
      سقف 180 روز تا سیگنال بنیادی فصلی جا شود (فاز 3) */
  validForMs: z.number().int().positive().max(180 * 24 * 3600_000).default(3600_000),
});

export type BaseSignal = z.infer<typeof BaseSignal>;

/** سیگنال کامل با payload اختصاصی هر ایجنت */
export type AgentSignal<T = unknown> = BaseSignal & {
  payload: T;
};

/** کیفیت داده پشت سیگنال -- مشترک همه ایجنت ها */
export const DataQuality = z.enum(['complete', 'partial', 'incomplete']);
export type DataQuality = z.infer<typeof DataQuality>;

/** پیام رویداد انتشار سیگنال در Signal Bus */
export const SignalEvent = z.object({
  kind: z.literal('signal'),
  signal: BaseSignal,
  v: z.literal(SIGNAL_CONTRACT_VERSION),
});
export type SignalEvent = z.infer<typeof SignalEvent>;

/** وزن پیش فرض مصوب هر ایجنت در رای گیری مستر (فاز 5 قابل تنظیم در UI) */
export const AGENT_WEIGHTS: Record<AgentId, number> = {
  fundamental: 4,
  technical: 3,
  tape: 2,
  portfolio: 1,
};

/** امتیاز عددی وزن سیگنال */
export const WEIGHT_SCORES: Record<SignalWeight, number> = {
  critical: 4,
  major: 3,
  minor: 2,
  info: 1,
};

/** آیا سیگنال در لحظه now منقضی شده است */
export function isSignalExpired(signal: Pick<BaseSignal, 'ts' | 'validForMs'>, now = Date.now()): boolean {
  return signal.ts + signal.validForMs < now;
}

/** اعتبارسنجی در نقطه انتشار: سیگنال خراب هرگز وارد باس نمی شود */
export function validateSignal(data: unknown): BaseSignal | null {
  const parsed = BaseSignal.safeParse(data);
  if (!parsed.success) {
    if (import.meta.env.DEV) {
      console.error('[contracts] سیگنال نامعتبر رد شد:', parsed.error.message);
    }
    return null;
  }
  return parsed.data;
}
