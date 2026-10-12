// shared/api/tapeHistory.ts — خواندنِ سابقۀ چندروزۀ هفت فیلترِ تابلو
//
// مسیرِ خواندنِ `/api/tape-history` (`api/market.py`)؛ نوشتن را خودِ تابلو
// می‌نویسد (`tape_flag_history.record_observations`). اینجا هیچ داوریِ تازه‌ای
// ساخته نمی‌شود و هیچ روزِ گذشته از دادهٔ امروز پُر نمی‌شود — دقیقاً همان چیزی
// که مالک درِ بندِ سوم مأموریت خواسته است.
//
// کلیدِ پرس‌وجو `ins_code` است (شناسۀ پایدار)، نه نامِ نمایشی.
import { useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { TAPE_FLAGS, type TapeFlag } from '@shared/lib/tapeFlags';

export type TapeDayCell = {
  active: boolean;
  first_at: string | null;
  last_at: string | null;
  passes: number;
  evidence: Record<string, unknown>;
};

export type TapeFlagSeries = {
  days: Record<string, TapeDayCell>;
  total: number;
  last_seen_at: string | null;
};

export type TapeHistoryPayload = {
  status: string;
  days: number[];
  reliable_from: number | null;
  by_symbol: Record<string, Partial<Record<TapeFlag, TapeFlagSeries>>>;
  flags: string[];
  /** خطایِ مسیرِ نوشتن — اگر باشد، سابقۀ همین دور قابل‌اعتماد نیست */
  write_error?: string | null;
  message?: string;
};

export const TAPE_HISTORY_KEY = ['tape-history'] as const;

/** نامِ نماد معیارِ هویت نیست؛ `ins_code` بله. پروندۀ نماد (برآیند، دیدهبان) نام
 *  را می‌شناسد و کوئریِ سابقه کلیدِ پایدار می‌خواهد، پس از همان فیدِ مشترکِ تابلو
 *  خوانده می‌شود — بی‌درخواستِ دوم. نبودش یعنی «سابقه خوانده نمی‌شود»، نه «صفر». */
export function useInsCodeFor(symbol: string | null | undefined): string | null {
  const norm = normalizeFa(symbol ?? '');
  const q = useMarketFeedShared((f) => {
    if (!norm) return null;
    const hit = (f.data ?? []).find((r) => normalizeFa(String(r.symbol ?? '')) === norm);
    return hit ? (String(hit.ins_code ?? '') || null) : null;
  }, 60_000);
  return q.data ?? null;
}

export function useTapeHistory(insCode: string | null | undefined, days = 6) {
  const code = String(insCode ?? '').trim();
  return useQuery<TapeHistoryPayload>({
    queryKey: [...TAPE_HISTORY_KEY, code, days],
    queryFn: ({ signal }) =>
      http<TapeHistoryPayload>(`/api/tape-history?codes=${encodeURIComponent(code)}&days=${days}`,
                               { signal }),
    enabled: code.length > 0,
    // سابقه با هر نوبتِ ثبت (۴ دقیقه) جلو می‌رود؛ تازه‌ترینِ همین‌جا کافی است
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

/** صفِ فیلترها همیشه همان هفت است، حتی وقتی پاسخِ خالی آمد — رابط بی‌ردیف
 *  نمی‌ماند و «صفر روز» دیده می‌شود (نه «داده نیست» در همه‌جا). */
export function seriesFor(payload: TapeHistoryPayload | undefined,
                          insCode: string | null | undefined): Partial<Record<TapeFlag, TapeFlagSeries>> {
  const by = payload?.by_symbol ?? {};
  return by[String(insCode ?? '').trim()] ?? Object.fromEntries(TAPE_FLAGS.map((f) => [f, {
    days: {}, total: 0, last_seen_at: null,
  }]));
}
