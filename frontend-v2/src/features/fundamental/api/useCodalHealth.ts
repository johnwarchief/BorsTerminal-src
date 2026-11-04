import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const Str = z.string().nullish();
const Num = z.number().nullish();
const Bool = z.boolean().nullish();

const Payload = z.looseObject({
  status: z.string(),
  message: Str,
  queue: z.looseObject({
    queued: Num, running: Num, done: Num, empty: Num, failed: Num,
    unresolved: Num, quarantined: Num, total: Num, retryable: Num,
  }).nullish(),
  dirty_symbols: Num,
  last_data_update: Str,
  gap_flag: Bool,
  last_successful_sync: z.looseObject({ at: Str, cycle: Str }).nullish(),
  last_attempt: z.looseObject({ started_at: Str, finished_at: Str, error: Str }).nullish(),
  checked_at: Str,
});

export type CodalHealth = z.infer<typeof Payload>;

export function useCodalHealth() {
  return useQuery<CodalHealth>({
    queryKey: ['codal-health'],
    queryFn: ({ signal }) => getJson('/api/sync/codal/pipeline', Payload, signal),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
