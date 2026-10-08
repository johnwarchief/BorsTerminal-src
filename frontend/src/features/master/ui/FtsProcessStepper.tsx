import { Link } from 'react-router';
import type { FunnelStageKey } from '../lib/ftsFunnel';

export const FUNNEL_STAGES = [
  { key: 'tape' as FunnelStageKey, index: 1, short: 'S', title: 'تابلوخوانی', page: 'گام ۱' },
  { key: 'technical' as FunnelStageKey, index: 2, short: 'T', title: 'تکنیکال', page: 'گام ۲' },
  { key: 'fundamental' as FunnelStageKey, index: 3, short: 'F', title: 'بنیادی', page: 'گام ۳' },
  { key: 'handover' as FunnelStageKey, index: 4, short: 'M', title: 'تحویل و جمع‌بندی', page: 'گام ۴' },
] as const;

export function funnelStagePath(stage: FunnelStageKey, preset?: string, symbol?: string | null) {
  const q = new URLSearchParams({ stage });
  if (preset) q.set('preset', preset);
  if (symbol) q.set('symbol', symbol);
  return `/master?${q.toString()}`;
}

export function FtsProcessStepper({
  active,
  preset,
  symbol,
}: {
  active: FunnelStageKey;
  preset?: string;
  symbol?: string | null;
}) {
  return (
    <nav aria-label="مراحل قیف FTS" data-testid="fts-process-stepper" className="w-full overflow-x-auto pb-1">
      <div className="flex min-w-[720px] items-center gap-2">
        {FUNNEL_STAGES.map((stage, i) => {
          const isActive = stage.key === active;
          return (
            <div key={stage.key} className="flex min-w-0 flex-1 items-center gap-2">
              <Link
                to={funnelStagePath(stage.key, preset, symbol)}
                aria-current={isActive ? 'step' : undefined}
                className={
                  isActive
                    ? 'flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-accent-blue/60 bg-accent-blue/10 px-3 py-2 shadow-sm'
                    : 'flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-border-c bg-bg-card/50 px-3 py-2 text-text-muted transition-colors hover:border-accent-blue/40 hover:text-text-primary'
                }
              >
                <span className={isActive ? 'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent-blue/20 text-xs font-black text-accent-blue' : 'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-border-c bg-bg-primary text-xs font-black text-text-muted'}>
                  {stage.short}
                </span>
                <span className="min-w-0">
                  <span className="block text-2xs font-black">{stage.page} · {stage.title}</span>
                  <span className="mt-0.5 block truncate text-3xs text-text-muted">
                    {isActive ? 'اکنون در این مرحله هستید' : 'رفتن به این مرحله'}
                  </span>
                </span>
              </Link>
              {i < FUNNEL_STAGES.length - 1 ? <span className="shrink-0 text-lg text-text-muted" aria-hidden>←</span> : null}
            </div>
          );
        })}
      </div>
    </nav>
  );
}
