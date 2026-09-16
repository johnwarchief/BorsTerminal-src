// features/master/ui/AgentMatrix.tsx -- جدول مقایسه چهار ایجنت با چراغ هوانوردی
import { Link } from 'react-router';
import { AGENT_WEIGHTS, isSignalExpired, type AgentId, type AgentSignal } from '@contracts/signal';
import { toFaDigits } from '@shared/lib/fmt';
import { fa0 } from '../lib/fmtNum';
import { Badge } from '@shared/components/Badge';
import type { MasterVerdict } from '@contracts/master';
import { layerStatusLabel } from '../lib/managementSummary';

const AGENT_FA: Record<AgentId, { label: string; link: (s: string) => string }> = {
  fundamental: { label: 'بنیادی', link: (s) => `/fundamental/${s}` },
  technical: { label: 'تکنیکال', link: (s) => `/technical/${s}` },
  tape: { label: 'تابلو', link: () => '/market' },
  portfolio: { label: 'پرتفوی', link: () => '/portfolio' },
};

export type AgentStatus = 'active' | 'expired' | 'nodata' | 'incomplete' | 'missing';

export function agentStatus(s: AgentSignal | undefined, now = Date.now()): AgentStatus {
  if (!s) return 'missing';
  if (isSignalExpired(s, now)) return 'expired';
  if (s.confidence === 'nodata') return 'nodata';
  const q = (s.payload as { dataQuality?: unknown } | null)?.dataQuality;
  if (q === 'incomplete') return 'incomplete';
  return 'active';
}

const STATUS_FA: Record<AgentStatus, { label: string; tone: 'green' | 'red' | 'yellow' | 'gray' }> = {
  active: { label: 'فعال', tone: 'green' },
  expired: { label: 'منقضی', tone: 'gray' },
  nodata: { label: 'بدون داده', tone: 'gray' },
  incomplete: { label: 'ناقص', tone: 'yellow' },
  missing: { label: 'منتشرنشده', tone: 'red' },
};

const CONF_FA = {
  high: 'بالا',
  medium: 'متوسط',
  low: 'کم',
  nodata: 'بدون داده',
} as const;

const CONF_TONE = {
  high: 'green',
  medium: 'blue',
  low: 'yellow',
  nodata: 'gray',
} as const;

/** سن سیگنال به فارسی نسبی: ساعت/روز */
export function signalAgeLabel(ts: number, now = Date.now()): string {
  const ms = Math.max(0, now - ts);
  const hours = ms / 3600_000;
  if (hours < 1) return 'لحظه ای';
  if (hours < 24) return `${toFaDigits(Math.round(hours))} ساعت پیش`;
  return `${toFaDigits(Math.round(hours / 24))} روز پیش`;
}

/** چراغ هوانوردی: سبز فعال، کهربایی هشدار، خاموش بدون داده */
function Beacon({ status }: { status: AgentStatus }) {
  const on = status === 'active';
  const warn = status === 'expired' || status === 'incomplete' || status === 'missing';
  return (
    <span
      aria-hidden
      className={`inline-block h-2.5 w-2.5 rounded-full transition-all duration-300 ${
        on
          ? 'bg-accent-green shadow-[0_0_10px_var(--accent-green)]'
          : warn
            ? 'animate-pulse bg-accent-yellow shadow-[0_0_8px_var(--accent-yellow)]'
            : 'bg-border-c'
      }`}
    />
  );
}

export function AgentMatrix({
  symbol,
  inputs,
  verdict,
}: {
  symbol: string;
  inputs: Partial<Record<AgentId, AgentSignal>>;
  verdict: MasterVerdict;
}) {
  const agents: AgentId[] = ['fundamental', 'technical', 'tape', 'portfolio'];
  return (
    <div className="glass-panel overflow-hidden">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-bg-card/70 text-start text-2xs uppercase tracking-wider text-text-secondary">
            <th className="px-4 py-2.5 font-bold">ایجنت</th>
            <th className="px-4 py-2.5 font-bold">وزن اعمال شده</th>
            <th className="px-4 py-2.5 font-bold">امتیاز خام</th>
            <th className="px-4 py-2.5 font-bold">برچسب لایه</th>
            <th className="px-4 py-2.5 font-bold">وضعیت</th>
            <th className="px-4 py-2.5 font-bold">آخرین سیگنال</th>
            <th className="px-4 py-2.5 font-bold">تب</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => {
            const s = inputs[a];
            const st = agentStatus(s);
            const active = st === 'active';
            const contrib = verdict.contributions.find((c) => c.agentId === a);
            return (
              <tr key={a} className="border-t border-[var(--hairline)] transition-colors duration-200 odd:bg-bg-secondary/40 hover:bg-bg-card/50">
                <td className="px-4 py-2.5">
                  <span className="flex items-center gap-2.5 font-bold text-text-primary">
                    <Beacon status={st} />
                    {AGENT_FA[a].label}
                  </span>
                </td>
                <td className="num px-4 py-2.5 text-text-primary">
                  {fa0(active ? AGENT_WEIGHTS[a] : 0)}
                </td>
                <td className="num px-4 py-2.5 text-text-primary">
                  {s?.score == null ? <span className="text-2xs text-text-muted">بدون داده</span> : <>{s.direction === 'bullish' ? '+' : s.direction === 'bearish' ? '-' : ''}{fa0(s.score)}</>}
                  {contrib && active ? <span className="text-text-muted"> (سهم <span className="num">{fa0(contrib.score)}</span>)</span> : null}
                </td>
                <td className="px-4 py-2.5">
                  {(() => {
                    const label = layerStatusLabel(a, s, {
                      volumeMultiple:
                        a === 'tape' && typeof (s?.payload as { volumeMultiple?: unknown } | null)?.volumeMultiple === 'number'
                          ? ((s?.payload as { volumeMultiple: number }).volumeMultiple)
                          : null,
                    });
                    return (
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-bold ${
                          label.tone === 'green'
                            ? 'border-accent-green/30 bg-accent-green/10 text-accent-green'
                            : label.tone === 'red'
                              ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
                              : label.tone === 'yellow'
                                ? 'border-accent-yellow/30 bg-accent-yellow/10 text-accent-yellow'
                                : 'border-border-c bg-bg-card text-text-muted'
                        }`}
                      >
                        {label.text}
                      </span>
                    );
                  })()}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-col items-start gap-1">
                    <Badge tone={STATUS_FA[st].tone}>{STATUS_FA[st].label}</Badge>
                    {s && st !== 'missing' ? <Badge tone={CONF_TONE[s.confidence]}>{CONF_FA[s.confidence]}</Badge> : null}
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  {s ? (
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs font-semibold text-text-secondary" title={s.title}>{s.title}</span>
                      <span className="text-2xs text-text-muted">{signalAgeLabel(s.ts)}</span>
                    </div>
                  ) : (
                    <span className="text-2xs text-text-muted">منتشرنشده — در انتظار سیگنال {AGENT_FA[a].label}</span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <Link to={AGENT_FA[a].link(symbol)} className="text-accent-blue transition-colors hover:text-neon-cyan hover:underline">
                    پرش
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
