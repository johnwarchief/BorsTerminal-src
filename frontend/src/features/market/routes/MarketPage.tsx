// features/market/routes/MarketPage.tsx -- صفحه تابلو بازار (ایجنت 3)
import { useEffect, useMemo, type ReactNode } from 'react';
import type { MarketRow } from '@shared/types/marketRow';
import { publishSignal } from '@shared/lib/signalBus';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketStore } from '@shared/stores/marketStore';
import { useMarketFeed } from '../api/useMarketFeed';
import { useMarketPulse } from '../api/useMarketPulse';
import { buildScreenerMap, useFtsScreener } from '../api/useFtsScreener';
import { classifyAssetType, type AssetType } from '../lib/assetType';
import { dropNumericSuffixRows } from '../lib/tapeFts';
import { rowsToTapeSignals } from '../signals/tapeSignals';
import { matchesDirection, matchesExitAccum, matchesVolRatio, useTapeStore } from '../stores/tapeStore';
import { countQuickMatches, MarketFilters } from '../components/MarketFilters';
import { MarketPulseBar } from '../components/MarketPulseBar';
import { MicroChartsDrawer } from '../components/MicroChartsDrawer';
import { TapeTable } from '../components/TapeTable';
import { VolumeFlow } from '../components/VolumeFlow';
import { WatchDrawer } from '../components/WatchDrawer';
import { TapeStatusBar } from '../components/TapeStatusBar';

export function applyFilters(
  rows: MarketRow[],
  query: string,
  assetTypes: AssetType[],
  quickFilters: string[],
  sector: string,
  liveOnly: boolean,
  direction: ReturnType<typeof useTapeStore.getState>['direction'],
  volRatioOn: boolean,
  volRatioMin: number,
  exitAccum: boolean,
): MarketRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter((r) => {
    if (q && !(r.symbol?.toLowerCase().includes(q) || (r.name ?? '').toLowerCase().includes(q))) return false;
    if (sector && (r.sector_name ?? '') !== sector) return false;
    if (!assetTypes.includes(classifyAssetType(r))) return false;
    for (const f of quickFilters) {
      if (!(r as unknown as Record<string, unknown>)[f]) return false;
    }
    if (liveOnly && r.is_live === false) return false;
    if (!matchesDirection(r.percent_change, direction)) return false;
    if (volRatioOn && !matchesVolRatio(r.vol_ratio, volRatioMin)) return false;
    if (exitAccum && !matchesExitAccum(r)) return false;
    return true;
  });
}

export default function MarketPage({
  renderBasketAction,
}: {
  /**
   * اسلات تزریقیِ اختیاری از پوسته برای اکشن «سبد» روی ردیف‌ها.
   * اگر پوسته چیزی ندهد، دکمهٔ سبک پیش‌فرض (انتشار قصد سبد) استفاده می‌شود.
   * مرز market فقط shared/contracts است، پس خودش SymbolBasketAction را import نمی‌کند.
   */
  renderBasketAction?: (symbol: string) => ReactNode;
} = {}) {
  const { data, isLoading, isError, refetch, dataUpdatedAt, isFetching } = useMarketFeed();
  const { data: pulse, isLoading: pulseLoading } = useMarketPulse();
  const { data: screener } = useFtsScreener();
  const rows = useMemo(() => data?.data ?? [], [data]);

  /** نقشهٔ وضعیت FTS (تأیید/رد/N/A) از همان منبع غربالگری FTS */
  const ftsMap = useMemo(() => buildScreenerMap(screener), [screener]);

  const query = useTapeStore((s) => s.query);
  const assetTypes = useTapeStore((s) => s.assetTypes);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const sector = useTapeStore((s) => s.sector);
  const liveOnly = useTapeStore((s) => s.liveOnly);
  const direction = useTapeStore((s) => s.direction);
  const volRatioOn = useTapeStore((s) => s.volRatioOn);
  const volRatioMin = useTapeStore((s) => s.volRatioMin);
  const exitAccum = useTapeStore((s) => s.exitAccum);

  const symbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);
  const setSector = useTapeStore((s) => s.setSector);
  const refetchIntervalMs = useMarketStore((s) => s.refetchIntervalMs);
  const setRefetchIntervalMs = useMarketStore((s) => s.setRefetchIntervalMs);

  const sectors = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) if (r.sector_name) set.add(r.sector_name);
    // صنعتِ انتخاب‌شدهٔ پنل inflow حتی اگر در ردیف‌های فعلی نبود در گزینه‌ها بماند
    if (sector) set.add(sector);
    return [...set].sort((a, b) => a.localeCompare(b, 'fa'));
  }, [rows, sector]);

  /** شمارش عبور هر فیلتر سریع -- فقط روی ردیف های زنده تا چیپ ها معنادار باشند */
  const quickMatches = useMemo(() => {
    const live = rows.filter((r) => r.is_live !== false);
    return countQuickMatches(live as unknown as Parameters<typeof countQuickMatches>[0]);
  }, [rows]);

  const exitAccumCount = useMemo(
    () => rows.filter((r) => r.is_live !== false && matchesExitAccum(r)).length,
    [rows],
  );
  const volRatioCount = useMemo(
    () => rows.filter((r) => r.is_live !== false && matchesVolRatio(r.vol_ratio, volRatioMin)).length,
    [rows, volRatioMin],
  );

  const filtered = useMemo(
    () =>
      dropNumericSuffixRows(
        applyFilters(
          rows,
          query,
          assetTypes,
          quickFilters,
          sector,
          liveOnly,
          direction,
          volRatioOn,
          volRatioMin,
          exitAccum,
        ),
      ),
    [rows, query, assetTypes, quickFilters, sector, liveOnly, direction, volRatioOn, volRatioMin, exitAccum],
  );

  const signals = useMemo(() => rowsToTapeSignals(filtered), [filtered]);

  /**
   * انتشار سیگنال های تابلو در باس: تک اسلات ایجنت «تابلو» روی هر نماد.
   * برای هر نماد فقط قاطع ترین سیگنالش منتشر می شود تا باس یکدست بماند.
   */
  useEffect(() => {
    if (signals.length === 0) return;
    const bySymbol = new Map<string, typeof signals[number]>();
    for (const s of signals) {
      const cur = bySymbol.get(s.symbol);
      if (!cur || (s.score ?? -1) > (cur.score ?? -1)) bySymbol.set(s.symbol, s);
    }
    for (const s of bySymbol.values()) publishSignal(s);
  }, [signals]);

  return (
    <div className="flex w-full max-w-none flex-col gap-2">
      <MarketPulseBar pulse={pulse ?? null} isLoading={pulseLoading} />

      <MarketFilters
        sectors={sectors}
        matches={quickMatches}
        exitAccumCount={exitAccumCount}
        volRatioCount={volRatioCount}
      />

      <TapeStatusBar
        shown={filtered.length}
        total={rows.length}
        liveCount={data?.live_count ?? 0}
        fossilCount={data?.fossil_count ?? 0}
        signals={signals.length}
        isLoading={isLoading}
        isError={isError}
        isFetching={isFetching}
        dataUpdatedAt={dataUpdatedAt}
        pollMs={refetchIntervalMs}
        onPollChange={setRefetchIntervalMs}
        onRetry={() => refetch()}
      />

      {/* جدول تمام‌عرض؛ دیده‌بان‌ها به دراور زیر جدول منتقل شدند */}
      <MicroChartsDrawer />
      <TapeTable
        rows={filtered}
        selected={symbol}
        onSelect={setSymbol}
        renderBasketAction={renderBasketAction}
        ftsMap={ftsMap}
      />
      <WatchDrawer rows={filtered} onSelect={setSymbol} onPickSector={setSector} />
      <VolumeFlow symbol={symbol} onClose={clearSymbol} />
    </div>
  );
}
