// features/fundamental/ui/FtsScreenTable.tsx -- دیده‌بان کلان بنیادی
// ماتریس مقایسه‌ای ۵ شاخص جزوهٔ FTS + ستون امتیاز نردبان (۰..۵) قابل سورت.
// کلیک روی سطر نماد را در استور فعال می‌کند تا سایدبار چپ و نمای
// کالبدشکافی باز شود. جای برچسب عمومی «شکاف داده»، علتِ واقعیِ هر شاخص
// نمایش داده می‌شود (lib/gapReason) — نه خطای خام، نه کرش.
// دروازه‌های سخت (قیمت‌گذاری دستوری/تعلیق): ردیف‌های excluded پیش‌فرض
// حذف می‌شوند؛ سوییچ «نمایش ردیف‌های حذف‌شده» فقط برای بازرسی آن‌هاست.
// قلمرو جدول: فقط «شرکت‌های تولیدی و خدماتی» — صندوق‌ها، کارگزاری‌ها،
// اوراق و مشتقه‌ها به‌صورت پیش‌فرض حذف می‌شوند (فیلتر نوع نماد).
import { memo, useMemo, useRef, useState, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { FTS_COLUMN_LABEL } from '@shared/lib/ftsLabels';
import { jalaliOf, pickAssemblyBadge, pickCapitalBadge, type AssemblyBadgeInfo, type CalEvent, type CapitalIncreaseBadge } from '../lib/assemblyEvent';
import { toFaDigits } from '@shared/lib/fmt';
import { DownloadRowsButton } from '@shared/components/DownloadRowsButton';
import { toExportTable, type ExportCell } from '@shared/lib/tableExport';
import { matchFa } from '@shared/lib/normalizeFa';
import { absurdHint, fmtPctGrouped, fmtRatioGrouped, isAbsurdPct } from '../lib/numFmt';
import { EmptyState } from '@shared/components/EmptyState';
import type { FtsScreenRow } from '../api/useFtsScreen';
import { isFundamentalCompany, isFinancialOrHolding } from '../lib/assetScope';
import {
  EPS_PARTIAL_TESTID,
  EPS_REQUIRED_YEARS,
  epsChangeText,
  epsChanges,
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

/** شمارهٔ شاخص با «—» از نامش جدا می‌شود؛ بی‌جداکننده، «۳ حاشیه…» یک عددِ بخشی از نام خوانده می‌شد. */
const COLS: { key: SortKey | null; label: string; title: string }[] = [
  { key: null, label: 'نماد', title: '' },
  { key: 'rev_growth', label: '۱ — رشد فروش (الف/ب)', title: 'الف: رشد ریالی فروش | ب: رشد تولیدی (تناژ)' },
  { key: null, label: '۲ — روند EPS', title: 'وضعیت و رشد سال‌به‌سال EPS' },
  { key: 'gross_margin', label: FTS_COLUMN_LABEL['gross_margin'], title: 'سود ناخالص ÷ درآمد عملیاتی' },
  { key: 'profit_potential_pct', label: FTS_COLUMN_LABEL['profit_potential'], title: 'سود ناخالص برآوردی ۱۲ماهه ÷ ارزش بازار یا نسبت فروش به ارزش بازار' },
  { key: null, label: '۵ — صنعت', title: 'رژیم قیمت‌گذاری صنعت' },
  { key: 'score', label: FTS_COLUMN_LABEL['score'], title: 'نردبان بنیادی ۰ تا ۵' },
];

/** سلول‌هایِ متنِ خالصِ یک ردیف، به همان ترتیبِ COLS — برایِ «دانلودِ فقطِ ردیف‌های
 *  دیدنی». همان قالب‌سازهایِ سلول خوانده می‌شود (`fmtPctGrouped`/`toFaDigits`) تا
 *  عددِ فایل با عددِ رویِ صفحه یکی باشد؛ هیچ فرمولِ دومی اینجا نوشته نمی‌شود. */
export function screenRowCells(r: FtsScreenRow): ExportCell[] {
  const pct = (v: number | null | undefined) => (v == null ? '—' : fmtPctGrouped(v));
  const eps = Array.isArray(r.eps_series) && r.eps_series.length
    ? r.eps_series.map((v) => (v == null ? '—' : toFaDigits(v))).join(' ← ')
    : '—';
  return [
    `${r.symbol} — ${r.name ?? ''}`.trim(),
    `${pct(r.rev_growth)} (الف: ${r.i1_pass === true ? '✓' : r.i1_pass === false ? '✗' : '؟'} / ب: ${r.i2_pass === true ? '✓' : r.i2_pass === false ? '✗' : '؟'})`,
    `${eps}${r.eps_last != null ? ` | ${toFaDigits(r.eps_last)}` : ''}${r.eps_data_gap ? ' | بی‌داده' : ''}`,
    pct(r.gross_margin),
    r.profit_potential_pct == null ? '—' : pct(r.profit_potential_pct),
    `${r.sector_name ?? '—'} (${r.pricing_mode === 'regulated' ? 'دستوری' : 'آزاد'})`,
    toFaDigits(r.score),
  ];
}

/** نمایش جریان سال‌به‌سال EPS همراه با اتصال فلش و درصد رشد YoY (#101).
 *  درصد از lib/epsHistory می‌آید — همان منبعِ کارت FTS و نردبان EPS، تا یک
 *  عدد در سه نما یکی خوانده شود. جایی که درصد قابل محاسبه نیست (سالِ غایب،
 *  مبنای صفر/زیان، یا سالِ نخست) هیچ درصدی نشان داده نمی‌شود: نه ۰٪، نه
 *  ۱۰۰٪ِ جعلی، نه فلشِ سبز/سرخ. */
function EpsFlow({
  series,
  trendText,
}: {
  series?: (number | null)[] | null;
  trendText?: string | null;
}) {
  if (!Array.isArray(series) || series.length === 0) {
    return <span>—</span>;
  }
  const clean = series.map((v) => (typeof v === 'number' && Number.isFinite(v) ? v : null));
  if (clean.every((v) => v === null)) {
    return <span>—</span>;
  }
  const changes = epsChanges(clean);

  return (
    <div
      dir="rtl"
      className="inline-flex items-center gap-1 text-sm font-bold text-text-primary"
      title={trendText ?? undefined}
    >
      {clean.map((val, idx) => {
        // فلشِ پس از هر عدد، رشدِ آن عدد تا عددِ بعدی را می‌گوید ⇒ changes[idx+1]
        const growthPct = changes[idx + 1] ?? null;
        const valStr =
          val != null
            ? toFaDigits(Number.isInteger(val) ? String(val) : val.toFixed(2).replace(/\.?0+$/, ''))
            : '—';

        return (
          <span key={idx} className="inline-flex items-center gap-1">
            <span className="whitespace-nowrap">{valStr}</span>
            {idx < clean.length - 1 ? (
              <span className="inline-flex flex-col items-center justify-center px-0.5" aria-hidden>
                {growthPct != null ? (
                  <span
                    className={`text-2xs font-black leading-none ${
                      growthPct > 0 ? 'text-accent-green' : growthPct < 0 ? 'text-accent-red' : 'text-text-muted'
                    }`}
                  >
                    {epsChangeText(growthPct)}
                  </span>
                ) : (
                  <span className="text-2xs text-text-muted leading-none">—</span>
                )}
                <span className="text-text-muted text-2xs leading-none">←</span>
              </span>
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

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

/** ارتفاع ثابت ردیف جدول (پیکسل) — همگام دقیق با DOM برای جلوگیری از لگ و پرش اسکرول */
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
      label={<span className="whitespace-nowrap leading-none text-accent-yellow font-semibold">{label}</span>}
      hintTitle={tooltip}
      evidence={evidence}
      compact
      testId={testId}
    />
  );
}

/** سلول بی‌داده با علتِ همان محور */
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
  stripe,
  assembly = null,
  capital = null,
}: {
  row: FtsScreenRow;
  /** برچسب مجمع این نماد (از نقشهٔ انبوهٔ والد) — null یعنی رویدادی نیست */
  assembly?: AssemblyBadgeInfo | null;
  /** برچسب «افزایش سرمایه» — هشدارِ تاریخ، بی‌هیچ حکمی */
  capital?: CapitalIncreaseBadge | null;
  thresholds?: Record<string, unknown> | null;
  onSelect: (symbol: string) => void;
  /** زبرا از ایندکسِ ردیف در آرایهٔ مرتب‌شده می‌آید — نه از :nth-child.
   *  اسپیسرهای مجازی‌ساز (padTop) برابریِ CSS را جابه‌جا می‌کنند. */
  stripe: 'odd' | 'even';
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
              const i1a = verdictOf(r.i1a_pass ?? r.i1_pass);
              const i1b = verdictOf(r.i1b_pass);
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
                  style={{ height: ROW_H }}
                  className={`h-[46px] border-b border-border-c/40 transition-colors ${
                    r.excluded
                      ? 'cursor-not-allowed bg-accent-red/5 opacity-55'
                      : `cursor-pointer group ${stripe === 'odd' ? 'bg-bg-secondary' : 'bg-bg-primary'} hover:bg-accent-blue/10`
                  }`}
                  data-testid="fts-screen-row"
                >
                  {/* ستونِ چسبان (RTL): نماد در لبهٔ start می‌چسبد تا با اسکرول افقی، ردیف گم نشود.
                      پس‌زمینهٔ توپر لازم است چون بک‌گراندِ ردیف رویِ <tr> است و ستون‌های دیگر از زیرش رد می‌شوند؛
                      ولی باید دقیقاً هم‌رنگِ زبرایِ همان ردیف باشد — پیش‌تر bg-bg-cardِ ثابت بود و
                      کاربر «خط‌چینی» را در ستونِ نماد نمی‌دید. group-hover همان hoverِ ردیف را دنبال می‌کند.
                      z-10 زیرِ هدرِ چسبان (z-20) می‌ماند تا در محور عمودی هدر برنده باشد. */}
                  <td className={`sticky start-0 z-10 border-e border-[var(--hairline)] px-3 py-1.5 align-middle transition-colors ${
                    r.excluded
                      ? 'bg-accent-red/5'
                      : stripe === 'odd'
                        ? 'bg-bg-secondary group-hover:bg-accent-blue/10'
                        : 'bg-bg-primary group-hover:bg-accent-blue/10'
                  }`}>
                    <div className="flex flex-col justify-center min-w-0">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className={`font-bold text-sm text-text-primary tracking-wide ${r.excluded ? 'line-through decoration-accent-red/60' : ''}`}>
                          {r.symbol}
                        </span>
                        {r.tech_hourglass_active ? (
                          <span className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold bg-accent-green/20 text-accent-green border border-accent-green/30" title="استراتژی ساعت شنی FTS فعال (خرید ۲x-۴x)">
                            ساعت شنی
                          </span>
                        ) : null}
                        {r.tech_jet ? (
                          <span className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold bg-accent-blue/20 text-accent-blue border border-accent-blue/30" title="ستاپ جت FTS (شکست مقاومت)">
                            جت
                          </span>
                        ) : null}
                        {r.tech_matrix_decision === 'REJECT' ? (
                          <span className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold bg-accent-red/20 text-accent-red border border-accent-red/30" title={r.tech_matrix_desc ?? 'ممنوعیت ورود FTS'}>
                            وتوی روند
                          </span>
                        ) : null}
                        {/* مجمع پیش‌رو — وتو (قرمز) یا فقط هشدار (زرد/آبی).
                            داورِ وتو بک‌اند است (`assembly_veto` در /api/screener،
                            بیرونِ کش و تازه در هر درخواست)؛ برچسبِ هشدار از
                            /api/calendar/upcoming می‌آید. هر دو یک افقِ ۱۴ روزه
                            دارند — گاردِ برابری: dev/test_calendar_v92.py بخش ۴.
                            تاریخ روی خودِ برچسب می‌ماند، چون خواستِ مالک
                            «هشدارِ تاریخِ مجمع» است نه فقط یک واژهٔ قرمز. */}
                        {r.assembly_veto ? (
                          <span
                            data-testid="row-assembly-veto-badge"
                            title={`مجمع عمومی در پیش است — ورود وتو شد${
                              r.assembly_date ? ` · تاریخ: ${jalaliOf(r.assembly_date)}` : ''
                            }${typeof r.assembly_days === 'number' ? ` · ${toFaDigits(r.assembly_days)} روز دیگر` : ''}`}
                            className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold border bg-accent-red/20 text-accent-red border-accent-red/30"
                          >
                            وتوی مجمع{r.assembly_date ? ` ${jalaliOf(r.assembly_date)}` : ''}
                          </span>
                        ) : assembly ? (
                          <span
                            data-testid={`row-${assembly.testId}`}
                            title={assembly.detail ? `${assembly.label} · ${assembly.detail}` : assembly.label}
                            className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold border ${
                              assembly.kind === 'near'
                                ? 'bg-accent-yellow/20 text-accent-yellow border-accent-yellow/30'
                                : 'bg-accent-blue/20 text-accent-blue border-accent-blue/30'
                            }`}
                          >
                            مجمع {assembly.jalali.split('-').slice(-2).join('/')}
                          </span>
                        ) : null}
                        {/* «افزایش سرمایه» — فقط برچسب. رأیِ pilot (#53): این رویداد
                            وتو نمی‌سازد و ردیف را خاکستری نمی‌کند؛ جایِ آن کنارِ
                            بجِ مجمع است، نه به‌جای آن. */}
                        {capital ? (
                          <span
                            data-testid={`row-${capital.testId}`}
                            title={
                              capital.detail
                                ? `افزایش سرمایه در پیش است — فقط هشدارِ تاریخ است، وتو نیست · تاریخ: ${capital.jalali} · ${capital.detail}`
                                : `افزایش سرمایه در پیش است — فقط هشدارِ تاریخ است، وتو نیست · تاریخ: ${capital.jalali}`
                            }
                            className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold border bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                          >
                            افزایش سرمایه {capital.jalali.split('-').slice(-2).join('/')}
                          </span>
                        ) : null}
                      </div>
                      <span className="truncate text-2xs text-text-muted leading-tight" title={r.name || r.sector_name || ''}>
                        {r.name || r.sector_name || ''}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 align-middle">
                    <div className="flex items-center justify-start gap-2 min-w-0">
                      <div className="shrink-0 flex items-center gap-1.5">
                        <span className="inline-flex items-center gap-0.5" title="۱-الف: رشد ریالی">
                          <span className="text-[10px] text-text-muted font-bold">الف</span>
                          {i1a === 'gap' ? (
                            <AxisGapMark axis="1a_monetary_growth" evidence={ev.i1a} />
                          ) : (
                            <PassMark
                              state={i1a}
                              evidence={ev.i1a}
                              testId="fts-mark-1a_monetary_growth"
                            />
                          )}
                        </span>
                        <span className="inline-flex items-center gap-0.5" title="۱-ب: رشد تولیدی (تناژ)">
                          <span className="text-[10px] text-text-muted font-bold">ب</span>
                          {isFinancialOrHolding(r) ? (
                            <span className="text-[9px] text-text-muted">N/A</span>
                          ) : i1b === 'gap' ? (
                            <AxisGapMark axis="1b_volume_growth" />
                          ) : (
                            <PassMark state={i1b} testId="fts-mark-1b_volume_growth" />
                          )}
                        </span>
                      </div>
                      <span
                        className={`num block min-w-0 text-end text-sm font-bold whitespace-nowrap ${
                          r.rev_growth == null
                            ? 'text-text-muted'
                            : r.rev_growth >= 0
                              ? 'text-accent-green'
                              : 'text-accent-red'
                        }`}
                        title={r.rev_growth == null ? VALUE_MISSING_WITH_VERDICT : (absurdHint(r.rev_growth) ?? undefined)}
                      >
                        {r.rev_growth == null ? '—' : fmtPctGrouped(r.rev_growth)}
                        {isAbsurdPct(r.rev_growth) ? ' ⚠' : ''}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 align-middle">
                    <div className="flex items-center justify-start gap-2 min-w-0">
                      <span className="shrink-0">
                        {epsPartialRejected ? (
                          <AuditBadge
                            state="fail"
                            label={<span className="whitespace-nowrap leading-none text-2xs font-semibold">{epsHist.label}</span>}
                            hintTitle={epsGapReason}
                            evidence={() => ({ ...ev.i2(), reason: epsGapReason })}
                            compact
                            testId={EPS_PARTIAL_TESTID}
                          />
                        ) : epsInsufficient || i2 === 'gap' ? (
                          /* F-10: برچسب علت‌دار می‌ماند، ولی tone از حکمِ موتور می‌آید */
                          <AuditBadge
                            state={i2 === 'pass' ? 'pass' : i2 === 'fail' ? 'fail' : 'na'}
                            label={<span className="whitespace-nowrap leading-none text-2xs font-semibold">{epsGapLabel(epsHist.realYears)}</span>}
                            hintTitle={`${epsGapReason} راه‌حل: ${gapReason('2_eps_trend').fix}`}
                            evidence={ev.i2}
                            compact
                            testId="eps-gap-reason"
                          />
                        ) : (
                          <PassMark state={i2} testId="fts-mark-2_eps_trend" />
                        )}
                      </span>
                      <div className="min-w-0 text-end overflow-hidden">
                        <EpsFlow series={r.eps_series} trendText={epsTrend ?? VALUE_MISSING_WITH_VERDICT} />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 align-middle">
                    <div className="flex items-center justify-start gap-2 min-w-0">
                      {/* تیکِ حکم در لبهٔ start (راست) و عدد بی‌فاصله کنارش — هر دو
                          زیرِ عنوانِ خودِ ستون؛ «عدد در انتهایِ مقابلِ ستون» باعث
                          می‌شد رقمِ ۲۸٪ زیرِ ستونِ کناری خوانده شود. */}
                      <span className="shrink-0">
                        {i3 === 'gap' ? (
                          isFinancialOrHolding(r) ? (
                            /* مؤسسهٔ مالی/هلدینگ: سود ناخالص ماهیتاً وجود ندارد → N/A نه «شکاف داده» */
                            <GapMark
                              label="N/A (ماهیت مالی)"
                              tooltip="بانک/بیمه/هلدینگ «سود ناخالص» گزارش نمی‌کند؛ این شاخص برای این ماهیت کاربرد ندارد — شکاف داده نیست."
                              evidence={ev.i3}
                              testId="fts-na-3_gross_margin"
                            />
                          ) : (
                            <AxisGapMark axis="3_gross_margin" evidence={ev.i3} />
                          )
                        ) : (
                          <PassMark
                            state={i3}
                            evidence={ev.i3}
                            testId="fts-mark-3_gross_margin"
                          />
                        )}
                      </span>
                      <span
                        className="num block min-w-0 text-end text-sm font-bold whitespace-nowrap text-text-primary"
                        title={r.gross_margin == null ? VALUE_MISSING_WITH_VERDICT : (absurdHint(r.gross_margin) ?? undefined)}
                      >
                        {r.gross_margin == null ? '—' : fmtPctGrouped(r.gross_margin)}
                        {isAbsurdPct(r.gross_margin) ? ' ⚠' : ''}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 align-middle">
                    <div className="flex items-center justify-start gap-2 min-w-0">
                      <span className="shrink-0">
                        {i4 === 'gap' ? (
                          isFinancialOrHolding(r) ? (
                            <GapMark
                              label="N/A (ماهیت مالی)"
                              tooltip="نسبت فروش/ارزش بازار برای بانک/بیمه/هلدینگ معنا ندارد؛ شکاف داده نیست."
                              evidence={ev.i4}
                              testId="fts-na-4_sales_to_mcap"
                            />
                          ) : (
                            <AxisGapMark axis="4_sales_to_mcap" evidence={ev.i4} />
                          )
                        ) : (
                          <PassMark
                            state={i4}
                            evidence={ev.i4}
                            testId="fts-mark-4_sales_to_mcap"
                          />
                        )}
                      </span>
                      <span
                        className="num block min-w-0 text-end text-sm font-bold whitespace-nowrap text-text-primary"
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
                    </div>
                  </td>
                  <td className="px-3 py-1.5 align-middle">
                    <div className="flex items-center justify-start gap-2 min-w-0">
                      <span className="shrink-0">
                        {i5 === 'gap' ? (
                          <AxisGapMark axis="5_industry" evidence={ev.i5} />
                        ) : (
                          <PassMark
                            state={i5}
                            evidence={ev.i5}
                            testId="fts-mark-5_industry"
                          />
                        )}
                      </span>
                      {r.excluded ? (
                        <span
                          className="block max-w-[14rem] truncate text-end text-2xs font-bold text-accent-red leading-tight"
                          title={r.exclusion_reasons ?? ''}
                        >
                          {r.exclusion_reasons}
                        </span>
                      ) : (
                        <span className="whitespace-nowrap text-xs font-semibold text-text-secondary text-end">
                          {r.pricing_mode === 'free' ? 'آزاد' : r.pricing_mode === 'mandatory' ? 'دستوری' : r.pricing_mode === 'neutral' ? 'سایر صنایع' : '—'}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-1.5 align-middle text-start">
                    <span
                      className={`num inline-flex h-6 w-9 items-center justify-center rounded-full border text-xs font-black shadow-xs ${
                        r.score == null
                          ? 'border-border-c/70 bg-bg-card/50 text-text-muted'
                          : r.score >= 4
                            ? 'border-accent-green/40 bg-accent-green/15 text-accent-green'
                            : r.score >= 3
                              ? 'border-accent-yellow/40 bg-accent-yellow/15 text-accent-yellow'
                              : 'border-accent-red/40 bg-accent-red/15 text-accent-red'
                      }`}
                    >
                      <span className="num font-bold">{r.score == null ? '؟' : toFaDigits(r.score)}</span>
                    </span>
                  </td>
                </tr>
              );
});

export function FtsScreenTable({
  rows,
  onSelect,
  thresholds,
  onDbUpdate,
  dbUpdate,
  assemblyEvents = null,
  capitalEvents = null,
  settingsSlot,
}: {
  rows: FtsScreenRow[];
  onSelect: (symbol: string) => void;
  /** تارگت‌های کانفیگ FTS (پاسخ /api/screener) برای کارت «چرا این وضعیت؟» */
  thresholds?: Record<string, unknown> | null;
  /** بروزرسانی دیتابیس کدال از snapshot گیت‌هاب (POST /api/sync/codal/db-download) */
  onDbUpdate?: () => void;
  /** وضعیت زندهٔ دانلود/ادغام برای لیبل دکمه (GET /api/sync/codal/db-status) */
  dbUpdate?: { running: boolean; stage: string; percent?: number; detail?: string; error?: string } | null;
  /** رویدادهای مجمعِ همهٔ نمادها از /api/calendar/upcoming — یک درخواست برای کل جدول */
  assemblyEvents?: Record<string, CalEvent[]> | null;
  /** «افزایش سرمایه»هایِ پیش‌رو — همان پاسخِ انبوه، کلیدِ دومِ `capital` */
  capitalEvents?: Record<string, CalEvent[]> | null;
  /** اسلاتِ تزریقیِ نوار جدول — مثلاً دکمهٔ تنظیمات FTS (بزرگ‌تر و افقی) */
  settingsSlot?: ReactNode;
}) {
  /** برچسب مجمعِ یک نماد؛ منطق انتخاب در lib/assemblyEvent.ts (آزمون‌شده) است */
  const assemblyBadge = (sym: string) =>
    assemblyEvents ? pickAssemblyBadge(assemblyEvents[sym] ?? []) : null;
  const capitalBadge = (sym: string) =>
    capitalEvents ? pickCapitalBadge(capitalEvents[sym] ?? []) : null;

  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [desc, setDesc] = useState(true);
  /** شاخص‌هایی که کاربر خواسته نمادهای مردود/ناقص‌شان از جدول حذف شود (دراور تنظیمات) */
  const excludeAxes = useExcludeAxes();

  const [strategicPreset, setStrategicPreset] = useState<'all' | 'super' | 'jet' | 'hourglass'>('all');
  /** جستجوی همین جدول — حالتِ محلی است نه سراسری: نمادی که اینجا جستجو می‌شود
   *  فقط همین جدول را تنگ می‌کند و به تب‌های دیگر (تابلو/تکنیکال) سرریز نمی‌کند. */
  const [query, setQuery] = useState('');

  /** تعداد ردیف‌های حذف‌شده توسط دروازه‌های سخت */
  const excludedCount = useMemo(() => rows.filter((r) => r.excluded === true).length, [rows]);

  /** فیلتر نوع نماد (Asset Type): صندوق/کارگزاری/اوراق/مشتقه پیش‌فرض حذف */
  const nonCompanyCount = useMemo(
    () => rows.filter((r) => !isFundamentalCompany(r)).length,
    [rows],
  );

  /** فیلتر «حذف بر اساس شاخص» روی ردیف‌های مجاز اعمال می‌شود (شمار حذف‌شده‌ها برای نمایش) */
  const { rows: rowsAfterAxisFilter, hidden: hiddenByAxes } = useMemo(
    () => applyExcludeFilter(rows, excludeAxes),
    [rows, excludeAxes],
  );

  const presetCounts = useMemo(() => {
    const base = rowsAfterAxisFilter.filter((r) => isFundamentalCompany(r) && r.excluded !== true);
    return {
      all: base.length,
      super: base.filter((r) => r.score >= 4 && r.pricing_mode === 'free').length,
      // «ستاپ جت» یعنی آخرینِ کندل پلکانِ مقاومتِ جزوه را شکسته باشد --
      // همان tech_jet که موتورِ اسکرینر از رویِ کندل‌ها حساب می‌کند. پیش از
      // این این چیپ i1_pass را می‌شمرد و نامش را جت می‌گذاشت.
      jet: base.filter((r) => r.tech_jet === true && r.pricing_mode === 'free').length,
      hourglass: base.filter((r) => r.score === 5 && r.excluded !== true).length,
    };
  }, [rowsAfterAxisFilter]);

  const visible = useMemo(
    () => {
      let base = rowsAfterAxisFilter.filter((r) => r.excluded !== true && isFundamentalCompany(r));

      const q = query.trim();
      if (q) base = base.filter((r) => matchFa(r.symbol, q) || matchFa(r.name, q) || matchFa(r.sector_name, q));

      if (strategicPreset === 'super') {
        base = base.filter((r) => r.score >= 4 && r.pricing_mode === 'free');
      } else if (strategicPreset === 'jet') {
        base = base.filter((r) => r.tech_jet === true && r.pricing_mode === 'free');
      } else if (strategicPreset === 'hourglass') {
        base = base.filter((r) => r.score === 5 && r.excluded !== true);
      }

      return base;
    },
    [rowsAfterAxisFilter, strategicPreset, query],
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
    return <EmptyState title="ردیفی از غربالگری FTS نیامد" hint="کارنامهٔ ماهانهٔ کدال هنوز به‌روز نشده است" />;
  }

  return (
    // min-w-0 + max-w-full: بدون این دو، پنل به اندازهٔ min-w-[1240px]ِ جدول
    // پهن می‌شود و overflow-autoِ درونش هرگز فعال نمی‌شود — نتیجه: کلِ صفحه
    // در دیدگاه‌های کوچک‌تر از ۱۲۴۰px (مثلاً ۷۶۸px) ۵۶۲px بیرون از کادر
    // می‌افتد و کاربر به ستون‌ها نمی‌رسد.
    <div className="glass-panel panel-in overflow-hidden rounded-2xl min-w-0 max-w-full">
      {/* نوار جدول: راست = جستجو و دیتابیس کدال و شمارش، چپ = تنظیمات (#179) */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--hairline)] px-4 py-2">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1 rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-2 py-0.5 focus-within:border-border-accent">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              type="search"
              placeholder="جستجوی نماد…"
              aria-label="جستجوی نماد در جدول غربالگری"
              data-testid="fts-search"
              className="w-28 bg-transparent text-2xs text-text-primary outline-none placeholder:text-text-muted"
            />
            {query ? (
              <button
                type="button"
                onClick={() => setQuery('')}
                aria-label="پاک کردن جستجو"
                data-testid="fts-search-clear"
                className="text-2xs font-bold text-text-muted hover:text-text-primary"
              >
                ×
              </button>
            ) : null}
          </label>
          <button
            type="button"
            onClick={() => onDbUpdate?.()}
            disabled={!onDbUpdate || dbUpdate?.running}
            data-testid="fts-db-update"
            title={dbUpdate?.error
              ? dbUpdate.error
              : 'جدیدترین صورت‌مالی‌های کدال را می‌گیرد و با دادهٔ همین رایانه ادغام می‌کند؛ ردیفی که تازه‌تر باشد دست‌نخورده می‌ماند.'}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-2xs font-bold transition-colors ${
              dbUpdate?.error
                ? 'border-accent-red/40 bg-accent-red/10 text-accent-red'
                : 'border-[var(--hairline)] bg-bg-card/60 text-text-secondary hover:border-border-accent hover:text-accent-blue disabled:opacity-50'
            }`}
          >
            <svg className={`h-3 w-3 ${dbUpdate?.running ? 'animate-pulse' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
            </svg>
            {dbUpdate?.running
              ? dbUpdate.stage === 'downloading' && dbUpdate.percent
                ? `دیتابیس کدال ${toFaDigits(Math.round(dbUpdate.percent))}٪`
                : dbUpdate.stage === 'rotating'
                  ? 'چرخش IP…'
                  : dbUpdate.stage === 'merging'
                    ? 'در حال ادغام…'
                    : 'در حال دریافت…'
              : dbUpdate?.error
                ? 'خطای دیتابیس کدال'
                : 'دیتابیس کدال'}
          </button>
          <span className="num text-2xs text-text-muted" title="فقط شرکت‌های تولیدی و خدماتی — صندوق‌ها و کارگزاری‌ها حذف شده‌اند">
            {toFaDigits(visible.length)} شرکت از {toFaDigits(rows.length)}
          </span>
          <DownloadRowsButton
            base="بنیادی FTS"
            testId="download-screen-rows"
            count={sorted.length}
            title={`دانلودِ ${toFaDigits(sorted.length)} ردیفِ دیدنی — با همین فیلتر، جستجو و مرتب‌سازی`}
            getTable={() => toExportTable(COLS.map((c) => c.label), sorted, screenRowCells)}
          />
        </div>
        {settingsSlot ?? <span />}
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

      {/* پری‌ست‌های استراتژیک ۱-کلیکه طبق جزوه FTS */}
      <div
        className="flex flex-wrap items-center gap-1.5 border-b border-[var(--hairline)] bg-bg-card/30 px-4 py-2 text-2xs"
        data-testid="fts-strategic-presets"
      >
        <span className="font-bold text-text-muted me-1">پری‌ست‌های استراتژیک FTS:</span>
        <button
          type="button"
          onClick={() => setStrategicPreset('all')}
          className={`rounded-lg border px-2.5 py-1 font-bold transition-all ${
            strategicPreset === 'all'
              ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-[0_0_8px_rgba(56,189,248,0.2)]'
              : 'border-[var(--hairline)] bg-bg-primary text-text-secondary hover:text-text-primary'
          }`}
        >
          همه شرکت‌ها ({toFaDigits(presetCounts.all)})
        </button>
        <button
          type="button"
          onClick={() => setStrategicPreset('super')}
          title="شرکت‌های با امتیاز ۴ یا ۵ و صنعت غیردستوری"
          className={`rounded-lg border px-2.5 py-1 font-bold transition-all ${
            strategicPreset === 'super'
              ? 'border-neon-cyan bg-neon-cyan/15 text-neon-cyan shadow-[0_0_8px_rgba(6,182,212,0.25)]'
              : 'border-[var(--hairline)] bg-bg-primary text-text-secondary hover:text-text-primary'
          }`}
        >
          💎 سوپر بنیادی‌ها ({toFaDigits(presetCounts.super)})
        </button>
        <button
          type="button"
          onClick={() => setStrategicPreset('jet')}
          title="رشد فروش بالای ۴۰٪ و صنعت آزاد"
          className={`rounded-lg border px-2.5 py-1 font-bold transition-all ${
            strategicPreset === 'jet'
              ? 'border-accent-green bg-accent-green/15 text-accent-green shadow-[0_0_8px_rgba(16,185,129,0.25)]'
              : 'border-[var(--hairline)] bg-bg-primary text-text-secondary hover:text-text-primary'
          }`}
        >
          🚀 نامزدهای ستاپ جت ({toFaDigits(presetCounts.jet)})
        </button>
        <button
          type="button"
          onClick={() => setStrategicPreset('hourglass')}
          title="امتیاز کامل ۵ از ۵ برای استراتژی ساعت شنی چندساله"
          className={`rounded-lg border px-2.5 py-1 font-bold transition-all ${
            strategicPreset === 'hourglass'
              ? 'border-accent-yellow bg-accent-yellow/15 text-accent-yellow shadow-[0_0_8px_rgba(234,179,8,0.25)]'
              : 'border-[var(--hairline)] bg-bg-primary text-text-secondary hover:text-text-primary'
          }`}
        >
          ⏳ ساعت شنی FTS ({toFaDigits(presetCounts.hourglass)})
        </button>
      </div>

      {/* اسکرول‌کانتینر جدول: ارتفاع متناسب با ویوپورت تا پایینِ
          جدول فضای خالی نماند و در هر رزولوشنی (به‌ویژه لپ‌تاپ) درست و کامل پر شود. */}
      <div ref={scrollRef} data-testid="fts-screen-scroll" className="h-[calc(100dvh-200px)] min-h-[320px] overflow-auto overscroll-contain">
        <table className="w-full min-w-[1240px] table-fixed text-start text-xs">
          <colgroup>
            {/* ستونِ نماد ۱۸٪ بود که در ۱۹۲۰ پهنای بی‌مصرف می‌گرفت؛ ۱۴٪ اندازهٔ
                خودِ نماد + یک برچسبِ کوتاه است. عرضِ آزادشده به سری EPS رفت. */}
            <col className="w-[14%]" />
            {/* ستون شاخص ۱ دو تیک (الف/ب) + عددِ تا ۴ رقم دارد؛ با ۱۲٪ عددِ ۲۴۴.۷٪
                از خانه بیرون می‌زد (اندازه‌گیری روی مرورگر واقعی). */}
            <col className="w-[13%]" />
            {/* شاخص ۲ سری EPS دارد (سه عدد + درصد رشد) — با بزرگ‌ترشدنِ فونتِ این ستون،
                عرضش از ستونِ صنعت گرفته شد که کوتاه‌ترین مقدار را دارد. */}
            <col className="w-[28%]" />
            <col className="w-[11%]" />
            <col className="w-[12%]" />
            <col className="w-[14%]" />
            <col className="w-[7%]" />
          </colgroup>
          <thead className="sticky top-0 z-20 bg-bg-card shadow-xs">
            <tr className="bg-bg-card text-2xs text-text-secondary border-b border-[var(--hairline)]">
              {COLS.map((c, i) =>
                c.key ? (
                  <th key={c.label} className="px-3 py-2.5 font-bold tracking-wide text-start">
                    <button
                      type="button"
                      onClick={() => toggle(c.key as SortKey)}
                      title={c.title}
                      className="inline-flex items-center gap-1 hover:text-accent-blue transition-colors"
                    >
                      {c.label} {sortKey === c.key ? (desc ? '↓' : '↑') : ''}
                    </button>
                  </th>
                ) : (
                  <th
                    key={i}
                    className={`px-3 py-2.5 font-bold tracking-wide text-start ${i === 0 ? 'sticky start-0 z-30 border-e border-[var(--hairline)] bg-bg-card' : ''}`}
                    title={c.title}
                  >
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
            return (
              <ScreenerRow
                key={r.symbol}
                row={r}
                thresholds={thresholds}
                onSelect={onSelect}
                stripe={vi.index % 2 === 0 ? 'odd' : 'even'}
                assembly={assemblyBadge(r.symbol)}
                capital={capitalBadge(r.symbol)}
              />
            );
          })}
          {padBottom > 0 ? <tr aria-hidden style={{ height: padBottom }} /> : null}
        </tbody>
        </table>
      </div>
      <div className="border-t border-border-c bg-bg-secondary/60 px-4 py-1.5 text-2xs text-text-muted">
        ✓ قبول · ✗ مردود · سلول بی‌داده به‌جای برچسب عمومی، علت را می‌نویسد (مثلاً «{gapLabel('1a_monetary_growth')}»
        ⇐ همان شاخص در کدال داده ندارد؛ با نگه‌داشتن ماوس علت و راه‌حل کامل می‌آید) — سطر حذف نمی‌شود
        · «سابقهٔ ناقص» = {toFaDigits(2)} سالِ موجودِ EPS (شاخص ۲) نمایش داده می‌شود ولی گیت {toFaDigits(EPS_REQUIRED_YEARS)} ساله رد است
        {excludedCount > 0
          ? ` · ${toFaDigits(excludedCount)} ردیفِ مشمول دروازه‌های سخت پنهان شد`
          : ''}
        {nonCompanyCount > 0
          ? ` · ${toFaDigits(nonCompanyCount)} صندوق/کارگزاری/اوراق با فیلتر نوع نماد حذف شد`
          : ''}
      </div>
    </div>
  );
}
