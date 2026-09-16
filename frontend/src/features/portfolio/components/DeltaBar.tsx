// features/portfolio/components/DeltaBar.tsx -- نوار شکاف و ری‌بالانس (نسخهٔ متراکم)
// جک اول دید: یک نوار پیشرفت خلاصه (پوشش فعلی در برابر هدف) + شمارش مازاد/کسری.
// جزئیات هر طبقه داخل یک دراور کشویی (پیش‌فرض بسته) است تا جدول نمادها اولویت دید بماند.
import { useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import type { DeltaRow } from '../stores/targetAllocation';

export function deltaTone(delta: number): 'green' | 'red' | 'gray' {
  if (delta > 0.05) return 'green';
  if (delta < -0.05) return 'red';
  return 'gray';
}

export function deltaLabel(delta: number): string {
  if (delta > 0.05) return `مازاد ${toFaDigits(Math.abs(delta))}٪ (فروش)`;
  if (delta < -0.05) return `کسری ${toFaDigits(Math.abs(delta))}٪ (خرید)`;
  return 'در هدف';
}

/** جمع وزن‌های هدف/فعلی — برای خلاصهٔ نوار پیشرفت (بدون عدد ساختگی) */
export function deltaTotals(rows: DeltaRow[]): { target: number; current: number; hasData: boolean } {
  const target = Math.round(rows.reduce((s, r) => s + (r.targetPct > 0 ? r.targetPct : 0), 0) * 10) / 10;
  const current = Math.round(rows.reduce((s, r) => s + (r.currentPct > 0 ? r.currentPct : 0), 0) * 10) / 10;
  return { target, current, hasData: current > 0 };
}

export function DeltaBar({ rows }: { rows: DeltaRow[] }) {
  const [open, setOpen] = useState(false);
  const { target, current, hasData } = useMemo(() => deltaTotals(rows), [rows]);
  const deficits = useMemo(() => rows.filter((r) => r.delta < -0.05), [rows]);
  const surplus = useMemo(() => rows.filter((r) => r.delta > 0.05), [rows]);

  // نسبت پوشش برای نوار (فقط اگر داده داشته باشیم؛ در غیر این صورت نوار خالی صادقانه می‌ماند)
  const coverPct = hasData && target > 0 ? Math.min(100, Math.round(((current / target) * 100 + Number.EPSILON) * 10) / 10) : 0;

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
            className="rounded-full border border-border-c bg-bg-card px-3 py-1 text-2xs font-bold text-text-secondary transition-colors duration-200 hover:border-border-accent hover:text-text-primary"
          >
            جزئیات ری‌بالانس ({toFaDigits(rows.length)} طبقه) {open ? '▴' : '▾'}
          </button>
        </div>
      </div>

      {/* نوار پیشرفت خلاصه: پوشش فعلی نسبت به هدف */}
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
          </>
        ) : (
          <span>وزن فعلی طبقات ثبت نشده است؛ کسری/مازاد محاسبه نمی‌شود.</span>
        )}
      </p>

      {/* دراور کشویی: جزئیات هر طبقه */}
      {open ? (
        <ul className="mt-3 flex max-h-60 flex-col gap-1.5 overflow-y-auto border-t border-[var(--hairline)] pt-3">
          {rows.map((r) => {
            const tone = deltaTone(r.delta);
            return (
              <li key={r.id} className="flex flex-wrap items-center gap-2 text-2xs">
                <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: r.color }} aria-hidden />
                <span className="min-w-0 flex-1 truncate font-bold text-text-secondary" title={r.label}>
                  {r.label}
                </span>
                <span className="shrink-0 text-text-muted">
                  هدف <span className="num">{toFaDigits(r.targetPct)}٪</span> · فعلی <span className="num">{toFaDigits(r.currentPct)}٪</span>
                </span>
                <span
                  className={`w-28 shrink-0 text-end font-black ${
                    tone === 'green' ? 'text-accent-green' : tone === 'red' ? 'text-accent-red' : 'text-text-muted'
                  }`}
                >
                  {deltaLabel(r.delta)}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
