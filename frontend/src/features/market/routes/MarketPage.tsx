// features/market/routes/MarketPage.tsx -- صفحه تابلو بازار (ایجنت 3)
import { useEffect, useMemo } from 'react';
import type { MarketRow } from '@shared/types/marketRow';
import { toFaDigits } from '@shared/lib/fmt';
import { publishSignals } from '@shared/lib/signalBus';
import { matchFa } from '@shared/lib/normalizeFa';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketStore } from '@shared/stores/marketStore';
import { useScreenFilterStore } from '@shared/stores/screenFilterStore';
import { useMarketFeed } from '../api/useMarketFeed';
import { ASSET_LABELS, classifyAssetType, type AssetType } from '../lib/assetType';
import { dropNumericSuffixRows } from '../lib/tapeFts';
import { rowsToTapeSignals } from '../signals/tapeSignals';
import { matchesDirection, matchesExitAccum, matchesVolRatio, QUICK_LABELS, useTapeStore, type QuickFilter } from '../stores/tapeStore';
import { countHiddenMatches, countQuickMatches, countUnevaluated, MarketFilters } from '../components/MarketFilters';
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
  /** «اشتراک» = همهٔ چیپ‌های روشن لازم‌اند؛ «اجتماع» = کم‌از‌یکی کافی است.
   *  تا پیش از این جدولِ تابلو فقط اشتراک را می‌شناخت و کلیدِ اجتماع هیچ اثری
   *  روی‌اش نداشت (رأیِ مالک ۱۴۰۵-۰۷-۱۹: «هر دو رو نشون بده، هم مشترک هارو»). */
  quickLogic: 'and' | 'or' = 'and',
): MarketRow[] {
  const q = query.trim();
  const passes = (r: MarketRow, f: string) =>
    filterConfig
      ? tapeFilterVerdict(r, f, filterConfig)
      : !!(r as unknown as Record<string, unknown>)[f];
  return rows.filter((r) => {
    if (q && !(matchFa(r.symbol, q) || matchFa(r.name, q))) return false;
    if (sector && (r.sector_name ?? '') !== sector) return false;
    if (!assetTypes.includes(classifyAssetType(r))) return false;
    if (quickFilters.length) {
      const hit = quickLogic === 'or'
        ? quickFilters.some((f) => passes(r, f))
        : quickFilters.every((f) => passes(r, f));
      if (!hit) return false;
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

export default function MarketPage() {
  const { data, isLoading, isError, refetch, dataUpdatedAt, isFetching } = useMarketFeed();
  const rows = useMemo(() => data?.data ?? [], [data]);

  const query = useTapeStore((s) => s.query);
  const assetTypes = useTapeStore((s) => s.assetTypes);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  // کلیدِ اشتراک/اجتماع همان است که چیپ‌ها نشان می‌دهند و قیف هم می‌فرستد.
  const screenLogic = useScreenFilterStore((s) => s.logic);
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
  const resetFilters = useTapeStore((s) => s.resetFilters);
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

  // چند ردیف هر فیلتر رویشان اجرا نشده (مأموریت P0) — فقط در تولتیپِ چیپ می‌آید.
  const quickUnevaluated = useMemo(
    () =>
      countUnevaluated(
        filterBase as unknown as Parameters<typeof countUnevaluated>[0],
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
            screenLogic,
          ),
    [filterBase, query, assetTypes, quickFilters, sector, liveOnly, direction, volRatioOn, volRatioMin, exitAccum, tapeFilterConfig, screenLogic],
  );

  const signals = useMemo(() => rowsToTapeSignals(filtered), [filtered]);

  /**
   * جدولِ خالی باید بگوید *کدام در* ردیف‌ها را نگه داشته است. سنجشِ زنده:
   * «فقط بازار پایه» جدول را صفر می‌کرد و تنها راهنما «فیلترها را کم کن» بود؛
   * کاربر نمی‌فهمید نمادها پنهان‌اند یا واقعاً واجدِ شرط نیستند.
   */
  const emptyNote = useMemo(() => {
    if (filtered.length > 0) return null;
    const doors: string[] = [];
    if (quickFilters.length) {
      const names = quickFilters.map((f) => QUICK_LABELS[f as QuickFilter]).join('، ');
      doors.push(`${screenLogic === 'or' ? 'اجتماعِ' : 'اشتراکِ'} ${names}`);
    }
    if (sector) doors.push(`صنعتِ «${sector}»`);
    if (query.trim()) doors.push(`جستجوی «${query.trim()}»`);
    if (liveOnly) doors.push('فقط زنده');
    if (!showNumericSuffix) doors.push('پسوندِ عددی پنهان');
    if (assetTypes.length === 1) doors.push(`فقط بازارِ «${ASSET_LABELS[assetTypes[0]]}»`);
    const hidden = quickFilters.reduce(
      (s, f) => s + (hiddenInfo?.[f as QuickFilter]?.count ?? 0),
      0,
    );
    const head = doors.length ? doors.join(' · ') : 'بی‌فیلترِ سریع';
    return hidden > 0
      ? `${head} — ${toFaDigits(hidden)} ردیفِ واجدِ شرط درِ این نما باز نشد؛ درهایِ بالا را بردار`
      : `${head} — با این ترکیب هیچ ردیفی واجدِ شرط نیست`;
  }, [filtered.length, quickFilters, screenLogic, sector, query, liveOnly, showNumericSuffix, assetTypes, hiddenInfo]);

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
    <div className="flex h-full min-h-0 w-full max-w-none flex-col gap-2">
      {/* رأیِ مالک (۱۴۰۵-۰۷-۲۲): سه بلوکِ «وضعیت بازار»، «نبض» و «نمودارهای
          درون‌روز» تکرارِ تبِّ مستقلِ «وضعیت بازار»اند و ازِ این صفحه بیرون
          رفتند؛ تابلو فقط فیلتر + جدول + کشویِ نظارت می‌ماند. */}
      <MarketFilters
        sectors={sectors}
        matches={quickMatches}
        hiddenInfo={hiddenInfo}
        unevaluated={quickUnevaluated}
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
        emptyNote={emptyNote}
        onClearFilters={resetFilters}
      />
      <WatchDrawer rows={filtered} onSelect={setSymbol} onPickSector={setSector} />
    </div>
  );
}
