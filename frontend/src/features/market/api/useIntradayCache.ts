// features/market/api/useIntradayCache.ts -- ثبت ~۳۰ثانیه‌ای اسنپ‌شات تجمعی در کش محلی
// آخرین نقطهٔ تایم‌لاین (وقتی بازار باز است) در LocalStorage ذخیره می‌شود تا سری
// t1,t2,… برای نمودار خطی ساخته شود. خارج ساعات بازار چیزی ثبت نمی‌شود (بدون داده).
import { useEffect, useRef, useState } from 'react';
import { appendSnapshot, dayKey, isMarketOpen, readCache } from '../lib/intradayCache';
import type { TimelinePoint } from '../lib/timelineMath';

export function useIntradayCache(latest: TimelinePoint | null): TimelinePoint[] {
  const [points, setPoints] = useState<TimelinePoint[]>(() => readCache());
  const latestRef = useRef(latest);
  latestRef.current = latest;

  const stamp = latest
    ? `${latest.t}|${latest.bq}|${latest.sq}|${latest.pos}|${latest.neg}`
    : '';

  useEffect(() => {
    const p = latestRef.current;
    if (!p || !isMarketOpen()) return;
    setPoints(appendSnapshot(p, dayKey()));
  }, [stamp]);

  return points;
}
