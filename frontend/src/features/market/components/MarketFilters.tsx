// features/market/components/MarketFilters.tsx -- نوار تک‌خطی فیلترها (h-11) + dropdown بازارها
// ۱۱ نوع دارایی TSETMC از چیپ‌های پراکنده به یک مالتی‌سلکت جمع شده‌اند؛ state استور دست‌نخورده.
// فیلتر سه‌گانه FTS (تابلو/تکنیکال/بنیادی) = سوییچ‌های مینیمال تک‌کلیکه روی ترتیب غربالگری.
// منوی بازارها با createPortal روی body و z-[9999] رندر می‌شود تا زیر جدول نیفتد.
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fmt';
import { ASSET_LABELS, ASSET_TYPES } from '../lib/assetType';
import {
  ASSET_PRESET_LABELS,
  ASSET_QUICK_PRESETS,
  DIRECTIONS,
  DIRECTION_LABELS,
  EXIT_ACCUM_HINT,
  EXIT_ACCUM_LABEL,
  QUICK_FILTERS,
  QUICK_LABELS,
  SCREEN_ORDER_LABELS,
  VOL_RATIO_MAX,
  VOL_RATIO_MIN,
  isDefaultAssetTypes,
  sameAssetSets,
  useTapeStore,
  type AssetQuickPreset,
  type QuickFilter,
  type ScreenOrder,
} from '../stores/tapeStore';
import {
  evaluateDynamicQuickFilter,
  isConfigCustomized,
  type TapeFilterConfig,
} from '../lib/tapeAlgorithms';
import { TapeFilterSettingsModal } from './TapeFilterSettingsModal';

function Chip({
  active,
  onClick,
  count,
  children,
  title,
}: {
  active: boolean;
  onClick: () => void;
  count?: number;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold transition-colors ${
        active
          ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
          : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
      }`}
    >
      {children}
      {count != null && count > 0 ? <span className="num ms-1 opacity-80">({toFaDigits(count)})</span> : null}
    </button>
  );
}

const CONTROL_CLS =
  'shrink-0 rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-xs text-text-primary';

/** مالتی‌سلکت «بازارها / ابزارها» -- ۱۱ گزینه TSETMC با پیش‌فرض پنج فعال */
function AssetFilterMenu() {
  const assetTypes = useTapeStore((s) => s.assetTypes);
  const toggleAssetType = useTapeStore((s) => s.toggleAssetType);
  const toggleAssetPreset = useTapeStore((s) => s.toggleAssetPreset);
  const setAllAssetTypes = useTapeStore((s) => s.setAllAssetTypes);
  const resetAssetTypes = useTapeStore((s) => s.resetAssetTypes);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onScrollOrResize = () => setOpen(false);
    document.addEventListener('mousedown', onDown);
    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
    };
  }, [open]);

  const menu = open
    ? (() => {
        const rect = ref.current?.getBoundingClientRect();
        const style = rect
          ? { position: 'fixed' as const, top: rect.bottom + 4, insetInlineStart: Math.max(8, window.innerWidth - rect.right), zIndex: 9999 }
          : { position: 'fixed' as const, top: 0, insetInlineStart: 0, zIndex: 9999 };
        return createPortal(
          <div
            ref={menuRef}
            style={style}
            data-testid="asset-filter-menu"
            aria-label="بازارها / ابزارها"
            className="w-72 rounded-xl border border-border-c bg-bg-primary p-2 shadow-2xl"
          >
            <div className="flex flex-col">
              {ASSET_TYPES.map((t) => (
                <label
                  key={t}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-xs text-text-primary hover:bg-bg-card"
                >
                  <input
                    type="checkbox"
                    checked={assetTypes.includes(t)}
                    onChange={() => toggleAssetType(t)}
                    aria-label={ASSET_LABELS[t]}
                    className="size-3.5 accent-[var(--accent-blue)]"
                  />
                  {ASSET_LABELS[t]}
                </label>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-1 border-t border-border-c/60 pt-2">
              {(Object.keys(ASSET_QUICK_PRESETS) as AssetQuickPreset[]).map((p) => (
                <Chip
                  key={p}
                  active={sameAssetSets(assetTypes, ASSET_QUICK_PRESETS[p])}
                  onClick={() => toggleAssetPreset(p)}
                  title="کلیک دوباره به پیش‌فرض پنج‌تایی برمی‌گرداند"
                >
                  {ASSET_PRESET_LABELS[p]}
                </Chip>
              ))}
              <Chip active={assetTypes.length === ASSET_TYPES.length} onClick={setAllAssetTypes} title="فعال کردن همهٔ ۱۱ نوع دارایی">
                همه
              </Chip>
              <Chip active={isDefaultAssetTypes(assetTypes)} onClick={resetAssetTypes}>
                پیش‌فرض
              </Chip>
            </div>
          </div>,
          document.body,
        );
      })()
    : null;

  return (
    <div ref={ref} className="shrink-0" data-testid="asset-filter">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        title={isDefaultAssetTypes(assetTypes) ? 'پنج بازار پیش‌فرض فعال است' : undefined}
        className={`${CONTROL_CLS} flex items-center gap-1.5 ${
          isDefaultAssetTypes(assetTypes) ? '' : 'border-border-accent text-accent-blue'
        }`}
      >
        بازارها / ابزارها
        <span className="num rounded-full bg-accent-blue/15 px-1.5 font-bold text-accent-blue">
          {toFaDigits(assetTypes.length)}
        </span>
        <span className={`transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {menu}
    </div>
  );
}

/** سوییچ‌های مینیمال تک‌کلیکه FTS -- ترتیب غربالگری سه‌ایجنتی */
function FtsTriToggle() {
  const screenOrder = useTapeStore((s) => s.screenOrder);
  const setScreenOrder = useTapeStore((s) => s.setScreenOrder);
  const tris: { key: ScreenOrder; label: string }[] = [
    { key: 'tape_first', label: 'تابلو' },
    { key: 'technical_first', label: 'تکنیکال' },
    { key: 'fundamental_first', label: 'بنیادی' },
  ];
  return (
    <div
      role="group"
      aria-label="ترتیب غربالگری FTS"
      title="اولویت عبور نمادها از ایجنت‌های تابلو، تکنیکال و بنیادی"
      className="flex shrink-0 overflow-hidden rounded-lg border border-border-c"
    >
      {tris.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          aria-pressed={screenOrder === key}
          title={SCREEN_ORDER_LABELS[key]}
          onClick={() => setScreenOrder(key)}
          className={`px-2 py-1 text-2xs font-semibold transition-colors ${
            screenOrder === key ? 'bg-accent-blue/20 text-accent-blue' : 'bg-bg-card text-text-secondary hover:text-accent-blue'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** تعداد ردیف هایی که هر فیلتر سریع را فعال می کنند -- برای نمایش کنار چیپ */
export function countQuickMatches(
  rows: MarketRowsLike,
  config?: TapeFilterConfig,
): Record<QuickFilter, number> {
  const out: Record<QuickFilter, number> = {
    f_clock: 0,
    f_susp: 0,
    f_jet: 0,
    f_roobi: 0,
    f_noqteh: 0,
    f_smart_flow: 0,
  };
  for (const r of rows) {
    for (const f of QUICK_FILTERS) {
      if (config) {
        if (evaluateDynamicQuickFilter(r as unknown as Parameters<typeof evaluateDynamicQuickFilter>[0], f, config)) {
          out[f] += 1;
        }
      } else {
        if (r[f]) out[f] += 1;
      }
    }
  }
  return out;
}

type MarketRowsLike = { [K in QuickFilter]?: boolean | null }[];

function AdvancedFiltersMenu({
  matches,
  exitAccumCount,
  volRatioCount,
  onOpenSettings,
}: {
  matches?: Record<QuickFilter, number>;
  exitAccumCount?: number;
  volRatioCount?: number;
  onOpenSettings?: () => void;
}) {
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const toggleQuickFilter = useTapeStore((s) => s.toggleQuickFilter);
  const volRatioOn = useTapeStore((s) => s.volRatioOn);
  const setVolRatioOn = useTapeStore((s) => s.setVolRatioOn);
  const volRatioMin = useTapeStore((s) => s.volRatioMin);
  const setVolRatioMin = useTapeStore((s) => s.setVolRatioMin);
  const exitAccum = useTapeStore((s) => s.exitAccum);
  const toggleExitAccum = useTapeStore((s) => s.toggleExitAccum);
  const liveOnly = useTapeStore((s) => s.liveOnly);
  const setLiveOnly = useTapeStore((s) => s.setLiveOnly);
  const filterConfig = useTapeStore((s) => s.tapeFilterConfig);
  const isCustom = isConfigCustomized(filterConfig);

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onScrollOrResize = () => setOpen(false);
    document.addEventListener('mousedown', onDown);
    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
    };
  }, [open]);

  const activeFilters = quickFilters.length + (exitAccum ? 1 : 0) + (volRatioOn ? 1 : 0) + (liveOnly ? 1 : 0);

  const menu = open
    ? (() => {
        const rect = ref.current?.getBoundingClientRect();
        const style = rect
          ? { position: 'fixed' as const, top: rect.bottom + 4, insetInlineStart: Math.max(8, window.innerWidth - rect.right), zIndex: 9999 }
          : { position: 'fixed' as const, top: 0, insetInlineStart: 0, zIndex: 9999 };
        return createPortal(
          <div
            ref={menuRef}
            style={style}
            data-testid="advanced-filter-menu"
            className="w-80 rounded-xl border border-border-c bg-bg-primary p-3 shadow-2xl space-y-4"
          >
            <div>
              <div className="text-xs font-bold mb-2">الگوهای تابلوخوانی</div>
              <div className="flex flex-wrap gap-1.5">
                {QUICK_FILTERS.map((f) => (
                  <Chip key={f} active={quickFilters.includes(f)} onClick={() => toggleQuickFilter(f)} count={matches?.[f]}>
                    {QUICK_LABELS[f]}
                  </Chip>
                ))}
                <Chip active={exitAccum} onClick={toggleExitAccum} count={exitAccumCount} title={EXIT_ACCUM_HINT}>
                  {EXIT_ACCUM_LABEL}
                </Chip>
              </div>
            </div>
            
            <div className="border-t border-border-c/60 pt-3">
              <label className="flex items-center gap-1.5 text-xs font-bold mb-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={volRatioOn}
                  onChange={(e) => setVolRatioOn(e.target.checked)}
                  className="size-3.5 accent-[var(--accent-blue)]"
                />
                ضریب حجم مشکوک
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  aria-label="آستانهٔ ضریب حجم"
                  min={VOL_RATIO_MIN}
                  max={VOL_RATIO_MAX}
                  step={0.5}
                  value={volRatioMin}
                  disabled={!volRatioOn}
                  onChange={(e) => setVolRatioMin(Number(e.target.value))}
                  className="flex-1 accent-[var(--accent-blue)] disabled:opacity-40"
                />
                <span aria-label="مقدار آستانهٔ ضریب حجم" className="num text-xs font-bold">
                  ≥{toFaDigits(volRatioMin.toFixed(1))}×
                </span>
                {volRatioOn && volRatioCount != null ? (
                  <span className="num text-2xs text-text-secondary">({toFaDigits(volRatioCount)})</span>
                ) : null}
              </div>
            </div>

            <div className="border-t border-border-c/60 pt-3">
              <label className="flex items-center gap-1.5 text-xs font-bold cursor-pointer text-text-secondary">
                <input
                  type="checkbox"
                  checked={liveOnly}
                  onChange={(e) => setLiveOnly(e.target.checked)}
                  className="size-3.5 accent-[var(--accent-blue)]"
                />
                فقط نمایش نمادهای دارای معامله امروز (زنده)
              </label>
            </div>

            <div className="border-t border-border-c/60 pt-3">
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onOpenSettings?.();
                }}
                className="flex w-full items-center justify-between rounded-lg border border-accent-blue/40 bg-accent-blue/10 px-3 py-2 text-xs font-bold text-accent-blue hover:bg-accent-blue/20 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <span>⚙️</span>
                  <span>شخصی‌سازی الگوریتم‌ها و تایم‌فریم‌ها</span>
                </span>
                {isCustom ? (
                  <span className="rounded-full bg-accent-blue px-1.5 py-0.5 text-3xs text-white">سفارشی</span>
                ) : null}
              </button>
            </div>
          </div>,
          document.body,
        );
      })()
    : null;

  return (
    <div ref={ref} className="shrink-0" data-testid="advanced-filters">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`${CONTROL_CLS} flex items-center gap-1.5 ${
          activeFilters > 0 ? 'border-border-accent text-accent-blue' : ''
        }`}
      >
        فیلترهای پیشرفته
        {activeFilters > 0 ? (
          <span className="num rounded-full bg-accent-blue/15 px-1.5 font-bold text-accent-blue">
            {toFaDigits(activeFilters)}
          </span>
        ) : null}
        <span className={`transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {menu}
    </div>
  );
}

export function MarketFilters({
  sectors,
  matches,
  exitAccumCount,
  volRatioCount,
}: {
  sectors: string[];
  /** شمارش عبور از هر فیلتر سریع روی ردیف های زنده */
  matches?: Record<QuickFilter, number>;
  /** شمارش ردیف‌های «خروج از انباشت» (ساعت + حجم مشکوک) */
  exitAccumCount?: number;
  /** شمارش عبور از فیلتر ضریب حجم روی ردیف‌های زنده */
  volRatioCount?: number;
}) {
  const query = useTapeStore((s) => s.query);
  const setQuery = useTapeStore((s) => s.setQuery);
  const assetTypes = useTapeStore((s) => s.assetTypes);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const sector = useTapeStore((s) => s.sector);
  const setSector = useTapeStore((s) => s.setSector);
  const liveOnly = useTapeStore((s) => s.liveOnly);
  const direction = useTapeStore((s) => s.direction);
  const setDirection = useTapeStore((s) => s.setDirection);
  const volRatioOn = useTapeStore((s) => s.volRatioOn);
  const exitAccum = useTapeStore((s) => s.exitAccum);
  const resetFilters = useTapeStore((s) => s.resetFilters);
  const filterConfig = useTapeStore((s) => s.tapeFilterConfig);
  const isCustom = isConfigCustomized(filterConfig);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [draft, setDraft] = useState(query);
  useEffect(() => setDraft(query), [query]);
  useEffect(() => {
    const t = setTimeout(() => {
      if (draft !== query) setQuery(draft);
    }, 220);
    return () => clearTimeout(t);
  }, [draft, query, setQuery]);

  const assetTypesDirty = !isDefaultAssetTypes(assetTypes);

  const activeCount =
    (query ? 1 : 0) +
    (sector ? 1 : 0) +
    (assetTypesDirty ? 1 : 0) +
    quickFilters.length +
    (liveOnly ? 1 : 0) +
    (direction !== 'all' ? 1 : 0) +
    (volRatioOn ? 1 : 0) +
    (exitAccum ? 1 : 0);

  return (
    <div
      data-testid="market-filters-bar"
      className="glass-panel panel-in flex h-11 w-full max-w-none items-center gap-2 overflow-x-auto px-2"
    >
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="جستجوی نماد یا نام..."
        aria-label="جستجوی نماد"
        className={`${CONTROL_CLS} w-40 shrink-0 placeholder:text-text-muted`}
      />

      <AssetFilterMenu />
      <FtsTriToggle />

      <select
        value={direction}
        onChange={(e) => setDirection(e.target.value as typeof direction)}
        className={CONTROL_CLS}
        aria-label="جهت تغییر قیمت"
      >
        {DIRECTIONS.map((d) => (
          <option key={d} value={d}>
            {DIRECTION_LABELS[d]}
          </option>
        ))}
      </select>

      <select
        value={sector}
        onChange={(e) => setSector(e.target.value)}
        className={`${CONTROL_CLS} max-w-36 truncate`}
        aria-label="فیلتر صنعت"
      >
        <option value="">همه صنایع</option>
        {sectors.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      <AdvancedFiltersMenu
        matches={matches}
        exitAccumCount={exitAccumCount}
        volRatioCount={volRatioCount}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <button
        type="button"
        onClick={() => setSettingsOpen(true)}
        title="شخصی‌سازی تایم‌فریم و آستانه‌های فیلترهای تابلو"
        className={`${CONTROL_CLS} flex items-center gap-1 hover:border-accent-blue/60 ${
          isCustom ? 'border-accent-blue bg-accent-blue/10 text-accent-blue font-bold' : 'text-text-secondary'
        }`}
      >
        <span>⚙️</span>
        <span className="hidden xl:inline">تنظیمات فیلترها</span>
        {isCustom ? <span className="size-1.5 rounded-full bg-accent-blue" /> : null}
      </button>

      <TapeFilterSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {activeCount > 0 ? (
        <button
          type="button"
          onClick={resetFilters}
          className="shrink-0 rounded-full border border-border-c px-2 py-0.5 text-xs text-text-secondary hover:border-accent-red/50 hover:text-accent-red"
        >
          پاک کردن <span className="num">{toFaDigits(activeCount)}</span> فیلتر
        </button>
      ) : null}
    </div>
  );
}
