// features/portfolio/components/DeltaBar.tsx -- نوار شکاف و ری‌بالانس
// مقایسهٔ وزن فعلی با هدف: مازاد/کسری هر طبقه.
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

export function DeltaBar({ rows }: { rows: DeltaRow[] }) {
  return (
    <div className="glass-panel p-4" aria-label="نوار شکاف و ری‌بالانس">
      <h3 className="mb-3 text-sm font-black text-text-primary">شکاف فعلی با هدف (ری‌بالانس)</h3>
      <ul className="flex flex-col gap-2">
        {rows.map((r) => {
          const tone = deltaTone(r.delta);
          // عرض نوار نسبت به بیشینه قدرمطلق دلتا
          const maxAbs = Math.max(...rows.map((x) => Math.abs(x.delta)), 5);
          const w = Math.min(100, (Math.abs(r.delta) / maxAbs) * 100);
          return (
            <li key={r.id} className="flex flex-wrap items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: r.color }} aria-hidden />
              <span className="min-w-0 flex-1 truncate text-xs font-bold text-text-secondary" title={r.label}>
                {r.label}
              </span>
              <div className="relative h-2 w-32 overflow-hidden rounded-full bg-bg-card" dir="ltr" aria-hidden>
                <span
                  className={`absolute inset-y-0 rounded-full transition-all duration-700 ${
                    tone === 'green' ? 'left-1/2 bg-accent-green' : tone === 'red' ? 'right-1/2 bg-accent-red' : 'left-1/2 w-0'
                  }`}
                  style={tone === 'gray' ? { width: 0 } : { width: `${w / 2}%` }}
                />
                <span className="absolute inset-y-0 left-1/2 w-px bg-border-c" />
              </div>
              <span className="min-w-32 text-left">
                <span
                  className={`num text-2xs font-black ${
                    tone === 'green' ? 'text-accent-green' : tone === 'red' ? 'text-accent-red' : 'text-text-muted'
                  }`}
                >
                  {deltaLabel(r.delta)}
                </span>
                <span className="num block text-2xs text-text-muted">
                  هدف {toFaDigits(r.targetPct)}٪ · فعلی {toFaDigits(r.currentPct)}٪
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
