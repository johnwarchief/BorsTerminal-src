/**
 * frontend-v2/src/features/technical/api/useTechnicalQueries.ts
 *
 * هوک‌های TanStack Query برای دریافت داده‌های پیش‌بینی، لبه آماری و اندیکاتورها.
 */

import { useQuery } from '@tanstack/react-query';
import { fetchForecast } from './forecastApi';
import { fetchCandleEdge } from './candleEdgeApi';
import { fetchIndicators } from './indicatorsApi';

export function useForecastQuery(symbol: string, horizon = 12, model = 'small', adjustment = 3, enabled = true) {
  return useQuery({
    queryKey: ['technical', 'forecast', symbol, horizon, model, adjustment],
    queryFn: ({ signal }) => fetchForecast(symbol, horizon, model, adjustment, signal),
    enabled: Boolean(symbol) && enabled,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useCandleEdgeQuery(symbol: string, swingPeriod = 5, enabled = true) {
  return useQuery({
    queryKey: ['technical', 'edge', symbol, swingPeriod],
    queryFn: ({ signal }) => fetchCandleEdge(symbol, swingPeriod, signal),
    enabled: Boolean(symbol) && enabled,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useIndicatorsQuery(symbol: string, enabled = true) {
  return useQuery({
    queryKey: ['technical', 'indicators', symbol],
    queryFn: ({ signal }) => fetchIndicators(symbol, signal),
    enabled: Boolean(symbol) && enabled,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
