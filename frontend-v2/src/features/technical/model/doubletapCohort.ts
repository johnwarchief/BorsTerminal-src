/**
 * frontend-v2/src/features/technical/model/doubletapCohort.ts
 *
 * خواندن کوهورت بازارِ تولیدشده از snapshot مرجع RA365.
 * اگر همان نماد نمونهٔ کافی نداشت، نرخ هم‌گروه بازار (و در صورت کفایت، سبد کیفیت)
 * به‌عنوان fallback استفاده می‌شود. این عدد «هم‌گروه بازار» برچسب می‌خورد، نه «همان نماد».
 */

import cohortData from '../data/doubletap-cohort.json';
import type { CohortEstimate } from './doubleTapEngine';

type CohortTimeframe = '1D' | '1W';
type Counts = { successes: number; failures: number; resolved: number; patterns: number; assets?: number };
type Band = { min: number; max: number } & Counts;

interface CohortFile {
  market: Record<CohortTimeframe, Counts>;
  qualityBands: Record<CohortTimeframe, Band[]>;
}

const data = cohortData as unknown as CohortFile;

export function getMarketCohort(timeframe: string, quality: number): CohortEstimate | null {
  const key: CohortTimeframe | null =
    timeframe === '1D' ? '1D' : timeframe === '1W' ? '1W' : null;
  if (!key) return null;

  const bandIndex = quality >= 80 ? 2 : quality >= 60 ? 1 : 0;
  const band = data.qualityBands[key]?.[bandIndex];
  const useBand = Boolean(band && band.resolved >= 8);
  const source = useBand && band ? band : data.market[key];
  if (!source || source.resolved < 8) return null;

  return {
    successes: source.successes,
    failures: source.failures,
    resolved: source.resolved,
    band: bandIndex,
    label: useBand ? 'بازار · کیفیت مشابه' : 'بازار',
  };
}
