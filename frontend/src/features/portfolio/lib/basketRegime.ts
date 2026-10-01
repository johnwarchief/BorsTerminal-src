// features/portfolio/lib/basketRegime.ts -- رژیمِ سبدِ یک نماد، از تصمیم‌هایِ واقعی
// پیش‌تر همین محاسبه درونِ MasterPage نوشته شده بود و سایدبارِ چپ به‌جای خواندنش
// `industryCapPct: 20` و `warRegime: false` و `inBasket: false` را ثابت می‌ گذاشت —
// پس برایِ یکِ نمادِ یکِ زمان، دو پنل دو جوابِ مختلف می‌دادند (سایدبار «خرید»،
// مستر «وتو»). اینجا یک منبع؛ هر مصرف‌کننده‌ای همان را می‌خواند.
import {
  SECTOR_BANDS,
  matchSectorBand,
  normalizeSector,
} from '../model/sectorAllocation';
import { DEFAULT_INDUSTRY_CAP_PCT } from '@features/master/lib/strictGates';

export type BasketDecisionLike = {
  symbol?: string;
  status?: string | null;
  sector?: string | null;
  weight_eff_pct?: number | null;
};

export type BasketRegime = {
  /** true = در سبد · false = بیرونِ سبد · null = سبد هنوز نخوانده شده */
  inBasket: boolean | null;
  /** سقفِ صنعتِ این نماد از طبقه‌بندیِ سبد (جزوه) — نه عددِ ثابت */
  industryCapPct: number;
  /** مجموعِ وزنِ پذیرفته‌شدهٔ همان صنعت، بدونِ خودِ این نماد */
  industryUsedPct: number | null;
  symbolWeightPct: number | null;
  bandLabel: string | null;
};

const UNKNOWN: BasketRegime = {
  inBasket: null,
  industryCapPct: DEFAULT_INDUSTRY_CAP_PCT,
  industryUsedPct: null,
  symbolWeightPct: null,
  bandLabel: null,
};

export function basketRegimeFor(
  symbol: string,
  decisions: readonly BasketDecisionLike[] | null | undefined,
): BasketRegime {
  // «هنوز نخوانده» (`null`) با «سبدِ خالیِ خوانده‌شده» (`[]`) یکی نیست: دومی یعنی
  // بیرونِ سبد، اولی یعنی هیچ حکمی نباید ساخته شود.
  if (!symbol || decisions == null) return UNKNOWN;
  const list = decisions;
  const mine = list.find((d) => d.symbol === symbol) ?? null;
  const status = (mine?.status ?? '').toLowerCase();
  // بی‌تصمیمِ ثبت‌شده یعنی «نمی‌دانیم»، نه «بیرونِ سبد است»: گیتِ سبد باید
  // pending بماند و حکمِ مثبتِ ساختگی ندهد.
  const inBasket: boolean | null = mine ? status === 'accept' : null;
  const sector = mine?.sector ?? null;
  const band = SECTOR_BANDS.find((b) => b.id === matchSectorBand(sector)) ?? null;
  const industryCapPct = band?.max ?? DEFAULT_INDUSTRY_CAP_PCT;
  const industryUsedPct =
    sector != null
      ? Math.round(
          list
            .filter(
              (d) =>
                (d.status ?? '').toLowerCase() === 'accept' &&
                d.symbol !== symbol &&
                normalizeSector(d.sector ?? '') === normalizeSector(sector),
            )
            .reduce((sum, d) => sum + (typeof d.weight_eff_pct === 'number' ? d.weight_eff_pct : 0), 0) * 10,
        ) / 10
      : null;
  const symbolWeightPct = typeof mine?.weight_eff_pct === 'number' ? mine.weight_eff_pct : null;
  return { inBasket, industryCapPct, industryUsedPct, symbolWeightPct, bandLabel: band?.label ?? null };
}
