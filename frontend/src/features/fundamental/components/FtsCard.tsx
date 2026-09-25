// features/fundamental/components/FtsCard.tsx -- کارت مدرن پنج لایه FTS
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { ConfidenceDial } from '@shared/components/ConfidenceDial';
import { gapReason, gapLabel, gapTooltip, type GapAxis } from '../lib/gapReason';
import { AuditBadge, type AuditEvidence } from './AuditBadge';
import { industryGateLabel, industryGatePassLabel } from '../lib/industryGate';
import type { DrillDownKey } from './FtsDrillDown';
import type { FtsCardIndicators } from '../api/useFtsCard';

const LAYERS: { key: GapAxis | '1_growth'; drill: DrillDownKey | null; label: string; hint: string }[] = [
  {
    key: '1_growth',
    drill: '1',
    label: '۱. رشد فروش کدال',
    hint: 'رشد درآمد ریالی و مقداری نسبت به دوره مشابه سال قبل — کلیک: نمودار و فرمول',
  },
  {
    key: '2_eps_trend',
    drill: '2',
    label: '۲. سودآوری ۳ ساله',
    hint: 'روند ۳ سال متوالی سود هر سهم از صورت‌های حسابرسی‌شده',
  },
  {
    key: '3_gross_margin',
    drill: '3',
    label: '۳. حاشیه سود ناخالص',
    hint: 'سود ناخالص ÷ درآمد عملیاتی — کلیک: نمودار و فرمول',
  },
  {
    key: '4_sales_to_mcap',
    drill: '4',
    label: '۴. ارزش بازار',
    hint: 'نسبت سالانه‌شده فروش یا پتانسیل سود ناخالص به ارزش بازار',
  },
  {
    key: '5_industry',
    drill: '5',
    label: '۵. رژیم صنعت',
    hint: 'عدم شمول قیمت‌گذاری دستوری (سیمان، فلزات، پتروشیمی، شیشه، IT)',
  },
];

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
  passes: Record<string, boolean>;
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
    <div className="glass-panel panel-in p-4 flex flex-col justify-between">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-black text-text-primary tracking-wide">کارت ارزیابی ۵ شاخص FTS</h3>
          </div>
          <span className="flex items-center gap-2">
            {score != null ? (
              <Badge tone={score >= 4 ? 'green' : score >= 3 ? 'yellow' : 'red'}>
                امتیاز {toFaDigits(score)} از ۵
              </Badge>
            ) : (
              <Badge tone="gray">بدون امتیاز</Badge>
            )}
            {verdict ? <Badge tone="blue">{verdict}</Badge> : null}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          {LAYERS.map((l) => {
            const isActive = l.drill != null && l.drill === activeDrill;
            
            // Special handling for merged indicator 1
            if (l.key === '1_growth') {
              const v1a = passes['1a_monetary_growth'];
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
              
              return (
                <button
                  key={l.key}
                  type="button"
                  disabled={!l.drill || !onDrill}
                  onClick={() => l.drill && onDrill?.(l.drill)}
                  aria-pressed={isActive}
                  data-testid={`fts-card-cell-${l.key}`}
                  title={l.hint}
                  className={`col-span-2 sm:col-span-2 group flex flex-col justify-between rounded-xl border p-2.5 text-start transition-all duration-200 ${
                    isActive
                      ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_15px_rgba(56,189,248,0.2)]'
                      : 'border-border-c/70 bg-bg-card/70 hover:border-border-accent hover:bg-bg-card disabled:cursor-default'
                  }`}
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-black text-text-primary group-hover:text-accent-blue transition-colors">
                      {l.label}
                    </span>
                    {mon?.months ? (
                      <span className="text-3xs px-1.5 py-0.5 rounded bg-bg-card/80 text-text-muted border border-border-c/40 font-mono">
                        {toFaDigits(mon.months)} ماهه
                      </span>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div data-testid="fts-card-cell-1a_monetary_growth" className="inline-flex items-center gap-1.5">
                      <span className="text-2xs font-semibold text-text-secondary">۱-الف (ریالی):</span>
                      {monPct != null ? (
                        <span
                          className={`font-mono text-xs font-black ${
                            v1a ? 'text-accent-green' : v1a === false ? 'text-accent-red' : 'text-text-primary'
                          }`}
                        >
                          {monPct >= 0 ? '+' : '−'}
                          {toFaDigits(Math.abs(monPct).toFixed(1))}٪
                        </span>
                      ) : null}
                      <AuditBadge
                        state={v1a == null ? 'na' : v1a ? 'pass' : 'fail'}
                        label={v1a == null ? gapLabel('1a_monetary_growth') : undefined}
                        hintTitle={v1a == null ? gapTooltip('1a_monetary_growth') : 'رشد ریالی'}
                        evidence={
                          v1a == null
                            ? { ...(audit?.['1a_monetary_growth'] ?? {}), reason: audit?.['1a_monetary_growth']?.reason ?? gapReason('1a_monetary_growth').why }
                            : (audit?.['1a_monetary_growth'] ?? null)
                        }
                        testId="fts-cell-audit-1a_monetary_growth"
                        compact
                      />
                    </div>
                    <div data-testid="fts-card-cell-1b_volume_growth" className="inline-flex items-center gap-1.5">
                      <span className="text-2xs font-semibold text-text-secondary">۱-ب (تولیدی):</span>
                      {!physicalApplicable ? (
                        <span className="text-2xs text-text-muted">غیرتولیدی</span>
                      ) : volPct != null ? (
                        <span
                          className={`font-mono text-xs font-black ${
                            v1b ? 'text-accent-green' : v1b === false ? 'text-accent-red' : 'text-text-primary'
                          }`}
                        >
                          {volPct >= 0 ? '+' : '−'}
                          {toFaDigits(Math.abs(volPct).toFixed(1))}٪
                        </span>
                      ) : null}
                      <AuditBadge
                        state={!physicalApplicable ? 'na' : v1b == null ? 'na' : v1b ? 'pass' : 'fail'}
                        label={!physicalApplicable ? undefined : v1b == null ? gapLabel('1b_volume_growth') : undefined}
                        hintTitle={!physicalApplicable ? undefined : v1b == null ? gapTooltip('1b_volume_growth') : 'رشد تولیدی'}
                        evidence={
                          !physicalApplicable
                            ? null
                            : v1b == null
                            ? { ...(audit?.['1b_volume_growth'] ?? {}), reason: audit?.['1b_volume_growth']?.reason ?? gapReason('1b_volume_growth').why }
                            : (audit?.['1b_volume_growth'] ?? null)
                        }
                        testId="fts-cell-audit-1b_volume_growth"
                        compact
                      />
                    </div>
                    {l.drill ? (
                      <span className="ms-auto text-text-muted opacity-40 group-hover:opacity-100 group-hover:text-accent-blue transition-all">
                        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <circle cx="11" cy="11" r="8" />
                          <line x1="21" y1="21" x2="16.65" y2="16.65" />
                        </svg>
                      </span>
                    ) : null}
                  </div>
                </button>
              );
            }

            const key = l.key as GapAxis;
            const v = passes[key];
            const isIndustry = key === '5_industry' && industryMode !== undefined;

            let resultNode: React.ReactNode = null;
            if (key === '2_eps_trend') {
              const i2 = indicators?.['2'];
              const epsRising = i2?.strictly_rising ?? v;
              const epsYears = i2?.years_available ?? (typeof audit?.['2_eps_trend']?.actualValue === 'number' ? (audit?.['2_eps_trend']?.actualValue as number) : null);
              const label = epsRising ? 'روند ۳ سال صعودی' : epsYears ? `${toFaDigits(epsYears)} سال سودده` : 'سودآوری';
              resultNode = <span className="text-2xs font-bold text-accent-blue truncate">{label}</span>;
            } else if (key === '3_gross_margin') {
              const i3 = indicators?.['3'];
              const marginPct = i3?.margin_pct ?? (typeof audit?.['3_gross_margin']?.actualValue === 'number' ? (audit?.['3_gross_margin']?.actualValue as number) : null);
              resultNode = (
                <div className="flex items-baseline gap-1">
                  <span className="text-3xs text-text-muted">حاشیه:</span>
                  <span className={`font-mono text-xs font-black ${v ? 'text-accent-green' : v === false ? 'text-accent-red' : 'text-text-primary'}`}>
                    {marginPct != null ? `${toFaDigits(marginPct.toFixed(1))}٪` : '—'}
                  </span>
                </div>
              );
            } else if (key === '4_sales_to_mcap') {
              const i4 = indicators?.['4'];
              const salesRatio = i4?.sales_to_mcap ?? (typeof audit?.['4_sales_to_mcap']?.actualValue === 'number' ? (audit?.['4_sales_to_mcap']?.actualValue as number) : null);
              const potPct = i4?.potential_pct;
              resultNode = (
                <div className="flex items-baseline gap-1">
                  <span className="text-3xs text-text-muted">فروش/ارزش:</span>
                  <span className="font-mono text-xs font-black text-text-primary">
                    {salesRatio != null ? `${toFaDigits(salesRatio.toFixed(2))}×` : potPct != null ? `${toFaDigits(potPct.toFixed(0))}٪` : '—'}
                  </span>
                </div>
              );
            } else if (key === '5_industry') {
              const label = industryMode !== undefined ? industryGateLabel(industryMode) : (typeof audit?.['5_industry']?.actualValue === 'string' ? (audit?.['5_industry']?.actualValue as string) : 'نرخ‌گذاری آزاد');
              resultNode = (
                <span
                  className="text-2xs font-bold text-accent-blue truncate"
                  data-testid={`fts-card-label-${key}`}
                >
                  {label}
                </span>
              );
            }

            const industryBadge = isIndustry ? (
              <AuditBadge
                state={v == null ? 'na' : v ? 'pass' : 'fail'}
                label={
                  v == null ? gapLabel(key) : industryGatePassLabel(v === true)
                }
                hintTitle={v == null ? gapTooltip(key) : `${industryGateLabel(industryMode)} · ${industryGatePassLabel(v === true)}`}
                evidence={audit?.['5_industry'] ?? null}
                testId={`fts-cell-audit-${key}`}
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
                className={`group flex flex-col justify-between rounded-xl border p-2.5 text-start transition-all duration-200 ${
                  isActive
                    ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_15px_rgba(56,189,248,0.2)]'
                    : 'border-border-c/70 bg-bg-card/70 hover:border-border-accent hover:bg-bg-card disabled:cursor-default'
                }`}
              >
                <div className="mb-1.5 flex flex-col">
                  <span className="text-xs font-black text-text-primary group-hover:text-accent-blue transition-colors">
                    {l.label}
                  </span>
                  <div className="mt-0.5">{resultNode}</div>
                </div>
                <div className="mt-1 flex items-center justify-between">
                  {industryBadge ?? (
                    <AuditBadge
                      state={v == null ? 'na' : v ? 'pass' : 'fail'}
                      label={v == null ? gapLabel(key) : undefined}
                      hintTitle={v == null ? gapTooltip(key) : undefined}
                      evidence={
                        v == null
                          ? { ...(audit?.[key] ?? {}), reason: audit?.[key]?.reason ?? gapReason(key).why }
                          : (audit?.[key] ?? null)
                      }
                      testId={`fts-cell-audit-${key}`}
                    />
                  )}
                  {l.drill ? (
                    <span className="text-text-muted opacity-40 group-hover:opacity-100 group-hover:text-accent-blue transition-all">
                      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <circle cx="11" cy="11" r="8" />
                        <line x1="21" y1="21" x2="16.65" y2="16.65" />
                      </svg>
                    </span>
                  ) : null}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-border-c/60 flex items-center justify-between">
        <div className="flex items-center gap-2 text-2xs text-text-secondary">
          <span className="h-2 w-2 rounded-full bg-accent-blue animate-pulse"></span>
          <span>ضریب اطمینان بنیادی:</span>
        </div>
        <ConfidenceDial value={score == null ? 'nodata' : score >= 4 ? 'high' : score >= 3 ? 'medium' : 'low'} />
      </div>
    </div>
  );
}

