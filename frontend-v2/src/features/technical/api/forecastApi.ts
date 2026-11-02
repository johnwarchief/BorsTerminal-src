/**
 * frontend-v2/src/features/technical/api/forecastApi.ts
 *
 * دریافت داده‌های پیش‌بینی افق زمانی هوش مصنوعی (مدل‌های Kronos و Chronos)
 * از اندپوینت GET /api/chart/{symbol}/forecast?horizon=...
 */

import { z } from 'zod';
import { getJson } from '@shared/api/http';
import type { PredictionData, ForecastStep } from '../model/types';

export const ForecastStepSchema = z.looseObject({
  step_index: z.number().optional(),
  stepIndex: z.number().optional(),
  timestamp: z.number(),
  p10: z.number(),
  p50: z.number(),
  p90: z.number(),
});

export const ForecastResponseSchema = z.looseObject({
  symbol: z.string(),
  generated_at: z.number().optional(),
  generatedAt: z.number().optional(),
  horizon: z.number().default(12),
  is_liquid: z.boolean().default(true),
  isLiquid: z.boolean().optional(),
  liquidity_note: z.string().optional(),
  liquidityNote: z.string().optional(),
  historical_end: z.number().optional(),
  historicalEnd: z.number().optional(),
  forecast_steps: z.array(ForecastStepSchema).optional().default([]),
  forecastSteps: z.array(ForecastStepSchema).optional(),
  upside_probability: z.number().optional(),
  upsideProbability: z.number().optional(),
  volatility_amplification: z.number().optional(),
  volatilityAmplification: z.number().optional(),
  model_used: z.string().optional(),
  modelUsed: z.string().optional(),
});

export type ForecastResponse = z.infer<typeof ForecastResponseSchema>;

export function transformForecastResponse(data: ForecastResponse): PredictionData {
  const rawSteps = data.forecast_steps || data.forecastSteps || [];
  const steps: ForecastStep[] = rawSteps.map((s, idx) => ({
    stepIndex: s.step_index ?? s.stepIndex ?? idx + 1,
    timestamp: s.timestamp,
    p10: s.p10,
    p50: s.p50,
    p90: s.p90,
  }));

  return {
    symbol: data.symbol,
    generatedAt: data.generated_at ?? data.generatedAt ?? Date.now(),
    horizon: data.horizon,
    isLiquid: data.is_liquid ?? data.isLiquid ?? true,
    liquidityNote: data.liquidity_note ?? data.liquidityNote,
    historicalEnd: data.historical_end ?? data.historicalEnd,
    forecastSteps: steps,
    upsideProbability: data.upside_probability ?? data.upsideProbability,
    volatilityAmplification: data.volatility_amplification ?? data.volatilityAmplification,
    modelUsed: data.model_used ?? data.modelUsed,
  };
}

export async function fetchForecast(
  symbol: string,
  horizon = 12,
  model = 'small',
  adjustment = 3,
  signal?: AbortSignal,
): Promise<PredictionData> {
  const raw = await getJson(
    `/api/chart/${encodeURIComponent(symbol)}/forecast?horizon=${horizon}&model=${encodeURIComponent(model)}&adjustment=${adjustment}`,
    ForecastResponseSchema,
    signal,
  );
  return transformForecastResponse(raw);
}
