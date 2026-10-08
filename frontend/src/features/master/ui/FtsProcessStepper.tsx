import { Link } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
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

/** گام‌هایِ قیف — یک ردیفِ tabِ فشرده.
 *
 *  پیشِ این هر گام کارتِ ۸×۸ با سطرِ دوم («اکنون در این مرحله هستید») بود و
 *  `min-w-[720px]` می‌خواست؛ مالک آن را «navigationِ بزرگ» شمرد. خودِ جدول
 *  باید اول دیده شود، پس این‌جا فقط چهار برچسب است. */
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
    <nav aria-label="مراحل غربالگری FTS" data-testid="fts-process-stepper" className="w-full">
      <div className="flex items-center gap-1">
        {FUNNEL_STAGES.map((stage) => {
          const isActive = stage.key === active;
          return (
            <Link
              key={stage.key}
              to={funnelStagePath(stage.key, preset, symbol)}
              aria-current={isActive ? 'step' : undefined}
              data-testid={`fts-step-${stage.key}`}
              className={
                isActive
                  ? 'rounded-lg border border-accent-blue/60 bg-accent-blue/15 px-2.5 py-1 text-2xs font-black text-accent-blue'
                  : 'rounded-lg border border-border-c bg-bg-card/50 px-2.5 py-1 text-2xs font-bold text-text-muted hover:border-accent-blue/40 hover:text-text-primary'
              }
            >
              <span className="num">{toFaDigits(stage.index)}</span> · {stage.title}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
