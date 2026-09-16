// features/fundamental/ui/FtsScreenTable.tsx -- دیده‌بان کلان بنیادی
// ماتریس مقایسه‌ای ۵ شاخص جزوهٔ FTS + ستون امتیاز نردبان (۰..۵) قابل سورت.
// کلیک روی سطر نماد را در استور فعال می‌کند تا سایدبار چپ و نمای
// کالبدشکافی باز شود. جای برچسب عمومی «شکاف داده»، علتِ واقعیِ هر شاخص
// نمایش داده می‌شود (lib/gapReason) — نه خطای خام، نه کرش.
// دروازه‌های سخت (قیمت‌گذاری دستوری/تعلیق): ردیف‌های excluded پیش‌فرض
// حذف می‌شوند؛ سوییچ «نمایش ردیف‌های حذف‌شده» فقط برای بازرسی آن‌هاست.
// قلمرو جدول: فقط «شرکت‌های تولیدی و خدماتی» — صندوق‌ها، کارگزاری‌ها،
// اوراق و مشتقه‌ها به‌صورت پیش‌فرض حذف می‌شوند (فیلتر نوع نماد).
import { memo, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { toFaDigits } from '@shared/lib/fmt';
import { absurdHint, fmtPctGrouped, fmtRatioGrouped, isAbsurdPct } from '../lib/numFmt';
import { EmptyState } from '@shared/components/EmptyState';
import type { FtsScreenRow } from '../api/useFtsScreen';
import { isFundamentalCompany } from '../lib/assetScope';
import {
  EPS_PARTIAL_TESTID,
  EPS_REQUIRED_YEARS,
  epsGapLabel,
  epsHistory,
  epsSeriesText,
} from '../lib/epsHistory';
import { gapLabel, gapReason, gapTooltip, type GapAxis } from '../lib/gapReason';
import { AuditBadge, type AuditEvidenceInput } from '../components/AuditBadge';
import { screenAuditEvidence } from '../lib/auditEvidence';
import {
  EXCLUDE_LABEL,
  applyExcludeFilter,
  resetExcludeAxes,
  useExcludeAxes,
} from '../lib/exclusionFilter';

type SortKey = 'score' | 'rev_growth' | 'gross_margin' | 'sales_to_mcap' | 'profit_potential_pct';

const COLS: { key: SortKey | null; label: string; title: string }[] = [
  { key: null, label: 'نماد', title: '' },
  { key: 'rev_growth', label: '۱ رشد کدال', title: 'رشد فروش تجمعی نسبت به دوره مشابه سال قبل' },
  { key: null, label: '۲ روند EPS', title: 'وضعیت سه سال اخیر EPS' },
  { key: 'gross_margin', label: '۳ حاشیه', title: 'سود ناخالص ÷ درآمد عملیاتی' },
  { key: 'profit_potential_pct', label: '۴ پتانسیل', title: 'سود ناخالص برآوردی ۱۲ماهه ÷ ارزش بازار' },
  { key: null, label: '۵ صنعت', title: 'رژیم قیمت‌گذاری صنعت' },
  { key: 'score', label: 'امتیاز', title: 'نردبان بنیادی ۰ تا ۵' },
];

/** چهارحالتهٔ شاخص ۲ (قبول / سابقهٔ ناقص / مردود / بدون داده) و سه‌حالتهٔ بقیهٔ شاخص‌ها */
type CellState = 'pass' | 'fail' | 'gap' | 'partial';

/**
 * حکمِ سلول از پرچمِ موتور FTS می‌آید؛ «بدون داده» فقط وقتی است که هیچ حکمی نداریم.
 * F-10: پیش از این، شرط «مقدار غایب ⇒ gap» باعث می‌شد ۲۶۳ ردیف در شاخص ۱، ۳۱۷ در شاخص ۳،
 * ۱۸۱ در شاخص ۲ و ۶۶ در شاخص ۴ با وجود حکمِ موتور، برچسب «داده نیست» بگیرند و با امتیاز/کارت
 * نماد ناسازگار شوند. مقدار غایب فقط نمایش «—» می‌گیرد، نه حکمِ دروغ.
 */
function verdictOf(flag: boolean | null | undefined): CellState {
  if (flag === true) return 'pass';
  if (flag === false) return 'fail';
  return 'gap';
}

/** tooltip وقتی مقدار در پاسخ غربالگری نیست ولی حکمِ موتور برای همان شاخص وجود دارد */
const VALUE_MISSING_WITH_VERDICT =
  'مقدار در پاسخ غربالگری نیامده؛ حکمِ موتور FTS برای این شاخص اعمال شده است (جزئیات در کارت نماد).';

const STATE_BADGE: Record<'pass' | 'fail', { tone: 'green' | 'red'; label: string }> = {
  pass: { tone: 'green', label: '✓' },
  fail: { tone: 'red', label: '✗' },
};

/** ارتفاع ثابت ردیف جدول (پیکسل) — مجازی‌سازی و اسکرول روان روی همین حساب می‌شود */
const ROW_H = 46;

/** نشان قبول/مردود — حالت‌های «partial» و «gap» هرگز به اینجا نمی‌رسند
 *  (پیش از آن با برچسب علت‌دار یا برچسب سابقهٔ ناقص رندر می‌شوند). */
function PassMark({
  state,
  evidence,
  testId,
}: {
  state: CellState;
  evidence?: AuditEvidenceInput;
  testId?: string;
}) {
  const b = STATE_BADGE[state === 'pass' ? 'pass' : 'fail'];
  return (
    <AuditBadge
      state={state === 'pass' ? 'pass' : 'fail'}
      label={b.label}
      evidence={evidence}
      compact
      testId={testId ?? `fts-mark-${state === 'pass' ? 'pass' : 'fail'}`}
    />
  );
}

/** سلول بی‌داده: جای برچسب عمومی «شکاف داده»، علتِ واقعی را می‌نویسد
 *  (برچسب کوتاه + tooltip علت و راه‌حل — الگوی GapHint) */
function GapMark({
  label,
  tooltip,
  evidence,
  testId,
}: {
  label: string;
  tooltip: string;
  evidence?: AuditEvidenceInput;
  testId?: string;
}) {
  return (
    <AuditBadge
      state="na"
      label={<span className="max-w-[9.5rem] leading-snug text-accent-yellow">{label}</span>}
      hintTitle={tooltip}
      evidence={evidence}
      compact
      testId={testId}
    />
  );
}

/** سلول بی‌داده با علتِ همان محور */
/** سلول بی‌داده با علتِ همان محور (شاهد تنبل از ردیف ساخته می‌شود) */
function AxisGapMark({ axis, evidence }: { axis: GapAxis; evidence?: AuditEvidenceInput }) {
  return (
    <GapMark
      label={gapLabel(axis)}
      tooltip={gapTooltip(axis)}
      evidence={evidence}
      testId={`fts-gap-reason-${axis}`}
    />
  );
}

/** ردیف جدول غربالگری — memo شده؛ فقط ردیف‌های در دید (مجازی‌سازی) رندر می‌شوند و
 *  شاهد ممیزی هر سلول به‌صورت تابعِ تنبل ساخته می‌شود (تا وقتی کارت پاپ‌اور بسته است، هیچ محاسبه‌ای نمی‌شود). */
const ScreenerRow = memo(function ScreenerRow({
  row: r,
  thresholds,
  onSelect,
}: {
  row: FtsScreenRow;
  thresholds?: Record<string, unknown> | null;
  onSelect: (symbol: string) => void;
}) {
  /** شاهد ممیزی هر محور، تنبل — فقط هنگام باز شدن کارت «چرا این وضعیت؟» فراخوانی می‌شود */
  const ev = useMemo(
    () => ({
      i1a: () => screenAuditEvidence('1a_monetary_growth', r, thresholds),
      i2: () => screenAuditEvidence('2_eps_trend', r, thresholds),
      i3: () => screenAuditEvidence('3_gross_margin', r, thresholds),
      i4: () => screenAuditEvidence('4_sales_to_mcap', r, thresholds),
      i5: () => screenAuditEvidence('5_industry', r, thresholds),
    }),
    [r, thresholds],
  );
              const i1 = verdictOf(r.i1_pass);
              /** شاخص ۲ — چهاردحالته از روی خودِ داده (lib/epsHistory):
               *  pass / partial «مردود — سابقهٔ ناقص (۲ از ۳ سال)» / fail / gap (<۲ سال) */
              const epsHist = epsHistory(
                r.eps_series,
                r.eps_years_required ?? EPS_REQUIRED_YEARS,
                r.eps_years_available,
              );
              /** شاخص ۲: برچسب «سابقهٔ ناقص» ارجح است (۲ از ۳ سال)، وگرنه حکمِ موتور */
              const i2: CellState = epsHist.state === 'partial' ? 'partial' : verdictOf(r.i2_pass);
              const i3 = verdictOf(r.i3_pass);
              const i4 = verdictOf(r.i4_pass);
              /** شاخص ۵: حکمِ موتور؛ «بدون داده» فقط اگر پرچم نبود (پیش‌تر pricing_mode=null ⇒ gap و i5_pass=null ⇒ fail بود) */
              const i5: CellState = verdictOf(r.i5_pass);
              const epsTrend = epsSeriesText(r.eps_series);
              /** برچسب و علت از همان منبع حقیقتِ نردبان EPS و drill-down */
              const epsPartialRejected = i2 === 'partial';
              /** سابقهٔ EPS کمتر از ۲ سال: برچسبِ علت‌دار (F-02) حفظ می‌شود ولی رنگ/حکم از پرچم موتور می‌آید */
              const epsInsufficient = epsHist.state === 'insufficient';
              const epsGapReason = epsHist.realYears
                ? `فقط ${toFaDigits(epsHist.realYears)} سال از ${toFaDigits(epsHist.requiredYears)} سالِ لازم EPS موجود است — سابقهٔ کامل سه‌ساله برای قضاوت شاخص ۲ کافی نیست.`
                : 'این ردیفِ اسکنر سابقهٔ EPS سالانه ندارد؛ علت دقیق در کارت نماد (دادهٔ جزئیات کدال) دیده می‌شود.';
              return (
                <tr
                  key={r.symbol}
                  onClick={() => r.symbol && !r.excluded && onSelect(r.symbol)}
                  className={`border-b border-border-c/40 transition-colors ${
                    r.excluded
                      ? 'cursor-not-allowed bg-accent-red/5 opacity-55'
                      : 'cursor-pointer odd:bg-bg-secondary even:bg-bg-primary hover:bg-accent-blue/10'
                  }`}
                  data-testid="fts-screen-row"
                >
                  <td className="px-2 py-2">
                    <div className="flex flex-col">
                      <span className={`font-bold text-text-primary ${r.excluded ? 'line-through decoration-accent-red/60' : ''}`}>
                        {r.symbol}
                      </span>
                      <span className="truncate text-2xs text-text-muted">{r.name || r.sector_name || ''}</span>
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`num whitespace-nowrap ${r.rev_growth != null && r.rev_growth >= 0 ? 'text-accent-green' : 'text-accent-red'}`}
                        title={r.rev_growth == null ? VALUE_MISSING_WITH_VERDICT : (absurdHint(r.rev_growth) ?? undefined)}
                      >
                        {r.rev_growth == null ? '—' : fmtPctGrouped(r.rev_growth)}
                        {isAbsurdPct(r.rev_growth) ? ' ⚠' : ''}
                      </span>
                      {i1 === 'gap' ? (
                        <AxisGapMark axis="1a_monetary_growth" evidence={ev.i1a} />
                      ) : (
                        <PassMark
                          state={i1}
                          evidence={ev.i1a}
                          testId="fts-mark-1a_monetary_growth"
                        />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="num whitespace-nowrap text-text-secondary"
                        title={epsTrend ?? VALUE_MISSING_WITH_VERDICT}
                      >
                        {epsTrend ?? '—'}
                      </span>
                      {epsPartialRejected ? (
                        <AuditBadge
                          state="fail"
                          label={epsHist.label}
                          hintTitle={epsGapReason}
                          evidence={() => ({ ...ev.i2(), reason: epsGapReason })}
                          compact
                          testId={EPS_PARTIAL_TESTID}
                        />
                      ) : epsInsufficient || i2 === 'gap' ? (
                        /* F-10: برچسب علت‌دار می‌ماند، ولی tone از حکمِ موتور می‌آید
                           (پیش‌تر حتی وقتی موتور «مردود» داده بود، برچسب زردِ بی‌حکم نشان داده می‌شد) */
                        <AuditBadge
                          state={i2 === 'pass' ? 'pass' : i2 === 'fail' ? 'fail' : 'na'}
                          label={<span className="max-w-[9.5rem] leading-snug">{epsGapLabel(epsHist.realYears)}</span>}
                          hintTitle={`${epsGapReason} راه‌حل: ${gapReason('2_eps_trend').fix}`}
                          evidence={ev.i2}
                          compact
                          testId="eps-gap-reason"
                        />
                      ) : (
                        <PassMark state={i2} testId="fts-mark-2_eps_trend" />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="num whitespace-nowrap text-text-primary"
                        title={r.gross_margin == null ? VALUE_MISSING_WITH_VERDICT : (absurdHint(r.gross_margin) ?? undefined)}
                      >
                        {r.gross_margin == null ? '—' : fmtPctGrouped(r.gross_margin)}
                        {isAbsurdPct(r.gross_margin) ? ' ⚠' : ''}
                      </span>
                      {i3 === 'gap' ? (
                        <AxisGapMark axis="3_gross_margin" evidence={ev.i3} />
                      ) : (
                        <PassMark
                          state={i3}
                          evidence={ev.i3}
                          testId="fts-mark-3_gross_margin"
                        />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="num whitespace-nowrap text-text-primary"
                        title={
                          r.profit_potential_pct == null
                            ? r.sales_to_mcap != null
                              ? `نسبت فروش/ارزش بازار ${fmtRatioGrouped(r.sales_to_mcap)} — پتانسیل سود ناخالص ثبت نشده`
                              : VALUE_MISSING_WITH_VERDICT
                            : (absurdHint(r.profit_potential_pct) ?? undefined)
                        }
                      >
                        {r.profit_potential_pct == null ? '—' : fmtPctGrouped(r.profit_potential_pct)}
                        {isAbsurdPct(r.profit_potential_pct) ? ' ⚠' : ''}
                      </span>
                      {i4 === 'gap' ? (
                        <AxisGapMark axis="4_sales_to_mcap" evidence={ev.i4} />
                      ) : (
                        <PassMark
                          state={i4}
                          evidence={ev.i4}
                          testId="fts-mark-4_sales_to_mcap"
                        />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      {i5 === 'gap' ? (
                        <AxisGapMark axis="5_industry" evidence={ev.i5} />
                      ) : (
                        <PassMark
                          state={i5}
                          evidence={ev.i5}
                          testId="fts-mark-5_industry"
                        />
                      )}
                    </div>
                    {r.excluded ? (
                      <span
                        className="ms-1 inline-block max-w-[12rem] truncate align-middle text-2xs text-accent-red"
                        title={r.exclusion_reasons ?? ''}
                      >
                        {r.exclusion_reasons}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-2">
                    <span
                      className={`num inline-flex h-6 w-9 items-center justify-center rounded-full border text-2xs font-black ${
                        r.score >= 4
                          ? 'border-accent-green/40 bg-accent-green/15 text-accent-green'
                          : r.score >= 3
                            ? 'border-accent-yellow/40 bg-accent-yellow/15 text-accent-yellow'
                            : 'border-accent-red/40 bg-accent-red/15 text-accent-red'
                      }`}
                    >
                      <span className="num">{toFaDigits(r.score)}</span>
                    </span>
                  </td>
                </tr>
              );
});

export function FtsScreenTable({
  rows,
  onSelect,
  thresholds,
  onRefresh,
  refreshing,
}: {
  rows: FtsScreenRow[];
  onSelect: (symbol: string) => void;
  /** تارگت‌های کانفیگ FTS (پاسخ /api/screener) برای کارت «چرا این وضعیت؟» */
  thresholds?: Record<string, unknown> | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [desc, setDesc] = useState(true);
  /** دروازه‌های سخت فعال‌اند → ردیف‌های excluded پیش‌فرض حذف می‌شوند؛ سوییچ فقط برای بازرسی */
  const [showExcluded, setShowExcluded] = useState(false);
  /** شاخص‌هایی که کاربر خواسته نمادهای مردود/ناقص‌شان از جدول حذف شود (دراور تنظیمات) */
  const excludeAxes = useExcludeAxes();

  /** فیلتر نوع نماد (Asset Type): صندوق/کارگزاری/اوراق/مشتقه پیش‌فرض حذف */
  const excludedCount = useMemo(() => rows.filter((r) => r.excluded === true).length, [rows]);
  const nonCompanyCount = useMemo(
    () => rows.filter((r) => !isFundamentalCompany(r)).length,
    [rows],
  );

  /** فیلتر «حذف بر اساس شاخص» روی ردیف‌های مجاز اعمال می‌شود (شمار حذف‌شده‌ها برای نمایش) */
  const { rows: rowsAfterAxisFilter, hidden: hiddenByAxes } = useMemo(
    () => applyExcludeFilter(rows, excludeAxes),
    [rows, excludeAxes],
  );

  const visible = useMemo(
    () => {
      const base = showExcluded ? rowsAfterAxisFilter : rowsAfterAxisFilter.filter((r) => r.excluded !== true);
      // حتی در حالت بازرسی excluded، صندوق‌ها/کارگزاری‌ها/مشتقه‌ها می‌مانند؟ نه —
      // «نمایش ردیف‌های حذف‌شده» فقط دروازه‌های سخت را برمی‌گرداند؛ قلمرو
      // شرکت‌محورِ جدول بنیادی روی هر دو حالت اعمال می‌شود.
      return base.filter((r) => isFundamentalCompany(r));
    },
    [rowsAfterAxisFilter, showExcluded],
  );

  const sorted = useMemo(() => {
    const arr = [...visible];
    arr.sort((a, b) => {
      const va = (a[sortKey] as number | null | undefined) ?? Number.NEGATIVE_INFINITY;
      const vb = (b[sortKey] as number | null | undefined) ?? Number.NEGATIVE_INFINITY;
      if (va === vb) return b.score - a.score;
      return desc ? vb - va : va - vb;
    });
    return arr;
  }, [visible, sortKey, desc]);

  const toggle = (k: SortKey) => {
    if (k === sortKey) setDesc((d) => !d);
    else {
      setSortKey(k);
      setDesc(true);
    }
  };

  const scrollRef = useRef<HTMLDivElement | null>(null);
  /** مجازی‌سازی: فقط ردیف‌های در دید + حاشیه (overscan) رندر می‌شوند */
  const virtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_H,
    overscan: 8,
    initialRect: { width: 0, height: 640 },
  });
  const virtualRows = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const padTop = virtualRows.length ? virtualRows[0].start : 0;
  const padBottom = virtualRows.length ? Math.max(0, totalSize - virtualRows[virtualRows.length - 1].end) : 0;

  if (rows.length === 0) {
    return <EmptyState title="ردیفی از غربالگری FTS نیامد" hint="کارنامهٔ ماهانهٔ کدال هنوز سینک نشده است" />;
  }

  return (
    <div className="glass-panel panel-in overflow-hidden rounded-2xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--hairline)] px-4 py-2.5">
        <h3 className="text-sm font-black text-text-primary">دیده‌بان کلان بنیادی — ماتریس ۵ شاخص FTS</h3>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onRefresh?.()}
            disabled={!onRefresh || refreshing}
            data-testid="fts-refresh"
            title="تازه‌سازیِ ۵ شاخص FTS از کدال (فقط دِلتا، با چرخش IP) و بازخوانیِ جدول"
            className="flex items-center gap-1.5 rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-2.5 py-1 text-2xs font-bold text-text-secondary transition-colors hover:border-border-accent hover:text-accent-blue disabled:opacity-50"
          >
            <span aria-hidden>{refreshing ? "…" : "↻"}</span>
            {refreshing ? "در حال بروزرسانی…" : "بروزرسانی"}
          </button>
          {excludedCount > 0 ? (
            <button
              type="button"
              onClick={() => setShowExcluded((v) => !v)}
              aria-pressed={showExcluded}
              title={`دروازه‌های سخت: ${toFaDigits(excludedCount)} ردیف حذف‌شده ${showExcluded ? 'نمایش داده' : 'پنهان'} می‌شود`}
              className={`flex items-center gap-2 rounded-lg border px-2.5 py-1 text-2xs font-bold transition-colors ${
                showExcluded
                  ? 'border-accent-red/40 bg-accent-red/10 text-accent-red'
                  : 'border-[var(--hairline)] bg-bg-card/60 text-text-secondary hover:border-border-accent hover:text-accent-blue'
              }`}
            >
              <span
                aria-hidden
                dir="ltr"
                className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${
                  showExcluded ? 'bg-accent-red/70' : 'bg-bg-card'
                }`}
              >
                <span
                  className={`absolute h-3 w-3 rounded-full bg-white shadow transition-all ${
                    showExcluded ? 'left-[14px]' : 'left-0.5'
                  }`}
                />
              </span>
              {showExcluded ? 'پنهان‌سازی ردیف‌های حذف‌شده' : 'نمایش ردیف‌های حذف‌شده'}
            </button>
          ) : null}
          <span className="num text-2xs text-text-muted" title="فقط شرکت‌های تولیدی و خدماتی — صندوق‌ها و کارگزاری‌ها حذف شده‌اند">
            {toFaDigits(visible.length)} شرکت از {toFaDigits(rows.length)}
          </span>
        </div>
      </div>
      {excludeAxes.length > 0 ? (
        <div
          className="flex flex-wrap items-center gap-2 border-b border-[var(--hairline)] bg-accent-yellow/5 px-4 py-1.5"
          data-testid="fts-axis-filter-bar"
        >
          <span
            className="num text-2xs font-bold text-accent-yellow"
            data-testid="fts-axis-filter-count"
            title={excludeAxes.map((a) => EXCLUDE_LABEL[a]).join(' · ')}
          >
            {hiddenByAxes > 0
              ? `${toFaDigits(hiddenByAxes)} نماد با فیلتر شاخصی حذف شد`
              : 'فیلتر شاخصی فعال — نمادی حذف نشد'}
          </span>
          <span className="text-2xs text-text-muted">
            ({excludeAxes.map((a) => EXCLUDE_LABEL[a]).join(' · ')})
          </span>
          <button
            type="button"
            onClick={resetExcludeAxes}
            data-testid="fts-axis-filter-reset"
            title="همهٔ فیلترهای حذف بر اساس شاخص خاموش شوند"
            className="ms-auto rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-2 py-1 text-2xs font-bold text-text-secondary transition-colors hover:border-accent-red hover:text-accent-red"
          >
            بازنشانی فیلترها
          </button>
        </div>
      ) : null}
      <div ref={scrollRef} data-testid="fts-screen-scroll" className="max-h-[70vh] overflow-auto">
        <table className="w-full min-w-[720px] text-start text-xs">
          <thead className="sticky top-0 z-20 bg-bg-card">
            <tr className="bg-bg-card text-2xs text-text-secondary">
              {COLS.map((c, i) =>
                c.key ? (
                  <th key={c.label} className="px-2 py-2 font-bold">
                    <button
                      type="button"
                      onClick={() => toggle(c.key as SortKey)}
                      title={c.title}
                      className="hover:text-accent-blue"
                    >
                      {c.label} {sortKey === c.key ? (desc ? '↓' : '↑') : ''}
                    </button>
                  </th>
                ) : (
                  <th key={i} className="px-2 py-2 font-bold" title={c.title}>
                    {c.label}
                  </th>
                ),
              )}
            </tr>
          </thead>
        <tbody>
          {padTop > 0 ? <tr aria-hidden style={{ height: padTop }} /> : null}
          {virtualRows.map((vi) => {
            const r = sorted[vi.index];
            if (!r) return null;
            return <ScreenerRow key={r.symbol} row={r} thresholds={thresholds} onSelect={onSelect} />;
          })}
          {padBottom > 0 ? <tr aria-hidden style={{ height: padBottom }} /> : null}
        </tbody>
        </table>
      </div>
      <div className="border-t border-border-c bg-bg-secondary/60 px-4 py-1.5 text-2xs text-text-muted">
        ✓ قبول · ✗ مردود · سلول بی‌داده به‌جای برچسب عمومی، علت را می‌نویسد (مثلاً «{gapLabel('1a_monetary_growth')}»
        ⇐ همان شاخص در کدال داده ندارد؛ با نگه‌داشتن ماوس علت و راه‌حل کامل می‌آید) — سطر حذف نمی‌شود
        · «سابقهٔ ناقص» = {toFaDigits(2)} سالِ موجودِ EPS (شاخص ۲) نمایش داده می‌شود ولی گیت {toFaDigits(EPS_REQUIRED_YEARS)} ساله رد است
        {excludedCount > 0 && !showExcluded
          ? ` · ${toFaDigits(excludedCount)} ردیفِ مشمول دروازه‌های سخت پنهان شد`
          : ''}
        {nonCompanyCount > 0
          ? ` · ${toFaDigits(nonCompanyCount)} صندوق/کارگزاری/اوراق با فیلتر نوع نماد حذف شد`
          : ''}
      </div>
    </div>
  );
}
