// features/market/api/useMarketFeed.ts -- خوراک تابلو با پولینگ
// گزینه‌ها از shared/api/marketFeed می‌آید: همان کلید، همان queryFn که پس از
// اولین بار دلتا می‌خواند (بی‌بدنۀ ۴ مگابایتی هر پنج ثانیه) و همان ارجاعِ
// داده در بی‌تغییری، تا پولینگِ بی‌کاری رندر نسازد.
import { useQuery } from '@tanstack/react-query';
import { marketFeedOptions } from '@shared/api/marketFeed';
import { useMarketStore } from '@shared/stores/marketStore';

export function useMarketFeed() {
  const refetchIntervalMs = useMarketStore((s) => s.refetchIntervalMs);
  const paused = useMarketStore((s) => s.paused);
  return useQuery(marketFeedOptions(refetchIntervalMs, paused));
}

