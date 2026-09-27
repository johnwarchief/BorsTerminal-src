// features/fundamental/components/CardSpark.tsx -- نمودارکِ یک‌نگاه رویِ کارت (#201)
// ارتفاع پیکسلی ثابت (همان قراردادِ QuarterlyTrend): واحدِ viewBox = پیکسلِ CSS،
// تا هرچقدر کارت کشید ستونه و خط کشیده نشوند و نوشته‌ها درشت نمانند.
// حالتِ ایستاده == حالتِ نهایی؛ انیمیشن فقط «از صفر به بالا»ی یک‌بارمصرف است.
// پس prefers-reduced-motion و دروازۀ بی‌کاری (#198) نمودارِ نصفه‌کاره نمی‌گذارند.
import { toFaDigits } from '@shared/lib/fmt';
import { useElementWidth } from '@shared/hooks/useElementWidth';

const H = 42;
const PAD = 3;

export type SparkPoint = { label: string; value: number | null };

/** میله‌ها — برای سه دورۀ EPS. صفرِ واقعی میله دارد؛ «نیست» هیچ‌وقت صفر نیست. */
export function SparkBars({ points, testId, title }: { points: SparkPoint[]; testId: string; title: string }) {
  const [ref, w] = useElementWidth<HTMLDivElement>(200);
  const vals = points.map((p) => p.value).filter((v): v is number => v != null);
  if (vals.length < 2) return null;
  const hi = Math.max(...vals, 0);
  const lo = Math.min(...vals, 0);
  const span = hi - lo || 1;
  const zeroY = PAD + (hi / span) * (H - PAD * 2);
  const slot = (w - PAD * 2) / points.length;
  const bw = Math.max(5, Math.min(28, slot * 0.55));
  return (
    <div ref={ref} className="w-full" data-testid={testId} title={title}>
      <svg
        viewBox={`0 0 ${w} ${H}`}
        width={w}
        height={H}
        style={{ width: '100%', height: `${H}px` }}
        className="block"
        role="img"
        aria-label={title}
      >
        <line x1={PAD} x2={w - PAD} y1={zeroY} y2={zeroY} stroke="var(--border-color)" strokeWidth="1" />
        {points.map((p, i) => {
          if (p.value == null) return null;
          const h = Math.max(1.5, (Math.abs(p.value) / span) * (H - PAD * 2));
          const up = p.value >= 0;
          return (
            <rect
              key={i}
              className="spark-rise"
              style={{ transformBox: 'fill-box', transformOrigin: up ? 'bottom' : 'top' }}
              x={PAD + i * slot + (slot - bw) / 2}
              y={up ? zeroY - h : zeroY}
              width={bw}
              height={h}
              rx="1.5"
              fill={p.value < 0 ? 'var(--accent-red)' : 'var(--accent-blue)'}
              opacity="0.85"
            >
              <title>{`${p.label}: ${toFaDigits(p.value)}`}</title>
            </rect>
          );
        })}
      </svg>
    </div>
  );
}

/** خطِ روند — برای حاشیهٔ سود ناخالصِ فصلی. کفِ جزوه اگر بکاند خط‌چین می‌خورد. */
export function SparkLine({
  points,
  testId,
  title,
  floor = null,
}: {
  points: SparkPoint[];
  testId: string;
  title: string;
  floor?: number | null;
}) {
  const [ref, w] = useElementWidth<HTMLDivElement>(200);
  const vals = points.map((p) => p.value).filter((v): v is number => v != null);
  if (vals.length < 2) return null;
  const hi = Math.max(...vals, floor ?? 0, 1);
  const lo = Math.min(...vals, 0);
  const span = hi - lo || 1;
  const y = (v: number) => H - PAD - ((v - lo) / span) * (H - PAD * 2);
  const x = (i: number) => PAD + (i * (w - PAD * 2)) / (points.length - 1);
  const pts = points.map((p, i) => ({ ...p, x: x(i), y: p.value == null ? null : y(p.value) }));
  const line = pts
    .filter((p) => p.y != null)
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${(p.y as number).toFixed(1)}`)
    .join(' ');
  return (
    <div ref={ref} className="w-full" data-testid={testId} title={title}>
      <svg
        viewBox={`0 0 ${w} ${H}`}
        width={w}
        height={H}
        style={{ width: '100%', height: `${H}px` }}
        className="block"
        role="img"
        aria-label={title}
      >
        {floor != null ? (
          <line
            x1={PAD}
            x2={w - PAD}
            y1={y(floor)}
            y2={y(floor)}
            stroke="var(--accent-red)"
            strokeWidth="1"
            strokeDasharray="3 3"
            opacity="0.7"
          >
            <title>{`کف ${toFaDigits(floor)}٪`}</title>
          </line>
        ) : null}
        <path
          d={line}
          pathLength={100}
          fill="none"
          stroke="var(--accent-blue)"
          strokeWidth="2"
          strokeLinejoin="round"
          className="spark-draw"
        />
        {pts.map(
          (p, i) =>
            p.y != null && (
              <circle key={i} cx={p.x} cy={p.y} r="2.2" fill="var(--accent-blue)">
                <title>{`${p.label}: ${toFaDigits((p.value as number).toFixed(1))}٪`}</title>
              </circle>
            ),
        )}
      </svg>
    </div>
  );
}
