// features/fundamental/api/useSectorBoard.ts -- تابلوی سبک برای میانه صنعت
// جدا از useMarketFeed ایجنت تابلو تا مرز B1 حفظ شود (بدون پولینگ، کش بلند).
import { useMarketFeedShared } from '@shared/api/marketFeed';
import type { MarketFeed } from '@shared/types/marketRow';

export interface SectorBoardRow {
  symbol: string;
  sector_name: string;
  pe: number | null;
}

// selectِ پایدار + کشِ کلید=مرجعِ ردیف‌ها (Phase پرفورمنس) — بی‌تغییری یعنی
// همان آرایۀ قبلی، نه mapِ تازهٔ ۵۵۹۸تایی در هر poll.
let sectorCache: { src: MarketFeed['data']; rows: SectorBoardRow[] } | null = null;

function selectSectorBoard(feed: MarketFeed): SectorBoardRow[] {
  if (sectorCache && sectorCache.src === feed.data) return sectorCache.rows;
  const rows = feed.data.map((r) => ({
    symbol: r.symbol,
    sector_name: r.sector_name ?? '',
    pe: r.pe ?? null,
  }));
  sectorCache = { src: feed.data, rows };
  return rows;
}

export function useSectorBoard() {
  // میانهٔ صنعت از همان تابلو می‌آید؛ کوئریِ جدا یعنی یک ۴ مگابایتِ دوم.
  return useMarketFeedShared(selectSectorBoard, 5 * 60_000);
}
