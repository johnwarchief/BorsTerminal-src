import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

export const PhaseSchema = z.looseObject({
  status: z.string(),
  phase: z.string().nullish(),
  label: z.string().nullish(),
  phase_source: z.string().nullish(),
  official: z.boolean().nullish(),
  official_state_title: z.string().nullish(),
  is_live: z.boolean().nullish(),
  session_day: z.number().nullish(),
  verdict_allowed: z.boolean().nullish(),
  clock_now: z.string().nullish(),
  session_start: z.string().nullish(),
  session_end: z.string().nullish(),
});

export type Phase = z.infer<typeof PhaseSchema>;

export function usePhase() {
  return useQuery<Phase>({
    queryKey: ['market-phase'],
    queryFn: ({ signal }) => getJson('/api/mstat/phase', PhaseSchema, signal),
    refetchInterval: 30_000,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}
