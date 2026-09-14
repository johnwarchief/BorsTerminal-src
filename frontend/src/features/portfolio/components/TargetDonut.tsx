// features/portfolio/components/TargetDonut.tsx -- چارت دونات SVG خالص
// بدون وابستگی چارت (no recharts/d3) — قوس‌ها با stroke-dasharray.
import { toFaDigits } from '@shared/lib/fmt';
import type { TargetClass } from '../stores/targetAllocation';

const R = 56;
const CIRC = 2 * Math.PI * R;

export type DonutSeg = {
  id: string;
  label: string;
  color: string;
  pct: number;
};

/** ساخت قوس‌های دونات از درصدها — ترتیب از ساعت ۱۲ بهادار (RTL-friendly خنثی) */
export function donutSegments(classes: TargetClass[]): DonutSeg[] {
  return classes
    .filter((c) => c.pct > 0)
    .map((c) => ({ id: c.id, label: c.label, color: c.color, pct: c.pct }));
}

export function TargetDonut({ classes }: { classes: TargetClass[] }) {
  const segs = donutSegments(classes);
  const total = segs.reduce((s, x) => s + x.pct, 0);
  let offset = 0;
  return (
    <div className="flex flex-wrap items-center justify-center gap-6">
      <svg width="170" height="170" viewBox="0 0 140 140" role="img" aria-label="چارت دونات پرتفوی هدف" className="shrink-0">
        <circle cx="70" cy="70" r={R} fill="none" stroke="var(--border-color)" strokeOpacity="0.35" strokeWidth="16" />
        {total > 0 &&
          segs.map((s) => {
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
                strokeWidth="16"
                strokeDasharray={`${dash - 1.5} ${CIRC - dash + 1.5}`}
                strokeDashoffset={-offset}
                transform="rotate(-90 70 70)"
                style={{ transition: 'stroke-dasharray 0.6s cubic-bezier(0.22, 1, 0.36, 1), stroke-dashoffset 0.6s cubic-bezier(0.22, 1, 0.36, 1)' }}
              >
                <title>{`${s.label}: ${toFaDigits(s.pct)}٪`}</title>
              </circle>
            );
            offset += dash;
            return el;
          })}
        <text x="70" y="66" textAnchor="middle" fontSize="15" fontWeight="900" fill="var(--text-primary)" className="num">
          {toFaDigits(Math.round(total))}٪
        </text>
        <text x="70" y="82" textAnchor="middle" fontSize="8.5" fill="var(--text-muted)">
          جمع تخصیص
        </text>
      </svg>
      <ul className="flex min-w-44 flex-col gap-1.5" aria-label="درصدهای طبقات">
        {segs.map((s) => (
          <li key={s.id} className="flex items-center gap-2 text-xs">
            <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} aria-hidden />
            <span className="min-w-0 flex-1 truncate font-semibold text-text-secondary" title={s.label}>{s.label}</span>
            <span className="num font-black text-text-primary">{toFaDigits(s.pct)}٪</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
