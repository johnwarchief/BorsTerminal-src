// features/fundamental/components/FtsCard.tsx -- کارت مدرن پنج شاخص بنیادی FTS
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { ConfidenceDial } from '@shared/components/ConfidenceDial';
import { gapReason, gapLabel, gapTooltip, type GapAxis } from '../lib/gapReason';
import { AuditBadge, type AuditEvidence } from './AuditBadge';
import { industryGateLabel, industryGatePassLabel, industryGateTone } from '../lib/industryGate';
import { MathFraction } from './MathFormula';
import type { DrillDownKey } from './FtsDrillDown';
import type { FtsCardIndicators } from '../api/useFtsCard';

const LAYERS: { key: GapAxis | '1_growth'; drill: DrillDownKey | null; label: string; hint: string }[] = [
  {
    key: '1_growth',
    drill: '1',
    label: '۱. رشد فروش کدال',
    hint: 'رشد درآمد ریالی و مقداری نسبت به دوره مشابه سال قبل — کلیک: نمودار و جزئیات',
  },
  {
    key: '2_eps_trend',
    drill: '2',
    label: '۲. سودآوری ۳ ساله',
    hint: 'روند ۳ سال متوالی سود هر سهم از صورت‌های حسابرسی‌شده — کلیک: نمودار و جزئیات',
  },
  {
    key: '3_gross_margin',
    drill: '3',
    label: '۳. حاشیه سود ناخالص',
    hint: 'سود ناخالص ÷ درآمد عملیاتی — کلیک: نمودار و جزئیات',
  },
  {
    key: '4_sales_to_mcap',
    drill: '4',
    label: '۴. ارزش بازار',
    hint: 'نسبت سالانه‌شده فروش یا پتانسیل سود به ارزش بازار — کلیک: نمودار و جزئیات',
  },
  {
    key: '5_industry',
    drill: '5',
    label: '۵. رژیم صنعت',
    hint: 'عدم شمول قیمت‌گذاری دستوری (بورس کالا و نرخ‌های آزاد) — کلیک: نمودار و جزئیات',
  },
];

/** سه‌حاله: رأیِ مالک ۱۴۰۵-۰۷-۰۳ — «نظر نمی‌دهد» نباید سرخِ «رد شده» دیده شود. */
function tone(pass: boolean | null | undefined): string {
  return pass === true ? 'text-accent-green' : pass === false ? 'text-accent-red' : 'text-text-muted';
}

function getCardToneClasses(pass: boolean | null | undefined, isActive: boolean): string {
  if (isActive) {
    return 'border-accent-blue bg-accent-blue/15 shadow-[0_0_18px_rgba(56,189,248,0.25)] ring-1 ring-accent-blue/50';
  }
  if (pass === true) {
    return 'border-emerald-500/30 bg-emerald-500/[0.04] hover:border-emerald-500/60 hover:bg-emerald-500/[0.08]';
  }
  if (pass === false) {
    return 'border-rose-500/30 bg-rose-500/[0.04] hover:border-rose-500/60 hover:bg-rose-500/[0.08]';
  }
  return 'border-border-c/70 bg-bg-card/70 hover:border-border-accent hover:bg-bg-card';
}

export function FtsCard({
  score,
  passes,
  verdict,
  physicalApplicable = true,
  industryMode,
  audit,
  indicators,
  activeDrill = null,
  onDrill,
}: {
  score: number | null;
  /** سه‌حاله (رأی ۱۴۰۵-۰۷-۰۳): null = «نظر نمی‌دهد»، نه سبز و نه سرخ. */
  passes: Record<string, boolean | null | undefined>;
  verdict: string | null;
  /** رشد فیزیکی صرفاً برای تولیدی معنا دارد — هلدینگ/خدماتی/مالی N/A */
  physicalApplicable?: boolean;
  /** رژیم قیمت‌گذاری صنعت (free|mandatory|neutral) */
  industryMode?: string | null;
  /** شاهد ممیزی هر محور برای کارت «چرا این وضعیت؟» (lib/auditEvidence) */
  audit?: Partial<Record<GapAxis, AuditEvidence>> | null;
  /** داده‌های خام شاخص‌ها برای نمایش مقادیر و درصدهای واقعی */
  indicators?: FtsCardIndicators | null;
  activeDrill?: DrillDownKey | null;
  onDrill?: (k: DrillDownKey) => void;
}) {
  return (
    <div className="glass-panel panel-in p-4 flex flex-col justify-between" dir="rtl">
      <div>
        {/* سربرگ کارت ارزیابی ۵ شاخص */}
        <div className="mb-3.5 flex items-center justify-between border-b border-border-c/40 pb-2.5">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-blue/15 text-accent-blue border border-accent-blue/30 font-black text-2xs">
              FTS
            </span>
            <h3 className="text-xs sm:text-sm font-black text-text-primary tracking-wide">
              کارت ارزیابی ۵ شاخص FTS
            </h3>
          </div>

          <div className="flex items-center gap-2">
            {/* امتیاز با پیپ‌های بصری و متن */}
            <div className="flex items-center gap-2 rounded-lg border border-border-c/80 bg-bg-card/90 px-2.5 py-1 shadow-xs">
              {score != null ? (
                <>
                  <div className="flex items-center gap-1" aria-hidden="true">
                    {[1, 2, 3, 4, 5].map((idx) => {
                      const filled = idx <= score;
                      return (
                        <span
                          key={idx}
                          className={`h-2 w-2 rounded-full transition-all ${
                            filled
                              ? score >= 4
                                ? 'bg-accent-green shadow-[0_0_6px_rgba(34,197,94,0.6)]'
                                : score >= 3
                                  ? 'bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]'
                                  : 'bg-accent-red shadow-[0_0_6px_rgba(239,68,68,0.5)]'
                              : 'bg-border-c/70'
                          }`}
                        />
                      );
                    })}
                  </div>
                  <span className="text-xs font-black text-text-primary">
                    امتیاز {toFaDigits(score)} از ۵
                  </span>
                </>
              ) : (
                <span className="text-xs font-bold text-text-muted">بدون امتیاز</span>
              )}
            </div>

            {verdict ? (
              <Badge tone={score != null && score >= 4 ? 'green' : score != null && score >= 3 ? 'yellow' : 'red'}>
                {verdict}
              </Badge>
            ) : null}
          </div>
        </div>

        {/* شبکه ۵ کارت شاخص — چیدمان مدرن با اولویت قرارگیری عدد و نتیجه در کنار هم + فرمول ریاضی */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2.5">
          {LAYERS.map((l) => {
            const isActive = l.drill != null && l.drill === activeDrill;

            // شاخص ۱: رشد فروش کدال (ترکیبی ریالی و مقداری)
            if (l.key === '1_growth') {
              const v1a = passes['1a_monetary_growth'];
              const volThreshold = indicators?.['1']?.volume?.threshold ?? 0;
              const v1b = passes['1b_volume_growth'];
              const mon = indicators?.['1']?.monetary;
              const vol = indicators?.['1']?.volume;
              const monPct =
                mon?.monetary_pct ??
                (typeof audit?.['1a_monetary_growth']?.actualValue === 'number'
                  ? (audit?.['1a_monetary_growth']?.actualValue as number)
                  : null);
              const volPct =
                vol?.real_pct ??
                vol?.volume_pct ??
                (typeof audit?.['1b_volume_growth']?.actualValue === 'number'
                  ? (audit?.['1b_volume_growth']?.actualValue as number)
                  : null);

              const card1Pass =
                v1a === false || (physicalApplicable && v1b === false)
                  ? false
                  : v1a === true && (!physicalApplicable || v1b === true)
                    ? true
                    : null;

              return (
                <button
                  key={l.key}
                  type="button"
                  disabled={!l.drill || !onDrill}
                  onClick={() => l.drill && onDrill?.(l.drill)}
                  aria-pressed={isActive}
                  data-testid={`fts-card-cell-${l.key}`}
                  title={l.hint}
                  className={`col-span-1 sm:col-span-2 xl:col-span-2 group flex flex-col justify-between rounded-xl border p-2.5 text-start transition-all duration-200 cursor-pointer ${getCardToneClasses(
                    card1Pass,
                    isActive,
                  )}`}
                >
                  {/* سربرگ کارت ۱ */}
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-black text-text-primary group-hover:text-accent-blue transition-colors">
                      {l.label}
                    </span>
                    {mon?.months ? (
                      <span className="text-3xs px-1.5 py-0.5 rounded bg-bg-card/90 text-text-muted border border-border-c/50 font-mono">
                        {toFaDigits(mon.months)} ماهه
                      </span>
                    ) : null}
                  </div>

                  {/* بدنه کارت ۱: دو ستون متقارن با نتیجه و درصد در کنار بج وضعیت */}
                  <div className="grid grid-cols-2 gap-2">
                    {/* ستون ۱-الف: ریالی */}
                    <div
                      data-testid="fts-card-cell-1a_monetary_growth"
                      className="flex flex-col justify-between rounded-lg border border-border-c/40 bg-bg-card/50 p-2"
                    >
                      <div className="flex items-center justify-between gap-1 mb-1.5">
                        <span className="text-2xs font-bold text-text-secondary">درآمد ریالی</span>
                        {/* نتیجه: عدد و درصد دقیقاً پهلو به پهلوی بج وضعیت */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          {monPct != null ? (
                            <span
                              className={`font-mono text-xs font-black ${
                                v1a ? 'text-accent-green' : v1a === false ? 'text-accent-red' : 'text-text-primary'
                              }`}
                            >
                              {monPct >= 0 ? '+' : '−'}
                              {toFaDigits(Math.abs(monPct).toFixed(1))}٪
                            </span>
                          ) : (
                            <span className="font-mono text-2xs font-bold text-text-muted">—</span>
                          )}
                          <AuditBadge
                            state={v1a == null ? 'na' : v1a ? 'pass' : 'fail'}
                            label={v1a == null ? gapLabel('1a_monetary_growth') : undefined}
                            hintTitle={v1a == null ? gapTooltip('1a_monetary_growth') : 'رشد ریالی'}
                            evidence={
                              v1a == null
                                ? {
                                    ...(audit?.['1a_monetary_growth'] ?? {}),
                                    reason: audit?.['1a_monetary_growth']?.reason ?? gapReason('1a_monetary_growth').why,
                                  }
                                : (audit?.['1a_monetary_growth'] ?? null)
                            }
                            testId="fts-cell-audit-1a_monetary_growth"
                            compact
                          />
                        </div>
                      </div>

                      {/* فرمول ریاضی واقعی */}
                      <div className="my-1 flex items-center justify-center rounded border border-border-c/30 bg-bg-primary/40 py-1 px-1.5 overflow-hidden">
                        <div className="flex items-center gap-1 text-3xs font-mono text-text-secondary whitespace-nowrap" dir="ltr">
                          <MathFraction
                            numerator={<span className="text-3xs px-0.5 whitespace-nowrap">فروش امسال</span>}
                            denominator={<span className="text-3xs px-0.5 whitespace-nowrap">فروش سال قبل</span>}
                          />
                          <span>− 1</span>
                          <span className={`font-bold ${v1a ? 'text-accent-green' : 'text-accent-red'}`}>≥ تورم (۴۰٪)</span>
                        </div>
                      </div>

                      <span className="text-3xs text-text-muted">کف: نرخ تورم سالانه</span>
                    </div>

                    {/* ستون ۱-ب: رشد مقداری / فیزیکی */}
                    <div
                      data-testid="fts-card-cell-1b_volume_growth"
                      className="flex flex-col justify-between rounded-lg border border-border-c/40 bg-bg-card/50 p-2"
                    >
                      <div className="flex items-center justify-between gap-1 mb-1.5">
                        <span className="text-2xs font-bold text-text-secondary">رشد مقداری</span>
                        {/* نتیجه: عدد و درصد دقیقاً پهلو به پهلوی بج وضعیت */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          {!physicalApplicable ? (
                            <span className="text-2xs font-semibold text-text-muted">غیرتولیدی</span>
                          ) : volPct != null ? (
                            <span
                              className={`font-mono text-xs font-black ${
                                v1b ? 'text-accent-green' : v1b === false ? 'text-accent-red' : 'text-text-primary'
                              }`}
                            >
                              {volPct >= 0 ? '+' : '−'}
                              {toFaDigits(Math.abs(volPct).toFixed(1))}٪
                            </span>
                          ) : (
                            <span className="font-mono text-2xs font-bold text-text-muted">—</span>
                          )}
                          <AuditBadge
                            state={!physicalApplicable ? 'na' : v1b == null ? 'na' : v1b ? 'pass' : 'fail'}
                            label={!physicalApplicable ? undefined : v1b == null ? gapLabel('1b_volume_growth') : undefined}
                            hintTitle={!physicalApplicable ? undefined : v1b == null ? gapTooltip('1b_volume_growth') : 'رشد مقداری'}
                            evidence={
                              !physicalApplicable
                                ? null
                                : v1b == null
                                  ? {
                                      ...(audit?.['1b_volume_growth'] ?? {}),
                                      reason: audit?.['1b_volume_growth']?.reason ?? gapReason('1b_volume_growth').why,
                                    }
                                  : (audit?.['1b_volume_growth'] ?? null)
                            }
                            testId="fts-cell-audit-1b_volume_growth"
                            compact
                          />
                        </div>
                      </div>

                      {/* فرمول ریاضی واقعی */}
                      <div className="my-1 flex items-center justify-center rounded border border-border-c/30 bg-bg-primary/40 py-1 px-1.5 overflow-hidden">
                        <div className="flex items-center gap-1 text-3xs font-mono text-text-secondary whitespace-nowrap" dir="ltr">
                          {!physicalApplicable ? (
                            <span className="text-3xs text-text-muted">معاف از شرط فیزیکی</span>
                          ) : (
                            <>
                              <MathFraction
                                numerator={<span className="text-3xs px-0.5 whitespace-nowrap">تولید امسال</span>}
                                denominator={<span className="text-3xs px-0.5 whitespace-nowrap">تولید سال قبل</span>}
                              />
                              <span>− 1</span>
                              <span className={`font-bold ${tone(v1b)}`}>≥ {toFaDigits(volThreshold)}٪</span>
                            </>
                          )}
                        </div>
                      </div>

                      <span className="text-3xs text-text-muted">
                        {!physicalApplicable ? 'معاف از رشد فیزیکی' : 'کف: حفظ حجم تولید (رشد مقداری)'}
                      </span>
                    </div>
                  </div>
                </button>
              );
            }

            const key = l.key as GapAxis;
            const rawPass = passes[key];
            /** رأیِ مالک (۱۴۰۵-۰۷-۰۳): «معاف / کاربرد ندارد» نظر نمی‌دهد است، نه
             *  رد. بک‌اند همین را در na/exempt می‌فرستد ( passes برای سازگاریِ
             *  مرتب‌سازی هنوز bool است)؛ پس نشانه از همان پرچمِ موتور خوانده
             *  می‌شود — محاسبهٔ دوباره در UI نیست. */
            const axisNa =
              key === '4_sales_to_mcap' &&
              (indicators?.['4']?.na === true || indicators?.['4']?.exempt === true);
            const v = axisNa ? null : rawPass;
            const isIndustry = key === '5_industry' && industryMode !== undefined;

            let resultNumberNode: React.ReactNode = null;
            let mathFormulaNode: React.ReactNode = null;
            let benchmarkHint: string = '';

            if (key === '2_eps_trend') {
              const i2 = indicators?.['2'];
              const epsYearsReq = i2?.years_required ?? 3;
              const epsRising = i2?.strictly_rising ?? v;
              const epsYears =
                i2?.years_available ??
                (typeof audit?.['2_eps_trend']?.actualValue === 'number'
                  ? (audit?.['2_eps_trend']?.actualValue as number)
                  : null);

              resultNumberNode = (
                <span
                  className={`text-xs font-black ${
                    v ? 'text-accent-green' : v === false ? 'text-accent-red' : 'text-text-primary'
                  }`}
                >
                  {epsRising ? `${toFaDigits(epsYearsReq)} سال صعودی` : epsYears ? `${toFaDigits(epsYears)} سال` : 'شکست روند'}
                </span>
              );

              mathFormulaNode = (
                <div className="flex items-center justify-center gap-1 font-mono text-2xs font-bold text-text-primary whitespace-nowrap" dir="ltr">
                  <span>EPS<sub>t</sub></span>
                  <span className={tone(v)}>&gt;</span>
                  <span>EPS<sub>t-1</sub></span>
                  <span className={tone(v)}>&gt;</span>
                  <span>EPS<sub>t-2</sub></span>
                  <span className={tone(v)}>&gt;</span>
                  <span>0</span>
                </div>
              );
              benchmarkHint = `شرط: ${toFaDigits(epsYearsReq)} سال متوالی سوددهی صعودی`;
            } else if (key === '3_gross_margin') {
              const i3 = indicators?.['3'];
              const marginFloor = i3?.threshold ?? 20;
              const marginIdeal = i3?.ideal_threshold ?? i3?.optimal_threshold ?? 30;
              const marginPct =
                i3?.margin_pct ??
                (typeof audit?.['3_gross_margin']?.actualValue === 'number'
                  ? (audit?.['3_gross_margin']?.actualValue as number)
                  : null);

              resultNumberNode = (
                <span
                  className={`font-mono text-xs sm:text-sm font-black ${
                    v ? 'text-accent-green' : v === false ? 'text-accent-red' : 'text-text-primary'
                  }`}
                >
                  {marginPct != null ? `${toFaDigits(marginPct.toFixed(1))}٪` : '—'}
                </span>
              );

              mathFormulaNode = (
                <div className="flex items-center justify-center gap-1 text-3xs font-mono text-text-secondary whitespace-nowrap" dir="ltr">
                  <MathFraction
                    numerator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">سود ناخالص</span>}
                    denominator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">درآمد عملیاتی</span>}
                  />
                  <span className="text-3xs text-text-muted">× 100</span>
                  <span className={`text-2xs font-black ms-0.5 ${tone(v)}`}>≥ {toFaDigits(marginFloor)}٪</span>
                </div>
              );
              benchmarkHint = `کف استاندارد: ${toFaDigits(marginFloor)}٪ (ایده‌آل ${toFaDigits(marginIdeal)}٪)`;
            } else if (key === '4_sales_to_mcap') {
              const i4 = indicators?.['4'];
              const salesFloor = i4?.sales_threshold ?? 0.33;
              const salesRatio =
                i4?.sales_to_mcap ??
                (typeof audit?.['4_sales_to_mcap']?.actualValue === 'number'
                  ? (audit?.['4_sales_to_mcap']?.actualValue as number)
                  : null);
              const potPct = i4?.potential_pct;

              resultNumberNode = (
                <span
                  className={`font-mono text-xs sm:text-sm font-black ${
                    v ? 'text-accent-green' : v === false ? 'text-accent-red' : 'text-text-primary'
                  }`}
                >
                  {salesRatio != null
                    ? `${toFaDigits(salesRatio.toFixed(2))}×`
                    : potPct != null
                      ? `${toFaDigits(potPct.toFixed(0))}٪`
                      : '—'}
                </span>
              );

              mathFormulaNode = (
                <div className="flex items-center justify-center gap-1 text-3xs font-mono text-text-secondary whitespace-nowrap" dir="ltr">
                  <MathFraction
                    numerator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">فروش سالانه</span>}
                    denominator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">ارزش روز بازار</span>}
                  />
                  <span className={`text-2xs font-black ms-0.5 ${tone(v)}`}>≥ {toFaDigits(salesFloor.toFixed(2))}×</span>
                </div>
              );
              benchmarkHint = `کف نسبت: ${toFaDigits(salesFloor.toFixed(2))}× (${toFaDigits(Math.round(salesFloor * 100))}٪)`;
            } else if (key === '5_industry') {
              const indLabel =
                industryMode !== undefined
                  ? industryGateLabel(industryMode)
                  : typeof audit?.['5_industry']?.actualValue === 'string'
                    ? (audit?.['5_industry']?.actualValue as string)
                    : industryGateLabel(null);
              const indTone = industryGateTone(industryMode);

              resultNumberNode = (
                <span
                  data-testid={`fts-card-label-${key}`}
                  className={`text-2xs sm:text-xs font-bold truncate ${
                    indTone === 'green'
                      ? 'text-accent-green'
                      : indTone === 'yellow'
                        ? 'text-amber-400'
                        : indTone === 'red'
                          ? 'text-accent-red'
                          : 'text-text-primary'
                  }`}
                >
                  {indLabel}
                </span>
              );

              mathFormulaNode = (
                <div className="flex items-center justify-center gap-1 text-3xs font-mono text-text-secondary whitespace-nowrap" dir="ltr">
                  <span>نرخ</span>
                  <span className="text-accent-blue font-bold">∈</span>
                  <span className="font-bold text-text-primary">&#123;بورس کالا, آزاد&#125;</span>
                  <span className="text-accent-red font-bold">≠</span>
                  <span className="text-text-muted">دستوری</span>
                </div>
              );
              benchmarkHint = 'بورس کالا / نرخ آزاد';
            }

            const industryBadge = isIndustry ? (
              <AuditBadge
                state={v == null ? 'na' : v ? 'pass' : 'fail'}
                label={
                  v == null
                    ? gapLabel(key)
                    : v === false
                      ? industryGatePassLabel(false)
                      : industryGateLabel(industryMode)
                }
                hintTitle={
                  v == null
                    ? gapTooltip(key)
                    : `${industryGateLabel(industryMode)} · ${industryGatePassLabel(v === true)}`
                }                evidence={audit?.['5_industry'] ?? null}
                testId={`fts-cell-audit-${key}`}
                compact
              />
            ) : null;

            return (
              <button
                key={key}
                type="button"
                disabled={!l.drill || !onDrill}
                onClick={() => l.drill && onDrill?.(l.drill)}
                aria-pressed={isActive}
                data-testid={`fts-card-cell-${key}`}
                title={l.hint}
                className={`col-span-1 group flex flex-col justify-between rounded-xl border p-2.5 text-start transition-all duration-200 cursor-pointer ${getCardToneClasses(
                  v,
                  isActive,
                )}`}
              >
                {/* ردیف بالا: نام شاخص در راست + نتیجه (درصد/عدد + تایید/قبول) در چپ در کنار هم */}
                <div className="mb-2 flex items-center justify-between gap-1">
                  <span className="text-xs font-black text-text-primary group-hover:text-accent-blue transition-colors">
                    {l.label}
                  </span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {resultNumberNode}
                    {industryBadge ?? (
                      <AuditBadge
                        state={v == null ? 'na' : v ? 'pass' : 'fail'}
                        label={v == null ? (axisNa ? 'N/A' : gapLabel(key)) : undefined}
                        hintTitle={
                          v == null
                            ? (axisNa ? (audit?.[key]?.reason ?? gapTooltip(key)) : gapTooltip(key))
                            : undefined
                        }
                        evidence={
                          v == null
                            ? { ...(audit?.[key] ?? {}), reason: audit?.[key]?.reason ?? gapReason(key).why }
                            : (audit?.[key] ?? null)
                        }
                        testId={`fts-cell-audit-${key}`}
                        compact
                      />
                    )}
                  </div>
                </div>

                {/* ردیف وسط: فرمول ریاضی واقعی با کسر و نمادهای دقیق */}
                <div className="my-1.5 flex items-center justify-center rounded-lg border border-border-c/30 bg-bg-card/40 py-1.5 px-1.5 overflow-hidden">
                  {mathFormulaNode}
                </div>

                {/* ردیف پایین: شرط مرجع */}
                <span className="text-3xs text-text-muted mt-1 truncate">{benchmarkHint}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* نوار پایین: ضریب اطمینان بنیادی */}
      <div className="mt-3.5 pt-2.5 border-t border-border-c/50 flex items-center justify-between">
        <div className="flex items-center gap-2 text-2xs text-text-secondary">
          <span className="h-2 w-2 rounded-full bg-accent-blue animate-pulse"></span>
          <span className="font-medium">ضریب اطمینان بنیادی:</span>
        </div>
        <ConfidenceDial value={score == null ? 'nodata' : score >= 4 ? 'high' : score >= 3 ? 'medium' : 'low'} />
      </div>
    </div>
  );
}
