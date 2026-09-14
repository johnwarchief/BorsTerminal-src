// features/fundamental/components/FtsDrillDown.tsx -- Drill-down تعاملی ۵ شاخص
// با کلیک روی هر کارت شاخص FtsCard پنل زیرین باز می‌شود و نمودار +
// فرمول شفافِ همان شاخص نمایش می‌یابد. همهٔ داده‌ها از card.indicators
// می‌آیند ( همان چیزی که موتور FTS v10 بک‌اند محاسبه کرده ) — این
// کامپوننت فقط شفاف‌سازی می‌کند، نه محاسبهٔ دوباره.
import { toFaDigits, fmtPct, fmtInt } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { GapHint, epsGapReason, GENERIC_GAP_REASON, PHYSICAL_NA_REASON, VALUATION_GAP_REASON } from './GapHint';
import type { FtsCard } from '../api/useFtsCard';
import type { FiscalQuarter } from '../lib/fundMath';
import { EPS_PARTIAL_TESTID, epsHistory, epsRealYears } from '../lib/epsHistory';

export type DrillDownKey = '1' | '2' | '3' | '4' | '5';

const PANEL_TITLE: Record<DrillDownKey, string> = {
  '1': 'شاخص ۱ — رشد فروش و درآمد',
  '2': 'شاخص ۲ — سابقه عملکرد سودسازی ۳ ساله',
  '3': 'شاخص ۳ — حاشیه سود ناخالص',
  '4': 'شاخص ۴ — فروش سالانه‌شده به ارزش بازار',
  '5': 'شاخص ۵ — چشم‌انداز صنعت و نرخ‌گذاری',
};

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
      <span className="w-20 shrink-0 text-[11px] text-text-secondary">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-card">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
      </div>
      <span className="num w-16 shrink-0 text-left text-[11px] font-bold text-text-primary">{valueLabel}</span>
    </div>
  );
}

/** شاخص ۱: درآمد YTD اخیر در برابر سال قبل + درصد رشد + مبنای تورم + وضعیت N/A هلدینگ */
function Panel1({ card, physicalApplicable }: { card: FtsCard; physicalApplicable: boolean }) {
  const mon = card.indicators?.['1']?.monetary;
  const vol = card.indicators?.['1']?.volume;
  const growth = mon?.monetary_pct ?? null;
  const now = mon?.ytd_now_bt ?? null;
  const prev = mon?.ytd_prev_bt ?? null;
  const inflation = mon?.threshold ?? null;
  const realGrowth = vol?.real_pct ?? null;
  const maxBar = Math.max(now ?? 0, prev ?? 0, 1);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {growth == null ? (
          <GapHint reason={GENERIC_GAP_REASON}>
            <Badge tone="gray">شکاف داده</Badge>
          </GapHint>
        ) : (
          <Badge tone={growth >= (inflation ?? 0) ? 'green' : 'yellow'}>رشد {fmtPct(growth)}</Badge>
        )}
        {mon?.months != null ? (
          <Badge tone="blue">{toFaDigits(mon.months)} ماهه · {toFaDigits(mon.period ?? '')}</Badge>
        ) : null}
        {inflation != null ? <Badge tone="gray">مبنای تورم {fmtPct(inflation, 0)}</Badge> : null}
      </div>
      <div className="flex flex-col gap-2">
        <Bar
          label="دورهٔ مشابه امسال"
          value={now ?? 0}
          max={maxBar}
          tone="blue"
          valueLabel={now == null ? '—' : `${fmtInt(now)} m‌ت`}
        />
        <Bar
          label="دورهٔ مشابه سال قبل"
          value={prev ?? 0}
          max={maxBar}
          tone="green"
          valueLabel={prev == null ? '—' : `${fmtInt(prev)} m‌ت`}
        />
      </div>
      <p className="text-[11px] leading-relaxed text-text-secondary">
        فرمول: رشد = (فروش تجمیعی دورهٔ امسال ÷ فروش تجمیعی همان دورهٔ سال قبل × ۱۰۰) − ۱۰۰
        {mon?.denominator_basis ? ` · مبنا: ${mon.denominator_basis}` : ''}
      </p>
      <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-2.5">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[11px] font-bold text-text-primary">رشد مقداری (تناژ فیزیکی)</span>
          {!physicalApplicable ? (
            <GapHint reason={PHYSICAL_NA_REASON}>
              <Badge tone="gray">N/A — غیرقابل اعمال</Badge>
            </GapHint>
          ) : null}
        </div>
        <p className="text-[11px] leading-relaxed text-text-secondary">
          {!physicalApplicable
            ? 'این شرکت تولیدی نیست و گزارش فیزیکی/تناژ ندارد؛ رشد مقداری برای هلدینگ و شرکت خدماتی معنا ندارد و خودکار نادیده گرفته می‌شود.'
            : realGrowth != null
              ? `رشد واقعی پس از کسر اثر نرخ: ${fmtPct(realGrowth)} (اثر تقریبی نرخ ${fmtPct(vol?.implied_price_pct ?? null, 0)})`
              : vol?.data_gap
                ? 'شکاف داده — ستون تناژ فیزیکی در گزارش ماهانهٔ کدال ثبت نشده است.'
                : 'شکاف داده — رشد مقداری قابل محاسبه نیست.'}
        </p>
      </div>
    </div>
  );
}

/** شاخص ۲: نمودار پله‌ای EPS سال‌های مالی اخیر — رحیم‌تر با دادهٔ ناقص:
 *  با ≥۲ سالِ موجود همان سال‌ها را نشان می‌دهد ولی صریحاً «مردود در شاخص ۲
 *  (سابقهٔ ناقص)» برچسب می‌زند؛ با <۲ سال همان «شکاف داده» قبلی می‌ماند. */
function Panel2({ card }: { card: FtsCard }) {
  const ind = card.indicators?.['2'];
  const series = ind?.eps_series ?? [];
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
  const gapReason = epsGapReason({
    available: realYears,
    required,
    interimAvailable: ind?.interim?.available ?? false,
  });
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {rising == null && realYears < 2 ? (
          <GapHint reason={gapReason}>
            <Badge tone="gray">شکاف داده</Badge>
          </GapHint>
        ) : partialShown ? (
          <span
            data-testid={EPS_PARTIAL_TESTID}
            className="inline-flex items-center rounded-full border border-accent-susp/40 bg-accent-susp-bg px-2.5 py-0.5 text-xs font-semibold text-accent-susp"
          >
            {hist.label}
          </span>
        ) : (
          <Badge tone={rising == null ? 'gray' : rising ? 'green' : 'red'}>
            {rising == null ? 'شکاف داده' : rising ? 'صعودی ✓' : 'صعودی نیست ✗'}
          </Badge>
        )}
        {ind?.evidence_tier ? <Badge tone="blue">{ind.evidence_tier}</Badge> : null}
        {ind?.interim?.eps_interim != null ? (
          <Badge tone="gray">
            میاندوره: {toFaDigits(ind.interim.eps_interim)} ({toFaDigits(ind.interim.period_months ?? 0)} ماهه)
          </Badge>
        ) : null}
      </div>
      {series.length > 0 ? (
        <div className="flex items-end gap-3" data-testid="drilldown-eps-chart">
          {series.map((v, i) => {
            const h = v == null || v <= 0 ? 4 : Math.max(6, ((v - min) / span) * 90);
            return (
              <div key={i} className="flex min-w-14 flex-1 flex-col items-center gap-1">
                <span className="num text-[11px] font-bold text-text-primary">{v == null ? '؟' : toFaDigits(v.toFixed(0))}</span>
                <div
                  className={`w-full rounded-t-lg ${v == null ? 'bg-text-muted/20' : rising === false && i > 0 && (series[i - 1] ?? 0) > v ? 'bg-accent-red/70' : 'bg-accent-green/70'}`}
                  style={{ height: `${h}px` }}
                />
                <span className="num text-[10px] text-text-muted">{toFaDigits(slots[i] ?? '—')}</span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-[11px] text-text-muted">سری EPS سالانهٔ حسابرسی‌شده موجود نیست.</p>
      )}
      <p className="text-[11px] leading-relaxed text-text-secondary">
        فرمول: EPS هر سال مالی (صورت سود و زیان ۱۲ماههٔ حسابرسی‌شدهٔ ۱۲/۲۹) — باید سه سال متوالی صعودی باشد.
        {ind?.interim?.annualize_label ? ` · میاندوره: ${ind.interim.annualize_label}` : ''}
      </p>
      {partialShown ? (
        <p className="text-[11px] leading-relaxed text-accent-susp">
          دادهٔ موجود ({toFaDigits(realYears)} سال) نمایش داده می‌شود، اما چون سابقهٔ کامل {toFaDigits(required)} ساله
          ندارد، این نماد در شاخص ۲ مردود است — داده حیف نمی‌شود ولی گیت سه‌ساله پاس نمی‌شود.
        </p>
      ) : null}
    </div>
  );
}

/** شاخص ۳: فرمول + روند خطی ۶ فصل + آستانه‌ها */
function Panel3({ card, quarters }: { card: FtsCard; quarters: FiscalQuarter[] }) {
  const ind = card.indicators?.['3'];
  const margin = ind?.margin_pct ?? null;
  const band =
    margin == null
      ? 'na'
      : margin >= (ind?.optimal_threshold ?? 30)
        ? 'ideal'
        : margin >= (ind?.threshold ?? 20)
          ? 'conditional'
          : 'rejected';
  const BAND_LABEL: Record<string, string> = { ideal: 'مطلوب', conditional: 'مشروط', rejected: 'مردود', na: 'N/A' };
  // روند خطی ۶ فصل حاشیه: سود عملیاتی ÷ درآمد (تفکیک‌شده از fundMath)
  const trend = quarters
    .filter((q) => q.revenue != null && (q.revenue ?? 0) > 0 && q.operatingProfit != null)
    .slice(-6);
  const maxTrend = Math.max(1, ...trend.map((q) => Math.abs(((q.operatingProfit ?? 0) / (q.revenue ?? 1)) * 100)));
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={band === 'ideal' ? 'green' : band === 'conditional' ? 'yellow' : band === 'rejected' ? 'red' : 'gray'}>
          {margin == null ? 'N/A' : `${fmtPct(margin)} · ${BAND_LABEL[band]}`}
        </Badge>
        {ind?.basis ? <Badge tone="blue">{ind.basis}</Badge> : null}
      </div>
      {trend.length >= 2 ? (
        <svg viewBox="0 0 400 120" className="w-full" role="img" aria-label="روند ۶ فصل حاشیه سود ناخالص" data-testid="drilldown-margin-chart">
          {(() => {
            const W = 400;
            const H = 120;
            const P = 24;
            const pts = trend.map((q, i) => {
              const m = ((q.operatingProfit ?? 0) / (q.revenue ?? 1)) * 100;
              return { x: P + (i * (W - P * 2)) / (trend.length - 1), y: H - P - (Math.max(0, m) / maxTrend) * (H - P * 2) };
            });
            const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
            return (
              <>
                <line x1={P} x2={W - P} y1={H - P} y2={H - P} stroke="var(--border-color)" strokeWidth="1" />
                {pts.map((p, i) => (
                  <g key={i}>
                    <circle cx={p.x} cy={p.y} r="3.5" fill="var(--accent-blue)" />
                    <text x={p.x} y={H - 8} textAnchor="middle" fontSize="9" fill="var(--text-muted)">
                      {`${Q_LABEL[trend[i].quarter - 1]} ${toFaDigits(trend[i].yearLabel.slice(2))}`}
                    </text>
                  </g>
                ))}
                <path d={line} fill="none" stroke="var(--accent-blue)" strokeWidth="2" />
              </>
            );
          })()}
        </svg>
      ) : null}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className={`rounded-lg border px-2 py-1.5 text-[10px] font-bold ${band === 'rejected' ? 'border-accent-red/40 bg-accent-red/10 text-accent-red' : 'border-border-c bg-bg-primary text-text-muted'}`}>
          زیر ۲۰٪ → مردود
        </div>
        <div className={`rounded-lg border px-2 py-1.5 text-[10px] font-bold ${band === 'conditional' ? 'border-accent-yellow/40 bg-accent-yellow/10 text-accent-yellow' : 'border-border-c bg-bg-primary text-text-muted'}`}>
          ۲۰–۳۰٪ → مشروط
        </div>
        <div className={`rounded-lg border px-2 py-1.5 text-[10px] font-bold ${band === 'ideal' ? 'border-accent-green/40 bg-accent-green/10 text-accent-green' : 'border-border-c bg-bg-primary text-text-muted'}`}>
          بالای ۳۰٪ → مطلوب
        </div>
      </div>
      <p className="text-[11px] leading-relaxed text-text-secondary">
        فرمول: حاشیه = (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰{ind?.period_end ? ` · دوره: ${toFaDigits(ind.period_end)}` : ''}
        {ind?.na ? ' · این شرکت «بهای تمام‌شده» درج نمی‌کند — N/A' : ''}
      </p>
    </div>
  );
}

/** شاخص ۴: سالانه‌سازی داینامیک ×۱۲÷م + نسبت فروش/مارکت‌کپ + پتانسیل سود */
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
  const salesThresh = ind?.sales_threshold ?? 0.5;
  const scaleTable = ind?.annual?.scale_table ?? [];
  return (
    <div className="flex flex-col gap-3" data-testid="drilldown-panel-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="blue">م = {toFaDigits(m)} ماه · ضریب ×{toFaDigits(scale.toFixed(2))}</Badge>
        {s2m != null ? (
          <Badge tone={s2m >= salesThresh ? 'green' : 'yellow'}>
            فروش/ارزش بازار {toFaDigits(s2m.toFixed(2))}× (کف {fmtPct(salesThresh * 100, 0)})
          </Badge>
        ) : null}
        {potential != null ? (
          <Badge tone={potential >= (ind?.potential_threshold ?? 33) ? 'green' : 'yellow'}>
            پتانسیل سود {fmtPct(potential)}
          </Badge>
        ) : null}
      </div>
      <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-3">
        <div className="mb-1.5 text-[11px] font-bold text-text-primary">فرمول سالانه‌سازی داینامیک</div>
        <div dir="ltr" className="num rounded-lg bg-bg-primary px-3 py-2 text-center text-xs font-bold text-accent-blue" data-testid="annualize-formula">
          Annualized Sales = (Cumulative Sales / {m}) × 12
        </div>
        <p className="mt-1.5 text-[10px] leading-relaxed text-text-muted">
          N همان ماه‌های سپری‌شدهٔ سال مالی است — نه همیشه ۳ ماه ×۴. تقسیم بر صفر ممکن نیست: م = ۰ سالانه‌سازی ندارد و به فروش سالانهٔ کدال جانشین می‌شود.
        </p>
        {ytd != null ? (
          <p className="num mt-1.5 text-[11px] text-text-secondary">
            فروش تجمیعی {fmtInt(ytd)} میلیارد تومان × {toFaDigits(scale.toFixed(2))} = {fmtInt(annualSales ?? 0)} میلیارد تومان سالانه
          </p>
        ) : null}
      </div>
      {scaleTable.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {scaleTable.map((s) => (
            <span
              key={s.months}
              className={`num rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${
                s.months === m ? 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue' : 'border-border-c bg-bg-primary text-text-muted'
              }`}
            >
              {toFaDigits(s.months)} ماه ×{toFaDigits(String(s.factor).replace('.', '٫'))}
            </span>
          ))}
        </div>
      ) : null}
      <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-3" data-testid="potential-formula">
        <div className="mb-2 text-[11px] font-bold text-text-primary">فرمول پتانسیل سود — شاخص ۴</div>
        <div dir="rtl" className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1.5 rounded-lg bg-bg-primary px-3 py-2.5 text-xs font-black leading-relaxed">
          <span className="text-text-secondary">پتانسیل سود =</span>
          <span className="rounded-md border border-border-c bg-bg-card/60 px-2 py-0.5 text-accent-blue">
            A: فروش سالانه‌شده{' '}
            {annualSales != null ? (
              `${toFaDigits(fmtInt(annualSales))} m‌ت`
            ) : (
              <GapHint reason={VALUATION_GAP_REASON}>
                <span className="text-accent-red">بدون داده</span>
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
                <span className="text-accent-red">بدون داده</span>
              </GapHint>
            )}
          </span>
          <span className="text-text-secondary">÷</span>
          <span className="rounded-md border border-border-c bg-bg-card/60 px-2 py-0.5 text-accent-blue">
            D: مارکت‌کپ{' '}
            {mcapHt != null ? (
              `${toFaDigits(mcapHt.toFixed(2))} همت`
            ) : (
              <GapHint reason={VALUATION_GAP_REASON}>
                <span className="text-accent-red">بدون داده</span>
              </GapHint>
            )}
          </span>
          <span className="text-text-secondary">=</span>
          <span className={`rounded-md px-2 py-0.5 ${potential != null ? 'bg-accent-green/15 text-accent-green' : 'bg-bg-card/60 text-accent-red'}`}>
            {potential != null ? (
              fmtPct(potential)
            ) : (
              <GapHint reason={VALUATION_GAP_REASON}>بدون داده</GapHint>
            )}
          </span>
        </div>
        <p className="mt-1.5 text-[10px] leading-relaxed text-text-muted">
          A از سالانه‌سازی داینامیک N ماهه می‌آید؛ B حاشیهٔ ناخالص آخرین دورهٔ حسابرسی‌شده؛ D ارزش لحظه‌ای بازار. هر متغیرِ غایب فقط در جای خودش «بدون داده» می‌شود — بقیهٔ فرمول سالم نمایش می‌یابد.
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
  const fxExposure = /شیمیایی|شيميايي|فلزات|کانی|كاني|کاشی|كاشي|سیمان|سيمان|نفت|صادراتی|صادراتي/.test(fxText);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={isFree ? 'green' : isMandatory ? 'red' : 'yellow'}>{ind?.regime_label ?? ind?.label ?? regime}</Badge>
        {sector ? <Badge tone="gray">{sector}</Badge> : null}
        {ind?.market_share_pct != null ? <Badge tone="blue">سهم بازار {fmtPct(ind.market_share_pct)}</Badge> : null}
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        <div className={`rounded-xl border p-2.5 ${isFree ? 'border-accent-green/40 bg-accent-green/10' : 'border-border-c bg-bg-primary'}`}>
          <div className="text-[11px] font-bold text-text-primary">نوع قیمت‌گذاری</div>
          <div className={`mt-1 text-[10px] leading-snug ${isFree ? 'text-accent-green' : isMandatory ? 'text-accent-red' : 'text-text-secondary'}`}>
            {isFree ? 'آزاد / بورس کالا — نرخ از بازار' : isMandatory ? 'دستوری — نرخ با مصوبهٔ دولت' : 'مختلط / موردی'}
          </div>
        </div>
        <div className="rounded-xl border border-border-c bg-bg-primary p-2.5">
          <div className="text-[11px] font-bold text-text-primary">ریسک ناترازی انرژی</div>
          <div className="mt-1 text-[10px] leading-snug text-text-secondary">
            {/نیروگاه|برق|فولاد|پتروشیمی|پترو شیمی|سیمان|سيمان|فولاد|مجتمع فولاد/.test(fxText)
              ? 'انرژی‌بر — ناترازی گاز تابستان (توقف خطوط) و برق زمستان ریسک تولید است.'
              : 'صنعت انرژی‌بر نیست — ناترازی فصلی انرژی اثر محدودی دارد.'}
          </div>
        </div>
        <div className="rounded-xl border border-border-c bg-bg-primary p-2.5">
          <div className="text-[11px] font-bold text-text-primary">پتانسیل ارزی</div>
          <div className={`mt-1 text-[10px] leading-snug ${fxExposure ? 'text-accent-green' : 'text-text-secondary'}`}>
            {fxExposure ? 'صادراتی/دلاری — درآمد به دلار گره خورده؛ پتانسیل نرخ ارز بالا.' : 'درآمد ریالی — پتانسیل ارزی مستقیم ندارد.'}
          </div>
        </div>
      </div>
      {outlook ? <p className="text-[11px] leading-relaxed text-text-secondary">چشم‌انداز: {outlook}</p> : null}
      <p className="text-[11px] leading-relaxed text-text-secondary">
        فرمول: صنعت دستوری (خودرو، دارو، نیروگاه، غذا، لاستیک، شوینده) مردود · آزاد (سیمان، فلزات، پتروشیمی، کانی، کاشی) مطلوب
      </p>
    </div>
  );
}

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
