// features/master/ui/MasterVerdictCard.tsx -- گیج HUD با پرتو نور و عقربه
import type { AgentId, AgentSignal } from '@contracts/signal';
import type { MasterVerdict } from '@contracts/master';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';

const ACTION_FA = {
  strong_buy: 'خرید قوی',
  buy: 'خرید',
  hold: 'نگهداری',
  watch: 'زیر نظر',
  reduce: 'کاهش',
  sell: 'فروش',
  strong_sell: 'فروش قوی',
  no_data: 'بدون داده',
} as const;

const ACTION_TONE = {
  strong_buy: 'green',
  buy: 'green',
  hold: 'gray',
  watch: 'blue',
  reduce: 'yellow',
  sell: 'red',
  strong_sell: 'red',
  no_data: 'gray',
} as const;

const AGENT_FA: Record<AgentId, string> = {
  fundamental: 'بنیادی',
  technical: 'تکنیکال',
  tape: 'تابلو',
  portfolio: 'پرتفوی',
};

const CONF_FA = {
  high: 'اطمینان بالا',
  medium: 'اطمینان متوسط',
  low: 'اطمینان کم',
  nodata: 'بدون داده',
} as const;

const CONF_TONE = {
  high: 'green',
  medium: 'blue',
  low: 'yellow',
  nodata: 'gray',
} as const;

/** ميلي متر نوار مساهم هر ايگنت: نسبت قدر مطلق سهم به بیشینه قدر مطلق */
export function contribBarWidth(score: number, maxAbs: number): number {
  if (maxAbs <= 0) return 0;
  return Math.max(2, Math.min(100, (Math.abs(score) / maxAbs) * 100));
}

export function MasterVerdictCard({ verdict, inputs }: { verdict: MasterVerdict; inputs?: Partial<Record<AgentId, AgentSignal>> }) {
  const pct = Math.max(0, Math.min(100, (verdict.compositeScore + 100) / 2));
  const r = 52;
  const circ = 2 * Math.PI * r;
  const color = pct >= 60 ? 'var(--accent-green)' : pct >= 40 ? 'var(--neon-cyan)' : 'var(--neon-red)';
  // عقربه روی نیم دایره بالا: از 180- درجه (چپ) تا 0+ (راست)
  const needleDeg = -90 + (pct / 100) * 180;
  const activeCount = verdict.usedSignalIds.length;
  const activeContribs = verdict.contributions.filter((c) => c.signalCount > 0);
  const maxAbs = activeContribs.reduce((m, c) => Math.max(m, Math.abs(c.score)), 0);

  return (
    <div className="glass-panel panel-in overflow-hidden p-5">
      <div className="pointer-events-none absolute -left-16 -top-16 h-44 w-44 rounded-full bg-neon-cyan/10 blur-3xl" aria-hidden />
      <div className="relative flex flex-wrap items-center gap-6">
        <div className="relative" dir="ltr">
          <svg width="150" height="150" viewBox="0 0 130 130" role="img" aria-label="گیج برآیند">
            <defs>
              <filter id="gauge-glow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="2.6" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <linearGradient id="beam-grad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={color} stopOpacity="0" />
                <stop offset="100%" stopColor={color} stopOpacity="0.9" />
              </linearGradient>
            </defs>
            {/* خط کش های دور گیج */}
            {Array.from({ length: 21 }, (_, i) => {
              const a = (-90 + i * 9) * (Math.PI / 180);
              const inner = i % 5 === 0 ? 42 : 45.5;
              return (
                <line
                  key={i}
                  x1={65 + inner * Math.sin(a + Math.PI)}
                  y1={65 - inner * Math.cos(a + Math.PI)}
                  x2={65 + 48.5 * Math.sin(a + Math.PI)}
                  y2={65 - 48.5 * Math.cos(a + Math.PI)}
                  stroke="var(--border-color)"
                  strokeWidth={i % 5 === 0 ? 1.6 : 0.8}
                />
              );
            })}
            <circle cx="65" cy="65" r={r} fill="none" stroke="var(--border-color)" strokeOpacity="0.45" strokeWidth="9" />
            <circle
              cx="65"
              cy="65"
              r={r}
              fill="none"
              stroke={color}
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={circ}
              strokeDashoffset={circ * (1 - pct / 100)}
              transform="rotate(-90 65 65)"
              filter="url(#gauge-glow)"
              style={{ transition: 'stroke-dashoffset 0.7s cubic-bezier(0.22, 1, 0.36, 1)' }}
            />
            {/* پرتو نور هوانوردی */}
            <g
              className="hud-beam"
              style={{ ['--beam-to' as string]: `${needleDeg}deg`, ['--beam-from' as string]: `${-90}deg`, transform: `rotate(${needleDeg}deg)`, transformOrigin: '65px 65px', transition: 'transform 0.7s cubic-bezier(0.22, 1, 0.36, 1)' }}
            >
              <line x1="65" y1="65" x2="18" y2="65" stroke="url(#beam-grad)" strokeWidth="2.4" strokeLinecap="round" />
              <circle cx="18" cy="65" r="3" fill={color} filter="url(#gauge-glow)" />
            </g>
            <text x="65" y="60" textAnchor="middle" fontSize="23" fontWeight="900" fill="var(--text-primary)" className="num">
              {toFaDigits(Math.round(pct))}
            </text>
            <text x="65" y="80" textAnchor="middle" fontSize="10.5" fill="var(--text-muted)">
              برآیند ۱۰۰ تا ۰
            </text>
          </svg>
        </div>

        <div className="flex min-w-52 flex-col gap-2.5">
          <div className="flex items-center gap-2">
            <Badge tone={ACTION_TONE[verdict.finalAction]}>{ACTION_FA[verdict.finalAction]}</Badge>
            {verdict.hasConflict ? <Badge tone="orange">تضاد افق زمانی</Badge> : null}
          </div>
          <div className="text-xs leading-6 text-text-secondary">
            <span className="num text-base font-black text-text-primary">{toFaDigits(pct)}٪</span> توافق ایجنت ها ·{' '}
            <span className="num">{toFaDigits(activeCount)}</span> از <span className="num">۴</span> سیگنال فعال
            {verdict.discardedSignalIds.length > 0 ? (
              <span className="text-text-muted"> ({toFaDigits(verdict.discardedSignalIds.length)} کنارگذاشته شده)</span>
            ) : null}
          </div>
          <div className="flex gap-1.5" dir="ltr" aria-hidden>
            {Array.from({ length: 4 }, (_, i) => (
              <span
                key={i}
                className={`h-1.5 flex-1 rounded-full transition-colors duration-500 ${
                  i < activeCount ? 'bg-neon-cyan shadow-[0_0_8px_var(--neon-cyan)]' : 'bg-bg-card'
                }`}
              />
            ))}
          </div>
          <div className="text-2xs uppercase tracking-widest text-text-muted">Master Decision · HUD</div>
        </div>
      </div>

      {activeContribs.length > 0 ? (
        <div className="relative mt-4 flex flex-col gap-2 border-t border-[var(--hairline)] pt-3">
          <div className="text-2xs uppercase tracking-widest text-text-muted">سهم هر ایجنت در برآیند</div>
          {activeContribs.map((c) => {
            const s = inputs?.[c.agentId];
            return (
              <div key={c.agentId} className="flex items-center gap-2 text-xs">
                <span className="w-14 shrink-0 font-bold text-text-primary">{AGENT_FA[c.agentId]}</span>
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-bg-card" dir="ltr">
                  <span
                    className={`absolute inset-y-0 left-1/2 w-px bg-border-c ${c.score === 0 ? 'opacity-100' : 'opacity-60'}`}
                    aria-hidden
                  />
                  {c.score !== 0 ? (
                    <span
                      className={`absolute inset-y-0 rounded-full transition-all duration-700 ${
                        c.score > 0 ? 'left-1/2 bg-accent-green' : 'right-1/2 bg-accent-red'
                      }`}
                      style={{ width: `${contribBarWidth(c.score, maxAbs) / 2}%` }}
                    />
                  ) : null}
                </div>
                <span className={`num w-14 shrink-0 text-left font-bold ${c.score > 0 ? 'text-accent-green' : c.score < 0 ? 'text-accent-red' : 'text-text-muted'}`}>
                  {c.score > 0 ? '+' : ''}
                  {toFaDigits(c.score)}
                </span>
                <Badge tone={CONF_TONE[c.confidence]}>{CONF_FA[c.confidence]}</Badge>
                {s ? <span className="truncate text-2xs text-text-muted" title={s.title}>{s.title}</span> : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
