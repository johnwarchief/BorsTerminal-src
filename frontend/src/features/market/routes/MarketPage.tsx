// features/market/routes/MarketPage.tsx -- صفحه تابلو بازار (ایجنت 3)
import { useEffect, useMemo } from 'react';
import type { MarketRow } from '@shared/types/marketRow';
import { publishSignals } from '@shared/lib/signalBus';
import { matchFa } from '@shared/lib/normalizeFa';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketStore } from '@shared/stores/marketStore';
import { useMarketFeed } from '../api/useMarketFeed';
import { useMarketPulse } from '../api/useMarketPulse';
import { classifyAssetType, type AssetType } from '../lib/assetType';
import { dropNumericSuffixRows } from '../lib/tapeFts';
import { rowsToTapeSignals } from '../signals/tapeSignals';
import { matchesDirection, matchesExitAccum, matchesVolRatio, useTapeStore } from '../stores/tapeStore';
import { countHiddenMatches, countQuickMatches, MarketFilters } from '../components/MarketFilters';
import { MarketPulseBar } from '../components/MarketPulseBar';
import { CollapsibleSection } from '@shared/components/CollapsibleSection';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { pulseIndex, pulseVerdict, type MarketPulseData } from '../api/useMarketPulse';
import { MicroChartsDrawer } from '../components/MicroChartsDrawer';
import { TapeTable } from '../components/TapeTable';
import { WatchDrawer } from '../components/WatchDrawer';

import {
  tapeFilterVerdict,
  type TapeFilterConfig,
} from '../lib/tapeAlgorithms';

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
  exitAccum = false,
  filterConfig?: TapeFilterConfig,
): MarketRow[] {
  const q = query.trim();
  return rows.filter((r) => {
    if (q && !(matchFa(r.symbol, q) || matchFa(r.name, q))) return false;
    if (sector && (r.sector_name ?? '') !== sector) return false;
    if (!assetTypes.includes(classifyAssetType(r))) return false;
    for (const f of quickFilters) {
      if (filterConfig) {
        if (!tapeFilterVerdict(r, f, filterConfig)) return false;
      } else {
        if (!(r as unknown as Record<string, unknown>)[f]) return false;
      }
    }
    // #197: جدول بی‌پیش‌فرض فقط «همین نشست» را می‌نمایاند؛ ولی وقتی کاربر
    // خودش نمادی را نوشته منظورش دیدنِ همان نماد است، پس جستجو از این بند
    // مستثنی می‌ماند (وگرنه جست‌وجویِ یک نمادِ خاموش = «ردیفی نیامد»ِ گمراه‌کننده).
    if (liveOnly && !q && r.is_live === false) return false;
    if (!matchesDirection(r.percent_change, direction)) return false;
    if (volRatioOn && !matchesVolRatio(r.vol_ratio, volRatioMin)) return false;
    if (exitAccum && !matchesExitAccum(r, filterConfig)) return false;
    return true;
  });
}

/** خلاصهٔ یک‌خطیِ نبض برایِ حالتِ جمع‌شده: شاخصِ کل و حکمِ امروز.
 *  همان داده‌ای که خودِ نوار می‌کشد — بی‌محاسبهٔ تازه، پس نمی‌تواند با آن
 *  اختلاف پیدا کند. */
const VERDICT_TONE: Record<string, string> = {
  go: 'text-accent-green',
  watch: 'text-accent-yellow',
  wait: 'text-text-secondary',
  avoid: 'text-accent-red',
  nodata: 'text-text-muted',
};

function PulseSummary({ pulse }: { pulse: MarketPulseData | null }) {
  const ix = pulseIndex(pulse);
  const v = pulseVerdict(pulse);
  if (!ix && !v) return <span className="text-2xs text-text-muted">نبض هنوز نیامده</span>;
  return (
    <span className="flex items-center gap-2.5 text-2xs">
      {ix?.last != null ? (
        <span className="flex items-center gap-1">
          <span className="text-text-muted">شاخص</span>
          <span className="num font-bold text-text-primary">{fmtInt(ix.last)}</span>
          {ix.pct != null ? (
            <span className={`num font-bold ${ix.pct > 0 ? 'text-accent-green' : ix.pct < 0 ? 'text-accent-red' : 'text-text-secondary'}`}>
              {toFaDigits(ix.pct.toFixed(2))}٪
            </span>
          ) : null}
        </span>
      ) : null}
      {v ? (
        <span className={`font-bold ${VERDICT_TONE[v.verdict] ?? 'text-text-secondary'}`} title={v.reason}>
          {v.label}
        </span>
      ) : null}
    </span>
  );
}

export default function MarketPage() {
  const { data, isLoading, isError, refetch, dataUpdatedAt, isFetching } = useMarketFeed();
  const { data: pulse, isLoading: pulseLoading } = useMarketPulse();
  const rows = useMemo(() => data?.data ?? [], [data]);

  const query = useTapeStore((s) => s.query);
  const assetTypes = useTapeStore((s) => s.assetTypes);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const sector = useTapeStore((s) => s.sector);
  const liveOnly = useTapeStore((s) => s.liveOnly);
  const direction = useTapeStore((s) => s.direction);
  const volRatioOn = useTapeStore((s) => s.volRatioOn);
  const volRatioMin = useTapeStore((s) => s.volRatioMin);
  const exitAccum = useTapeStore((s) => s.exitAccum);
  const showNumericSuffix = useTapeStore((s) => s.showNumericSuffix);
  const tapeFilterConfig = useTapeStore((s) => s.tapeFilterConfig);

  const symbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
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

  /**
   * پایهٔ جدول و شمارش: همان ردیف‌هایی که جدول بی‌فیلترِ سریع نشان می‌دهد.
   * بدون این، چیپ روی کل تابلو می‌شمرد (۱۷۹) و کلیک روی همان چیپ ۸۰ ردیف
   * از بازارهای فعال را نشان می‌داد — عددِ وعده‌دهنده با نتیجه یکی نبود.
   */
  const boardBase = useMemo(
    () =>
      applyFilters(
        rows,
        query,
        assetTypes,
        [],
        sector,
        liveOnly,
        direction,
        volRatioOn,
        volRatioMin,
        exitAccum,
        tapeFilterConfig,
      ),
    [rows, query, assetTypes, sector, liveOnly, direction, volRatioOn, volRatioMin, exitAccum, tapeFilterConfig],
  );

  const filterBase = useMemo(
    () => (showNumericSuffix ? boardBase : dropNumericSuffixRows(boardBase)),
    [boardBase, showNumericSuffix],
  );

  /**
   * ردیف‌هایی که فیلتر را می‌گذرانند ولی درِ نمایِ فعلی تابلو نیستند. بی‌شمارشِ
   * آن‌ها، چیپِ «کف‌روبی (۱)» در برابر ۳۱ ردیفِ فیلترنویسِ TSETMC هیچ توضیحی
   * نداشت و همان «جدول با TSE فرق دارد» باقی می‌ماند.
   *
   * سنجشِ ۱۴۰۵-۰۷-۰۷ رویِ فیدِ زنده (۵۳۶۰ ردیف): ردیف‌هایِ پنهانِ پنج فیلتر
   * هم‌زمان پسوندِ عددی داشتند و بازارشان خاموش بود، و هیچ‌کدام خاموشِ تابلو نبود
   * — پس دلیلِ پنهان باید از خودِ ردیف‌ها بخواند، نه از یک فهرستِ ثابت.
   */
  const hiddenRows = useMemo(() => {
    const shown = new Set(filterBase);
    return rows.filter((r) => !shown.has(r));
  }, [rows, filterBase]);

  const hiddenInfo = useMemo(
    () =>
      countHiddenMatches(
        hiddenRows,
        { assetTypes, liveOnly, query, sector, dropSuffix: !showNumericSuffix },
        tapeFilterConfig,
      ),
    [hiddenRows, assetTypes, liveOnly, query, sector, showNumericSuffix, tapeFilterConfig],
  );

  const quickMatches = useMemo(
    () =>
      countQuickMatches(
        filterBase as unknown as Parameters<typeof countQuickMatches>[0],
        tapeFilterConfig,
      ),
    [filterBase, tapeFilterConfig],
  );

  const filtered = useMemo(
    () =>
      quickFilters.length === 0
        ? filterBase
        : applyFilters(
            filterBase,
            query,
            assetTypes,
            quickFilters,
            sector,
            liveOnly,
            direction,
            volRatioOn,
            volRatioMin,
            exitAccum,
            tapeFilterConfig,
          ),
    [filterBase, query, assetTypes, quickFilters, sector, liveOnly, direction, volRatioOn, volRatioMin, exitAccum, tapeFilterConfig],
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
    publishSignals(Array.from(bySymbol.values()));
  }, [signals]);

  return (
    <div className="flex w-full max-w-none flex-col gap-2">
      {/* نبضِ بازار جمع‌شونده: رویِ ۱۳۶۶×۷۶۸ این داشبورد بیشترِ ارتفاع را
          می‌گرفت و جدولِ تابلو زیرِ خطِ تا می‌افتاد. حالا کاربر انتخاب
          می‌کند، و انتخابش می‌ماند. در حالتِ جمع، شاخص و حکمِ امروز روی
          همان نوار می‌مانند تا جمع‌کردن کور نکند. */}
      <CollapsibleSection
        title="نبض بازار"
        storageKey="bors.market.pulse.open"
        // رویِ نمایشگرِ کوتاه (لپ‌تاپِ ۱۳۶۶×۷۶۸) نبض پیش‌فرض جمع است.
        // حساب: نوارِ عنوان ~۷۵ + نوارِ شرط‌ها ~۸۰ + کارت‌هایِ نبض ~۲۱۰ +
        // نمودارها ~۴۵ + نوارِ فیلتر ~۹۵ = ~۵۰۵ پیکسل، یعنی از ۷۶۸ فقط
        // ~۱۰۰ پیکسل برایِ خودِ جدول می‌ماند — کمتر از سه ردیف.
        // هر دو بُعد شرط‌اند:
        //   • عمودیِ گوشی (۴۱۲×۹۱۵) از قیدِ ارتفاع رد می‌شد، در حالی که
        //     شبکه آنجا یک‌ستونی است و چهار کارت رویِ هم تلنبار می‌شوند.
        //   • افقیِ گوشی (۹۱۵×۴۱۲) از قیدِ عرض رد می‌شد، در حالی که
        //     ارتفاعش از لپ‌تاپِ ۷۶۸ هم کمتر است.
        // انتخابِ کاربر همیشه مقدم است (اول localStorage خوانده می‌شود).
        defaultOpen={
          typeof window === 'undefined'
          || (window.innerHeight > 820 && window.innerWidth > 820)
        }
        testId="market-pulse-section"
        summary={<PulseSummary pulse={pulse ?? null} />}
      >
        <MarketPulseBar pulse={pulse ?? null} isLoading={pulseLoading} />
      </CollapsibleSection>

      {/* نمودارهای جریان سفارش‌ها بالای نوار تابلو */}
      <MicroChartsDrawer />

      <MarketFilters
        sectors={sectors}
        matches={quickMatches}
        hiddenInfo={hiddenInfo}
        shown={filtered.length}
        total={rows.length}
        pollMs={refetchIntervalMs}
        onPollChange={setRefetchIntervalMs}
        dataUpdatedAt={dataUpdatedAt}
        isFetching={isFetching}
        isLoading={isLoading}
        isError={isError}
        onRetry={refetch}
      />

      <TapeTable
        rows={filtered}
        selected={symbol}
        onSelect={setSymbol}
        isLoading={isLoading}
        isError={isError}
        onRetry={refetch}
      />
      <WatchDrawer rows={filtered} onSelect={setSymbol} onPickSector={setSector} />
    </div>
  );
}
