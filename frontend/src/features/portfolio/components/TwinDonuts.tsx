// features/portfolio/components/TwinDonuts.tsx -- پنل سه‌بخشی بالای تب هدف
// [دونات چپ: پرتفوی واقعی] · [باکس میانی: سنجهٔ هم‌ترازی FTS] · [دونات راست: سبد استاندارد FTS]
// سهام از پوزیشن‌های سبد و سایر طبقات از ارزش ثبت‌شده؛ نبود داده ⇒ «بدون داده» (Circuit Breaker).
import { useMemo, useState } from 'react';
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { usePortfolio } from '../api/usePortfolio';
import { useAssetValues } from '../stores/assetValues';
import { useTargetAllocation, type TargetClass } from '../stores/targetAllocation';
import {
  ASSET_VALUE_KEYS,
  alignmentScore,
  alignmentStatus,
  compareToStandard,
  dataCoverage,
  filledPct,
  rebalanceOrders,
  trackingError,
  type AssetValueKey,
  type BucketComparison,
} from '../model/standardAllocation';

const R = 52;
const CIRC = 2 * Math.PI * R;

type DonutSlice = {
  id: string;
  label: string;
  color: string;
  pct: number;
  /** وضعیت پویا: مازاد/کسری/عادی/بدون داده */
  state?: BucketComparison['state'];
};

/**
 * دونات SVG با هایلایت مازاد (حلقهٔ قرمز) و مات‌کردن کسری.
 * اندازهٔ ثابت و واکنش‌گرا (viewBox + w-full max-w).
 */
function Donut({
  slices,
  centerLabel,
  centerValue,
  ariaLabel,
  total,
}: {
  slices: DonutSlice[];
  centerLabel: string;
  centerValue: string;
  ariaLabel: string;
  total: number;
}) {
  let offset = 0;
  return (
    <div className="flex w-full flex-col items-center gap-2">
      <svg
        viewBox="0 0 140 140"
        role="img"
        aria-label={ariaLabel}
        className="h-auto w-full max-w-[190px] shrink-0"
      >
        <circle cx="70" cy="70" r={R} fill="none" stroke="var(--border-color)" strokeOpacity="0.35" strokeWidth="14" />
        {total > 0 &&
          slices
            .filter((s) => s.pct > 0)
            .map((s) => {
              const frac = s.pct / total;
              const dash = frac * CIRC;
              const el = (
                <circle
                  key={s.id}
                  cx="70"
                  cy="70"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={s.state === 'overweight' ? 18 : 14}
                  strokeOpacity={s.state === 'underweight' ? 0.35 : 1}
                  strokeDasharray={`${Math.max(0, dash - 1.5)} ${CIRC - dash + 1.5}`}
                  strokeDashoffset={-offset}
                  transform="rotate(-90 70 70)"
                  style={{ transition: 'stroke-dasharray 0.5s cubic-bezier(0.22, 1, 0.36, 1)' }}
                >
                  <title>{`${s.label}: ${toFaDigits(s.pct)}٪`}</title>
                </circle>
              );
              offset += dash;
              return el;
            })}
        {/* حلقهٔ هشدار مازاد */}
        {slices.some((s) => s.state === 'overweight') ? (
          <circle cx="70" cy="70" r={64} fill="none" stroke="var(--accent-red)" strokeOpacity="0.7" strokeWidth="2" strokeDasharray="6 6" />
        ) : null}
        <text x="70" y="64" textAnchor="middle" fontSize="15" fontWeight="900" fill="var(--text-primary)" className="num">
          {centerValue}
        </text>
        <text x="70" y="82" textAnchor="middle" fontSize="9" fill="var(--text-muted)">
          {centerLabel}
        </text>
      </svg>
    </div>
  );
}

/** ردیف افسانهٔ فشرده (بدون کارت عریض) */
function Legend({ items }: { items: DonutSlice[] }) {
  return (
    <ul className="flex w-full flex-col gap-1">
      {items.map((s) => (
        <li key={s.id} className="flex items-center gap-2 text-2xs">
          <span
            className="inline-block h-2 w-2 shrink-0 rounded-sm"
            style={{ background: s.color, opacity: s.state === 'underweight' ? 0.4 : 1 }}
            aria-hidden
          />
          <span className="min-w-0 flex-1 truncate text-text-secondary" title={s.label}>
            {s.label}
          </span>
          <span className="num shrink-0 font-bold text-text-primary">{toFaDigits(s.pct)}٪</span>
        </li>
      ))}
    </ul>
  );
}

export function useActualPortfolioData() {
  const portfolio = usePortfolio();
  const classes = useTargetAllocation((s) => s.classes);
  const assetValues = useAssetValues();

  const decisions = useMemo(() => portfolio.data?.decisions ?? [], [portfolio.data]);

  const equityWeightPct = useMemo(() => {
    const accepted = decisions.filter((d) => (d.status ?? '').trim().toLowerCase() === 'accept');
    if (accepted.length === 0) return null;
    return (
      Math.round(accepted.reduce((s, d) => s + (typeof d.weight_eff_pct === 'number' ? d.weight_eff_pct : 0), 0) * 10) / 10
    );
  }, [decisions]);

  const rows = useMemo(
    () =>
      compareToStandard({
        equityWeightPct,
        totalValueToman: assetValues.totalToman,
        values: assetValues.values,
      }),
    [equityWeightPct, assetValues.totalToman, assetValues.values],
  );

  const filled = useMemo(() => filledPct(rows), [rows]);

  const actualByClass = useMemo(() => {
    const map = new Map<string, number | null>();
    const equityRow = rows.find((r) => r.bucket.id === 'equity');
    map.set('equity', equityRow?.actualPct ?? null);
    for (const r of rows) {
      if (r.bucket.id === 'equity') continue;
      for (const classId of r.bucket.classIds) {
        map.set(classId, r.actualPct == null ? null : classId === r.bucket.classIds[0] ? r.actualPct : 0);
      }
    }
    return map;
  }, [rows]);

  const actualSlices: DonutSlice[] = classes.map((c: TargetClass) => {
    const actual = actualByClass.get(c.id);
    const bucket = rows.find((r) => r.bucket.classIds.includes(c.id)) ?? null;
    return {
      id: c.id,
      label: c.label,
      color: c.color,
      pct: Math.max(0, actual ?? 0),
      state: actual == null ? 'nodata' : bucket?.state ?? 'ok',
    };
  });
  const actualTotal = actualSlices.reduce((s, x) => s + x.pct, 0);

  return { rows, actualSlices, actualTotal, filled, hasAnyActual: filled != null, equityWeightPct };
}

/** کامپوننت چارت دونات پرتفوی واقعی و درصد پر شده از سرمایه — قابل استفاده در تب پرتفوی فعلی */
export function ActualPortfolioCard({ className = '' }: { className?: string }) {
  const { actualSlices, actualTotal, filled, hasAnyActual } = useActualPortfolioData();

  return (
    <div
      className={`glass-panel flex flex-col items-center justify-between gap-4 rounded-2xl border border-[var(--hairline)] bg-bg-card/70 p-4 shadow-sm md:flex-row ${className}`}
      aria-label="چارت دونات پرتفوی واقعی و درصد پرشده از سرمایه"
    >
      <div className="flex shrink-0 flex-col items-center gap-2">
        <Donut
          slices={actualSlices}
          centerLabel="درصد پرشده از سرمایه"
          centerValue={filled != null ? `${toFaDigits(filled)}٪` : '—'}
          ariaLabel="چارت دونات پرتفوی واقعی"
          total={actualTotal}
        />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--hairline)] pb-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-black text-text-primary">وضعیت تخصیص سرمایه واقعی (Actual Allocation)</span>
            <Badge tone={filled != null && filled > 100 ? 'red' : filled != null && filled >= 80 ? 'green' : 'blue'}>
              {filled != null ? `${toFaDigits(filled)}٪ از کل سرمایه` : 'بدون داده'}
            </Badge>
          </div>
          <span className="text-2xs text-text-muted">
            سنجهٔ FTS: سهام + طلا + درآمد ثابت + نقدینگی
          </span>
        </div>
        {hasAnyActual ? (
          <Legend items={actualSlices.filter((s) => s.pct > 0)} />
        ) : (
          <p className="text-2xs leading-5 text-text-muted">
            هنوز دارایی ثبت نشده است؛ برای ساخت پرتفوی واقعی، نماد به سبد اضافه کنید یا ارزش سایر طبقات را در تب هدف ثبت کنید.
          </p>
        )}
      </div>
    </div>
  );
}

export function TwinDonuts({
  onEdit,
  showActual = true,
}: {
  onEdit?: () => void;
  showActual?: boolean;
}) {
  const portfolio = usePortfolio();
  const classes = useTargetAllocation((s) => s.classes);
  const resetTarget = useTargetAllocation((s) => s.reset);
  const assetValues = useAssetValues();
  const [showOrders, setShowOrders] = useState(false);

  const { rows, actualSlices, actualTotal, filled, hasAnyActual } = useActualPortfolioData();

  const te = useMemo(() => trackingError(rows), [rows]);
  const score = useMemo(() => alignmentScore(te), [te]);
  const status = useMemo(() => alignmentStatus(rows, score), [rows, score]);
  const coverage = useMemo(() => dataCoverage(rows), [rows]);
  const orders = useMemo(() => rebalanceOrders(rows, assetValues.totalToman), [rows, assetValues.totalToman]);

  // دونات راست: طبقات هدف (نسبت‌های مصوب سند به‌صورت پیش‌فرض)
  const targetSlices: DonutSlice[] = classes.map((c: TargetClass) => ({
    id: c.id,
    label: c.label,
    color: c.color,
    pct: c.pct,
  }));
  const targetTotal = targetSlices.reduce((s, x) => s + x.pct, 0);

  return (
    <section className="glass-panel panel-in relative overflow-hidden p-4" aria-label="دونات دوقلو و سنجهٔ هم‌ترازی">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-black text-text-primary">تحلیل دارایی‌های پرتفو</h3>
          <p className="mt-0.5 text-2xs leading-5 text-text-muted">
            {showActual
              ? 'دونات راست = سبد استاندارد FTS · دونات چپ = پرتفوی واقعی · باکس میانی = سنجهٔ هم‌ترازی و دستورات ری‌بالانس.'
              : 'سبد استاندارد FTS و سنجهٔ هم‌ترازی دارایی‌ها به همراه دستورات ری‌بالانس.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {onEdit ? (
            <>
              <button
                type="button"
                onClick={onEdit}
                className="rounded-full border border-accent-blue/40 bg-accent-blue/10 px-3 py-1 text-2xs font-bold text-accent-blue hover:bg-accent-blue/20"
              >
                ویرایش دارایی
              </button>
              <button
                type="button"
                onClick={onEdit}
                className="rounded-full border border-border-c bg-bg-card px-3 py-1 text-2xs font-bold text-text-secondary hover:text-text-primary"
              >
                افزودن دارایی
              </button>
              <button
                type="button"
                onClick={() => resetTarget()}
                className="rounded-full border border-border-c bg-bg-card px-3 py-1 text-2xs font-bold text-text-secondary hover:text-text-primary"
              >
                بازنشانی به پیش‌فرض FTS
              </button>
            </>
          ) : null}
        </div>
      </div>

      <div className={`grid items-start gap-4 ${showActual ? 'lg:grid-cols-3' : 'lg:grid-cols-2'}`}>
        {/* دونات چپ — پرتفوی واقعی (فقط در صورت درخواست، وگرنه منحصراً در تب پرتفوی فعلی نمایش داده می‌شود) */}
        {showActual ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--hairline)] bg-bg-secondary/30 p-3">
            <Donut
              slices={actualSlices}
              centerLabel="درصد پرشده از سرمایه"
              centerValue={filled != null ? `${toFaDigits(filled)}٪` : '—'}
              ariaLabel="چارت دونات پرتفوی واقعی"
              total={actualTotal}
            />
            {hasAnyActual ? (
              <Legend items={actualSlices.filter((s) => s.pct > 0)} />
            ) : (
              <p className="text-2xs leading-5 text-text-muted">
                بدون داده — برای ساخت پرتفوی واقعی، نماد به سبد اضافه کن یا ارزش دارایی‌ها را ثبت کن.
              </p>
            )}
          </div>
        ) : null}

        {/* باکس میانی — سنجهٔ هم‌ترازی */}
        <div className="flex flex-col gap-2 rounded-2xl border border-[var(--hairline)] bg-bg-secondary/30 p-3">
          <div className="text-2xs font-black text-text-primary">سنجهٔ هم‌ترازی FTS</div>
          <div className="flex items-end gap-2">
            <span className="num text-3xl font-black text-text-primary">{score != null ? toFaDigits(score) : '—'}</span>
            <span className="text-2xs text-text-muted">از ۱۰۰</span>
            <Badge tone={status.tone}>{score == null ? 'بدون داده' : score >= 80 ? 'هم‌تراز' : score >= 55 ? 'متوسط' : 'واگرا'}</Badge>
          </div>
          <p className="text-2xs leading-5 text-text-secondary">{status.label}</p>
          <p className="num text-2xs text-text-muted">
            خطای انحراف (TE): {te != null ? toFaDigits(te) : 'بدون داده'} · پوشش داده: {toFaDigits(coverage.covered)} از{' '}
            {toFaDigits(coverage.total)} طبقه
          </p>
          <ul className="flex flex-col gap-1">
            {rows.map((r) => (
              <li key={r.bucket.id} className="flex items-center gap-2 text-2xs">
                <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: r.bucket.color }} aria-hidden />
                <span className="min-w-0 flex-1 truncate text-text-secondary">{r.bucket.label}</span>
                <span className="text-text-muted">
                  هدف <span className="num">{toFaDigits(r.targetPct)}٪</span>
                </span>
                <span className="text-text-muted">
                  واقعی <span className="num">{r.actualPct != null ? `${toFaDigits(r.actualPct)}٪` : 'بدون داده'}</span>
                </span>
                {r.state === 'overweight' ? <Badge tone="red">مازاد</Badge> : null}
                {r.state === 'underweight' ? <Badge tone="yellow">کسری</Badge> : null}
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setShowOrders((v) => !v)}
            aria-expanded={showOrders}
            className="mt-1 self-start rounded-full border border-neon-cyan/40 bg-neon-cyan/10 px-3 py-1 text-2xs font-bold text-neon-cyan hover:bg-neon-cyan/20"
          >
            محاسبه دستورات ری‌بالانس {showOrders ? '▴' : '▾'}
          </button>
          {showOrders ? (
            orders.length > 0 ? (
              <ul className="flex flex-col gap-1 rounded-xl border border-[var(--hairline)] bg-bg-card/50 p-2">
                {orders.map((o) => (
                  <li key={o.bucket.id} className="flex flex-wrap items-center gap-2 text-2xs">
                    <span
                      className={`rounded-full border px-2 py-0.5 font-bold ${
                        o.action === 'buy' ? 'border-accent-green/40 text-accent-green' : 'border-accent-red/40 text-accent-red'
                      }`}
                    >
                      {o.action === 'buy' ? 'خرید' : 'فروش'}
                    </span>
                    <span className="min-w-0 flex-1 text-text-secondary">{o.text}</span>
                    <span className="shrink-0 text-text-muted">
                      {o.amountToman != null ? <span className="num">{toFaDigits(o.amountToman)}</span> : 'مبلغ: بدون داده'}
                      {o.amountToman != null ? ' تومان' : ''}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-2xs text-text-muted">دستور ری‌بالانسی لازم نیست یا داده کافی برای محاسبه نیست.</p>
            )
          ) : null}
        </div>

        {/* دونات راست — سبد استاندارد FTS */}
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--hairline)] bg-bg-secondary/30 p-3">
          <Donut
            slices={targetSlices}
            centerLabel="تخصیص هدف"
            centerValue={`${toFaDigits(Math.round(targetTotal))}٪`}
            ariaLabel="چارت دونات پرتفوی هدف"
            total={targetTotal}
          />
          <Legend items={targetSlices} />
        </div>
      </div>

      {/* ثبت ارزش دارایی‌ها (اختیاری) — لازمهٔ وزن واقعی طبقات غیرسهامی */}
      <details className="mt-3 rounded-xl border border-dashed border-border-c bg-bg-secondary/30 p-2">
        <summary className="cursor-pointer text-2xs font-bold text-text-secondary">
          ثبت ارزش دارایی‌ها (تومان) — برای محاسبهٔ وزن واقعی و مبلغ ریالی ری‌بالانس
        </summary>
        <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
            ارزش کل دارایی‌ها
            <input
              type="number"
              min={0}
              step={1_000_000}
              defaultValue={assetValues.totalToman > 0 ? assetValues.totalToman : ''}
              onBlur={(e) => assetValues.setTotalToman(Number(e.target.value))}
              aria-label="ارزش کل دارایی‌ها (تومان)"
              dir="ltr"
              placeholder="ثبت‌نشده"
              className="num rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-start text-xs text-text-primary outline-none focus:border-border-accent"
            />
          </label>
          {ASSET_VALUE_KEYS.map((k: AssetValueKey) => {
            const label =
              k === 'gold' ? 'طلا و سکه' : k === 'crypto' ? 'ارز دیجیتال' : k === 'silver' ? 'نقره' : 'درآمد ثابت و نقدینگی';
            return (
              <label key={k} className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
                {label}
                <input
                  type="number"
                  min={0}
                  step={1_000_000}
                  defaultValue={assetValues.values[k] > 0 ? assetValues.values[k] : ''}
                  onBlur={(e) => assetValues.setValue(k, Number(e.target.value))}
                  aria-label={`ارزش ${label} (تومان)`}
                  dir="ltr"
                  placeholder="ثبت‌نشده"
                  className="num rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-start text-xs text-text-primary outline-none focus:border-border-accent"
                />
              </label>
            );
          })}
        </div>
        <p className="mt-1.5 text-2xs leading-5 text-text-muted">
          وزن سهام به‌طور خودکار از پوزیشن‌های ثبت‌شدهٔ سبد خوانده می‌شود؛ بقیهٔ طبقات از ارزش‌های بالا محاسبه می‌شوند.
        </p>
      </details>
    </section>
  );
}
