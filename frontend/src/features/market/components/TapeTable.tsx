// features/market/components/TapeTable.tsx -- جدول مجازی تابلو
// ردیف ها با React.memo و کلید نماد؛ فقط ردیف های دیدنی رندر می شوند.
import { memo, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { MarketRow } from '@shared/types/marketRow';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { EmptyState } from '@shared/components/EmptyState';
import { FlashNum } from '@shared/components/FlashNum';
import {
  GOLDEN_HOUR_HINT,
  GOLDEN_HOUR_LABEL,
  STRONG_CLOCK_HINT,
  STRONG_HOUR_LABEL,
  SWEEP_HINT,
  detectBoxExit,
  detectGoldenHour,
  detectStrongHour,
  detectSweep,
  lastCloseDiff,
} from '../lib/tapePatterns';
import { FTS_VOL_RATIO_HOT, buyPerCapitaMt, buySellShare, sellPerCapitaMt } from '../lib/tapeFts';
import { powerTone } from '../api/useMarketPulse';
import { LIMIT_PCT, useTapeStore } from '../stores/tapeStore';
import { evaluateDynamicQuickFilter } from '../lib/tapeAlgorithms';

type SortKey =
  | 'symbol'
  | 'p_closing'
  | 'p_last'
  | 'percent_change'
  | 'percent_last'
  | 'tvol'
  | 'z_tot_tran'
  | 'q_tot_cap'
  | 'vol_ratio'
  | 'buyer_power'
  | 'last_vs_close';

/**
 * يازده ستونِ تابلو (۱۱). عرض‌ها از روی سنجشِ واقعیِ «پهنای لازمِ محتوا» در فونتِ
 * 16pxِ همین جدول گذاشته شده‌اند، نه حدس:
 * [نماد 150] [آخرین 66] [پایانی 66] [تغییر٪ 62] [آخرین٪ 62] [حجم 130] [تعداد 64]
 * [ارزش 58] [حجم/ماه 58] [خرید/فروش 104 — نوارِ دوسُره + عددِ نسبت] [ساعت 200].
 * سه ستونِ «سرانۀ خرید / سرانۀ فروش / قدرتِ خریدار» در #146 به یک ستونِ دوسُره
 * جمع شد؛ دو ستون از عرضِ جدول آزاد شد تا اسکرولِ افقی زودتر نیفتد.
 */
const ROW_GRID =
  'grid-cols-[minmax(150px,1.6fr)_minmax(66px,0.85fr)_minmax(66px,0.85fr)_minmax(62px,0.8fr)_minmax(62px,0.8fr)_minmax(130px,1.05fr)_minmax(64px,0.85fr)_minmax(58px,0.8fr)_minmax(58px,0.78fr)_minmax(104px,1.15fr)_minmax(200px,1.5fr)]';

/** کمترینِ عرضِ جدول = جمعِ مینیمم‌ها + فاصله‌ها + padding (زیرِ این، جدول افقی اسکرول می‌خورد) */
const TABLE_MIN_W = 'min-w-[1104px]';

const HEADERS: { key: SortKey; label: string; hint?: string }[] = [
  // برچسبِ ستون «فیلتر» نیست و فقط خواندنِ سرستون را می‌سازد؛ پس کوتاه‌ترین
  // شکلِ ممکن نوشته می‌شود و نامِ کامل + واحد در title می‌ماند. رویِ
  // نمایشگرِ ۱۳۶ این تیترهای بلند در ستونِ ۶۲-۷۸ پیکسلی می‌شکستند و
  // سرستون افقی اسکرول می‌خورد.
  { key: 'symbol', label: 'نماد' },
  { key: 'p_last', label: 'آخرین' },
  { key: 'p_closing', label: 'پایانی', hint: 'قیمت پایانیِ همین نشست (p_closing)' },
  { key: 'percent_change', label: 'تغییر٪', hint: 'پایانی نسبت به دیروز — همان plp درِ فیلترها' },
  { key: 'percent_last', label: 'آخرین٪', hint: 'آخرین نسبت به دیروز؛ با درصدِ پایانی فرق دارد' },
  { key: 'tvol', label: 'حجم' },
  { key: 'z_tot_tran', label: 'تعداد', hint: 'تعدادِ معاملات (z_tot_tran) — tno درِ فیلترها' },
  { key: 'q_tot_cap', label: 'ارزش', hint: 'ارزش معاملات — میلیارد ریال (q_tot_cap)' },
  { key: 'vol_ratio', label: 'حجم/ماه', hint: 'نسبت حجمِ امروز به میانگینِ حجمِ ماه' },
  {
    key: 'buyer_power',
    label: 'خرید / فروش',
    hint:
      'سرانۀ خرید حقیقی در برابرِ سرانۀ فروش حقیقی (میلیون تومان) — سبز = خرید، قرمز = فروش؛ ' +
      'عددِ کنار نسبتِ خرید به فروش است (سرانۀ خرید ÷ سرانۀ فروش)',
  },
  { key: 'last_vs_close', label: 'ساعت', hint: 'الگوی ساعت — اختلاف آخرین و پایانی' },
];

/** ریال → میلیارد ریال (q_tot_cap درِ بانک ریال است؛ همان واحدِ تابلوی TSETMC) */
function toBillionRial(rials: number | null | undefined): number | null {
  return typeof rials === 'number' && Number.isFinite(rials) ? rials / 1e9 : null;
}

const NEG = Number.NEGATIVE_INFINITY;

function sortVal(r: MarketRow, key: SortKey): number | string {
  switch (key) {
    case 'symbol':
      return r.symbol ?? '';
    case 'p_last':
      return r.p_last ?? NEG;
    case 'p_closing':
      return r.p_closing ?? NEG;
    case 'percent_change':
      return r.percent_change ?? NEG;
    case 'percent_last':
      return r.percent_last ?? NEG;
    case 'tvol':
      return r.tvol ?? NEG;
    case 'z_tot_tran':
      return r.z_tot_tran ?? NEG;
    case 'q_tot_cap':
      return r.q_tot_cap ?? NEG;
    case 'vol_ratio':
      return r.vol_ratio ?? NEG;
    case 'buyer_power':
      return r.buyer_power ?? NEG;
    case 'last_vs_close':
      return lastCloseDiff(r) ?? NEG;
  }
}

/** رنگ ردیف از روی جهت و صف -- فقط رنگ متن، بدون بکس‌های درشت */
function pctTone(pct: number | null | undefined): string {
  if (pct == null) return 'text-text-muted';
  if (pct >= LIMIT_PCT) return 'text-accent-green font-bold';
  if (pct > 0) return 'text-accent-green';
  if (pct <= -LIMIT_PCT) return 'text-accent-red font-bold';
  if (pct < 0) return 'text-accent-red';
  return 'text-text-secondary';
}

const MICRO_TONES = {
  violet: 'bg-purple-100 text-purple-950 border border-purple-300 dark:bg-[#8b5cf6]/25 dark:text-[#ddd6fe] dark:border-[#8b5cf6]/40',
  amber: 'bg-amber-100 text-amber-950 border border-amber-300 dark:bg-accent-yellow/25 dark:text-[#fef08a] dark:border-accent-yellow/45',
  cyan: 'bg-sky-100 text-sky-950 border border-sky-300 dark:bg-neon-cyan/20 dark:text-[#a5f3fc] dark:border-neon-cyan/40',
  emerald: 'bg-emerald-100 text-emerald-950 border border-emerald-300 dark:bg-accent-green/20 dark:text-[#bbf7d0] dark:border-accent-green/40',
  green: 'bg-green-100 text-green-950 border border-green-300 dark:bg-accent-green/20 dark:text-[#bbf7d0] dark:border-accent-green/40',
  red: 'bg-red-100 text-red-950 border border-red-300 dark:bg-accent-red/20 dark:text-[#fecaca] dark:border-accent-red/40',
  gray: 'bg-slate-200 text-slate-900 border border-slate-300 dark:bg-bg-card/90 dark:text-text-primary dark:border-border-c',
} as const;

type MicroTone = keyof typeof MICRO_TONES;

/** رنگِ عددِ نسبت از همان آستانه‌های ۱.۵/۰.۸ِ نبض بازار — این‌جا داوری نمی‌شود */
function powerClass(tone: 'good' | 'mid' | 'bad' | null): string {
  if (tone === 'good') return 'text-accent-green font-bold';
  if (tone === 'bad') return 'text-accent-red font-bold';
  if (tone === 'mid') return 'text-accent-yellow';
  return 'text-text-secondary';
}

const mt = (v: number | null): string => (v == null ? '—' : `${toFaDigits(v.toFixed(1))} م.ت`);

/**
 * ستونِ یکیِ خرید/فروش (#146): نوارِ دوسُره سهمِ سرانۀ خرید (سبز، از راست) را از
 * سرانۀ فروش (قرمز) جدا می‌کند و عددِ نسبتِ خرید به فروش کنارش می‌ماند. دو عددِ
 * سرانه از بین نمی‌روند — در titleِ خودِ ستون‌اند.
 * یک طرف غایب ⇒ نوار رسم نمی‌شود: نبودِ داده «فروش صفر» یا «خرید صددرصد» نیست.
 */
function BuySellCell({ buyPc, sellPc, power }: { buyPc: number | null; sellPc: number | null; power: number | null | undefined }) {
  const share = buySellShare(buyPc, sellPc);
  return (
    <span
      data-testid="tape-buy-sell"
      className="flex min-w-0 items-center gap-1.5"
      title={`سرانۀ خرید ${mt(buyPc)} · سرانۀ فروش ${mt(sellPc)} — نسبتِ خرید به فروش ${
        power == null ? '—' : `${toFaDigits(power.toFixed(2))}×`
      }`}
    >
      <span dir="rtl" aria-hidden className="flex h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-bg-card/80">
        {share == null ? null : (
          <>
            <span className="bg-accent-green transition-[width] duration-300 ease-out" style={{ width: `${share * 100}%` }} />
            <span className="bg-accent-red transition-[width] duration-300 ease-out" style={{ width: `${(1 - share) * 100}%` }} />
          </>
        )}
      </span>
      <span className={`num shrink-0 text-2xs ${powerClass(powerTone(power))}`}>
        <FlashNum value={power} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(2)))} />
      </span>
    </span>
  );
}

/** میکرو-بج متنی های‌دنسیتی با کنتراست و خوانایی بالا؛ جزئیات عددی در title (Tooltip) هر بج */
function MicroBadge({ pattern, tone, title, children }: { pattern: string; tone: MicroTone; title: string; children: React.ReactNode }) {
  return (
    <span
      data-testid={`badge-${pattern}`}
      data-pattern={pattern}
      title={title}
      className={`shrink-0 inline-flex items-center justify-center rounded-md px-1 py-px text-3xs font-bold leading-none tracking-tight shadow-2xs whitespace-nowrap select-none ${MICRO_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

/** tooltip یکپارچهٔ ردیف: جزئیات عددی که از چشمِ بج‌ها برداشته شده */
export function rowTooltip(r: MarketRow): string {
  const bits: string[] = [];
  if (typeof r.vol_ratio === 'number' && Number.isFinite(r.vol_ratio)) {
    bits.push(`حجم ${toFaDigits(r.vol_ratio.toFixed(1))} برابر حجم ماهانه`);
  }
  const diff = lastCloseDiff(r);
  if (diff != null) bits.push(`اختلاف آخرین و پایانی ${fmtPct(diff * 100)}`);
  const active: string[] = [];
  if (detectStrongHour(r)) active.push(`ساعت قوی (${STRONG_CLOCK_HINT})`);
  else if (detectGoldenHour(r)) active.push('ساعت طلایی');
  else if (r.f_clock) active.push('الگوی ساعت');
  if (detectSweep(r)) active.push('کف‌روبی');
  if (detectBoxExit(r)) active.push('خروج از باکس');
  if (active.length) bits.push(`اعتبار الگو: ${active.join('، ')}`);
  return bits.join(' · ');
}

const TapeRow = memo(function TapeRow({
  row,
  selected,
  onSelect,
}: {
  row: MarketRow;
  selected: boolean;
  onSelect: (s: string) => void;
}) {
  const tapeFilterConfig = useTapeStore((s) => s.tapeFilterConfig);
  const diff = lastCloseDiff(row);
  const strongHour = detectStrongHour(row);
  const goldenHour = !strongHour && detectGoldenHour(row);
  const sweep = detectSweep(row);
  const pct = row.percent_change;
  const atLimitUp = pct != null && pct >= LIMIT_PCT;
  const atLimitDown = pct != null && pct <= -LIMIT_PCT;
  const tooltip = rowTooltip(row);
  const volHot = row.vol_ratio != null && row.vol_ratio > FTS_VOL_RATIO_HOT;
  const volMult = row.vol_ratio != null ? `${toFaDigits(row.vol_ratio.toFixed(1))}× میانگین ماه` : '—';
  const buyPc = buyPerCapitaMt(row);
  const sellPc = sellPerCapitaMt(row);

  const isSusp = evaluateDynamicQuickFilter(row, 'f_susp', tapeFilterConfig) || !!row.f_susp;
  const isJet = evaluateDynamicQuickFilter(row, 'f_jet', tapeFilterConfig) || !!row.f_jet;
  const isRoobi = evaluateDynamicQuickFilter(row, 'f_roobi', tapeFilterConfig) || sweep;
  const isNoqteh = evaluateDynamicQuickFilter(row, 'f_noqteh', tapeFilterConfig);
  const isClock = evaluateDynamicQuickFilter(row, 'f_clock', tapeFilterConfig) || strongHour || goldenHour || !!row.f_clock;

  const badges: React.ReactNode[] = [];
  if (isClock)
    badges.push(
      <MicroBadge
        key="clock"
        pattern={strongHour ? 'strong-hour' : goldenHour ? 'golden-hour' : 'clock'}
        tone={goldenHour ? 'amber' : 'violet'}
        title={
          strongHour
            ? `${STRONG_HOUR_LABEL} — ${STRONG_CLOCK_HINT}${diff != null ? ` · دلتا: ${fmtPct(diff * 100)}` : ''}`
            : goldenHour
              ? `${GOLDEN_HOUR_LABEL} — ${GOLDEN_HOUR_HINT}`
              : `الگوی ساعت: پایانی بالاتر از آخرین${diff != null ? ` · اختلاف آخرین و پایانی: ${fmtPct(diff * 100)}` : ''}`
        }
      >
        {strongHour ? 'ساعت' : goldenHour ? 'طلایی' : 'ساعت'}
      </MicroBadge>,
    );
  if (isSusp) badges.push(<MicroBadge key="susp" pattern="susp" tone="amber" title={`حجم مشکوک: ${volMult}`} >مشکوک</MicroBadge>);
  if (isJet) badges.push(<MicroBadge key="jet" pattern="jet" tone="cyan" title={`جت: شکست مقاومت با سرانه خرید ${row.buyer_power != null ? toFaDigits(row.buyer_power.toFixed(2)) : '—'}×`} >جت</MicroBadge>);
  if (isRoobi) badges.push(<MicroBadge key="sweep" pattern="sweep" tone="emerald" title={`کف‌روب: ${SWEEP_HINT}`} >کف‌روب</MicroBadge>);
  if (isNoqteh) badges.push(<MicroBadge key="noqteh" pattern="noqteh" tone="amber" title="نقطه‌زنی: فاصله نزدیک از کف ۳۰ روزه" >نقطه</MicroBadge>);
  if (atLimitUp) badges.push(<MicroBadge key="lu" pattern="limit-up" tone="green" title="صف خرید (تغییر ≥ ۴.۹٪)" >صف+</MicroBadge>);
  if (atLimitDown) badges.push(<MicroBadge key="ld" pattern="limit-down" tone="red" title="صف فروش (تغییر ≤ −۴.۹٪)" >صف−</MicroBadge>);
  return (
    <div
      role="button"
      tabIndex={0}
      data-testid="tape-row"
      onClick={() => row.symbol && onSelect(row.symbol)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (row.symbol) onSelect(row.symbol);
        }
      }}
      title={tooltip}
      className={`grid w-full ${ROW_GRID} cursor-pointer items-center gap-1.5 border-b border-border-c/50 px-3 text-start text-base ${
        selected ? 'bg-accent-blue/15' : 'odd:bg-bg-secondary even:bg-bg-primary hover:bg-bg-card/70'
      } ${atLimitUp ? 'border-s-2 border-s-accent-green' : atLimitDown ? 'border-s-2 border-s-accent-red' : ''}`}
      style={{ height: 40 }}
    >
      <span className="font-bold text-base text-text-primary flex items-baseline gap-1.5 truncate">
        {row.symbol}
        <span className="truncate text-xs font-normal text-text-muted">{row.name ?? ''}</span>
      </span>
      {/* تراز ستون (fix): محتوای عددی با `.num` (direction:ltr) به‌صورت خودکار چپ‌چین می‌شد
          و زیر هدرِ راست‌چین نمی‌نشست؛ `text-end` آن را با لبهٔ راست (جای هدر) هم‌تراز می‌کند. */}
      <span className="num text-end text-text-primary font-bold">
        <FlashNum value={row.p_last} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      <span className="num text-end text-text-secondary">
        <FlashNum value={row.p_closing} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      <span className={`num text-end font-bold ${pctTone(pct)}`}>
        <FlashNum value={pct} render={(v) => (v == null ? '-' : fmtPct(v))} />
      </span>
      <span className={`num text-end ${pctTone(row.percent_last)}`}>
        <FlashNum value={row.percent_last} render={(v) => (v == null ? '-' : fmtPct(v))} />
      </span>
      <span className="num text-end text-text-secondary">
        <FlashNum value={row.tvol} render={fmtInt} />
      </span>
      {/* تعدادِ معاملات: بدونش «tno > ۵۰» و «qd1 > ۱۰۰» درِ فیلترها قابلِ
          ردیابی نبود. صفرِ جعلی نداریم؛ نبودنش «-» است. */}
      <span className="num text-end text-text-secondary">
        <FlashNum value={row.z_tot_tran} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      <span className="num text-end text-text-secondary" title={row.q_tot_cap != null ? `${fmtInt(row.q_tot_cap)} ریال` : undefined}>
        <FlashNum value={toBillionRial(row.q_tot_cap)}
                  render={(v) => (v == null ? '-' : v >= 100 ? fmtInt(v) : toFaDigits(v.toFixed(1)))} />
      </span>
      <span
        className={`num text-end ${volHot ? 'font-bold text-accent-susp' : 'text-text-secondary'}`}
        title={volHot ? `حجم مشکوک FTS: بیش از ${toFaDigits(FTS_VOL_RATIO_HOT)} برابر میانگین ماهانه` : undefined}
      >
        <FlashNum value={row.vol_ratio} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(1)) + (v > FTS_VOL_RATIO_HOT ? '×' : ''))} />
      </span>
      <BuySellCell buyPc={buyPc} sellPc={sellPc} power={row.buyer_power} />
      <span className="flex min-w-0 items-center gap-1.5">
        <span className="num shrink-0 text-text-muted font-medium text-xs">
          <FlashNum value={diff} render={(v) => (v == null ? '-' : fmtPct(v * 100))} />
        </span>
        {/* `flex-wrap` به‌جای `overflow-x-auto`: نوارِ بج هیچ‌وقت اسکرول
            افقی نمی‌شود؛ اگر روزی چهار بج با هم بیایند، در ارتفاعِ ۴۰
            ردیف می‌شکنند و دیده می‌شوند — نه اینکه پشتِ لبهٔ ستون پنهان
            شوند (باگِ گزارش‌شدهٔ کاربر: «برچسب‌ها قابل اسکرول‌اند»). */}
        <span className="flex min-w-0 flex-1 flex-wrap items-center gap-0.5 overflow-hidden py-0.5">{badges}</span>
      </span>
    </div>
  );
});

export function TapeTable({
  rows,
  selected,
  onSelect,
  isLoading,
  isError,
  onRetry,
}: {
  rows: MarketRow[];
  selected: string;
  onSelect: (s: string) => void;
  /** وضعیتِ فید: جدولِ خالی نباید تقصیرِ فیلترِ کاربر باشد */
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('vol_ratio');
  const [desc, setDesc] = useState(true);
  const parentRef = useRef<HTMLDivElement>(null);

  const sorted = useMemo(() => {
    const arr = [...rows];
    arr.sort((a, b) => {
      if (sortKey === 'symbol') {
        const va = a.symbol ?? '';
        const vb = b.symbol ?? '';
        return desc ? vb.localeCompare(va, 'fa') : va.localeCompare(vb, 'fa');
      }
      const va = sortVal(a, sortKey) as number;
      const vb = sortVal(b, sortKey) as number;
      return desc ? vb - va : va - vb;
    });
    return arr;
  }, [rows, sortKey, desc]);

  const virtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 12,
  });

  if (rows.length === 0) {
    // صادقانه: تا فید نرسیده یا خطا داده، «فیلتر شما غلط است» گفتن درست نیست.
    if (isError) {
      return (
        <EmptyState
          title="فیدِ تابلو برنگشت"
          hint="اینترنت یا سرویسِ تابلو را بررسی کن، دوباره تلاش کن"
          action={
            onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                data-testid="tape-retry"
                className="rounded-lg border border-accent-blue bg-accent-blue/10 px-3 py-1 text-xs font-bold text-accent-blue"
              >
                تلاش دوباره
              </button>
            ) : undefined
          }
        />
      );
    }
    if (isLoading) {
      return <EmptyState title="در حالِ خواندنِ تابلو…" hint="نخستین نشستِ داده کمی طول می‌کشد" />;
    }
    return <EmptyState title="نمادی با این فیلترها نیست" hint="فیلترها را کم کن یا جستجو را پاک کن" />;
  }

  const toggle = (k: SortKey) => {
    if (k === sortKey) setDesc((d) => !d);
    else {
      setSortKey(k);
      setDesc(true);
    }
  };

  return (
    <div className="glass-panel overflow-hidden rounded-2xl">
      <div className="overflow-x-auto overscroll-x-contain">
        <div className={`sticky top-0 z-10 grid w-full ${TABLE_MIN_W} ${ROW_GRID} gap-1.5 bg-bg-card/95 px-3 py-2.5 text-start text-3xs font-bold text-text-secondary backdrop-blur`}>
          {HEADERS.map((h) => (
            <button
              key={h.key}
              type="button"
              onClick={() => toggle(h.key)}
              title={h.hint ?? (h.key === 'last_vs_close' ? 'الگوی ساعت — مرتب‌سازی بر اساس اختلاف آخرین/پایانی' : undefined)}
              className="block w-full truncate text-start whitespace-nowrap hover:text-accent-blue transition-colors"
            >
              {h.label} {sortKey === h.key ? (desc ? '↓' : '↑') : ''}
            </button>
          ))}
        </div>
        <div ref={parentRef} className="h-[calc(100dvh-260px)] min-h-[420px] overflow-y-auto overscroll-contain" data-testid="tape-scroll">
          <div className={`relative w-full ${TABLE_MIN_W}`} style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((v) => {
            const row = sorted[v.index];
            return (
              <div
                key={row.symbol}
                className="absolute inset-x-0 top-0 w-full will-change-transform"
                style={{
                  height: `${v.size}px`,
                  transform: `translateY(${v.start}px)`,
                }}
              >
                <TapeRow
                  row={row}
                  selected={row.symbol === selected}
                  onSelect={onSelect}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
    <div className="border-t border-border-c bg-bg-secondary/60 px-3 py-1 text-2xs text-text-muted">
      <span className="num font-bold">{toFaDigits(sorted.length)}</span> نماد
    </div>
  </div>
);
}
