// features/fundamental/components/FtsCard.tsx -- کارت مدرن پنج شاخص بنیادی FTS
// قراردادِ واژه (#169): حکمِ هر سلول یک‌بار نوشته می‌شود — در برچسبِ VerdictChip.
// بجِ ممیزی فقط «ⓘ» است («چرا این وضعیت؟»); آن‌جا که حکمی وجود ندارد (سلولِ
// بی‌داده/معاف) بج همان علت را می‌نویسد («N/A»، «گزارش ماهانهٔ کدال نیست»).
import type { ReactNode } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { FTS_LABEL } from '@shared/lib/ftsLabels';
import { Badge } from '@shared/components/Badge';
import { ConfidenceDial } from '@shared/components/ConfidenceDial';
import { gapReason, gapLabel, gapTooltip, type GapAxis } from '../lib/gapReason';
import { AuditBadge, type AuditEvidence } from './AuditBadge';
import { industryGateLabel, industryGatePassLabel, industryGateTone } from '../lib/industryGate';
import { MathFraction } from './MathFormula';
import { epsChangeText, epsChanges, epsGrowthReason } from '../lib/epsHistory';
import type { DrillDownKey } from './FtsDrillDown';
import type { FtsCardIndicators } from '../api/useFtsCard';

const LAYERS: { key: GapAxis | '1_growth'; drill: DrillDownKey | null; label: string; hint: string }[] = [
  {
    key: '1_growth',
    drill: '1',
    label: FTS_LABEL['1_growth'],
    hint: 'رشد درآمد ریالی و تولیدی نسبت به دوره مشابه سال قبل — کلیک: نمودار و جزئیات',
  },
  {
    key: '2_eps_trend',
    drill: '2',
    label: FTS_LABEL['2_eps_trend'],
    hint: 'روند ۳ سال متوالی سود هر سهم از صورت‌های حسابرسی‌شده — کلیک: نمودار و جزئیات',
  },
  {
    key: '3_gross_margin',
    drill: '3',
    label: FTS_LABEL['3_gross_margin'],
    hint: 'سود ناخالص ÷ درآمد عملیاتی — کلیک: نمودار و جزئیات',
  },
  {
    key: '4_sales_to_mcap',
    drill: '4',
    label: FTS_LABEL['4_sales_to_mcap'],
    hint: 'نسبت سالانه‌شده فروش یا پتانسیل سود به ارزش بازار — کلیک: نمودار و جزئیات',
  },
  {
    key: '5_industry',
    drill: '5',
    label: FTS_LABEL['5_industry'],
    hint: 'عدم شمول قیمت‌گذاری دستوری (بورس کالا و نرخ‌های آزاد) — کلیک: نمودار و جزئیات',
  },
];

/** سه‌حالۀ کیفیت — «ایده‌آل» فقط آن‌جا که خودِ موتور آستانۀ ایده‌آل را جدا
 *  داده است. در نسخهٔ فعلی تنها شاخص ۳ آن را می‌فرستد (`band`: ideal/acceptable/
 *  below). شاخص ۱ یک درِ ۶۰٪ دارد و «کف ۴۰٪» مالِ اسکرینر است نه کارت (رأیِ
 *  مالک و کامنتِ بالای FTS_V10_DEFAULTS در api/fundamental.py) — پس آن‌جا
 *  حالتِ سوم ساخته نمی‌شود. */
type Quality = 'ideal' | 'ok' | 'below' | 'na';

const QUALITY_WORD: Record<Quality, string> = {
  ideal: 'ایده‌آل',
  ok: 'قبول',
  below: 'رد',
  na: 'نظر نمی‌دهد',
};

const QUALITY_CHIP: Record<Quality, string> = {
  ideal: 'border-cyan-400/50 bg-cyan-400/15 text-cyan-300',
  ok: 'border-accent-green/45 bg-accent-green/15 text-accent-green',
  below: 'border-accent-red/45 bg-accent-red/15 text-accent-red',
  na: 'border-border-c bg-bg-card/80 text-text-muted',
};

const QUALITY_CARD: Record<Quality, string> = {
  ideal: 'border-cyan-400/40 bg-cyan-400/[0.06] hover:border-cyan-400/70 hover:bg-cyan-400/[0.10]',
  ok: 'border-emerald-500/30 bg-emerald-500/[0.04] hover:border-emerald-500/60 hover:bg-emerald-500/[0.08]',
  below: 'border-rose-500/30 bg-rose-500/[0.04] hover:border-rose-500/60 hover:bg-rose-500/[0.08]',
  na: 'border-border-c/70 bg-bg-card/70 hover:border-border-accent hover:bg-bg-card',
};

const QUALITY_TEXT: Record<Quality, string> = {
  ideal: 'text-cyan-300',
  ok: 'text-accent-green',
  below: 'text-accent-red',
  na: 'text-text-primary',
};

function qualityFrom(pass: boolean | null | undefined, ideal?: boolean | null): Quality {
  if (pass == null) return 'na';
  if (pass && ideal === true) return 'ideal';
  return pass ? 'ok' : 'below';
}

/** سه‌حاله: رأیِ مالک ۱۴۰۵-۰۷-۰۳ — «نظر نمی‌دهد» نباید سرخِ «رد شده» دیده شود. */
function tone(pass: boolean | null | undefined): string {
  return pass === true ? 'text-accent-green' : pass === false ? 'text-accent-red' : 'text-text-muted';
}

function getCardToneClasses(q: Quality, isActive: boolean): string {
  if (isActive) {
    return 'border-accent-blue bg-accent-blue/15 shadow-[0_0_18px_rgba(56,189,248,0.25)] ring-1 ring-accent-blue/50';
  }
  return QUALITY_CARD[q];
}

/** عددِ مالیِ کانفیگ؛ هر چیزِ دیگر ( رشته، آرایه، پنهان) «نمی‌دانیم» است. */
function cfgNum(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * برچسبِ نتیجه (#149 و #169): واژۀ کیفیت را یک‌بار و رو‌به‌را می‌نویسد. هیچ
 * داوریِ تازه‌ای این‌جا ساخته نمی‌شود — `pass` همان پرچمِ موتور است و «ایده‌آل»
 * فقط وقتی گفته می‌شود که خودِ موتور آستانۀ ایده‌آل را جدا فرستاده باشد.
 */
function VerdictChip({
  pass,
  quality,
  testId,
}: {
  pass: boolean | null | undefined;
  quality?: Quality;
  testId?: string;
}) {
  const q = quality ?? (pass == null ? 'na' : pass ? 'ok' : 'below');
  return (
    <span
      data-testid={testId ?? 'fts-verdict'}
      className={`shrink-0 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-2xs font-black leading-none ${QUALITY_CHIP[q]}`}
    >
      {QUALITY_WORD[q]}
    </span>
  );
}

/** عددِ نتیجۀ «در نگاه اول» (#149) — درشت‌ترین عنصرِ هر کاشی */
function BigResult({ children, className = '', testId = 'fts-big-result' }: { children: ReactNode; className?: string; testId?: string }) {
  return (
    <span data-testid={testId} className={`num font-mono text-lg leading-none font-black sm:text-xl ${className}`}>
      {children}
    </span>
  );
}

/**
 * نشانهٔ «کلیک کن» (#169): کل کارت از پیش کلیک‌پذیر بود ولی هیچ چیزی رویش
 * این را نمی‌گفت — رأیِ مالک: «برای شاخص ۱ … وقتی میزنیم روش برای دیدن بیشتر
 * جزییات بهتر باشه». متنِ ثابت، پس حدس زدنی نیست.
 */
function DrillAffordance({ active }: { active: boolean }) {
  return (
    <span
      data-testid="fts-drill-affordance"
      aria-hidden="true"
      className={`mt-1.5 inline-flex shrink-0 items-center gap-1 self-start rounded-md border px-1.5 py-0.5 text-3xs font-bold transition-colors ${
        active
          ? 'border-accent-blue/60 bg-accent-blue/15 text-accent-blue'
          : 'border-border-c/70 bg-bg-primary/50 text-text-muted group-hover:border-accent-blue/50 group-hover:text-accent-blue'
      }`}
    >
      نمودار و جزئیات
      <span className="leading-none">⌄</span>
    </span>
  );
}

/**
 * مقایسۀ دو دورۀ شاخص ۱ (#151): دو نوارِ افقی به مقیاسِ بزرگ‌ترِ دوره‌ها،
 * و زیرشان خطِ رشدی که کف و هدفِ جزوه روی همان خط نشسته‌اند. دورۀ غایب
 * نوارِ صفر نمی‌گیرد — «نیست» با «صفر» یکی نیست.
 */
function PeriodCompare({
  now,
  prev,
  months,
  pct,
  floor,
  target,
}: {
  now: number | null;
  prev: number | null;
  months: number | null;
  pct: number | null;
  floor: number | null;
  target: number | null;
}) {
  const max = Math.max(now ?? 0, prev ?? 0);
  const rows: { id: string; label: string; full: string | null; v: number | null; fill: string }[] = [
    { id: 'now', label: months ? `${toFaDigits(months)} ماهۀ امسال` : 'دورۀ جاری', full: null, v: now, fill: 'bg-accent-blue' },
    { id: 'prev', label: 'سال قبل', full: 'همان دورۀ سال قبل', v: prev, fill: 'bg-text-muted/60' },
  ];
  return (
    <div className="flex flex-col gap-1" data-testid="fts-period-compare">
      {rows.map((r) => (
        <div key={r.id} data-testid={`fts-period-${r.id}`} className="flex items-center gap-1.5">
          <span className="w-[86px] shrink-0 truncate text-3xs text-text-secondary" title={r.full ?? r.label}>
            {r.label}
          </span>
          <span className="relative h-2.5 min-w-0 flex-1 overflow-hidden rounded bg-bg-card/80">
            {r.v == null ? null : (
              <span
                className={`absolute inset-y-0 start-0 rounded ${r.fill}`}
                style={{ width: `${max > 0 ? Math.max(3, (r.v / max) * 100) : 0}%` }}
              />
            )}
          </span>
          <span className="num shrink-0 text-3xs font-bold text-text-primary">
            {r.v == null ? '—' : fmtInt(r.v)}
          </span>
        </div>
      ))}
      <span className="text-3xs text-text-muted">میلیارد تومان · سرجمعِ دوره</span>
      {pct != null && (floor != null || target != null) ? (
        <GrowthScale pct={pct} floor={floor} target={target} />
      ) : null}
    </div>
  );
}

/** خطِ رشد: جایِ درصدِ رشد نسبت به کف و هدفِ جزوه (#151) */
function GrowthScale({ pct, floor, target }: { pct: number; floor: number | null; target: number | null }) {
  const top = Math.max(pct, (target ?? 0) * 1.2, (floor ?? 0) * 1.2, 1);
  const at = (v: number) => `${Math.min(100, Math.max(0, (v / top) * 100))}%`;
  return (
    <div className="mt-0.5" data-testid="fts-growth-scale">
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-bg-card/80">
        <span className="absolute inset-y-0 start-0 rounded-full bg-accent-green/70" style={{ width: at(pct) }} />
        {floor != null ? (
          <span className="absolute inset-y-0 w-px bg-accent-yellow" style={{ insetInlineStart: at(floor) }} title={`کفِ قبولی ${toFaDigits(floor)}٪`} />
        ) : null}
        {target != null ? (
          <span className="absolute inset-y-0 w-px bg-neon-cyan" style={{ insetInlineStart: at(target) }} title={`هدفِ پوشش تورم ${toFaDigits(target)}٪`} />
        ) : null}
      </div>
      <div className="mt-0.5 flex items-center justify-between text-3xs text-text-muted">
        <span className="num">۰٪</span>
        <span>
          {floor != null ? `کف ${toFaDigits(floor)}٪` : ''}
          {target != null ? ` · هدف ${toFaDigits(target)}٪` : ''}
        </span>
      </div>
    </div>
  );
}

export function FtsCard({
  score,
  passes,
  verdict,
  physicalApplicable = true,
  industryMode,
  audit,
  indicators,
  thresholds = null,
  activeDrill = null,
  onDrill,
}: {
  score: number | null;
  /** سه‌حاله (رأی ۱۴۰۵-۰۷-۰۳): null = «نظر نمی‌دهد»، نه سبز و نه سرخ. */
  passes: Record<string, boolean | null | undefined>;
  verdict: string | null;
  /** رشد تولیدی صرفاً برای تولیدی معنا دارد — هلدینگ/خدماتی/مالی N/A */
  physicalApplicable?: boolean;
  /** رژیم قیمت‌گذاری صنعت (free|mandatory|neutral) */
  industryMode?: string | null;
  /** شاهد ممیزی هر محور برای کارت «چرا این وضعیت؟» (lib/auditEvidence) */
  audit?: Partial<Record<GapAxis, AuditEvidence>> | null;
  /** داده‌های خام شاخص‌ها برای نمایش مقادیر و درصدهای واقعی */
  indicators?: FtsCardIndicators | null;
  /** کف/هدفِ جاریِ پیش‌شرط‌ها از بک‌اند — برچسبِ کارت باید همین را بنویسد */
  thresholds?: Record<string, unknown> | null;
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

        {/* شبکه ۵ کارت (#169): سه کارتِ اول بالا و درشت‌تر، دو تای بعدی پایین.
            رأیِ داور jev-pilot: هر پنج در یک شبکهٔ شش‌ستونه، سه‌تای بالا
            دو ستون و دوتای پایین سه ستون. */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-6 gap-2.5">
          {LAYERS.map((l, li) => {
            const span = li <= 2 ? 'md:col-span-2' : 'md:col-span-3';
            const isActive = l.drill != null && l.drill === activeDrill;

            // شاخص ۱: رشد فروش کدال (ترکیبی ریالی و تولیدی)
            if (l.key === '1_growth') {
              const v1a = passes['1a_monetary_growth'];
              const v1b = passes['1b_volume_growth'];
              const mon = indicators?.['1']?.monetary;
              const vol = indicators?.['1']?.volume;
              /** کف و هدفِ واقعیِ جزوه از کانفیگِ جاری؛ عددِ دستِ JSX نبود —
               *  رأیِ مالک: «کف ۴۰٪ · هدف ۶۰٪ درست است و باید به کانفیگ وصل شود». */
              const growthFloor = cfgNum(thresholds?.growth_min);
              const growthTarget = cfgNum(mon?.threshold) ?? cfgNum(thresholds?.v10_monetary_growth_min);
              const volFloor = cfgNum(vol?.threshold);
              const breadthMin = cfgNum(vol?.breadth?.min);
              /** مبنای تورمِ داخلِ فرمولِ ۱ب — بک‌اند می‌فرستد (#153)؛ کارت فقط
               *  آن را نشان می‌دهد و عددِ تازه‌ای نمی‌سازد. */
              const inflationBasis = cfgNum(vol?.price_benchmark_pct);
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
                  className={`col-span-1 sm:col-span-2 ${span} group flex flex-col justify-between rounded-xl border p-2.5 text-start transition-all duration-200 cursor-pointer ${getCardToneClasses(
                    qualityFrom(card1Pass),
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

                  {/* بدنه کارت ۱: دو نیمه، هر کدام ≥۲۳۰px. چیدمان خودآزمون
                      است نه breakpointِ نمایشگر — چون عرضِ کارت به ستونِ صفحه
                      و باز/بسته بودن سایدبار بستگی دارد؛ در عرضِ کم دو نیمه
                      روی هم می‌نشینند و هیچ متنِ بریده‌ای باقی نمی‌ماند. */}
                  <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))' }}>
                    {/* ستون ۱-الف: ریالی */}
                    <div
                      data-testid="fts-card-cell-1a_monetary_growth"
                      className="flex flex-col justify-between rounded-lg border border-border-c/40 bg-bg-card/50 p-2"
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-2xs font-bold text-text-secondary">درآمد ریالی</span>
                        <VerdictChip pass={v1a} testId="fts-verdict-1a_monetary_growth" />
                      </div>

                      {/* نتیجۀ درشت (#149) + شاهدِ ممیزی در همان ردیف */}
                      <div className="mb-1.5 flex items-end justify-between gap-1.5">
                        <BigResult testId="fts-result-1a" className={v1a === false ? 'text-accent-red' : v1a == null ? 'text-text-primary' : 'text-accent-green'}>
                          {monPct == null ? '—' : `${monPct >= 0 ? '+' : '−'}${toFaDigits(Math.abs(monPct).toFixed(1))}٪`}
                        </BigResult>
                        <AuditBadge
                          state={v1a == null ? 'na' : v1a ? 'pass' : 'fail'}
                          label={v1a == null ? gapLabel('1a_monetary_growth') : 'ⓘ'}
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

                      {/* مقایسۀ دیداریِ دو دوره (#151): دو نوار + خطِ کف و هدف */}
                      <PeriodCompare
                        now={mon?.ytd_now_bt ?? null}
                        prev={mon?.ytd_prev_bt ?? null}
                        months={mon?.months ?? null}
                        pct={monPct}
                        floor={growthFloor}
                        target={growthTarget}
                      />
                      <div className="mt-1 flex items-center justify-center rounded border border-border-c/30 bg-bg-primary/40 py-1 px-1.5">
                        <div className="flex flex-wrap items-center justify-center gap-x-1 gap-y-0.5 text-3xs font-mono text-text-secondary" dir="ltr">
                          <MathFraction
                            numerator={<span className="text-3xs px-0.5 whitespace-nowrap">فروش امسال</span>}
                            denominator={<span className="text-3xs px-0.5 whitespace-nowrap">فروش سال قبل</span>}
                          />
                          <span>− 1</span>
                          <span className={`font-bold whitespace-nowrap ${tone(v1a)}`}>
                            ≥ هدفِ پوشش تورم{growthTarget == null ? '' : ` (${toFaDigits(growthTarget)}٪)`}
                          </span>
                        </div>
                      </div>
                      {mon?.denominator_basis ? (
                        <span className="mt-0.5 block text-3xs leading-snug text-text-muted line-clamp-2" title={mon.denominator_basis}>
                          مبنای مقایسه: {mon.denominator_basis}
                        </span>
                      ) : null}
                    </div>

                    {/* ستون ۱-ب: رشد تولیدی (تناژ) */}
                    <div
                      data-testid="fts-card-cell-1b_volume_growth"
                      className="flex flex-col justify-between rounded-lg border border-border-c/40 bg-bg-card/50 p-2"
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-2xs font-bold text-text-secondary">رشد تولیدی</span>
                        <VerdictChip pass={!physicalApplicable ? null : v1b} testId="fts-verdict-1b_volume_growth" />
                      </div>

                      <div className="mb-1.5 flex items-end justify-between gap-1.5">
                        <BigResult testId="fts-result-1b" className={!physicalApplicable || v1b == null ? 'text-text-primary' : v1b ? 'text-accent-green' : 'text-accent-red'}>
                          {!physicalApplicable || volPct == null ? '—' : `${volPct >= 0 ? '+' : '−'}${toFaDigits(Math.abs(volPct).toFixed(1))}٪`}
                        </BigResult>
                        <AuditBadge
                          state={!physicalApplicable ? 'na' : v1b == null ? 'na' : v1b ? 'pass' : 'fail'}
                          label={!physicalApplicable ? 'N/A' : v1b == null ? gapLabel('1b_volume_growth') : 'ⓘ'}
                          hintTitle={!physicalApplicable ? undefined : v1b == null ? gapTooltip('1b_volume_growth') : 'رشد تولیدی'}
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

                      {!physicalApplicable ? (
                        <span className="text-3xs text-text-muted">این شرکت محصول فیزیکی ندارد — شاخص اجرا نمی‌شود</span>
                      ) : (
                        <>
                          <div className="flex items-center justify-center rounded border border-border-c/30 bg-bg-primary/40 py-1 px-1.5">
                            <div className="flex flex-wrap items-center justify-center gap-x-1 gap-y-0.5 text-3xs font-mono text-text-secondary" dir="ltr">
                              <MathFraction
                                numerator={<span className="text-3xs px-0.5 whitespace-nowrap">۱ + رشد ریالی</span>}
                                denominator={<span className="text-3xs px-0.5 whitespace-nowrap">۱ + مبنای تورم</span>}
                              />
                              <span>− ۱</span>
                              <span className={`font-bold whitespace-nowrap ${tone(v1b)}`}>
                                {volFloor != null && volFloor > 0
                                  ? `≥ ${toFaDigits(volFloor)}٪`
                                  : breadthMin != null
                                    ? `پهنا ≥ ${toFaDigits(Math.round(breadthMin * 100))}٪`
                                    : 'بدون کف'}
                              </span>
                            </div>
                          </div>
                          <span className="mt-0.5 text-3xs text-text-muted">
                            {`مبنای تورم ${inflationBasis == null ? '—' : toFaDigits(inflationBasis) + '٪'} — از پنلِ تنظیمات` +
                              (vol?.breadth?.improved_months != null && vol?.breadth?.compared_months
                                ? ` · ${toFaDigits(vol.breadth.improved_months)} از ${toFaDigits(vol.breadth.compared_months)} ماه بهتر`
                                : '')}
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  {onDrill ? <DrillAffordance active={isActive} /> : null}
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
            /* رنگِ سه‌حالته فقط آن‌جا که موتور band/ideal فرستاده (شاخص ۳)؛
               جایِ دیگر «ایده‌آل» ساخته نمی‌شود. */
            let cardQuality = qualityFrom(v);

            let resultNumberNode: React.ReactNode = null;
            let mathFormulaNode: React.ReactNode = null;
            /** سطرِ اضافیِ پایینِ فرمول — همین‌جا فقط برای کارت EPS (#101) */
            let extraNode: React.ReactNode = null;
            let benchmarkHint: string | null = '';

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
                  className={v ? 'text-accent-green' : v === false ? 'text-accent-red' : 'text-text-primary'}
                >
                  {epsRising ? `${toFaDigits(epsYearsReq)} سالِ رشد` : epsYears ? `${toFaDigits(epsYears)} سال` : 'رشدِ متوالی ندارد'}
                </span>
              );

              // #101 — «درصدها نوشته بشه بدونیم چقدر رشد داشته». عددِ درصد از
              // سریِ EPSِ خودِ بک‌اند ساخته می‌شود (eps_yoy_pct اگر آمده باشد
              // مقدم است)؛ داوریِ شاخص ۲ هرگز اینجا بازسازی نمی‌شود.
              const growths = epsChanges(i2?.eps_series ?? [], i2?.eps_yoy_pct);
              const interimPct = i2?.interim?.interim_yoy_pct ?? null;
              extraNode = (
                <div
                  className="mt-1 flex flex-wrap items-center justify-center gap-x-1.5 gap-y-0.5 text-3xs"
                  data-testid="fts-card-eps-growth"
                  title="درصد رشد سال‌به‌سالِ EPS (قدیم ← جدید) — نمایشی است، حکمِ شاخص ۲ را عوض نمی‌کند"
                >
                  <span className="text-text-muted">رشد سال‌به‌سال:</span>
                  {growths.some((p) => p != null) ? (
                    growths.map((p, gi) =>
                      p == null ? (
                        <span key={gi} className="num font-mono font-bold text-text-muted">
                          —
                        </span>
                      ) : (
                        <span
                          key={gi}
                          className={`num font-mono font-black ${
                            p > 0 ? 'text-accent-green' : p < 0 ? 'text-accent-red' : 'text-text-secondary'
                          }`}
                        >
                          {epsChangeText(p)}
                        </span>
                      ),
                    )
                  ) : (
                    /* «داده نداریم» هیچ‌وقت ۰٪ و هیچ‌وقت فلش سبز/سرخ نمی‌شود */
                    <span className="font-bold text-text-muted" data-testid="fts-card-eps-growth-nodata">
                      {epsGrowthReason(i2?.eps_series ?? [])}
                    </span>
                  )}
                  {interimPct != null ? (
                    <span
                      className={`num font-mono font-black ${
                        interimPct > 0 ? 'text-accent-green' : interimPct < 0 ? 'text-accent-red' : 'text-text-secondary'
                      }`}
                      title="رشد EPS میاندوره نسبت به همان دورهٔ سال قبل (محاسبهٔ بک‌اند)"
                    >
                      میاندوره {epsChangeText(interimPct)}
                    </span>
                  ) : null}
                </div>
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
              benchmarkHint = `شرط: سود هر سهم در ${toFaDigits(epsYearsReq)} سالِ متوالی بالاتر رفته باشد`;
            } else if (key === '3_gross_margin') {
              const i3 = indicators?.['3'];
              const marginFloor = i3?.threshold ?? null;
              const marginIdeal = i3?.ideal_threshold ?? i3?.optimal_threshold ?? null;
              cardQuality = qualityFrom(v, i3?.band === 'ideal');
              const marginPct =
                i3?.margin_pct ??
                (typeof audit?.['3_gross_margin']?.actualValue === 'number'
                  ? (audit?.['3_gross_margin']?.actualValue as number)
                  : null);

              resultNumberNode = (
                <span className={QUALITY_TEXT[cardQuality]}>
                  {marginPct != null ? `${toFaDigits(marginPct.toFixed(1))}٪` : '—'}
                </span>
              );

              mathFormulaNode = (
                <div className="flex items-center justify-center gap-1 text-3xs font-mono text-text-secondary whitespace-nowrap" dir="ltr">
                  <MathFraction
                    numerator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">سود ناخالص</span>}
                    denominator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">درآمد عملیاتی</span>}
                  />
                  <span className="text-3xs text-text-muted">× ۱۰۰</span>
                  {marginFloor != null && (
                    <span className={`text-2xs font-black ms-0.5 ${tone(v)}`}>≥ {toFaDigits(marginFloor)}٪</span>
                  )}
                </div>
              );
              benchmarkHint =
                marginFloor == null
                  ? null
                  : `کف استاندارد: ${toFaDigits(marginFloor)}٪${
                      marginIdeal == null ? '' : ` (ایده‌آل ${toFaDigits(marginIdeal)}٪)`
                    }`;
            } else if (key === '4_sales_to_mcap') {
              const i4 = indicators?.['4'];
              /** هر دو کف از خودِ موتور (#150) — پیش‌تر ۰.۳۳ِ ثابتِ JSX بود */
              const salesFloor = cfgNum(i4?.sales_threshold);
              const potFloor = cfgNum(i4?.potential_threshold);
              const salesRatio =
                cfgNum(i4?.sales_to_mcap) ??
                (typeof audit?.['4_sales_to_mcap']?.actualValue === 'number'
                  ? (audit?.['4_sales_to_mcap']?.actualValue as number)
                  : null);
              const potPct = cfgNum(i4?.potential_pct);

              // تیترِ کارت «پتانسیل سود تا آخر سال» است، پس عددِ درشت همان
              // درصدِ پتانسیل است نه نسبتِ فروش÷ارزش (فایرا: ۲۷.۵٪ نه ۰.۹۷×).
              resultNumberNode = (
                <span className={v ? 'text-accent-green' : v === false ? 'text-accent-red' : 'text-text-primary'}>
                  {potPct != null
                    ? `${toFaDigits(potPct.toFixed(1))}٪`
                    : salesRatio != null
                      ? `${toFaDigits(salesRatio.toFixed(2))}×`
                      : '—'}
                </span>
              );

              extraNode = (
                <span className="num mt-0.5 block truncate text-3xs text-text-muted" data-testid="fts-card-4-secondary"
                  title={salesFloor == null ? undefined : `کفِ قبولِ نسبت: ${toFaDigits(salesFloor.toFixed(2))}×`}>
                  {salesRatio == null
                    ? 'نسبت فروش به ارزش بازار: بدون داده'
                    : `نسبت فروش ÷ ارزش بازار ${toFaDigits(salesRatio.toFixed(2))}×` +
                      (salesFloor == null ? '' : ` · کف ${toFaDigits(salesFloor.toFixed(2))}×`)}
                </span>
              );

              // فرمولِ پتانسیل سود، ریاضی و با واژه‌هایِ خودِ جزوه (#155)
              mathFormulaNode = (
                <div className="flex flex-col items-center gap-0.5 text-3xs font-mono text-text-secondary" dir="ltr">
                  <div className="flex items-center gap-1 whitespace-nowrap">
                    <MathFraction
                      numerator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">تخمین فروش ۱۲ ماهه × حاشیهٔ سود ناخالص</span>}
                      denominator={<span className="text-3xs text-text-primary px-0.5 whitespace-nowrap">ارزش بازار</span>}
                    />
                    <span>× ۱۰۰</span>
                  </div>
                  {potFloor != null ? (
                    <span className={`text-2xs font-black ${tone(v)}`}>≥ {toFaDigits(potFloor)}٪</span>
                  ) : null}
                </div>
              );
              benchmarkHint =
                potFloor == null
                  ? 'کفِ پتانسیل از بک‌اند نرسید'
                  : `کفِ پتانسیل سود ${toFaDigits(potFloor)}٪ از ارزش بازار`;
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
                  className={`truncate ${
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

              // نماد مجموعه و ∈ در پاراگرم RTL جای اجزاش را عوض می‌کرد
              // («دستوری: (بورس کالا + نرخ آزاد) ≠ نرخ»). صورتِ سادهٔ فارسی.
              mathFormulaNode = (
                <div className="flex items-center justify-center text-3xs font-mono whitespace-nowrap">
                  <span className="text-text-secondary">قیمت دستوری نباشد — آزاد / بورس کالا</span>
                </div>
              );
              benchmarkHint = 'رژیم قیمت‌گذاری صنعت';
            }

            const industryBadge = isIndustry ? (
              <AuditBadge
                state={v == null ? 'na' : v ? 'pass' : 'fail'}
                /* متنِ کامل هم در عددِ درشت هست؛ بج فقط «چرا؟» است (#169) */
                label="ⓘ"
                hintTitle={`${industryGateLabel(industryMode)} · ${industryGatePassLabel(v === true)}`}
                evidence={audit?.['5_industry'] ?? null}
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
                className={`col-span-1 ${span} group flex flex-col justify-between rounded-xl border p-2.5 text-start transition-all duration-200 cursor-pointer ${getCardToneClasses(
                  cardQuality,
                  isActive,
                )}`}
              >
                {/* ردیف ۱: نامِ شاخص + برچسبِ نتیجه (#149) */}
                <div className="flex items-start justify-between gap-1">
                  <span className="text-xs font-black text-text-primary group-hover:text-accent-blue transition-colors">
                    {l.label}
                  </span>
                  <VerdictChip pass={v} quality={cardQuality} testId={`fts-verdict-${key}`} />
                </div>

                {/* ردیف ۲: عددِ نتیجۀ درشت + شاهدِ ممیزی */}
                <div className="mb-1 flex items-end justify-between gap-1.5">
                  <BigResult testId={`fts-result-${l.key}`}>{resultNumberNode}</BigResult>
                  {industryBadge ?? (
                    <AuditBadge
                      state={v == null ? 'na' : v ? 'pass' : 'fail'}
                      label={v == null ? (axisNa ? 'N/A' : gapLabel(key)) : 'ⓘ'}
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

                {/* ردیف وسط: فرمول ریاضی واقعی با کسر و نمادهای دقیق */}
                <div className="my-1.5 flex items-center justify-center rounded-lg border border-border-c/30 bg-bg-card/40 py-1.5 px-1.5 overflow-hidden">
                  {mathFormulaNode}
                </div>

                {/* سطر درصد رشد EPS (#101) — بقیهٔ کارت‌ها null می‌دهند و چیزی رندر نمی‌شود */}
                {extraNode}

                {/* ردیف پایین: شرط مرجع + نشانهٔ کلیک (#169) */}
                <div className="mt-1 flex items-end justify-between gap-1.5">
                  <span className="min-w-0 flex-1 text-3xs leading-snug text-text-muted line-clamp-2">{benchmarkHint}</span>
                  {onDrill ? <DrillAffordance active={isActive} /> : null}
                </div>
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
