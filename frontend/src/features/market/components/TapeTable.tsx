// features/market/components/TapeTable.tsx -- جدول مجازی تابلو
// ردیف ها با React.memo و کلید نماد؛ فقط ردیف های دیدنی رندر می شوند.
import { memo, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { MarketRow } from '@shared/types/marketRow';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { EmptyState } from '@shared/components/EmptyState';
import { FlashNum } from '@shared/components/FlashNum';
import {
  STRONG_CLOCK_HINT,
  detectBoxExit,
  detectGoldenHour,
  detectStrongHour,
  detectSweep,
  lastCloseDiff,
} from '../lib/tapePatterns';
import { FTS_VOL_RATIO_HOT, buyPerCapitaMt, buySellShare, sellPerCapitaMt } from '../lib/tapeFts';
import { patternBadges } from '../lib/tapeBadges';
import { powerTone } from '../api/useMarketPulse';
import { LIMIT_PCT, useTapeStore } from '../stores/tapeStore';
import SymbolSelectBox from '@shared/components/SymbolSelectBox';
import WatchlistStar from '@shared/components/WatchlistStar';

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
 * دوازده ستونِ تابلو (۱۲). عرض‌ها از روی سنجشِ واقعیِ «پهنای لازمِ محتوا» در فونتِ
 * 16pxِ همین جدول گذاشته شده‌اند، نه حدس:
 * [نماد 150] [آخرین 66] [پایانی 66] [اختلاف٪ 60] [تغییر٪ 62] [آخرین٪ 62] [حجم 130] [تعداد 64]
 * [ارزش 58] [حجم/ماه 58] [خرید/فروش 118 — سرانه‌ها + نوارِ دوسُره + نسبت]
 * [الگو 142].
 * سه ستونِ «سرانۀ خرید / سرانۀ فروش / قدرتِ خریدار» در #146 به یک ستونِ دوسُره
 * جمع شد؛ در #172 خانهٔ «ساعت» دو ستون شد، چون عددِ اختلاف و بج‌هایِ الگو در یک
 * خانه به هم می‌چسبیدند و خواننده نمی‌فهمید عدد زیرِ کدام سرستون است. فاصلهٔ
 * ستون‌ها ۶→۴ و حاشیهٔ ردیف ۱۲→۸ آمد تا حدِ آستانهٔ عرض بالا نکند.
 */
const ROW_GRID =
  'grid-cols-[minmax(150px,1.6fr)_minmax(66px,0.85fr)_minmax(66px,0.85fr)_minmax(60px,0.6fr)_minmax(62px,0.8fr)_minmax(62px,0.8fr)_minmax(130px,1.05fr)_minmax(64px,0.85fr)_minmax(58px,0.8fr)_minmax(58px,0.78fr)_minmax(118px,1.1fr)_minmax(142px,1.5fr)]';

/** کمترینِ عرضِ جدول = جمعِ مینیمم‌ها + فاصله‌ها + padding (زیرِ این، جدول افقی اسکرول می‌خورد) */
const TABLE_MIN_W = 'min-w-[1100px]';

/** سرستونِ بی‌مرتب‌سازی (کلیدِ null) — ستونِ بج‌ها عددی نیست که بشود مرتبش کرد */
const HEADERS: { key: SortKey | null; label: string; hint?: string }[] = [
  // برچسبِ ستون «فیلتر» نیست و فقط خواندنِ سرستون را می‌سازد؛ پس کوتاه‌ترین
  // شکلِ ممکن نوشته می‌شود و نامِ کامل + واحد در title می‌ماند. رویِ
  // نمایشگرِ ۱۳۶۶ این تیترهای بلند در ستونِ ۶۲-۷۸ پیکسلی می‌شکستند و
  // سرستون افقی اسکرول می‌خورد.
  { key: 'symbol', label: 'نماد' },
  { key: 'p_last', label: 'آخرین' },
  { key: 'p_closing', label: 'پایانی', hint: 'قیمت پایانیِ همین نشست (p_closing)' },
  // اختلافِ آخرین تا پایانی بغلِ پایانی نشسته (#194): هر دو ستونِ یک مقایسه‌اند
  // — «آخرین» و «پایانی» و «فاصلۀ این دو» — و جدا از هم خوانده نمی‌شوند.
  {
    key: 'last_vs_close',
    label: 'اختلاف٪',
    hint: 'آخرین نسبت به پایانی — منفی یعنی پایانی بالاتر از آخرین، همان شرطِ الگوی ساعت',
  },
  {
    key: 'percent_change',
    label: 'تغییر٪',
    hint: 'پایانی نسبت به دیروز — همان متغیرِ pcp در فیلترنویسیِ TSETMC',
  },
  {
    key: 'percent_last',
    label: 'آخرین٪',
    hint: 'آخرین نسبت به دیروز — همان متغیرِ plp در فیلترنویسیِ TSETMC، و با درصدِ پایانی فرق دارد',
  },
  { key: 'tvol', label: 'حجم' },
  {
    key: 'z_tot_tran',
    label: 'تعداد',
    hint: 'تعدادِ معاملات — همان متغیرِ tno در فیلترنویسیِ TSETMC (z_tot_tran)',
  },
  { key: 'q_tot_cap', label: 'ارزش', hint: 'ارزش معاملات — میلیارد ریال (q_tot_cap)' },
  { key: 'vol_ratio', label: 'حجم/ماه', hint: 'نسبت حجمِ امروز به میانگینِ حجمِ ماه' },
  {
    key: 'buyer_power',
    label: 'خرید / فروش',
    hint:
      'بالا: سرانۀ خرید حقیقی (سبز) و سرانۀ فروش حقیقی (قرمز) به میلیون تومان. ' +
      'پایین: نوارِ سهمِ هر طرف و نسبتِ خرید به فروش',
  },
  {
    key: null,
    label: 'الگو',
    hint: 'برچسبِ الگوهایِ فعال روی همان ردیف: ساعت، حجم مشکوک، جت، کف‌روب، نقطه‌زنی، صف خرید و صف فروش',
  },
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

/** سرانه به میلیون تومان: عددِ tabular + واحدِ جدا. واحد در spanِ خودش است چون
 *  `.num` جهت را ltr می‌کند و «۵.۰ م.ت» را در آن «م.ت ۵.۰» می‌خواند. داده نیست ⇒
 *  فقط «—»؛ صفرِ جعلی نه. بالای ۱۰۰ اعشار نمی‌ماند (همان قاعدهٔ ستونِ ارزش):
 *  سرانۀِ صدها میلیونی با یک رقم اعشار در ستونِ ۱۱۸ پیکسلی جا نمی‌شد. */
function pcText(v: number): string {
  return v >= 100 ? fmtInt(v) : toFaDigits(v.toFixed(1));
}

function PcNum({ v, className, testId }: { v: number | null; className: string; testId: string }) {
  return (
    <span data-testid={testId} className={`flex shrink-0 items-baseline gap-px ${className}`}>
      {/* سرانه‌ها هم مثلِ بقیۀِ ستون‌هایِ عددی فلاش می‌گیرند (#12): تا پیش از این
          تنها «نسبتِ خرید/فروش» رنگ می‌دید و دو عددِ بالایِ همان خانه بی‌خبر عوض
          می‌شدند. */}
      <FlashNum
        value={v}
        className="num font-bold"
        render={(x) => (x == null ? '—' : pcText(x))}
      />
      {v != null && <span className="text-3xs opacity-80">م.ت</span>}
    </span>
  );
}

/**
 * ستونِ خرید/فروش (#146 و #172): دو خط. بالا خودِ دو سرانه (میلیون تومان) — سبز
 * خرید در راست، قرمز فروش در چپ؛ پایین نوارِ سهم و نسبتِ خرید به فروش. تا پیش از
 * #172 دو سرانه فقط در title بود و «با دیدنِ ستون جزئیات زیادی نمی‌داد».
 * یک طرف غایب ⇒ «—» و بی‌نوار: نبودِ داده «فروش صفر» یا «خرید صددرصد» نیست.
 */
function BuySellCell({
  buyPc,
  sellPc,
  power,
}: {
  buyPc: number | null;
  sellPc: number | null;
  power: number | null | undefined;
}) {
  const share = buySellShare(buyPc, sellPc);
  return (
    <span
      data-testid="tape-buy-sell"
      className="flex min-w-0 flex-col gap-0.5"
      title={`سرانۀ خرید ${mt(buyPc)} · سرانۀ فروش ${mt(sellPc)} — نسبتِ خرید به فروش ${
        power == null ? '—' : `${toFaDigits(power.toFixed(2))}×`
      }`}
    >
      <span className="flex min-w-0 items-baseline justify-between gap-1 text-3xs leading-none">
        <PcNum v={buyPc} className="text-accent-green" testId="tape-buy-pc" />
        <PcNum v={sellPc} className="text-accent-red" testId="tape-sell-pc" />
      </span>
      <span className="flex min-w-0 items-center gap-1">
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

export const TapeRow = memo(function TapeRow({
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
  const pct = row.percent_change;
  const atLimitUp = pct != null && pct >= LIMIT_PCT;
  const atLimitDown = pct != null && pct <= -LIMIT_PCT;
  const tooltip = rowTooltip(row);
  const volHot = row.vol_ratio != null && row.vol_ratio > FTS_VOL_RATIO_HOT;
  const buyPc = buyPerCapitaMt(row);
  const sellPc = sellPerCapitaMt(row);

  // بج‌های ستونِ «الگو» از lib می‌آیند: همان `tapeFilterVerdict` که چیپِ بالایِ
  // جدول می‌شمارد، تا عددِ چیپ و آنچه درِ ردیف دیده می‌شود یکی بماند.
  const badges = patternBadges(row, tapeFilterConfig);
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
      className={`grid w-full ${ROW_GRID} cursor-pointer items-center gap-1 border-b border-border-c/50 px-2 text-start text-base ${
        selected ? 'bg-accent-blue/15' : 'odd:bg-bg-secondary even:bg-bg-primary hover:bg-bg-card/70'
      } ${atLimitUp ? 'border-s-2 border-s-accent-green' : atLimitDown ? 'border-s-2 border-s-accent-red' : ''}`}
      style={{ height: 40 }}
    >
      <span className="font-bold text-base text-text-primary flex items-center gap-1.5 truncate">
        {/* جعبۀ انتخاب داخلِ همان ستونِ نماد است، نه ستونِ تازه: `ROW_GRID` با
            افزودنِ یک فرزندِ مستقیمِ grid از جا درمی‌رود. */}
        <SymbolSelectBox symbol={String(row.symbol ?? '')} name={String(row.name ?? '')}
                         insCode={row.ins_code ?? null} />
        <WatchlistStar symbol={String(row.symbol ?? '')} name={String(row.name ?? '')} />
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
      {/* اختلافِ آخرین تا پایانی یک ستونِ عددیِ مستقل است (#172) و بغلِ پایانی
          می‌نشیند (#194): تا پیش از این کنارِ بج‌ها بود و خواننده نمی‌فهمید
          عددِ درصد زیرِ کدام سرستون است، یا با «آخرین» و «پایانی» چه ربطی دارد. */}
      <span className="num text-end text-text-secondary" title={`اختلاف آخرین و پایانی: ${diff == null ? '—' : fmtPct(diff * 100)}`}>
        <FlashNum value={diff} render={(v) => (v == null ? '-' : fmtPct(v * 100))} />
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
      {/* `flex-wrap` به‌جای `overflow-x-auto`: نوارِ بج هیچ‌وقت اسکرول
          افقی نمی‌شود؛ اگر روزی چهار بج با هم بیایند، در ارتفاعِ ۴۰
          ردیف می‌شکنند و دیده می‌شوند — نه اینکه پشتِ لبهٔ ستون پنهان
          شوند (باگِ گزارش‌شدهٔ کاربر: «برچسب‌ها قابل اسکرول‌اند»). */}
      <span data-testid="tape-patterns" className="flex min-w-0 flex-wrap items-center gap-0.5 overflow-hidden py-0.5">
        {badges.map((b) => (
          <MicroBadge key={b.key} pattern={b.pattern} tone={b.tone} title={b.title}>
            {b.label}
          </MicroBadge>
        ))}
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
        <div data-testid="tape-head" className={`sticky top-0 z-10 grid w-full ${TABLE_MIN_W} ${ROW_GRID} gap-1 bg-bg-card/95 px-2 py-2.5 text-start text-3xs font-bold text-text-secondary backdrop-blur`}>
          {HEADERS.map((h) => {
            const k = h.key;
            if (k == null) {
              return (
                <span key={h.label} title={h.hint} className="block w-full truncate text-start whitespace-nowrap">
                  {h.label}
                </span>
              );
            }
            return (
              <button
                key={k}
                type="button"
                onClick={() => toggle(k)}
                title={h.hint}
                className="block w-full truncate text-start whitespace-nowrap hover:text-accent-blue transition-colors"
              >
                {h.label} {sortKey === k ? (desc ? '↓' : '↑') : ''}
              </button>
            );
          })}
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
