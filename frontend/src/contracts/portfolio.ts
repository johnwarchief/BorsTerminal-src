// contracts/portfolio.ts -- وضعیت تصمیم و ریسک سبد در قرارداد سیگنال
import { z } from 'zod';

export const PortfolioDecision = z.enum(['accept', 'reject', 'monitor', 'pending']);
export type PortfolioDecision = z.infer<typeof PortfolioDecision>;

export const PortfolioPayload = z.object({
  kind: z.literal('position_state'),
  decision: PortfolioDecision,
  weightPct: z.number().min(0).max(100).nullable().default(null),
  stopLoss: z.number().nullable().default(null),
  alerts: z.array(z.string()).default([]),
});
export type PortfolioPayload = z.infer<typeof PortfolioPayload>;
