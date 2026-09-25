// features/market/components/MarketFilters.tsx -- نوار کنترل و فیلترهای یکپارچه بالای جدول تابلو
// شامل ردیف اول: جستجوی نماد، شمارنده نمادها، انتخاب بازه به‌روزرسانی و پاک‌کردن فیلترها
// ردیف دوم: بازارها/ابزارها، صنایع و چیپ‌های فیلتر با پاپ‌اور تنظیمات اختصاصی (Split Chips)
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fmt';
import { fmtAge } from '@shared/lib/time';
import { SearchIcon } from '@shared/components/Icons';
import { ASSET_LABELS, ASSET_TYPES } from '../lib/assetType';
import {
  ASSET_PRESET_LABELS,
  ASSET_QUICK_PRESETS,
  QUICK_FILTERS,
  QUICK_LABELS,
  isDefaultAssetTypes,
  sameAssetSets,
  useTapeStore,
  type AssetQuickPreset,
  type QuickFilter,
} from '../stores/tapeStore';
import {
  evaluateDynamicQuickFilter,
  type TapeFilterConfig,
} from '../lib/tapeAlgorithms';
import { FilterConfigPopover } from './FilterConfigPopover';

const CONTROL_CLS =
  'shrink-0 rounded-lg border border-border-c bg-bg-primary px-2.5 py-1 text-xs text-text-primary transition-all';

const POLL_OPTIONS = [
  { ms: 5_000, label: '۵ ثانیه' },
  { ms: 15_000, label: '۱۵ ثانیه' },
  { ms: 60_000, label: '۱ دقیقه' },
  { ms: 300_000, label: '۵ دقیقه' },
];

/** چیپ ساده برای گزینه‌های داخل منوی بازارها */
function MenuChip({
  active,
  onClick,
  children,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={`shrink-0 rounded-full border px-2 py-0.5 text-2xs font-bold transition-all ${
        active
          ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-xs dark:bg-accent-blue/25'
          : 'border-border-c bg-bg-card text-text-primary/85 hover:border-accent-blue hover:text-accent-blue'
      }`}
    >
      {children}
    </button>
  );
}

/** چیپ ترکیبی (Split Chip): کلیک روی متن فیلتر را روشن/خاموش می‌کند و کلیک روی آیکون ⚙ پاپ‌اور تنظیمات همان فیلتر را باز می‌کند */
function SplitFilterChip({
  filter,
  active,
  onToggle,
  count,
}: {
  filter: QuickFilter;
  active: boolean;
  onToggle: () => void;
  count?: number;
}) {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const chipRef = useRef<HTMLDivElement>(null);
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null);

  const handleOpenConfig = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (chipRef.current) {
      setAnchorRect(chipRef.current.getBoundingClientRect());
    }
    setPopoverOpen((v) => !v);
  };

  return (
    <div
      ref={chipRef}
      className={`inline-flex shrink-0 items-center rounded-full border text-xs font-bold transition-all shadow-2xs select-none ${
        active
          ? 'border-accent-blue bg-accent-blue/15 text-accent-blue font-black dark:bg-accent-blue/25'
          : 'border-border-c bg-bg-card text-text-primary hover:border-accent-blue hover:text-accent-blue font-bold'
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-pressed={active}
        title={QUICK_LABELS[filter]}
        className="flex items-center ps-2.5 pe-1 py-0.5 focus:outline-none"
      >
        <span>{QUICK_LABELS[filter]}</span>
        {count != null && count > 0 ? (
          <span className="num ms-1 font-black opacity-95">({toFaDigits(count)})</span>
        ) : null}
      </button>

      <button
        type="button"
        onClick={handleOpenConfig}
        title={`تنظیم آستانه‌های ${QUICK_LABELS[filter]}`}
        aria-label={`تنظیمات ${QUICK_LABELS[filter]}`}
        className="flex items-center justify-center ps-1 pe-2 py-0.5 text-[11px] text-text-muted hover:text-accent-blue border-s border-border-c/60 focus:outline-none"
      >
        ⚙
      </button>

      <FilterConfigPopover
        filter={filter}
        open={popoverOpen}
        anchorRect={anchorRect}
        onClose={() => setPopoverOpen(false)}
      />
    </div>
  );
}

/** منوی بازشو «بازارها / ابزارها» TSETMC */
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
                <MenuChip
                  key={p}
                  active={sameAssetSets(assetTypes, ASSET_QUICK_PRESETS[p])}
                  onClick={() => toggleAssetPreset(p)}
                  title="کلیک دوباره به پیش‌فرض پنج‌تایی برمی‌گرداند"
                >
                  {ASSET_PRESET_LABELS[p]}
                </MenuChip>
              ))}
              <MenuChip active={assetTypes.length === ASSET_TYPES.length} onClick={setAllAssetTypes} title="فعال کردن همهٔ ۱۱ نوع دارایی">
                همه
              </MenuChip>
              <MenuChip active={isDefaultAssetTypes(assetTypes)} onClick={resetAssetTypes}>
                پیش‌فرض
              </MenuChip>
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
          isDefaultAssetTypes(assetTypes) ? '' : 'border-border-accent text-accent-blue font-bold'
        }`}
      >
        <span>بازارها / ابزارها</span>
        <span className="num rounded-full bg-accent-blue/15 px-1.5 font-bold text-accent-blue">
          {toFaDigits(assetTypes.length)}
        </span>
        <span className={`transition-transform text-3xs ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {menu}
    </div>
  );
}

/** تعداد ردیف‌هایی که هر فیلتر سریع را فعال می‌کنند */
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

export function MarketFilters({
  sectors,
  matches,
  shown,
  total,
  pollMs,
  onPollChange,
  dataUpdatedAt,
  isFetching,
}: {
  sectors: string[];
  matches?: Record<QuickFilter, number>;
  volRatioCount?: number;
  shown?: number;
  total?: number;
  pollMs?: number;
  onPollChange?: (ms: number) => void;
  dataUpdatedAt?: number;
  isFetching?: boolean;
}) {
  const query = useTapeStore((s) => s.query);
  const setQuery = useTapeStore((s) => s.setQuery);
  const assetTypes = useTapeStore((s) => s.assetTypes);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const toggleQuickFilter = useTapeStore((s) => s.toggleQuickFilter);
  const sector = useTapeStore((s) => s.sector);
  const setSector = useTapeStore((s) => s.setSector);
  const liveOnly = useTapeStore((s) => s.liveOnly);
  const volRatioOn = useTapeStore((s) => s.volRatioOn);
  const resetFilters = useTapeStore((s) => s.resetFilters);

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
    (volRatioOn ? 1 : 0);

  return (
    <div
      data-testid="market-filters-bar"
      className="glass-panel panel-in flex flex-col gap-1.5 w-full rounded-2xl p-2.5 shadow-sm"
    >
      {/* ── سطح اول: جستجوی نماد، شمارنده نمادها، بازه به‌روزرسانی و ریست ── */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-c/50 pb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex items-center">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="جستجوی نماد یا نام..."
              aria-label="جستجوی نماد"
              className={`${CONTROL_CLS} w-44 sm:w-56 ps-7 placeholder:text-text-muted`}
            />
            <SearchIcon size={13} className="absolute start-2 text-text-muted pointer-events-none" />
          </div>

          {shown != null && total != null ? (
            <span
              className="inline-flex items-center gap-1 rounded-lg border border-border-c bg-bg-card px-2.5 py-1 text-2xs font-bold text-text-primary"
              title="تعداد نمادهای فعال در جدول"
            >
              <span className="num text-accent-blue">{toFaDigits(shown)}</span>
              <span className="text-text-muted font-normal">از</span>
              <span className="num">{toFaDigits(total)}</span>
              <span>نماد</span>
            </span>
          ) : null}

          {dataUpdatedAt ? (
            <span className="hidden lg:inline text-3xs text-text-muted">
              (به‌روزرسانی: {fmtAge(dataUpdatedAt)})
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-2 ms-auto">
          {pollMs != null && onPollChange != null ? (
            <div className="flex items-center gap-1.5 text-2xs text-text-secondary">
              <span className="hidden sm:inline">بازه:</span>
              <select
                id="poll-ms"
                value={pollMs}
                onChange={(e) => onPollChange(Number(e.target.value))}
                className={`${CONTROL_CLS} py-0.5 text-2xs font-bold text-text-primary`}
                aria-label="بازه به‌روزرسانی"
              >
                {POLL_OPTIONS.map((o) => (
                  <option key={o.ms} value={o.ms}>
                    {o.label}
                  </option>
                ))}
              </select>
              {isFetching ? <span className="inline-block size-1.5 animate-ping rounded-full bg-accent-blue" /> : null}
            </div>
          ) : null}

          {activeCount > 0 ? (
            <button
              type="button"
              onClick={resetFilters}
              className="shrink-0 rounded-lg border border-accent-red/40 bg-accent-red/10 px-2 py-0.5 text-2xs font-bold text-accent-red hover:bg-accent-red/20 transition-all"
            >
              پاک کردن ({toFaDigits(activeCount)})
            </button>
          ) : null}
        </div>
      </div>

      {/* ── سطح دوم: بازارها/ابزارها، صنایع و فیلترهای پیشرفته با پاپ‌اور ── */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pt-0.5" data-testid="quick-filters-bar">
        <AssetFilterMenu />

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

        <div className="h-4 w-[1px] bg-border-c/70 shrink-0 mx-0.5" />

        {/* چیپ‌های فیلتر با پاپ‌اور اختصاصی */}
        {QUICK_FILTERS.map((f) => (
          <SplitFilterChip
            key={f}
            filter={f}
            active={quickFilters.includes(f)}
            onToggle={() => toggleQuickFilter(f)}
            count={matches?.[f]}
          />
        ))}
      </div>
    </div>
  );
}
