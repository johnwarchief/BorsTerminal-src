// features/portfolio/components/DeltaBar.tsx -- نوار شکاف و ری‌بالانس (متراکم)
// خلاصهٔ همیشه‌دیده: یک نوار پیشرفت + شمارش کسری/مازاد. جزئیات در دراور کشویی باز می‌شود و
// آیتم‌های کسری در شبکهٔ کارتی متراکم ۲/۳ ستونی نمایش داده می‌شوند:
// [دارایی | وزن هدف | وزن فعلی | نوار مینیاتوری کسری/مازاد (+ مبلغ ریالی در صورت وجود ارزش کل)]
import { useMemo, useState } from 'react';
import { Chevron, CollapseBody } from '@shared/components/Collapse';
import { toFaDigits } from '@shared/lib/fmt';
import { useAssetValues } from '../stores/assetValues';
import { mixSentence, type DeltaRow } from '../stores/targetAllocation';

export function deltaTone(delta: number | null): 'green' | 'red' | 'gray' {
  if (delta == null) return 'gray';
  if (delta > 0.05) return 'green';
  if (delta < -0.05) return 'red';
  return 'gray';
}

export function deltaLabel(delta: number | null): string {
  if (delta == null) return 'بدون داده';
  if (delta > 0.05) return `مازاد ${toFaDigits(Math.abs(delta))}٪ (فروش)`;
  if (delta < -0.05) return `کسری ${toFaDigits(Math.abs(delta))}٪ (خرید)`;
  return 'در هدف';
}

/** جمع وزن‌های هدف/فعلی — فقط طبقاتی که وزنِ فعلی‌شان معلوم است (#106) */
export function deltaTotals(rows: DeltaRow[]): { target: number; current: number; hasData: boolean } {
  const target = Math.round(rows.reduce((s, r) => s + (r.targetPct > 0 ? r.targetPct : 0), 0) * 10) / 10;
  const current = Math.round(rows.reduce((s, r) => s + (r.currentPct ?? 0), 0) * 10) / 10;
  return { target, current, hasData: rows.some((r) => r.currentPct != null) };
}

/** مبلغ ریالی کسری/مازاد یک طبقه؛ null یعنی ارزش کل ثبت نشده */
export function deltaToman(deltaPct: number, totalValueToman: number): number | null {
  if (!(totalValueToman > 0)) return null;
  return Math.round((Math.abs(deltaPct) / 100) * totalValueToman);
}

function RebalanceCard({ row, totalValueToman, maxAbs }: { row: DeltaRow; totalValueToman: number; maxAbs: number }) {
  // کارت فقط برای کسری/مازادِ معلوم ساخته می‌شود؛ بی‌داده یعنی «ردیفی نیست»
  if (row.delta == null) return null;
  const tone = deltaTone(row.delta);
  const amount = deltaToman(row.delta, totalValueToman);
  const width = Math.min(100, (Math.abs(row.delta) / Math.max(maxAbs, 20)) * 100);
  return (
    <li className="flex flex-col gap-1.5 rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-2.5 py-2">
      <div className="flex items-center gap-2">
        <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: row.color }} aria-hidden />
        <span className="min-w-0 flex-1 truncate text-2xs font-bold text-text-primary" title={row.label}>
          {row.label}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2 text-2xs text-text-muted">
        <span title={row.classLabel}>
          هدف{' '}
          <span className="num text-text-secondary">
            {toFaDigits(row.classTargetPct ?? row.targetPct)}٪
          </span>
          {row.classTargetPct != null ? <span className="text-2xs"> (جمعِ طبقه)</span> : null}
        </span>
        <span>
          فعلی{' '}
          {row.currentPct == null ? (
            <span className="text-text-muted">بدون داده</span>
          ) : (
            <>
              <span className="num text-text-secondary">{toFaDigits(row.currentPct)}٪</span>{' '}
              {/* مخرجِ درصد باید در جمله باشد، وگرنه ۸۷٪ سبد با ۴۵٪ سرمایه قیاس می‌شود */}
              <span className="text-2xs">{row.basis === 'capital' ? 'از سرمایه' : 'از سبد'}</span>
            </>
          )}
        </span>
      </div>
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-bg-card" dir="ltr" aria-hidden>
        <span
          className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ${
            tone === 'red' ? 'bg-accent-red' : tone === 'green' ? 'bg-accent-green/80' : 'bg-border-c'
          }`}
          style={{ width: `${tone === 'gray' ? 0 : width}%` }}
        />
      </div>
      <div className="flex items-center justify-between gap-2">
        <span
          className={`text-2xs font-black ${
            tone === 'red' ? 'text-accent-red' : tone === 'green' ? 'text-accent-green' : 'text-text-muted'
          }`}
        >
          {deltaLabel(row.delta)}
        </span>
        <span className="shrink-0 text-2xs text-text-muted">
          {tone === 'gray' ? '—' : amount != null ? <><span className="num">{toFaDigits(amount)}</span> تومان</> : 'مبلغ: بدون داده'}
        </span>
      </div>
    </li>
  );
}

export function DeltaBar({ rows }: { rows: DeltaRow[] }) {
  const [open, setOpen] = useState(false);
  const totalValueToman = useAssetValues((s) => s.totalToman);
  const { target, current, hasData } = useMemo(() => deltaTotals(rows), [rows]);
  const deficits = useMemo(() => rows.filter((r) => (r.delta ?? 0) < -0.05), [rows]);
  const surplus = useMemo(() => rows.filter((r) => (r.delta ?? 0) > 0.05), [rows]);
  // جملهٔ headline: «طلا و سکه ۴۳٪ از سرمایه — هدف ۴۵٪» (#106)
  const sentence = useMemo(() => mixSentence(rows), [rows]);

  const coverPct = hasData && target > 0 ? Math.min(100, Math.round(((current / target) * 100 + Number.EPSILON) * 10) / 10) : 0;
  const outstanding = useMemo(() => [...deficits, ...surplus], [deficits, surplus]);
  const maxAbsDelta = useMemo(
    () => Math.max(...rows.map((r) => Math.abs(r.delta ?? 0)), 1),
    [rows],
  );

  return (
    <div className="glass-panel relative overflow-hidden p-4" aria-label="نوار شکاف و ری‌بالانس">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-black text-text-primary">شکاف فعلی با هدف (ری‌بالانس)</h3>
        <div className="flex flex-wrap items-center gap-2">
          {hasData ? (
            <span className="num inline-flex items-center rounded-full border border-border-c bg-bg-card px-2.5 py-0.5 text-xs font-semibold text-text-secondary">
              پوشش {toFaDigits(coverPct)}٪
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full border border-border-c bg-bg-card px-2.5 py-0.5 text-xs font-semibold text-text-muted">
              بدون داده
            </span>
          )}
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="inline-flex items-center gap-1.5 rounded-full border border-border-c bg-bg-card px-3 py-1 text-2xs font-bold text-text-secondary transition-colors duration-200 hover:border-border-accent hover:text-text-primary"
          >
            جزئیات ری‌بالانس ({toFaDigits(outstanding.length)} مورد)
            <Chevron open={open} />
          </button>
        </div>
      </div>

      {sentence ? (
        <p data-testid="mix-sentence" className="mt-2 text-xs font-black text-text-primary">
          {sentence}
        </p>
      ) : null}

      {/* نوار پیشرفت خلاصه */}
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-bg-card" dir="ltr" aria-hidden>
        <span className="absolute inset-y-0 left-0 rounded-full bg-neon-cyan/70 transition-all duration-500" style={{ width: `${coverPct}%` }} />
        <span className="absolute inset-y-0 left-1/2 w-px bg-border-c" />
      </div>
      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs leading-5 text-text-muted">
        {hasData ? (
          <>
            <span>
              وزن فعلی سبد <span className="num">{toFaDigits(current)}٪</span> از هدف <span className="num">{toFaDigits(target)}٪</span>
            </span>
            <span className="text-accent-red">کسری {toFaDigits(deficits.length)} طبقه</span>
            <span className="text-accent-green">مازاد {toFaDigits(surplus.length)} طبقه</span>
            {rows.some((r) => r.currentPct == null && r.classTargetPct == null) ? (
              <span className="text-text-muted">
                {toFaDigits(rows.filter((r) => r.currentPct == null && r.classTargetPct == null).length)} طبقه بدون داده
              </span>
            ) : null}
            {rows.some((r) => r.currentPct == null && r.classTargetPct != null) ? (
              <span className="text-text-muted" title={rows.filter((r) => r.currentPct == null && r.classTargetPct != null).map((r) => r.classLabel).join(' | ')}>
                {toFaDigits(rows.filter((r) => r.currentPct == null && r.classTargetPct != null).length)} ردیف در طبقهٔ دیگر سنجیده شد
              </span>
            ) : null}
          </>
        ) : (
          <span>
            وزنِ هیچ طبقه‌ای از سبد معلوم نیست؛ برای وزنِ خودکار، «تعداد» هر دارایی را ثبت کن
            (یا ارزشِ طبقات غیرسهامی را). کسری/مازاد از عددِ بی‌داده ساخته نمی‌شود.
          </span>
        )}
      </p>

      {/* دراور: شبکهٔ کارتی متراکم ۲/۳ ستونی */}
      <CollapseBody open={open}>
        <div className="mt-3 border-t border-[var(--hairline)] pt-3">
          {outstanding.length > 0 ? (
            <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {outstanding.map((r) => (
                <RebalanceCard key={r.id} row={r} totalValueToman={totalValueToman} maxAbs={maxAbsDelta} />
              ))}
            </ul>
          ) : (
            <p className="text-2xs text-text-muted">همهٔ طبقات در هدف‌اند؛ دستور ری‌بالانسی لازم نیست.</p>
          )}
        </div>
      </CollapseBody>
    </div>
  );
}
