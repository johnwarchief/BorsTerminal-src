import type { ReactNode } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { AXES, statusFa, type AxisKey, type AxisStatus } from '../../lib/axisMeta';

/** عددِ اعشاری با ارقامِ فارسی، جداکنندهٔ اعشارِ «٫» و علامتِ منفیِ «−»؛ نبودِ مقدار «—». */
export function faFixed(value: number | null | undefined, digits = 1, suffix = ''): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${toFaDigits(value.toFixed(digits)).replace('.', '٫').replace(/^-/, '−')}${suffix}`;
}

/** عددِ صحیح/گردشده با ارقامِ فارسی. */
export function faInt(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return toFaDigits(Math.round(value)).replace(/^-/, '−');
}

/** آستانه‌ها معمولاً صحیح‌اند؛ اگر اعشار داشتند یک رقم و «٫» حفظ شود. */
export function faThreshold(value: number | null | undefined, suffix = ''): string {
  if (value == null || !Number.isFinite(value)) return `—${suffix}`;
  return Number.isInteger(value)
    ? `${toFaDigits(value).replace(/^-/, '−')}${suffix}`
    : faFixed(value, 1, suffix);
}

export interface AxisPanelProps {
  testId: string;
  axis: AxisKey;
  title: string;
  subtitle: string;
  status: AxisStatus;
  value: string;
  threshold: string;
  chart: ReactNode;
  /**
   * R-P1-13 (Minor 4): کلاسِ ارتفاعِ ناحیهٔ نمودار. پیش‌فرض `h-[32px]` است و برایِ
   * پنل‌های دیگر عوض نمی‌شود؛ پنل‌هایی که میلهٔ بلندتر می‌خواهند (تاریخچه) `h-[40px]` می‌دهند.
   */
  chartClass?: string;
  rows: Array<[string, string]>;
  details?: { formula?: string | null; source?: string | null } | null;
  children?: ReactNode;
}

/** قالبِ مشترکِ پنل‌های تصویری؛ وضعیت و رنگ فقط از `cardStatus`/توکن‌های fd می‌آید. */
export function AxisPanel({
  testId, axis, title, subtitle, status, value, threshold, chart, chartClass, rows, details, children,
}: AxisPanelProps) {
  const meta = AXES.find((item) => item.key === axis)!;
  return (
    <section
      data-testid={testId}
      id={testId}
      tabIndex={-1}
      className="fd-panel flex h-full flex-col gap-2 rounded-xl border border-[var(--fd-line)] bg-[var(--fd-panel)] p-3"
    >
      {/* R79: هدفِ فوکوسِ quintet سرصفحه است، نه ریشهٔ پنل. */}
      <header id={`${testId}-title`} tabIndex={-1} className="flex items-baseline gap-2">
        <span className="grid h-4 w-4 flex-none place-items-center rounded border border-[var(--fd-line-strong)] fd-meta text-[var(--fd-text-3)]">{meta.num}</span>
        <h3 className="fd-title text-[var(--fd-text)]">{title}</h3>
        <span className={`fd-status-word ms-auto fd-status--${status}`}>{statusFa(status)}</span>
      </header>
      <p className="fd-secondary leading-relaxed text-[var(--fd-text-3)]">{subtitle}</p>
      <div className="flex items-baseline gap-2">
        <b className="fd-figure tabular-nums text-[var(--fd-text)]">{value}</b>
        <span className="fd-meta text-[var(--fd-text-3)]">{threshold}</span>
      </div>
      {/* R73: نمودارِ نمای نماد با fade/scaleX کوتاه؛ ریشهٔ پنل با fd-panel بی‌انیمیشن می‌ماند.
          R-P1-13: ارتفاعِ ناحیه با chartClass تنظیم می‌شود؛ پیش‌فرض همان h-[32px] است. */}
      <div className={`fd-draw ${chartClass ?? 'h-[32px]'}`}>{chart}</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 fd-meta text-[var(--fd-text-3)]">
        {rows.map(([label, val]) => (
          <span key={label} className="flex justify-between gap-1 border-b border-[var(--fd-line)] py-1">
            <span>{label}</span>
            <b className="text-[var(--fd-text)]">{val}</b>
          </span>
        ))}
      </div>
      {children}
      <details className="border-t border-[var(--fd-line)] pt-1">
        <summary className="cursor-pointer fd-meta text-[var(--fd-text-3)]">فرمول و منبع</summary>
        <p className="mt-1 fd-secondary leading-relaxed text-[var(--fd-text-3)]">
          {details?.formula ?? '—'} — {details?.source ?? '—'}
        </p>
      </details>
    </section>
  );
}
