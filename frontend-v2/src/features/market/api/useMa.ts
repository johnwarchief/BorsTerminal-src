import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const PointSchema = z.tuple([z.string(), z.number().nullable()]);
const SeriesSchema = z.array(PointSchema);

const OkSchema = z.looseObject({
  status: z.literal('ok'),
  symbol: z.string(),
  periods: z.array(z.number()).nullish(),
  ma: z.looseObject({
    ma5: SeriesSchema.nullish(),
    ma20: SeriesSchema.nullish(),
    ma50: SeriesSchema.nullish(),
    ma120: SeriesSchema.nullish(),
  }),
  bars: z.number().nullish(),
});

const ErrorSchema = z.looseObject({
  status: z.literal('error'),
  message: z.string().nullish(),
});

export const MaSchema = z.union([OkSchema, ErrorSchema]);
export type MaPayload = z.infer<typeof MaSchema>;
export type MaSeries = Partial<Record<'ma5' | 'ma20' | 'ma50' | 'ma120',
  Array<[string, number | null]> | null>>;

export function useMa(symbol: string | null | undefined) {
  return useQuery<MaPayload>({
    queryKey: ['ma', symbol],
    queryFn: ({ signal }) => getJson(`/api/ma/${encodeURIComponent(String(symbol))}`, MaSchema, signal),
    enabled: Boolean(symbol),
    staleTime: 5 * 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export interface MaLevel {
  value: number;
  date: string;
  distancePct: number | null;
}

export interface TechnicalSummary {
  price: number | null;
  ma20: MaLevel | null;
  ma50: MaLevel | null;
  slope5Pct: number | null;
  trend: 'up' | 'down' | 'neutral' | null;
}

export const TREND_LABEL = { up: 'صعودی', down: 'نزولی', neutral: 'خنثی' } as const;

function lastFinite(series: MaSeries[keyof MaSeries]): [string, number] | null {
  const points = series ?? [];
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const point = points[index];
    const value = point?.[1];
    if (value != null && Number.isFinite(value)) return [point![0], value];
  }
  return null;
}

function level(series: MaSeries[keyof MaSeries], price: number | null): MaLevel | null {
  const last = lastFinite(series);
  if (!last) return null;
  const [date, value] = last;
  return {
    date,
    value,
    distancePct: price == null || value === 0 ? null : ((price - value) / value) * 100,
  };
}

function slopePct(series: MaSeries[keyof MaSeries], steps: number): number | null {
  const values = (series ?? [])
    .map((point) => point[1])
    .filter((value): value is number => value != null && Number.isFinite(value));
  if (values.length < steps + 1) return null;
  const last = values[values.length - 1]!;
  const first = values[values.length - 1 - steps]!;
  if (first === 0) return null;
  return ((last - first) / first) * 100;
}

export function technicalSummary(ma: MaSeries, price: number | null): TechnicalSummary {
  const ma20 = level(ma.ma20, price);
  const ma50 = level(ma.ma50, price);
  const slope5Pct = slopePct(ma.ma20, 5);
  let trend: TechnicalSummary['trend'] = null;
  if (price != null && ma20 && slope5Pct != null) {
    if (price > ma20.value && slope5Pct > 0) trend = 'up';
    else if (price < ma20.value && slope5Pct < 0) trend = 'down';
    else trend = 'neutral';
  }
  return { price, ma20, ma50, slope5Pct, trend };
}
