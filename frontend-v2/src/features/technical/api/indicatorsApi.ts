/**
 * frontend-v2/src/features/technical/api/indicatorsApi.ts
 *
 * دریافت محاسبات شاخص‌های تکنیکال سرورساید از اندپوینت
 * GET /api/chart/{symbol}/indicators
 */

import { z } from 'zod';
import { getJson } from '@shared/api/http';

export const IndicatorsResponseSchema = z.looseObject({
  symbol: z.string(),
  count: z.number().optional().default(0),
  dates: z.array(z.string()).optional().default([]),
  latest: z.record(z.string(), z.any()).optional().default({}),
  series: z.record(z.string(), z.any()).optional().default({}),
});

export type IndicatorsResponse = z.infer<typeof IndicatorsResponseSchema>;

export async function fetchIndicators(
  symbol: string,
  signal?: AbortSignal,
): Promise<IndicatorsResponse> {
  return getJson(
    `/api/chart/${encodeURIComponent(symbol)}/indicators`,
    IndicatorsResponseSchema,
    signal,
  );
}
