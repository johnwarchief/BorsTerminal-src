// features/market/components/MarketFilters.tsx -- نوار کنترل و فیلترهای یکپارچه بالای جدول تابلو
// شامل ردیف اول: جستجوی نماد، شمارنده نمادها، انتخاب بازه به‌روزرسانی و پاک‌کردن فیلترها
// ردیف دوم: بازارها/ابزارها، صنایع و چیپ‌های فیلتر با پاپ‌اور تنظیمات اختصاصی (Split Chips)
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fmt';
import { fmtAge } from '@shared/lib/time';
import { SearchIcon } from '@shared/components/Icons';
import { ASSET_LABELS, ASSET_TYPES, classifyAssetType, type AssetType } from '../lib/assetType';
import { isNumericSuffixSymbol } from '../lib/tapeFts';
import { matchFa } from '@shared/lib/normalizeFa';
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
  tapeFilterVerdict,
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

/** دو فیلترِ فایل‌محور هیچ آستانۀ تنظیم‌شدنی ندارند — داوری‌شان عینِ پرچمِ
 *  بک‌اند است؛ چرخ‌دندۀ بی‌محتوا دکمۀِ جعلیست و نمایش داده نمی‌شود. */
const BACKEND_ONLY_FILTERS: readonly QuickFilter[] = ['f_smart', 'f_legal'];

function SplitFilterChip({
  filter,
  active,
  onToggle,
  count,
  hidden,
}: {
  filter: QuickFilter;
  active: boolean;
  onToggle: () => void;
  count?: number;
  /** چند ردیفِ واجدِ شرط درِ نمایِ فعلی را باز نکردند، و کدام در هر کدام را */
  hidden?: HiddenInfo;
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

  // هر ردیفِ پنهان یک در دارد، پس جمعِ درها = +N؛ درِ بی‌سهم نام برده نمی‌شود.
  const doorLabel = hidden && hidden.count > 0 ? hiddenDoorsLabel(hidden.doors) : '';
  const doorHint = hidden && hidden.count > 0 ? hiddenDoorHint(hidden.doors) : '';
  const chipTitle =
    !hidden || hidden.count === 0
      ? QUICK_LABELS[filter]
      : `${QUICK_LABELS[filter]} — ${toFaDigits(hidden.count)} ردیفِ واجدِ شرط در تابلویِ فعلی دیده نمی‌شوند`
        + (doorLabel ? ` (${doorLabel})` : '')
        + doorHint;

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
        title={chipTitle}
        className="flex items-center ps-2.5 pe-1 py-0.5 focus:outline-none"
      >
        <span>{QUICK_LABELS[filter]}</span>
        {count != null && count > 0 ? (
          <span className="num ms-1 font-black opacity-95">({toFaDigits(count)})</span>
        ) : null}
        {/* +N = ردیف‌هایِ واجدِ شرطی که درِ این نمایِ تابلو نیستند. بی‌این، عددِ
            چیپ کوچک‌ترِ عددِ خودِ سایت به‌نظر می‌رسید و فقط با hover روشن می‌شد. */}
        {hidden != null && hidden.count > 0 ? (
          <span className="num ms-1 text-2xs font-bold text-text-muted opacity-80">
            +{toFaDigits(hidden.count)}
          </span>
        ) : null}
      </button>

      {!BACKEND_ONLY_FILTERS.includes(filter) && (
        <>
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
        </>
      )}
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
    f_smart: 0,
    f_legal: 0,
  };
  for (const r of rows) {
    for (const f of QUICK_FILTERS) {
      if (config) {
        if (tapeFilterVerdict(r as unknown as Parameters<typeof tapeFilterVerdict>[0], f, config)) {
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

/** ردیفِ خاموش‌شده: همان ردیفِ جدول، با فیلدهایی که درها می‌خوانند */
type HiddenRow = MarketRowsLike[number] & {
  symbol?: string | null;
  name?: string | null;
  sector_name?: string | null;
  board?: number | string | null;
  is_live?: boolean | null;
};

/**
 * درهایی که یک ردیف را بیرونِ نمایِ فعلیِ تابلو نگه می‌دارند.
 *
 * رتبه از درِ سخت شروع می‌شود چون تولتیپ وعده‌ای است که کاربر می‌تواند اجرا کند:
 * سنجشِ ۱۴۰۵-۰۷-۰۷ رویِ ۵۳۶۰ ردیف نشان داد هر ۷۱ ردیفِ پنهان هم پسوندِ عددی داشت
 * و هم بازارشان خاموش بود. اگر «بازار/ابزار» اول می‌آمد، چیپ وعدهٔ روشن‌کردنِ
 * منوی اختیار را می‌داد در حالی که قاعدۀ حذفِ مشتقه همان ردیف را نگه می‌داشت.
 * هر ردیف یک در می‌گیرد، پس جمعِ درها = شمارِ پنهانِ همان چیپ.
 */
export const HIDDEN_DOORS = [
  'پسوندِ عددی',
  'بازار/ابزارِ خاموش',
  'نمادِ خاموش',
  'صنعت',
  'جستجو',
] as const;
export type HiddenDoor = (typeof HIDDEN_DOORS)[number];

export type HiddenCtx = {
  assetTypes: AssetType[];
  liveOnly: boolean;
  query: string;
  sector: string;
  /** سوییچِ «حذفِ پسوندِ عددی» دستِ کاربر؛ روشن ⇒ این در ردیف می‌گیرد */
  dropSuffix: boolean;
};

export type HiddenInfo = { count: number; doors: Partial<Record<HiddenDoor, number>> };

export function hiddenDoorOf(r: HiddenRow, ctx: HiddenCtx): HiddenDoor | null {
  const q = ctx.query.trim();
  // وقتی کاربر خودِ همین در را باز گذاشته، ردیفی از این در نمی‌گذرد؛ وگرنه
  // توضیح چیزی را می‌گوید که کاربر خودش لغو کرده است.
  if (ctx.dropSuffix && isNumericSuffixSymbol(r.symbol)) return 'پسوندِ عددی';
  if (!ctx.assetTypes.includes(classifyAssetType(r))) return 'بازار/ابزارِ خاموش';
  // مثلِ خودِ درِ «فقط زنده»: با جستجویِ صریح جدول نمادِ خاموش را هم نشان می‌دهد (#197)
  if (ctx.liveOnly && !q && r.is_live === false) return 'نمادِ خاموش';
  if (ctx.sector && (r.sector_name ?? '') !== ctx.sector) return 'صنعت';
  if (q && !(matchFa(r.symbol, q) || matchFa(r.name, q))) return 'جستجو';
  return null;
}

/** شمارِ ردیف‌هایِ واجدِ شرطِ بیرونِ نما، به تفکیکِ دری که هر ردیف را نگه داشته */
export function countHiddenMatches(
  hidden: HiddenRow[],
  ctx: HiddenCtx,
  config?: TapeFilterConfig,
): Record<QuickFilter, HiddenInfo> {
  const out = {} as Record<QuickFilter, HiddenInfo>;
  for (const f of QUICK_FILTERS) out[f] = { count: 0, doors: {} };
  for (const r of hidden) {
    const door = hiddenDoorOf(r, ctx);
    for (const f of QUICK_FILTERS) {
      const hit = config
        ? tapeFilterVerdict(r as unknown as Parameters<typeof tapeFilterVerdict>[0], f, config)
        : Boolean(r[f]);
      if (!hit) continue;
      const info = out[f];
      info.count += 1;
      if (door) info.doors[door] = (info.doors[door] ?? 0) + 1;
    }
  }
  return out;
}

/** «پسوندِ عددی ۷۱، بازار/ابزارِ خاموش ۳» — به همان رتبهٔ HIDDEN_DOORS */
function hiddenDoorsLabel(doors: HiddenInfo['doors']): string {
  return HIDDEN_DOORS.filter((d) => (doors[d] ?? 0) > 0)
    .map((d) => `${d} ${toFaDigits(doors[d] as number)}`)
    .join('، ');
}

/**
 * سه درِ اول را کاربر می‌تواند خودش باز کند؛ «صنعت» و «جستجو» رأیِ خودِ کاربر
 * است و چیزی برای بازکردن ندارد. پس نامِ کلید فقط برای همین سه نوشته می‌شود —
 * عددی که راهِ حل ندارد وعده است، و مالک دقیقاً از همین شکایت کرد.
 */
const HIDDEN_DOOR_CONTROLS: Partial<Record<HiddenDoor, string>> = {
  'پسوندِ عددی': 'حذفِ پسوندِ عددی',
  'بازار/ابزارِ خاموش': 'بازارها / ابزارها',
  'نمادِ خاموش': 'فقط زنده',
};

function hiddenDoorHint(doors: HiddenInfo['doors']): string {
  const names = HIDDEN_DOORS.filter((d) => (doors[d] ?? 0) > 0 && HIDDEN_DOOR_CONTROLS[d]).map(
    (d) => HIDDEN_DOOR_CONTROLS[d] as string,
  );
  return names.length === 0 ? '' : ` — با «${names.join('» و «')}» در همین نوار باز می‌شوند`;
}

export function MarketFilters({
  sectors,
  matches,
  hiddenInfo,
  shown,
  total,
  pollMs,
  onPollChange,
  dataUpdatedAt,
  isFetching,
  isLoading,
  isError,
  onRetry,
}: {
  sectors: string[];
  matches?: Record<QuickFilter, number>;
  /** ردیف‌هایِ واجدِ شرطی که درِ نمایِ فعلی را باز نکردند، با تفکیکِ هر در —
   *  توضیحِ «چرا چیپ کمتر از فیلترنویسِ TSETMC است» */
  hiddenInfo?: Record<QuickFilter, HiddenInfo>;
  shown?: number;
  total?: number;
  pollMs?: number;
  onPollChange?: (ms: number) => void;
  dataUpdatedAt?: number;
  isFetching?: boolean;
  /** سلامتِ فید: کاربر باید بداند تابلو نرسیده، نه اینکه فیلتر غلط باشد */
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
}) {
  const query = useTapeStore((s) => s.query);
  const setQuery = useTapeStore((s) => s.setQuery);
  const assetTypes = useTapeStore((s) => s.assetTypes);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const toggleQuickFilter = useTapeStore((s) => s.toggleQuickFilter);
  const sector = useTapeStore((s) => s.sector);
  const setSector = useTapeStore((s) => s.setSector);
  const liveOnly = useTapeStore((s) => s.liveOnly);
  const setLiveOnly = useTapeStore((s) => s.setLiveOnly);
  const showNumericSuffix = useTapeStore((s) => s.showNumericSuffix);
  const setShowNumericSuffix = useTapeStore((s) => s.setShowNumericSuffix);
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

  // «پاک کردن» به پیش‌فرض برمی‌گرداند، پس فقط انحراف از پیش‌فرض شمرده می‌شود.
  // #197: پیش‌فرضِ liveOnly روشن است، بنابراین خاموش‌کردنش انحراف حساب
  // می‌شود — وگرنه دکمۀِ «پاک کردن (۱)» همیشه روی نوار می‌ماند.
  const activeCount =
    (query ? 1 : 0) +
    (sector ? 1 : 0) +
    (assetTypesDirty ? 1 : 0) +
    quickFilters.length +
    (!liveOnly ? 1 : 0) +
    (showNumericSuffix ? 1 : 0) +
    (volRatioOn ? 1 : 0);

  return (
    <div
      data-testid="market-filters-bar"
      className="glass-panel panel-in flex flex-wrap items-center gap-2 w-full rounded-2xl p-2 shadow-sm"
    >
      {/* #171: یک نوار به‌جای دو سطحِ روی‌هم — صنایع و چیپ‌ها سمتِ راست،
          جستجو/شمارندۀ نماد/بازۀ بروزرسانی سمتِ چپِ همان نوار. */}
      {/* نوارِ کنترل: زیر 2xl سطرِ خودش را می‌گیرد تا هیچ چیپی پشتِ لبه نرود؛
          پیش از این در صفحۀ باریک پنج‌صد‌و‌هفتاد‌وپنج پیکسل از کنترل‌ها بیرونِ
          کادر می‌ماند و no-scrollbar اسکرول را نامرئی می‌کرد. */}
      <div
        className="flex min-w-0 flex-1 flex-wrap items-center gap-2 no-scrollbar"
        data-testid="quick-filters-bar"
      >
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
            hidden={hiddenInfo?.[f]}
          />
        ))}

      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2" data-testid="filters-side">
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

          {/* #197: تا پیش از این «فقط زنده» در استور وجود داشت ولی هیچ‌جا
              روشن/خاموش نمی‌شد — و چون چیدمانِ پیش‌فرض ردیف‌هایِ بیرونِ تابلو
              را بالا می‌آورد، کاربر فلش را «خراب» می‌دید. */}
          <button
            type="button"
            onClick={() => setLiveOnly(!liveOnly)}
            aria-pressed={liveOnly}
            data-testid="live-only-toggle"
            title={
              liveOnly
                ? 'روشن: فقط نمادهای همین نشستِ تابلو. برای دیدن نمادهای خاموش/قدیمی خاموشش کنید.'
                : 'خاموش: نمادهای بیرونِ تابلو هم در جدول می‌مانند (اعدادشان تکان نمی‌خورد).'
            }
            className={`shrink-0 rounded-lg border px-2 py-1 text-2xs font-bold transition-all ${
              liveOnly
                ? 'border-accent-blue/50 bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-muted hover:text-text-primary'
            }`}
          >
            فقط زنده
          </button>

          {/* درِ «پسوندِ عددی» تا پیش از این بی‌قیدِ شرط بسته بود: کاربر درِ تولتیپ
              می‌خواند «۷۱ ردیف … (پسوندِ عددی ۷۱)» و هیچ کلیدی برای بازکردنش نبود.
              جهتِ سوییچ مثل «فقط زنده» است: روشن = قاعده در کار است. */}
          <button
            type="button"
            onClick={() => setShowNumericSuffix(!showNumericSuffix)}
            aria-pressed={!showNumericSuffix}
            data-testid="numeric-suffix-toggle"
            title={
              showNumericSuffix
                ? 'روشن: ردیف‌هایِ نمادِ پسونددار (فولاد۱، وخار۲ …) در جدول می‌مانند؛ این‌ها بیشترِ ردیف‌هایِ نشست‌هایِ قدیمی‌اند و تازگیِ تابلو را مخدوش می‌کنند.'
                : 'خاموش: ردیف‌هایِ نمادِ پسونددار از نما کنار گذاشته می‌شوند (پیش‌فرضِ تابلو). روشنش کنید تا همان ردیف‌ها در جدول بمانند؛ شمارِ +Nِ چیپ‌ها به همان اندازه کم می‌شود.'
            }
            className={`shrink-0 rounded-lg border px-2 py-1 text-2xs font-bold transition-all ${
              !showNumericSuffix
                ? 'border-accent-blue/50 bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-muted hover:text-text-primary'
            }`}
          >
            حذفِ پسوندِ عددی
          </button>

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

          {isError ? (
            <button
              type="button"
              onClick={onRetry}
              data-testid="filters-retry"
              title="فیدِ تابلو برنگشت — کلیک برای تلاشِ دوباره"
              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-accent-red/50 bg-accent-red/10 px-2 py-1 text-2xs font-bold text-accent-red transition-all hover:bg-accent-red/20"
            >
              ⚠ خطایِ فید — تلاشِ دوباره
            </button>
          ) : isLoading ? (
            <span
              data-testid="filters-loading"
              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border-c bg-bg-card px-2 py-1 text-2xs font-bold text-text-secondary"
            >
              در حالِ خواندنِ تابلو…
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
              data-testid="filters-reset"
              className="shrink-0 rounded-lg border border-accent-red/40 bg-accent-red/10 px-2 py-0.5 text-2xs font-bold text-accent-red hover:bg-accent-red/20 transition-all"
            >
              پاک کردن ({toFaDigits(activeCount)})
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
