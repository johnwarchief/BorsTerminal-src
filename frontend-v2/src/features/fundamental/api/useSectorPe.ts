import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const Row = z.looseObject({
  symbol: z.string(),
  sector_name: z.string().nullish(),
  pe: z.number().nullish(),
});
const Payload = z.looseObject({
  status: z.string(),
  data: z.array(Row).default([]),
});

export interface SectorPe {
  pe: number | null;
  median: number | null;
  sector: string | null;
  peers: number;
}

function medianOf(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1
    ? sorted[mid]!
    : (sorted[mid - 1]! + sorted[mid]!) / 2;
}

export function useSectorPe(symbol: string | null | undefined) {
  return useQuery<SectorPe>({
    queryKey: ['sector-pe', symbol],
    queryFn: async ({ signal }) => {
      const feed = await getJson('/api/market', Payload, signal);
      const row = feed.data.find((item) => item.symbol === symbol);
      const sector = row?.sector_name ?? null;
      const peers = sector
        ? feed.data.filter((item) => item.sector_name === sector)
        : [];
      // P/E منفی یا صفر «نسبت» نیست؛ میانه فقط رویِ مقادیرِ مثبتِ محدود.
      const ratios = peers
        .map((item) => item.pe)
        .filter((pe): pe is number => typeof pe === 'number' && Number.isFinite(pe) && pe > 0);
      const own = row?.pe;
      return {
        pe: typeof own === 'number' && Number.isFinite(own) ? own : null,
        median: medianOf(ratios),
        sector,
        peers: ratios.length,
      };
    },
    enabled: Boolean(symbol),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
