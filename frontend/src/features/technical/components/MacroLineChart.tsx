// features/technical/components/MacroLineChart.tsx -- چارت خطی نمای کلان (SVG سبک)
// برای سری کلان (نمونه‌های تایم‌لاین)؛ کندل نیست چون سری OHLC کل‌بازاری در بک‌اند
// وجود ندارد. کمتر از دو نقطه معتبر ⇒ «در انتظار نقاط» (Circuit Breaker)، نه خط ساختگی.
import { buildLineGeometry, finiteSeries } from '../lib/macroChart';
import { toFaDigits } from '@shared/lib/fmt';

const VIEW_W = 560;
const VIEW_H = 180;
const PAD = 10;

function fmtValue(v: number): string {
  if (!Number.isFinite(v)) return '-';
  if (Math.abs(v) >= 1000) return toFaDigits(Math.round(v).toLocaleString('en-US'));
  return toFaDigits(Number(v.toFixed(2)).toString());
}

export function MacroLineChart({
  values,
  title,
  unit,
  labels,
  testId = 'macro-line',
}: {
  values: (number | string | null | undefined)[];
  title: string;
  unit?: string;
  /** برچسب‌های زمان متناظر (اختیاری) برای ابتدا/انتهای محور */
  labels?: (string | number | null | undefined)[];
  testId?: string;
}) {
  const geometry = buildLineGeometry(values, VIEW_W, VIEW_H, PAD);
  const count = finiteSeries(values).length;

  if (!geometry) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-border-c bg-bg-secondary p-6 text-center"
        style={{ minHeight: 120 }}
        data-testid={`${testId}-empty`}
      >
        <span className="text-xs font-bold text-text-secondary">سری کلان آماده نیست</span>
        <span className="text-[11px] text-text-muted">
          {count === 0 ? 'هیچ نقطه‌ای از تایم‌لاین بازار برنگشت' : `تنها ${toFaDigits(count)} نقطه هست؛ برای رسم خط دست‌کم دو همگام‌سازی لازم است`}
        </span>
      </div>
    );
  }

  const areaPath = `${geometry.path} L${geometry.points[geometry.points.length - 1].x.toFixed(2)} ${(VIEW_H - PAD).toFixed(2)} L${geometry.points[0].x.toFixed(2)} ${(VIEW_H - PAD).toFixed(2)} Z`;
  const firstLabel = labels?.find((l) => l != null) ?? null;
  const lastLabels = (labels ?? []).filter((l) => l != null);
  const lastLabel = lastLabels.length > 0 ? lastLabels[lastLabels.length - 1] : null;

  return (
    <div className="flex flex-col gap-1" data-testid={testId}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-bold text-text-secondary">{title}</span>
        <span className="num text-[10px] text-text-muted">
          {toFaDigits(count)} نقطه{unit ? ` · ${unit}` : ''}
        </span>
      </div>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} preserveAspectRatio="none" className="h-[180px] w-full" role="img" aria-label={title}>
        <defs>
          <linearGradient id={`${testId}-fill`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={PAD}
            x2={VIEW_W - PAD}
            y1={PAD + (VIEW_H - PAD * 2) * f}
            y2={PAD + (VIEW_H - PAD * 2) * f}
            stroke="var(--border-color)"
            strokeWidth="1"
            strokeDasharray="3 5"
          />
        ))}
        <path d={areaPath} fill={`url(#${testId}-fill)`} stroke="none" />
        <path d={geometry.path} fill="none" stroke="var(--accent-blue)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div className="flex items-baseline justify-between gap-2 text-[10px] text-text-muted">
        <span className="num">
          کمینه <span className="font-bold text-text-secondary">{fmtValue(geometry.min)}</span>
        </span>
        <span className="num">
          بیشینه <span className="font-bold text-text-secondary">{fmtValue(geometry.max)}</span>
        </span>
      </div>
      {firstLabel != null || lastLabel != null ? (
        <div className="flex items-baseline justify-between gap-2 text-[10px] text-text-muted" data-testid={`${testId}-axis`}>
          <span className="num">{String(firstLabel ?? '')}</span>
          <span className="num">{String(lastLabel ?? '')}</span>
        </div>
      ) : null}
    </div>
  );
}
