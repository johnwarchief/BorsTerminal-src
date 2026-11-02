/**
 * frontend-v2/src/features/technical/api/candleEdgeApi.ts
 *
 * دریافت داده‌های لبه آماری و پرایس‌اکشن نهادی (SMC)
 * از اندپوینت GET /api/chart/{symbol}/edge?swing_period=...
 */

import { z } from 'zod';
import { getJson } from '@shared/api/http';
import type { CandleEdgeReport, PriceZone, MarketStructurePoint } from '../model/types';

export const PriceZoneSchema = z.looseObject({
  id: z.string(),
  type: z.enum(['FVG', 'ORDER_BLOCK']).default('FVG'),
  is_bullish: z.boolean().optional(),
  isBullish: z.boolean().optional(),
  top: z.number(),
  bottom: z.number(),
  equilibrium: z.number(),
  start_index: z.number().optional(),
  startIndex: z.number().optional(),
  start_ts: z.number().optional(),
  startTs: z.number().optional(),
  mitigated: z.boolean().default(false),
  mitigated_ts: z.number().optional(),
  mitigatedTs: z.number().optional(),
});

export const MarketStructurePointSchema = z.looseObject({
  type: z.enum(['BOS', 'CHoCH']),
  is_bullish: z.boolean().optional(),
  isBullish: z.boolean().optional(),
  price: z.number(),
  timestamp: z.number(),
  index: z.number().optional(),
});

export const CandleEdgeResponseSchema = z.looseObject({
  symbol: z.string(),
  pattern_name: z.string().optional(),
  patternName: z.string().optional(),
  win_rate_1bar: z.number().optional(),
  winRate1Bar: z.number().optional(),
  win_rate_3bar: z.number().optional(),
  winRate3Bar: z.number().optional(),
  win_rate_5bar: z.number().optional(),
  winRate5Bar: z.number().optional(),
  profit_factor: z.number().optional(),
  profitFactor: z.number().optional(),
  risk_reward_ratio: z.number().optional(),
  riskRewardRatio: z.number().optional(),
  sample_count: z.number().optional(),
  sampleCount: z.number().optional(),
  market_regime: z.string().optional(),
  marketRegime: z.string().optional(),
  active_zones: z.array(PriceZoneSchema).optional().default([]),
  activeZones: z.array(PriceZoneSchema).optional(),
  recent_structures: z.array(MarketStructurePointSchema).optional().default([]),
  recentStructures: z.array(MarketStructurePointSchema).optional(),
});

export type CandleEdgeResponse = z.infer<typeof CandleEdgeResponseSchema>;

export function transformCandleEdgeResponse(data: CandleEdgeResponse): CandleEdgeReport {
  const rawZones = data.active_zones || data.activeZones || [];
  const activeZones: PriceZone[] = rawZones.map((z) => ({
    id: z.id,
    type: z.type,
    isBullish: z.is_bullish ?? z.isBullish ?? true,
    top: z.top,
    bottom: z.bottom,
    equilibrium: z.equilibrium,
    startIndex: z.start_index ?? z.startIndex ?? 0,
    startTs: z.start_ts ?? z.startTs ?? 0,
    mitigated: z.mitigated,
    mitigatedTs: z.mitigated_ts ?? z.mitigatedTs,
  }));

  const rawStructures = data.recent_structures || data.recentStructures || [];
  const recentStructures: MarketStructurePoint[] = rawStructures.map((s) => ({
    type: s.type,
    isBullish: s.is_bullish ?? s.isBullish ?? true,
    price: s.price,
    timestamp: s.timestamp,
    index: s.index,
  }));

  return {
    symbol: data.symbol,
    patternName: data.pattern_name ?? data.patternName ?? 'نامشخص',
    winRate1Bar: data.win_rate_1bar ?? data.winRate1Bar ?? 0.5,
    winRate3Bar: data.win_rate_3bar ?? data.winRate3Bar ?? 0.5,
    winRate5Bar: data.win_rate_5bar ?? data.winRate5Bar ?? 0.5,
    profitFactor: data.profit_factor ?? data.profitFactor ?? 1.0,
    riskRewardRatio: data.risk_reward_ratio ?? data.riskRewardRatio ?? 1.0,
    sampleCount: data.sample_count ?? data.sampleCount ?? 0,
    marketRegime: (data.market_regime ?? data.marketRegime ?? 'RANGING') as any,
    activeZones,
    recentStructures,
  };
}

export async function fetchCandleEdge(
  symbol: string,
  swingPeriod = 5,
  signal?: AbortSignal,
): Promise<CandleEdgeReport> {
  const raw = await getJson(
    `/api/chart/${encodeURIComponent(symbol)}/edge?swing_period=${swingPeriod}`,
    CandleEdgeResponseSchema,
    signal,
  );
  return transformCandleEdgeResponse(raw);
}
