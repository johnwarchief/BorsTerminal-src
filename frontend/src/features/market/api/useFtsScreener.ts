// features/market/api/useFtsScreener.ts -- وضعیت FTS هر نماد از /api/screener
// همان منبع غربالگری FTS (fts_engine.bulk_scan): پرچم excluded + exclusion_reasons.
// نمادِ بدون صورت مالی در پاسخ نیست ⇒ صادقانه N/A، نه عدد/حکم ساختگی.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { isInsuranceSector, normSymbol } from '../lib/tapeFts';

/** exclusion_reasons در bulk_scan رشته است، در مسیر جزئیات آرایه — هر دو پذیرفته می‌شود */
const ReasonsSchema = z.union([z.string(), z.array(z.string())]).nullish();

const ScreenerRowSchema = z.object({
  symbol: z.string(),
  name: z.string().nullish(),
  score: z.number().nullish(),
  excluded: z.boolean().nullish(),
  exclusion_reasons: ReasonsSchema,
  verdict: z.string().nullish(),
  watchlist: z.boolean().nullish(),
  pricing_mode: z.string().nullish(),
});
export type ScreenerRow = z.infer<typeof ScreenerRowSchema>;

const ScreenerSchema = z.object({
  status: z.string(),
  count: z.number().nullish(),
  max_score: z.number().nullish(),
  data: z.array(ScreenerRowSchema),
});
export type ScreenerFeed = z.infer<typeof ScreenerSchema>;

export function useFtsScreener() {
  return useQuery({
    queryKey: ['market-fts-screener'],
    queryFn: ({ signal }) =>
      http<ScreenerFeed>('/api/screener', { schema: ScreenerSchema, signal }),
    staleTime: 120_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export function buildScreenerMap(feed: ScreenerFeed | undefined): Map<string, ScreenerRow> {
  const map = new Map<string, ScreenerRow>();
  for (const row of feed?.data ?? []) map.set(normSymbol(row.symbol), row);
  return map;
}

/** رشتهٔ دلایلِ اسکرینر → آرایهٔ تمیز (جداکنندهٔ ' · ') */
export function splitReasons(raw: ScreenerRow['exclusion_reasons']): string[] {
  if (raw == null) return [];
  const list = Array.isArray(raw) ? raw : raw.split('·');
  return list.map((t) => t.trim()).filter(Boolean);
}

export type FtsStatus = 'confirm' | 'reject' | 'na';

export const FTS_STATUS_LABEL: Record<FtsStatus, string> = {
  confirm: 'تأیید',
  reject: 'رد',
  na: 'N/A',
};

export type FtsView = {
  status: FtsStatus;
  label: string;
  score: number | null;
  reasons: string[];
};

const NA_VIEW: FtsView = { status: 'na', label: FTS_STATUS_LABEL.na, score: null, reasons: [] };

/**
 * وضعیت FTSِ یک ردیف تابلو:
 * - صنعت بیمه ⇒ «رد» قطعی (REJECT_ALL_INSURANCE سند v2.1) حتی اگر در اسکرینر نباشد
 * - symbol در اسکرینر و excluded ⇒ «رد» + دلایل (hovercard)
 * - symbol در اسکرینر و غیرمردود ⇒ «تأیید» + امتیاز
 * - symbol نبود در اسکرینر (بدون صورت مالی) ⇒ «N/A» صادقانه
 */
export function resolveFtsStatus(
  row: { symbol?: string | null; sector_name?: string | null },
  map: Map<string, ScreenerRow>,
): FtsView {
  if (isInsuranceSector(row.sector_name)) {
    return {
      status: 'reject',
      label: FTS_STATUS_LABEL.reject,
      score: null,
      reasons: ['صنعت بیمه — حذف خودکار (REJECT_ALL_INSURANCE سند v2.1)'],
    };
  }
  const hit = map.get(normSymbol(row.symbol));
  if (!hit) return NA_VIEW;

  const reasons = splitReasons(hit.exclusion_reasons);
  const score = typeof hit.score === 'number' ? hit.score : null;
  if (hit.excluded) {
    return {
      status: 'reject',
      label: FTS_STATUS_LABEL.reject,
      score,
      reasons: reasons.length > 0 ? reasons : ['ردشده در غربالگری FTS'],
    };
  }
  return { status: 'confirm', label: FTS_STATUS_LABEL.confirm, score, reasons };
}
