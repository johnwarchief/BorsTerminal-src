// features/technical/api/useFundGate.ts -- عبور از گیت بنیادی برای سیگنال پرواز
// اسکیمای حداقلی روی همان اندپوینت کارت؛ جدا از فیچر بنیادی تا مرز B1 حفظ شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const GateSchema = z.object({
  status: z.string(),
  score: z.number().nullish(),
  excluded: z.boolean().nullish(),
});

/** عبور یعنی حذف خودکار نشده و امتیاز دست کم 3 از 5 */
export function gatePassFromCard(card: { score?: number | null; excluded?: boolean | null } | null | undefined): boolean | null {
  if (card == null) return null;
  if (card.excluded) return false;
  return (card.score ?? 0) >= 3;
}

export function useFundGate(symbol: string) {
  const query = useQuery({
    queryKey: ['fund-gate', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof GateSchema>>(`/api/fundamental/${encodeURIComponent(symbol)}`, { schema: GateSchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 30 * 60_000,
    gcTime: 60 * 60_000,
    refetchOnWindowFocus: false,
  });
  return { ...query, pass: gatePassFromCard(query.data ?? null) };
}
