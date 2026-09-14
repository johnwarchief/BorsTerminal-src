// contracts/technical.ts -- ستاپ های v9.7.4 در قرارداد سیگنال
import { z } from 'zod';
import { DataQuality } from './signal';

export const Timeframe = z.enum(['daily', 'weekly', 'monthly']);
export type Timeframe = z.infer<typeof Timeframe>;

export const SetupKind = z.enum(['breakout', 'pullback', 'fibonacci', 'choch', 'bearish_div', 'range', 'trend']);
export type SetupKind = z.infer<typeof SetupKind>;

export const StopLossRef = z.enum(['ma14', 'rising_low', 'swing_stop']);
export type StopLossRef = z.infer<typeof StopLossRef>;

export const KeyLevel = z.object({
  type: z.string().min(1),
  price: z.number(),
});
export type KeyLevel = z.infer<typeof KeyLevel>;

export const TechnicalPayload = z.object({
  kind: z.literal('setup'),
  timeframe: Timeframe,
  setups: z.array(SetupKind).default([]),
  stopLossRef: StopLossRef.nullable().default(null),
  stopLossPrice: z.number().nullable().default(null),
  keyLevels: z.array(KeyLevel).default([]),
  /** کیفیت داده: تاریخچه کوتاه تر از 50 کندل یعنی partial (فاز 4) */
  dataQuality: DataQuality.default('complete'),
});
export type TechnicalPayload = z.infer<typeof TechnicalPayload>;
