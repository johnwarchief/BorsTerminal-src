// features/fundamental/components/FtsDrillDown.tsx -- Drill-down تعاملی ۵ شاخص
// با کلیک روی هر کارت شاخص FtsCard پنل زیرین باز می‌شود و نمودار +
// فرمول شفافِ همان شاخص نمایش می‌یابد. همهٔ داده‌ها از card.indicators
// می‌آیند ( همان چیزی که موتور FTS v10 بک‌اند محاسبه کرده ) — این
// کامپوننت فقط شفاف‌سازی می‌کند، نه محاسبهٔ دوباره.
import { toFaDigits, fmtPct, fmtInt } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { useElementWidth } from '@shared/hooks/useElementWidth';
import { GapHint, epsGapReason, GENERIC_GAP_REASON, VALUATION_GAP_REASON } from './GapHint';
import type { FtsCard } from '../api/useFtsCard';
import type { FiscalQuarter } from '../lib/fundMath';
import { EPS_PARTIAL_TESTID, epsChangeText, epsChanges, epsFailReason, epsGapLabel, epsHistory, epsRealYears } from '../lib/epsHistory';
import { industryGateTone } from '../lib/industryGate';
import { MathFraction } from './MathFormula';
import { FTS_PANEL_TITLE, FTS_FX_TITLE } from '@shared/lib/ftsLabels';
import {
  NO_ANNUAL_SALES,
  NO_GROSS_MARGIN,
  NO_MCAP,
  NOT_COMPUTABLE,
  gapReason as axisGapReason,
  gapTooltip as axisGapTooltip,
} from '../lib/gapReason';

export type DrillDownKey = '1' | '2' | '3' | '4' | '5';

const PANEL_TITLE: Record<DrillDownKey, string> = FTS_PANEL_TITLE;

const Q_LABEL = ['بهار', 'تابستان', 'پاییز', 'زمستان'];

function Bar({
  value,
  max,
  tone,
  label,
  valueLabel,
}: {
  value: number;
  max: number;
  tone: 'blue' | 'green' | 'red' | 'yellow';
  label: string;
  valueLabel: string;
}) {
  const w = Math.max(2, Math.min(100, (value / (max || 1)) * 100));
  const color =
    tone === 'blue' ? 'bg-accent-blue' : tone === 'green' ? 'bg-accent-green' : tone === 'red' ? 'bg-accent-red' : 'bg-accent-yellow';
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 shrink-0 text-2xs text-text-secondary">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-card">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
      </div>
      <span className="num w-16 shrink-0 text-end text-2xs font-bold text-text-primary">{valueLabel}</span>
    </div>
  );
}

/** شاخص ۱: درآمد YTD اخیر در برابر سال قبل + کفِ آستانه + وضعیت N/A هلدینگ */
function Panel1({ card, physicalApplicable }: { card: FtsCard; physicalApplicable: boolean }) {
  const mon = card.indicators?.['1']?.monetary;
  const vol = card.indicators?.['1']?.volume;
  const growth = mon?.monetary_pct ?? null;
  const now = mon?.ytd_now_bt ?? null;
  const prev = mon?.ytd_prev_bt ?? null;
  // اثر تورم در خودِ آستانه‌های جزوه (کف ۴۰ / هدف ۶۰) لحاظ می‌شود؛ نرخِ تورمِ
  // جدا و «رشد واقعی»ِ دوباره‌محاسبه‌شده در UI یعنی دو جواب برای یک نماد.
  const floor = mon?.threshold ?? null;
  const realGrowth = vol?.real_pct ?? null;
  const maxBar = Math.max(now ?? 0, prev ?? 0, 1);
  const beatsFloor = growth != null && floor != null && growth >= floor;
  const floorDelta = growth != null && floor != null ? growth - floor : null;
  const gapFloor = floorDelta == null ? null : Math.abs(Math.round(floorDelta * 10) / 10);
  const passes1a = card.passes?.['1a_monetary_growth'];
  // «جلو زدن از تارگت» را بک‌اند با همان آستانهٔ جزوه می‌سنجد؛ نرخِ تورمِ
  // جدا در UI یعنی دو جواب برای یک نماد، پس نشانه از حکمِ شاخص ۱ می‌آید.
  const beatsTarget = passes1a ?? beatsFloor;
  const passes1b = card.passes?.['1b_volume_growth'];

  return (
    <div className="flex flex-col gap-3.5">
      {/* نوار وضعیت و معیارِ آستانه */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-c/40 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          {growth == null ? (
            <GapHint reason={axisGapTooltip('1a_monetary_growth')}>
              <span className="rounded-full border border-accent-yellow/40 bg-bg-card/60 px-2.5 py-0.5 text-xs font-semibold text-accent-yellow">
                {axisGapReason('1a_monetary_growth').label}
              </span>
            </GapHint>
          ) : (
            <Badge tone={(passes1a ?? beatsFloor) ? 'green' : 'yellow'}>
              رشد <span className="num font-black">{fmtPct(growth)}</span>
              {floor == null ? (
                <span className="text-2xs font-normal"> / بدون آستانه</span>
              ) : beatsFloor ? (
                <span className="text-2xs font-bold text-accent-green">
                  {' '}(+{toFaDigits(gapFloor!.toFixed(1))}٪ بر کفِ {toFaDigits(floor)}٪)
                </span>
              ) : (
                <span className="text-2xs font-bold text-accent-yellow">
                  {' '}({toFaDigits(gapFloor!.toFixed(1))}٪ تا کفِ {toFaDigits(floor)}٪)
                </span>
              )}
            </Badge>
          )}
          {mon?.months != null ? (
            <Badge tone="blue">
              <span className="num">{toFaDigits(mon.months)}</span> ماهه · <span className="num">{toFaDigits(mon.period ?? '')}</span>
            </Badge>
          ) : null}
        </div>

        {/* معیارِ موتور، فقط‌خواندنی — تغییرش جای خودش است: کشوی تنظیمات */}
        <div className="flex items-center gap-2 rounded-xl border border-border-c/60 bg-bg-card/60 px-2.5 py-1" data-testid="fts-floor-criterion">
          <span className="text-2xs font-bold text-text-secondary">کفِ آستانهٔ رشد:</span>
          <span className="font-mono text-2xs font-black text-text-primary">
            {floor == null ? '—' : `≥ ${toFaDigits(floor)}٪`}
          </span>
        </div>
      </div>

      {/* ۱-الف: مقایسه فروش ریالی و درصد رشد */}
      <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-3.5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-black text-text-primary">۱-الف. مقایسه فروش ریالی</span>
            <span className="text-2xs text-text-muted">(دوره جاری در برابر دوره مشابه سال قبل)</span>
          </div>
          {growth != null ? (
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xs text-text-muted">نرخ رشد ریالی:</span>
              <span className={`font-mono text-sm font-black ${(passes1a ?? beatsFloor) ? 'text-accent-green' : 'text-accent-yellow'}`}>
                {growth >= 0 ? '+' : '−'}{toFaDigits(Math.abs(growth).toFixed(1))}٪
              </span>
            </div>
          ) : null}
        </div>

        {/* کارت‌های مقایسه شفاف دو دوره در کنار هم */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 my-2.5">
          {/* دوره جاری */}
          <div className="flex flex-col justify-between rounded-xl border border-accent-blue/30 bg-accent-blue/5 p-2.5">
            <div className="flex items-center justify-between text-2xs text-text-muted mb-1">
              <span className="font-bold text-accent-blue">عملکرد دوره جاری</span>
              {mon?.period ? <span className="font-mono">{toFaDigits(mon.period)}</span> : null}
            </div>
            <div className="flex items-baseline justify-between mt-1">
              <span className="text-2xs text-text-secondary">فروش تجمیعی:</span>
              <span className="font-mono text-sm font-black text-text-primary">
                {now == null ? '—' : `${fmtInt(now)} ب.ت`}
              </span>
            </div>
            {mon?.months ? (
              <span className="text-3xs text-text-muted mt-1 font-mono">
                {toFaDigits(mon.months)} ماهه از ابتدای سال مالی
              </span>
            ) : null}
          </div>

          {/* دوره مشابه سال قبل */}
          <div className="flex flex-col justify-between rounded-xl border border-border-c/60 bg-bg-card/60 p-2.5">
            <div className="flex items-center justify-between text-2xs text-text-muted mb-1">
              <span className="font-bold text-text-secondary">عملکرد سال قبل</span>
              {mon?.year && mon?.period ? (
                <span className="font-mono">{toFaDigits(mon.period.replace(String(mon.year), String(mon.year - 1)))}</span>
              ) : null}
            </div>
            <div className="flex items-baseline justify-between mt-1">
              <span className="text-2xs text-text-secondary">فروش تجمیعی:</span>
              <span className="font-mono text-sm font-black text-text-primary">
                {prev == null ? '—' : `${fmtInt(prev)} ب.ت`}
              </span>
            </div>
            {mon?.months ? (
              <span className="text-3xs text-text-muted mt-1 font-mono">
                همان بازهٔ {toFaDigits(mon.months)} ماهه در سال قبل
              </span>
            ) : null}
          </div>

          {/* اختلاف و تغییرات */}
          <div className={`flex flex-col justify-between rounded-xl border p-2.5 ${
            beatsTarget ? 'border-accent-green/30 bg-accent-green/5' : 'border-amber-400/30 bg-amber-400/5'
          }`}>
            <div className="flex items-center justify-between text-2xs mb-1">
              <span className="font-bold text-text-secondary">تغییر ریالی دوره</span>
              <span className={`font-mono text-2xs font-bold ${now == null || prev == null ? 'text-text-muted' : now >= prev ? 'text-accent-green' : 'text-accent-red'}`}>
                {now != null && prev != null ? (now >= prev ? 'رشد مثبت' : 'کاهش فروش') : '—'}
              </span>
            </div>
            <div className="flex items-baseline justify-between mt-1">
              <span className="text-2xs text-text-secondary">اختلاف فروش:</span>
              <span className={`font-mono text-sm font-black ${now == null || prev == null ? 'text-text-muted' : now >= prev ? 'text-accent-green' : 'text-accent-red'}`}>
                {now != null && prev != null ? `${now >= prev ? '+' : '−'}${fmtInt(Math.abs(now - prev))} ب.ت` : '—'}
              </span>
            </div>
            <span className="text-3xs text-text-muted mt-1">
              {floor == null
                ? 'کفِ رشدِ FTS در پاسخِ این نماد نیامده — عددی ساخته نمی‌شود.'
                : beatsTarget
                  ? `بالای کفِ ${toFaDigits(floor)}٪ FTS ✓`
                  : `زیر کفِ ${toFaDigits(floor)}٪ FTS`}
            </span>
          </div>
        </div>

        {/* نمودار میله‌ای افقی مقایسه تصویری دو دوره */}
        <div className="flex flex-col gap-2 my-3 rounded-lg border border-border-c/40 bg-bg-card/30 p-2.5">
          <Bar
            label="دوره جاری (امسال)"
            value={now ?? 0}
            max={maxBar}
            tone="blue"
            valueLabel={now == null ? '—' : `${fmtInt(now)} ب.ت`}
          />
          <Bar
            label="دوره مشابه سال قبل"
            value={prev ?? 0}
            max={maxBar}
            tone="green"
            valueLabel={prev == null ? '—' : `${fmtInt(prev)} ب.ت`}
          />
        </div>

        {/* نمایش استاندارد فرمول ریاضی با جاگذاری دقیق مقادیر سهم */}
        <div className="my-2 flex flex-wrap items-center justify-center gap-1.5 rounded-lg border border-border-c/50 bg-bg-primary/50 py-2 px-3 font-mono text-2xs sm:text-xs" dir="ltr">
          <span className="font-bold text-accent-blue">رشد = </span>
          <span className="text-sm text-text-muted">(</span>
          <MathFraction
            numerator={
              <span className="text-3xs text-text-primary px-1 font-bold whitespace-nowrap">
                {now != null ? `${fmtInt(now)} ب.ت` : 'فروش دوره جاری'}
              </span>
            }
            denominator={
              <span className="text-3xs text-text-primary px-1 font-bold whitespace-nowrap">
                {prev != null ? `${fmtInt(prev)} ب.ت` : 'فروش دوره مشابه قبل'}
              </span>
            }
          />
          <span className="text-xs text-text-secondary">− 1</span>
          <span className="text-sm text-text-muted">)</span>
          <span className="text-xs text-text-secondary">× ۱۰۰</span>
          {growth != null ? (
            <>
              <span className="text-text-muted">=</span>
              <span className={`font-bold ${beatsTarget ? 'text-accent-green' : 'text-accent-yellow'}`}>
                {growth >= 0 ? '+' : '−'}{toFaDigits(Math.abs(growth).toFixed(1))}٪
              </span>
            </>
          ) : null}
        </div>

        <p className="mt-1 text-3xs leading-relaxed text-text-muted">
          فرمول FTS: رشد = (فروش تجمیعی دورهٔ جاری ÷ فروش تجمیعی همان دورهٔ سال قبل × ۱۰۰) − ۱۰۰
          {mon?.denominator_basis ? ` · مبنا: ${toFaDigits(mon.denominator_basis)}` : ''}
        </p>
      </div>

      {/* ۱-ب: رشد تولیدی / فیزیکی */}
      {physicalApplicable ? (
        <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-text-primary">۱-ب. رشد تولیدی (تناژ)</span>
              <span className="text-2xs text-text-muted">(حذف اثر نرخ تورم و ارزیابی رشد واقعی تولید)</span>
            </div>
            {realGrowth != null ? (
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xs text-text-muted">رشد تولیدی:</span>
                <span className={`font-mono text-sm font-black ${(passes1b ?? realGrowth >= 0) ? 'text-accent-green' : 'text-accent-red'}`}>
                  {realGrowth >= 0 ? '+' : '−'}{toFaDigits(Math.abs(realGrowth).toFixed(1))}٪
                </span>
              </div>
            ) : null}
          </div>
          <p className="text-2xs leading-relaxed text-text-secondary">
            {realGrowth != null
              ? `رشد واقعی پس از کسر اثر نرخ: ${realGrowth >= 0 ? '+' : '−'}${toFaDigits(Math.abs(realGrowth).toFixed(1))}٪` +
                (vol?.implied_price_pct != null
                  ? ` (اثر تقریبی نرخ ${toFaDigits(Math.round(vol.implied_price_pct))}٪)`
                  : '')
              : vol?.data_gap
                ? `${axisGapReason('1b_volume_growth').why} رشد تولیدی از این گزارش حساب نمی‌شود.`
                : 'رشد تولیدی قابل محاسبه نیست — گزارش ماهانهٔ تولیدی کدال ناقص است.'}
          </p>
        </div>
      ) : null}
    </div>
  );
}

/** شاخص ۲: نمودار پله‌ای EPS سال‌های مالی اخیر — رحیم‌تر با دادهٔ ناقص:
 *  با ≥۲ سالِ موجود همان سال‌ها را نشان می‌دهد ولی صریحاً «مردود در شاخص ۲
 *  (سابقهٔ ناقص)» برچسب می‌زند؛ با <۲ سال همان «شکاف داده» قبلی می‌ماند. */
function Panel2({ card }: { card: FtsCard }) {
  const ind = card.indicators?.['2'];
  const series = ind?.eps_series ?? [];
  /** #101: درصد رشدِ همان سری — اگر موتور فرستاده باشد همان مقدم است (کارت و
   *  دریل‌دان یک عدد)، وگرنه از روی سریِ خودِ بک‌اند حساب می‌شود. */
  const changes = epsChanges(series, ind?.eps_yoy_pct);
  const slots = ind?.period_slots ?? ind?.fiscal_years ?? [];
  const max = Math.max(1, ...series.filter((v): v is number => v != null && v > 0));
  const min = Math.min(0, ...series.filter((v): v is number => v != null));
  const span = max - min || 1;
  const rising = ind?.strictly_rising ?? null;
  const required = ind?.years_required ?? card.metrics?.eps_required ?? 3;
  const realYears = epsRealYears(series);
  /** همان منطق و برچسبِ جدولِ غربالگری/نردبان (lib/epsHistory) */
  const hist = epsHistory(series, required);
  const partialShown = ind?.partial == true && hist.state === 'partial';
  const gapWhy = epsGapReason({
    available: realYears,
    required,
    interimAvailable: ind?.interim?.available ?? false,
  });
  /** سابقهٔ کامل ولی گیت رد ⇒ دلیل واقعی شکست (نه شکاف داده) */
  const failReason =
    ind != null && (ind.years_available ?? realYears) >= required && ind.data_gap !== true && ind.pass !== true
      ? epsFailReason({
          series,
          slots: ind.period_slots ?? ind.fiscal_years,
          strictlyRising: ind.strictly_rising,
          allProfitable: ind.all_profitable,
        })
      : null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {rising == null && realYears < 2 ? (
          <GapHint reason={`${gapWhy} راه‌حل: ${axisGapReason('2_eps_trend').fix}`}>
            <span className="rounded-full border border-accent-yellow/40 bg-bg-card/60 px-2.5 py-0.5 text-xs font-semibold text-accent-yellow">
              {epsGapLabel(realYears)}
            </span>
          </GapHint>
        ) : partialShown ? (
          <span
            data-testid={EPS_PARTIAL_TESTID}
            title={gapWhy}
            className="inline-flex items-center rounded-full border border-accent-susp/40 bg-accent-susp-bg px-2.5 py-0.5 text-xs font-semibold text-accent-susp"
          >
            {hist.label}
          </span>
        ) : (
          <span title={failReason ?? undefined}>
          <Badge tone={rising == null ? 'gray' : rising ? 'green' : 'red'}>
            {rising == null ? epsGapLabel(realYears) : rising ? 'سه سالِ متوالی بالاتر ✓' : 'رشدِ متوالی ندارد ✗'}
          </Badge>
          </span>
        )}
        {ind?.evidence_tier ? (
          <span className="text-2xs text-text-muted" data-testid="drilldown-evidence-tier">
            مدرک: {EVIDENCE_TIER_FA[ind.evidence_tier] ?? ind.evidence_tier}
          </span>
        ) : null}
        {ind?.interim?.eps_interim != null ? (
          <Badge tone="gray">
            میاندوره: <span className="num">{toFaDigits(ind.interim.eps_interim)}</span> (<span className="num">{toFaDigits(ind.interim.period_months ?? 0)}</span> ماهه)
          </Badge>
        ) : null}
      </div>
      {series.length > 0 ? (
        <div className="flex items-end gap-3" data-testid="drilldown-eps-chart">
          {series.map((v, i) => {
            const h = v == null || v <= 0 ? 4 : Math.max(6, ((v - min) / span) * 90);
            return (
              <div key={i} className="flex min-w-14 flex-1 flex-col items-center gap-1">
                <span className="num text-2xs font-bold text-text-primary">{v == null ? '؟' : toFaDigits(v.toFixed(0))}</span>
                {/* درصد رشد نسبت به سال قبل — جایی که محاسبه نمی‌شود هیچ عددی
                    نیست (نه ۰٪، نه فلش)، طبق قاعدهٔ «نبودِ داده صفر نیست». */}
                <span
                  className={`num text-3xs font-black ${
                    changes[i] == null
                      ? 'text-text-muted'
                      : changes[i]! > 0
                        ? 'text-accent-green'
                        : changes[i]! < 0
                          ? 'text-accent-red'
                          : 'text-text-secondary'
                  }`}
                  data-testid={`drilldown-eps-change-${i}`}
                  title={changes[i] == null ? 'درصد رشد قابل محاسبه نیست' : 'رشد سود هر سهم نسبت به سال مالی قبل'}
                >
                  {epsChangeText(changes[i]) ?? '—'}
                </span>
                <div
                  className={`w-full rounded-t-lg ${v == null ? 'bg-text-muted/20' : rising === false && i > 0 && (series[i - 1] ?? 0) > v ? 'bg-accent-red/70' : 'bg-accent-green/70'}`}
                  style={{ height: `${h}px` }}
                />
                <span className="num text-2xs text-text-muted">{toFaDigits(slots[i] ?? '—')}</span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-2xs text-text-muted">سری EPS سالانهٔ حسابرسی‌شده موجود نیست.</p>
      )}
      {/* نمایش استاندارد شرط ریاضی */}
      <div className="my-2 flex flex-col items-center justify-center gap-1 rounded-lg border border-border-c/50 bg-bg-primary/50 py-1.5 px-3 font-mono text-xs">
        <span className="text-2xs font-bold text-accent-blue">شرط شاخص ۲:</span>
        <span className="flex items-center justify-center gap-2 text-text-primary font-bold" dir="ltr">
          EPS<sub>t</sub> &gt; EPS<sub>t-1</sub> &gt; EPS<sub>t-2</sub> &gt; 0
        </span>
      </div>

      <p className="text-2xs leading-relaxed text-text-secondary">
        فرمول: EPS هر سال مالی (صورت سود و زیان ۱۲ماههٔ حسابرسی‌شدهٔ ۱۲/۲۹) — باید سه سالِ متوالی بالاتر برود.
        {ind?.interim?.annualize_label ? ` · میاندوره: ${ind.interim.annualize_label}` : ''}
      </p>
      {partialShown ? (
        <p className="text-2xs leading-relaxed text-accent-susp">
          دادهٔ موجود (<span className="num">{toFaDigits(realYears)}</span> سال) نمایش داده می‌شود، اما چون سابقهٔ کامل <span className="num">{toFaDigits(required)}</span> ساله
          ندارد، این نماد در شاخص ۲ مردود است — داده دور ریخته نمی‌شود، ولی شرط سه‌ساله برآورده نمی‌شود.
        </p>
      ) : failReason != null ? (
        <p className="text-2xs leading-relaxed text-accent-red" data-testid="eps-fail-reason">
          دلیل رد: {failReason}
        </p>
      ) : null}
    </div>
  );
}

/** شاخص ۳: فرمول + روند خطی ۶ فصل + آستانه‌ها */
function Panel3({ card, quarters }: { card: FtsCard; quarters: FiscalQuarter[] }) {
  /** عرضِ ظرف به‌جای viewBoxِ ثابت (#169) — ارتفاعِ نمودار ثابت می‌ماند */
  const [mRef, mW] = useElementWidth<HTMLDivElement>(400);
  const ind = card.indicators?.['3'];
  const margin = ind?.margin_pct ?? null;
  /** کف و سقفِ نوار را موتور می‌گوید؛ اگر در JSX حک می‌شدیم، هر «ذخیره» در
   *  کشوی تنظیمات برچسبِ این پنل را خلافِ آستانهٔ واقعی می‌کرد. */
  const floor = ind?.threshold ?? null;
  const ceil = ind?.optimal_threshold ?? ind?.ideal_threshold ?? null;
  /** رأیِ نهایی هم بازخوانی نمی‌شود: optimal و passِ خودِ موتور خوانده می‌شوند. */
  const band =
    margin == null
      ? 'na'
      : ind?.pass === false
        ? 'rejected'
        : ind?.optimal === true
          ? 'ideal'
          : 'conditional';
  const BAND_LABEL: Record<string, string> = { ideal: 'مطلوب', conditional: 'مشروط', rejected: 'مردود', na: 'N/A' };
  // روند خطی ۶ فصل حاشیهٔ **ناخالص** فصلی (تفکیک‌شده از fundMath).
  // #102: مبنای مقایسه با درآمد، سود ناخالص است. FiscalQuarter.margin از
  // سود ناخالص ساخته می‌شود و وقتی آن NULL است (صندوق/هلدینگ بدون سطر بهای
  // تمام‌شده) null می‌ماند — پس این فیلتر آن فصل‌ها را بیرون می‌گذارد و نمودار
  // برای نمادهای بی‌سود-ناخالص رسم نمی‌شود. دیگر هیچ‌جا سود خالص زیر برچسب
  // «سود ناخالص» نمایش داده نمی‌شود.
  const trend = quarters.filter((q) => q.margin != null).slice(-6);
  const getMargin = (q: FiscalQuarter) => q.margin ?? 0;
  const maxTrend = Math.max(1, ...trend.map((q) => Math.abs(getMargin(q))));
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={band === 'ideal' ? 'green' : band === 'conditional' ? 'yellow' : band === 'rejected' ? 'red' : 'gray'}>
          {margin == null ? 'N/A' : `${fmtPct(margin)} · ${BAND_LABEL[band]}`}
        </Badge>
        {ind?.basis ? (
          <span className="text-2xs text-text-muted" data-testid="drilldown-margin-basis">
            مبنای محاسبه: {toFaDigits(ind.basis)}
          </span>
        ) : null}
      </div>
      {trend.length >= 2 ? (
        <div ref={mRef} className="w-full">
          <svg
            viewBox={`0 0 ${mW} 128`}
            width={mW}
            height={128}
            style={{ width: '100%', height: '128px' }}
            className="block"
            role="img"
            aria-label="روند ۶ فصل حاشیه سود ناخالص"
            data-testid="drilldown-margin-chart"
          >
            {(() => {
              const W = mW;
              const H = 128;
              const P = 24;
              const pts = trend.map((q, i) => {
                const m = getMargin(q);
                return { x: P + (i * (W - P * 2)) / (trend.length - 1), y: H - P - (Math.max(0, m) / maxTrend) * (H - P * 2) };
              });
              const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
              return (
                <>
                  <line x1={P} x2={W - P} y1={H - P} y2={H - P} stroke="var(--border-color)" strokeWidth="1" />
                  {pts.map((p, i) => (
                    <g key={i}>
                      <circle cx={p.x} cy={p.y} r="3.5" fill="var(--accent-blue)" />
                      <text x={p.x} y={H - 8} textAnchor="middle" fontSize="9.5" fill="var(--text-muted)">
                        {`${Q_LABEL[trend[i].quarter - 1]} ${toFaDigits(trend[i].yearLabel.slice(2))}`}
                      </text>
                    </g>
                  ))}
                  <path d={line} fill="none" stroke="var(--accent-blue)" strokeWidth="2" />
                </>
              );
            })()}
          </svg>
        </div>
      ) : (
        quarters.length > 0 ? (
          <p className="text-2xs leading-relaxed text-text-muted" data-testid="drilldown-margin-no-trend">
            سود ناخالصِ فصلیِ این نماد در کدال ثبت نشده — روندِ حاشیهٔ ناخالص رسم نمی‌شود
            (نبودِ داده، صفر نیست).
          </p>
        ) : null
      )}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className={`rounded-lg border px-2 py-1.5 text-2xs font-bold ${band === 'rejected' ? 'border-accent-red/40 bg-accent-red/10 text-accent-red' : 'border-border-c bg-bg-primary text-text-muted'}`}>
          {floor == null ? 'بی‌کف' : `زیر ${toFaDigits(floor)}٪`} ← مردود
        </div>
        <div className={`rounded-lg border px-2 py-1.5 text-2xs font-bold ${band === 'conditional' ? 'border-accent-yellow/40 bg-accent-yellow/10 text-accent-yellow' : 'border-border-c bg-bg-primary text-text-muted'}`}>
          {floor == null || ceil == null ? 'مشروط' : `${toFaDigits(floor)}–${toFaDigits(ceil)}٪`} ← مشروط
        </div>
        <div className={`rounded-lg border px-2 py-1.5 text-2xs font-bold ${band === 'ideal' ? 'border-accent-green/40 bg-accent-green/10 text-accent-green' : 'border-border-c bg-bg-primary text-text-muted'}`}>
          {ceil == null ? 'بالای هدف' : `بالای ${toFaDigits(ceil)}٪`} ← مطلوب
        </div>
      </div>

      {/* نمایش استاندارد فرمول ریاضی */}
      <div className="my-1.5 flex items-center justify-center gap-2 rounded-lg border border-border-c/50 bg-bg-primary/50 py-1.5 px-3 font-mono text-xs" dir="ltr">
        <span className="font-bold text-accent-blue">حاشیهٔ ناخالص٪ = </span>
        <MathFraction
          numerator={<span className="text-2xs text-text-primary px-1">سود ناخالص</span>}
          denominator={<span className="text-2xs text-text-primary px-1">درآمدهای عملیاتی</span>}
        />
        <span className="text-xs text-text-secondary">× ۱۰۰</span>
        <span className="text-accent-green font-bold ms-2">{floor == null ? 'بی‌کف' : `≥ ${toFaDigits(floor)}٪`}</span>
      </div>

      <p className="text-2xs leading-relaxed text-text-secondary">
        فرمول: حاشیه = (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰{ind?.period_end ? ` · دوره: ${toFaDigits(ind.period_end)}` : ''}
        {ind?.na ? ' · این شرکت «بهای تمام‌شده» درج نمی‌کند — N/A' : ''}
      </p>
    </div>
  );
}

/** شاخص ۴: سالانه‌سازی داینامیک ×۱۲÷م + نسبت فروش ÷ ارزش بازار + پتانسیل سود */
function Panel4({ card }: { card: FtsCard }) {
  const ind = card.indicators?.['4'];
  const m = Math.max(1, Math.round(ind?.months_used ?? card.metrics?.months_used ?? 12));
  const scale = ind?.scale_factor ?? card.metrics?.scale_factor ?? 1;
  const ytd = ind?.annual?.ytd_sales_bt ?? null;
  const annualSales = ind?.annual_sales_bt ?? card.metrics?.annual_sales_bt ?? null;
  const s2m = ind?.sales_to_mcap ?? card.metrics?.sales_to_mcap ?? null;
  const potential = ind?.potential_pct ?? card.metrics?.profit_potential_pct ?? null;
  const mcapHt = ind?.mcap_ht ?? card.metrics?.mcap_hmt ?? null;
  const marginUsed = ind?.margin_used_pct ?? card.metrics?.gross_margin ?? null;
  /** کف‌ها از خودِ موتور (#150). نبودِشان «رد» نیست — فقط مقایسه نداریم. */
  const salesThresh = typeof ind?.sales_threshold === 'number' ? ind.sales_threshold : null;
  const potThresh = typeof ind?.potential_threshold === 'number' ? ind.potential_threshold : null;
  const salesFloorLabel = salesThresh == null ? 'کفِ نسبت از بک‌اند نرسید' : `≥ ${toFaDigits(salesThresh.toFixed(2))}×`;
  const scaleTable = ind?.annual?.scale_table ?? [];
  return (
    <div className="flex flex-col gap-3" data-testid="drilldown-panel-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="blue">م = <span className="num">{toFaDigits(m)}</span> ماه · ضریب ×<span className="num">{toFaDigits(scale.toFixed(2))}</span></Badge>
        {s2m != null ? (
          <Badge tone={salesThresh == null ? 'gray' : s2m >= salesThresh ? 'green' : 'yellow'}>
            نسبت فروش ÷ ارزش بازار <span className="num">{toFaDigits(s2m.toFixed(2))}</span>×
            {salesThresh == null ? '' : ` (کف ${toFaDigits(salesThresh.toFixed(2))}×)`}
          </Badge>
        ) : null}
        {potential != null ? (
          <Badge tone={potThresh == null ? 'gray' : potential >= potThresh ? 'green' : 'yellow'}>
            پتانسیل سود <span className="num">{fmtPct(potential)}</span>
            {potThresh == null ? '' : ` (کف ${toFaDigits(potThresh)}٪)`}
          </Badge>
        ) : null}
      </div>
      <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-3">
        <div className="mb-1.5 text-2xs font-bold text-text-primary">فرمول سالانه‌سازی داینامیک</div>
        <div className="num rounded-lg bg-bg-primary px-3 py-2 text-center text-xs font-bold text-accent-blue" data-testid="annualize-formula">
          فروش سالانه‌شده = (فروش تجمعی ÷ {toFaDigits(m)} ماه) × {toFaDigits(12)}
        </div>
        <div className="mt-2 flex items-center justify-center gap-2 rounded-lg border border-border-c/50 bg-bg-primary/50 py-1.5 px-3 font-mono text-xs" dir="ltr">
          <span className="font-bold text-accent-blue">فروش ÷ ارزش بازار = </span>
          <MathFraction
            numerator={<span className="text-2xs text-text-primary px-1">فروش سالانه‌شده</span>}
            denominator={<span className="text-2xs text-text-primary px-1">ارزش روز بازار</span>}
          />
          <span className="text-accent-green font-bold ms-2">{salesFloorLabel}</span>
        </div>
        <p className="mt-1.5 text-2xs leading-relaxed text-text-muted">
          N همان ماه‌های سپری‌شدهٔ سال مالی است — نه همیشه ۳ ماه ×۴. تقسیم بر صفر ممکن نیست: م = ۰ سالانه‌سازی ندارد و به فروش سالانهٔ کدال جانشین می‌شود.
        </p>
        {ytd != null ? (
          <p className="num mt-1.5 text-2xs text-text-secondary">
            فروش تجمیعی {fmtInt(ytd)} میلیارد تومان × {toFaDigits(scale.toFixed(2))} = {fmtInt(annualSales ?? 0)} میلیارد تومان سالانه
          </p>
        ) : null}
        <p className="mt-1 text-2xs leading-relaxed text-text-muted" data-testid="annualize-basis">
          مبنا: {m >= 12 ? '۱۲ ماه کاملِ سال مالی (بدون سالانه‌سازی)' : `سالانه‌شده از دورهٔ ${toFaDigits(m)} ماهه`}
          {ind?.annualize_basis ? ` · ${toFaDigits(ind.annualize_basis)}` : ''}
        </p>
        {ind?.annual?.reconciled === false ? (
          <p className="mt-1 text-2xs font-bold text-accent-yellow" data-testid="annualize-unreconciled">
            برآوردِ ماهانه با فروش صورت مالی سالانه هم‌خوان نبود؛ مبنا به فروش سالانهٔ کدال برگشت.
          </p>
        ) : null}
      </div>
      {scaleTable.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {scaleTable.map((s) => (
            <span
              key={s.months}
              className={`num rounded-md border px-1.5 py-0.5 text-2xs font-bold ${
                s.months === m ? 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue' : 'border-border-c bg-bg-primary text-text-muted'
              }`}
            >
              {toFaDigits(s.months)} ماه ×{toFaDigits(String(s.factor).replace('.', '٫'))}
            </span>
          ))}
        </div>
      ) : null}
      <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-3" data-testid="potential-formula">
        <div className="mb-2 text-2xs font-bold text-text-primary">فرمول پتانسیل سود — شاخص ۴</div>
        {/* #202: کسرِ ریاضی با خطِ کسری، نه «A × B ÷ D»یِ متنی — و دقیقاً همان
            جبری که موتور می‌زند: (فروش × حاشیه) ÷ ارزش بازار، در ۱۰۰. هر
            متغیرِ غایب فقط درِ جایِ خودشِ کسر علت می‌گیرد. */}
        <div dir="ltr" className="flex flex-wrap items-center justify-center gap-x-2.5 gap-y-2 rounded-lg bg-bg-primary px-3 py-3 text-xs font-black leading-relaxed">
          <span dir="rtl" className="text-text-secondary">پتانسیل سود =</span>
          <span data-testid="potential-fraction" className="inline-flex">
            <MathFraction
              numerator={
                <span className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1">
                  <span className="rounded-md border border-border-c bg-bg-card/60 px-2 py-0.5 text-accent-blue">
                    A: فروش سالانه‌شده{' '}
                    {annualSales != null ? (
                      `${toFaDigits(fmtInt(annualSales))} ب.ت`
                    ) : (
                      <GapHint reason={VALUATION_GAP_REASON}>
                        <span className="text-accent-red">{NO_ANNUAL_SALES}</span>
                      </GapHint>
                    )}
                  </span>
                  <span className="text-text-secondary">×</span>
                  <span className="rounded-md border border-border-c bg-bg-card/60 px-2 py-0.5 text-accent-blue">
                    B: حاشیه ناخالص{' '}
                    {marginUsed != null ? (
                      fmtPct(marginUsed)
                    ) : (
                      <GapHint reason={GENERIC_GAP_REASON}>
                        <span className="text-accent-red">{NO_GROSS_MARGIN}</span>
                      </GapHint>
                    )}
                  </span>
                </span>
              }
              denominator={
                <span className="rounded-md border border-border-c bg-bg-card/60 px-2 py-0.5 text-accent-blue">
                  D: ارزش بازار{' '}
                  {mcapHt != null ? (
                    `${toFaDigits(mcapHt.toFixed(2))} همت`
                  ) : (
                    <GapHint reason={VALUATION_GAP_REASON}>
                      <span className="text-accent-red">{NO_MCAP}</span>
                    </GapHint>
                  )}
                </span>
              }
            />
          </span>
          <span className="text-text-secondary">× ۱۰۰</span>
          <span className="text-text-secondary">=</span>
          <span className={`rounded-md px-2 py-0.5 ${potential != null ? 'bg-accent-green/15 text-accent-green' : 'bg-bg-card/60 text-accent-red'}`}>
            {potential != null ? (
              fmtPct(potential)
            ) : (
              <GapHint reason={VALUATION_GAP_REASON}>{NOT_COMPUTABLE}</GapHint>
            )}
          </span>
        </div>
        <p className="mt-1.5 text-2xs leading-relaxed text-text-muted">
          A از سالانه‌سازیِ دورۀ N ماهه می‌آید؛ B حاشیهٔ سود ناخالصِ آخرین دورۀ حسابرسی‌شده؛ D ارزش بازارِ روز. هر متغیرِ غایب فقط در جای خودش با علت مشخص می‌شود — بقیهٔ فرمول سالم نمایش می‌یابد.
        </p>
      </div>
    </div>
  );
}

/** شاخص ۵: ماتریس نوع قیمت‌گذاری + ریسک ناترازی انرژی + پتانسیل ارزی */
function Panel5({ card }: { card: FtsCard }) {
  const ind = card.indicators?.['5'];
  const regime = ind?.verdict ?? card.pricing_mode ?? 'neutral';
  const sector = ind?.sector ?? card.sector ?? '';
  const outlook = ind?.outlook ?? '';
  const isFree = regime === 'free';
  const isMandatory = regime === 'mandatory';
  // پتانسیل ارزی: صنایع صادراتی/دلاری از tokens آزاد جزوه (ی/ي هر دو)
  const fxText = `${(ind?.matched_tokens ?? []).join(' ')} ${ind?.sector ?? ''}`;
  const fxExposure = /شیشه|شيشه|شیمیایی|شيميايي|فلزات|کانی|كاني|کاشی|كاشي|سیمان|سيمان|نفت|صادراتی|صادراتي/.test(fxText);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={industryGateTone(regime)}>{ind?.regime_label ?? ind?.label ?? regime}</Badge>
        {sector ? <Badge tone="gray">{sector}</Badge> : null}
        {ind?.market_share_pct != null ? <Badge tone="blue">سهم بازار <span className="num">{fmtPct(ind.market_share_pct)}</span></Badge> : null}
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        <div className={`rounded-xl border p-2.5 ${isFree ? 'border-accent-green/40 bg-accent-green/10' : 'border-border-c bg-bg-primary'}`}>
          <div className="text-2xs font-bold text-text-primary">نوع قیمت‌گذاری</div>
          <div className={`mt-1 text-2xs leading-snug ${isFree ? 'text-accent-green' : isMandatory ? 'text-accent-red' : 'text-text-secondary'}`}>
            {isFree ? 'آزاد / بورس کالا — نرخ از بازار' : isMandatory ? 'دستوری — نرخ با مصوبهٔ دولت' : 'سایر صنایع — بررسی موردی'}
          </div>
        </div>
        <div className="rounded-xl border border-border-c bg-bg-primary p-2.5">
          <div className="text-2xs font-bold text-text-primary">ریسک ناترازی انرژی</div>
          <div className="mt-1 text-2xs leading-snug text-text-secondary">
            {/شیشه|شيشه|نیروگاه|برق|فولاد|پتروشیمی|پترو شیمی|سیمان|سيمان|فولاد|مجتمع فولاد/.test(fxText)
              ? 'انرژی‌بر — ناترازی گاز در زمستان (توقف خطوط) و برق در تابستان ریسک تولید است.'
              : 'صنعت انرژی‌بر نیست — ناترازی فصلی انرژی اثر محدودی دارد.'}
          </div>
        </div>
        <div className="rounded-xl border border-border-c bg-bg-primary p-2.5">
          <div className="text-2xs font-bold text-text-primary">{FTS_FX_TITLE}</div>
          <div className={`mt-1 text-2xs leading-snug ${fxExposure ? 'text-accent-green' : 'text-text-secondary'}`}>
            {fxExposure ? 'صادراتی/دلاری — درآمد به دلار گره خورده؛ پتانسیل نرخ ارز بالا.' : 'درآمد ریالی — پتانسیل ارزی مستقیم ندارد.'}
          </div>
        </div>
      </div>
      {outlook ? <p className="text-2xs leading-relaxed text-text-secondary">چشم‌انداز: {outlook}</p> : null}
      <p className="text-2xs leading-relaxed text-text-secondary">
        فرمول: صنعت دستوری (خودرو، دارو، نیروگاه، غذا، لاستیک، شوینده) مردود · آزاد (سیمان، فلزات، پتروشیمی، کانی، کاشی) مطلوب
      </p>
    </div>
  );
}

/** لایهٔ مدرکِ EPS — آینهٔ _EV_FA در api/fundamental.py (کلیدِ موتور به فارسی) */
const EVIDENCE_TIER_FA: Record<string, string> = {
  audited_year_end: '۱۲ماهه حسابرسی‌شدهٔ شرکت اصلی (غیرتلفیقی)',
  year_end_unaudited: 'سال‌پایانِ غیرتلفیقیِ حسابرسی‌نشده',
  consolidated_year_end: 'سال‌پایانِ تلفیقی (صورت ۱۲ماههٔ غیرتلفیقی منتشر نشده)',
  year_end_plus_interim: 'سال‌پایان + سال‌سازیِ میاندوره × ۱۲÷م برای تکمیلِ سه سال',
  insufficient: 'مبنای معتبری یافت نشد',
};

export function FtsDrillDown({
  card,
  active,
  quarters,
  physicalApplicable,
}: {
  card: FtsCard;
  active: DrillDownKey | null;
  quarters: FiscalQuarter[];
  physicalApplicable: boolean;
}) {
  if (!active) return null;
  return (
    <div className="glass-panel panel-in p-4" data-testid={`fts-drilldown-${active}`} aria-live="polite">
      <h3 className="mb-3 text-sm font-black text-text-primary">{PANEL_TITLE[active]}</h3>
      {active === '1' ? <Panel1 card={card} physicalApplicable={physicalApplicable} /> : null}
      {active === '2' ? <Panel2 card={card} /> : null}
      {active === '3' ? <Panel3 card={card} quarters={quarters} /> : null}
      {active === '4' ? <Panel4 card={card} /> : null}
      {active === '5' ? <Panel5 card={card} /> : null}
    </div>
  );
}
