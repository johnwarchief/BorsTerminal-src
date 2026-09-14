// features/technical/api/useMarketSeries.ts -- لایهٔ دادهٔ واحد برای سری «کل بورس»
// هدف: سری کل‌بازار پشت یک انتزاع روشن باشد تا بعداً «سری شاخص کل واقعی (TEDPIX)»
// بدون refactor بزرگ جایگزین شود: فقط buildMarketSeries عوض می‌شود و مصرف‌کننده
// (MarketOverview) بی‌تغییر می‌ماند. عدد ساختگی ممنوع؛ ready=false صادقانه.
import { useMemo } from 'react';
import { useMarketMacro, type MacroTimeline } from './useMarketMacro';

export type MarketSeriesPoint = { label: string | number | null; value: number };

export type MarketSeries = {
  /** کلید پایدار نمودار — جایگزینی منبع این کلید را عوض نمی‌کند */
  key: 'whole-market';
  title: string;
  unit: string;
  /** منبع واقعی داده — برای نمایش صادقانه در UI */
  source: string;
  /** آیا سری برای رسم آماده است (دست‌کم دو نقطهٔ معتبر) */
  ready: boolean;
  points: MarketSeriesPoint[];
  note: string | null;
  day: number | null;
};

/** شناسهٔ منبع فعلی — بعداً 'tsetmc:tedpix' با همین کلید جایگزین می‌شود */
export const WHOLE_MARKET_SERIES_SOURCE = 'local:mstat-timeline';

/** خالص: ساخت سری «کل بورس» از پاسخ تایم‌لاین کلان */
export function buildMarketSeries(timeline: MacroTimeline | null | undefined): MarketSeries | null {
  if (!timeline) return null;
  const raw = timeline.series?.val_bt ?? [];
  const labels = timeline.series?.t ?? [];
  const points: MarketSeriesPoint[] = [];
  raw.forEach((v, i) => {
    const n = typeof v === 'string' ? Number(v) : v;
    if (typeof n === 'number' && Number.isFinite(n)) points.push({ label: labels[i] ?? null, value: n });
  });
  return {
    key: 'whole-market',
    title: 'ارزش معاملات خرد (سری تجمعی درون‌روزی)',
    unit: 'سری کلان',
    source: timeline.source ?? WHOLE_MARKET_SERIES_SOURCE,
    ready: timeline.ready === true && points.length >= 2,
    points,
    note: timeline.note ?? null,
    day: timeline.day ?? null,
  };
}

/** هوک مصرفی: سری واحد «کل بورس» (پشت همان کوئری mstat، پس بدون fetch اضافه) */
export function useMarketSeries() {
  const q = useMarketMacro();
  const data = useMemo(() => buildMarketSeries(q.data?.timeline), [q.data]);
  return { data, isLoading: q.isLoading, isError: q.isError };
}
