// features/fundamental/ui/FtsScreenTable.tsx -- دیده‌بان کلان بنیادی
// ماتریس مقایسه‌ای ۵ شاخص جزوهٔ FTS + ستون امتیاز نردبان (۰..۵) قابل سورت.
// کلیک روی سطر نماد را در استور فعال می‌کند تا سایدبار چپ و نمای
// کالبدشکافی باز شود. جای برچسب عمومی «شکاف داده»، علتِ واقعیِ هر شاخص
// نمایش داده می‌شود (lib/gapReason) — نه خطای خام، نه کرش.
// دروازه‌های سخت (قیمت‌گذاری دستوری/تعلیق): ردیف‌های excluded پیش‌فرض
// حذف می‌شوند؛ سوییچ «نمایش ردیف‌های حذف‌شده» فقط برای بازرسی آن‌هاست.
// قلمرو جدول: فقط «شرکت‌های تولیدی و خدماتی» — صندوق‌ها، کارگزاری‌ها،
// اوراق و مشتقه‌ها به‌صورت پیش‌فرض حذف می‌شوند (فیلتر نوع نماد).
import { useMemo, useState } from 'react';
import { toFaDigits, fmtPct } from '@shared/lib/fmt';
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
import { AuditBadge, type AuditEvidence } from '../components/AuditBadge';
import { screenAuditEvidence } from '../lib/auditEvidence';

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

function cellState(pass: boolean | null | undefined, value: number | null | undefined): CellState {
  if (pass == null || value == null) return 'gap';
  return pass ? 'pass' : 'fail';
}

const STATE_BADGE: Record<'pass' | 'fail', { tone: 'green' | 'red'; label: string }> = {
  pass: { tone: 'green', label: '✓' },
  fail: { tone: 'red', label: '✗' },
};

/** نشان قبول/مردود — حالت‌های «partial» و «gap» هرگز به اینجا نمی‌رسند
 *  (پیش از آن با برچسب علت‌دار یا برچسب سابقهٔ ناقص رندر می‌شوند). */
function PassMark({
  state,
  evidence,
  testId,
}: {
  state: CellState;
  evidence?: AuditEvidence;
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
  evidence?: AuditEvidence;
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
function AxisGapMark({ axis, evidence }: { axis: GapAxis; evidence?: AuditEvidence }) {
  return (
    <GapMark
      label={gapLabel(axis)}
      tooltip={gapTooltip(axis)}
      evidence={evidence}
      testId={`fts-gap-reason-${axis}`}
    />
  );
}

export function FtsScreenTable({
  rows,
  onSelect,
  thresholds,
}: {
  rows: FtsScreenRow[];
  onSelect: (symbol: string) => void;
  /** تارگت‌های کانفیگ FTS (پاسخ /api/screener) برای کارت «چرا این وضعیت؟» */
  thresholds?: Record<string, unknown> | null;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [desc, setDesc] = useState(true);
  /** دروازه‌های سخت فعال‌اند → ردیف‌های excluded پیش‌فرض حذف می‌شوند؛ سوییچ فقط برای بازرسی */
  const [showExcluded, setShowExcluded] = useState(false);

  /** فیلتر نوع نماد (Asset Type): صندوق/کارگزاری/اوراق/مشتقه پیش‌فرض حذف */
  const excludedCount = useMemo(() => rows.filter((r) => r.excluded === true).length, [rows]);
  const nonCompanyCount = useMemo(
    () => rows.filter((r) => !isFundamentalCompany(r)).length,
    [rows],
  );

  const visible = useMemo(
    () => {
      const base = showExcluded ? rows : rows.filter((r) => r.excluded !== true);
      // حتی در حالت بازرسی excluded، صندوق‌ها/کارگزاری‌ها/مشتقه‌ها می‌مانند؟ نه —
      // «نمایش ردیف‌های حذف‌شده» فقط دروازه‌های سخت را برمی‌گرداند؛ قلمرو
      // شرکت‌محورِ جدول بنیادی روی هر دو حالت اعمال می‌شود.
      return base.filter((r) => isFundamentalCompany(r));
    },
    [rows, showExcluded],
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

  if (rows.length === 0) {
    return <EmptyState title="ردیفی از غربالگری FTS نیامد" hint="کارنامهٔ ماهانهٔ کدال هنوز سینک نشده است" />;
  }

  return (
    <div className="glass-panel panel-in overflow-hidden rounded-2xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--hairline)] px-4 py-2.5">
        <h3 className="text-sm font-black text-text-primary">دیده‌بان کلان بنیادی — ماتریس ۵ شاخص FTS</h3>
        <div className="flex items-center gap-3">
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
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-start text-xs">
          <thead>
            <tr className="bg-bg-card/70 text-2xs text-text-secondary">
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
            {sorted.map((r) => {
              const i1 = cellState(r.i1_pass, r.rev_growth);
              /** شاخص ۲ — چهاردحالته از روی خودِ داده (lib/epsHistory):
               *  pass / partial «مردود — سابقهٔ ناقص (۲ از ۳ سال)» / fail / gap (<۲ سال) */
              const epsHist = epsHistory(
                r.eps_series,
                r.eps_years_required ?? EPS_REQUIRED_YEARS,
                r.eps_years_available,
              );
              const i2: CellState =
                epsHist.state === 'partial'
                  ? 'partial'
                  : epsHist.state === 'insufficient'
                    ? r.eps_data_gap === false
                      ? r.i2_pass
                        ? 'pass'
                        : 'fail'
                      : 'gap'
                    : r.i2_pass
                      ? 'pass'
                      : 'fail';
              const i3 = cellState(r.i3_pass, r.gross_margin);
              const i4Value = r.profit_potential_pct ?? r.sales_to_mcap ?? null;
              const i4 = cellState(r.i4_pass, i4Value);
              const i5: CellState = r.pricing_mode == null ? 'gap' : r.i5_pass ? 'pass' : 'fail';
              const epsTrend = epsSeriesText(r.eps_series);
              /** برچسب و علت از همان منبع حقیقتِ نردبان EPS و drill-down */
              const epsPartialRejected = i2 === 'partial';
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
                      <span className={`num ${r.rev_growth != null && r.rev_growth >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                        {r.rev_growth == null ? '—' : fmtPct(r.rev_growth)}
                      </span>
                      {i1 === 'gap' ? (
                        <AxisGapMark axis="1a_monetary_growth" evidence={screenAuditEvidence('1a_monetary_growth', r, thresholds)} />
                      ) : (
                        <PassMark
                          state={i1}
                          evidence={screenAuditEvidence('1a_monetary_growth', r, thresholds)}
                          testId="fts-mark-1a_monetary_growth"
                        />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <span className="num text-text-secondary" title={epsTrend ?? ''}>
                        {epsTrend ?? '—'}
                      </span>
                      {epsPartialRejected ? (
                        <AuditBadge
                          state="fail"
                          label={epsHist.label}
                          hintTitle={epsGapReason}
                          evidence={{
                            ...screenAuditEvidence('2_eps_trend', r, thresholds),
                            reason: epsGapReason,
                          }}
                          compact
                          testId={EPS_PARTIAL_TESTID}
                        />
                      ) : i2 === 'gap' ? (
                        <GapMark
                          evidence={screenAuditEvidence('2_eps_trend', r, thresholds)}
                          label={epsGapLabel(epsHist.realYears)}
                          tooltip={`${epsGapReason} راه‌حل: ${gapReason('2_eps_trend').fix}`}
                          testId="eps-gap-reason"
                        />
                      ) : (
                        <PassMark state={i2} />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <span className="num text-text-primary">{r.gross_margin == null ? '—' : fmtPct(r.gross_margin)}</span>
                      {i3 === 'gap' ? (
                        <AxisGapMark axis="3_gross_margin" evidence={screenAuditEvidence('3_gross_margin', r, thresholds)} />
                      ) : (
                        <PassMark
                          state={i3}
                          evidence={screenAuditEvidence('3_gross_margin', r, thresholds)}
                          testId="fts-mark-3_gross_margin"
                        />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <span className="num text-text-primary">
                        {r.profit_potential_pct == null ? '—' : fmtPct(r.profit_potential_pct)}
                      </span>
                      {i4 === 'gap' ? (
                        <AxisGapMark axis="4_sales_to_mcap" evidence={screenAuditEvidence('4_sales_to_mcap', r, thresholds)} />
                      ) : (
                        <PassMark
                          state={i4}
                          evidence={screenAuditEvidence('4_sales_to_mcap', r, thresholds)}
                          testId="fts-mark-4_sales_to_mcap"
                        />
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      {i5 === 'gap' ? (
                        <AxisGapMark axis="5_industry" evidence={screenAuditEvidence('5_industry', r, thresholds)} />
                      ) : (
                        <PassMark
                          state={i5}
                          evidence={screenAuditEvidence('5_industry', r, thresholds)}
                          testId="fts-mark-5_industry"
                        />
                      )}
                    </div>
                    {r.excluded ? (
                      <span className="ms-1 text-2xs text-accent-red" title={r.exclusion_reasons ?? ''}>
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
            })}
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
