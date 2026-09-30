// features/market/api/useSymbolFlow.ts -- سری درون‌روزِ حجم از همان خوراکِ تابلو
// هیچ اندپوینتی برایِ حجمِ دقیقه‌ای وجود ندارد (bank تاریخچه ندارد، رأیِ مالک بند ۴).
// خوراکِ تابلو همین حالا در سطحِ اپ پولینگ می‌شود؛ اینجا فقط دلتای آن ثبت می‌شود،
// پس درخواستِ تازه‌ای ساخته نمی‌شود و هزینه‌اش یک find رویِ ردیف‌هایِ موجود است.
import { useEffect, useMemo, useRef, useState } from 'react';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { isMarketOpen } from '@shared/lib/marketHours';
import { useMarketFeed } from './useMarketFeed';
import { minuteKey, readFlow, recordFlow, type FlowBucket } from '../lib/symbolFlow';

export type { FlowBucket };

export function findBoardRow<T extends { symbol: string }>(rows: T[], symbol: string): T | null {
  const n = normalizeFa(symbol);
  return rows.find((r) => r.symbol === symbol || normalizeFa(r.symbol) === n) ?? null;
}

export function useSymbolFlow(symbol: string) {
  const { data, isLoading } = useMarketFeed();
  const [buckets, setBuckets] = useState<FlowBucket[]>(() => readFlow(symbol));
  const stampRef = useRef('');

  useEffect(() => {
    stampRef.current = '';
    setBuckets(readFlow(symbol));
  }, [symbol]);

  const rows = data?.data;
  useEffect(() => {
    if (!symbol || !rows?.length || !isMarketOpen()) return;
    const row = findBoardRow(rows, symbol);
    if (!row || row.q_tot_tran == null) return;
    const t = minuteKey();
    const price = row.p_last ?? null;
    const stamp = `${t}|${row.q_tot_tran}|${price ?? ''}`;
    if (stamp === stampRef.current) return;
    stampRef.current = stamp;
    setBuckets(recordFlow(symbol, { t, cumVol: Number(row.q_tot_tran), price }));
  }, [symbol, rows]);

  const max = useMemo(() => buckets.reduce((m, b) => Math.max(m, b.vol), 0), [buckets]);
  return { buckets, max, isLoading };
}
