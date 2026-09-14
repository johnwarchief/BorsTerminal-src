// contracts/tape.ts -- الگوی ساعت و جریان سفارشات در قرارداد سیگنال
import { z } from 'zod';

export const TapePattern = z.enum(['closing_auction_pop', 'suspicious_volume', 'none']);
export type TapePattern = z.infer<typeof TapePattern>;

export const TapePayload = z.object({
  kind: z.literal('tape_pattern'),
  pattern: TapePattern,
  /** نسبت (آخرین - پایانی) به پایانی */
  lastVsClose: z.number(),
  /** نسبت حجم مشکوک به میانگین -- null یعنی قابل محاسبه نبود */
  volumeMultiple: z.number().nullable().default(null),
});
export type TapePayload = z.infer<typeof TapePayload>;
