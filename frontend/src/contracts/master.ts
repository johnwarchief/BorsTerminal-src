// contracts/master.ts -- خروجی ایجنت مستر
import { z } from 'zod';
import { AgentId, Confidence } from './signal';

export const FinalAction = z.enum(['strong_buy', 'buy', 'hold', 'watch', 'reduce', 'sell', 'strong_sell', 'no_data']);
export type FinalAction = z.infer<typeof FinalAction>;

export const AgentContribution = z.object({
  agentId: AgentId,
  score: z.number().min(-100).max(100),
  signalCount: z.number().int().nonnegative(),
  confidence: Confidence,
});
export type AgentContribution = z.infer<typeof AgentContribution>;

export const DissentEntry = z.object({
  agents: z.tuple([AgentId, AgentId]),
  gap: z.number().min(0).max(200),
  note: z.string(),
});
export type DissentEntry = z.infer<typeof DissentEntry>;

export const MasterVerdict = z.object({
  symbol: z.string().min(1),
  ts: z.number().int().positive(),
  /** نتیجه رای گیری وزنی: 100- تا 100+ */
  compositeScore: z.number().min(-100).max(100),
  finalAction: FinalAction,
  contributions: z.array(AgentContribution).default([]),
  dissent: z.array(DissentEntry).default([]),
  usedSignalIds: z.array(z.string()).default([]),
  discardedSignalIds: z.array(z.string()).default([]),
  /** تضاد افق زمانی بین ایجنت ها (فاز 5) */
  hasConflict: z.boolean().default(false),
});
export type MasterVerdict = z.infer<typeof MasterVerdict>;
