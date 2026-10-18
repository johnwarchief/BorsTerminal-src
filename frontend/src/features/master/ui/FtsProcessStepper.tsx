import { Link } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import type { FunnelFlow, FunnelStageKey, StageSummary } from '../lib/ftsFunnel';
import { stageOrderOf } from '../lib/ftsFunnel';

export const FUNNEL_STAGES = [
  { key: 'tape' as FunnelStageKey, index: 1, short: 'S', title: 'تابلوخوانی', page: 'گام ۱' },
  { key: 'technical' as FunnelStageKey, index: 2, short: 'T', title: 'تکنیکال', page: 'گام ۲' },
  { key: 'fundamental' as FunnelStageKey, index: 3, short: 'F', title: 'بنیادی', page: 'گام ۳' },
  { key: 'handover' as FunnelStageKey, index: 4, short: 'M', title: 'تحویل و جمع‌بندی', page: 'گام ۴' },
] as const;

/** ترتیبِ تب‌ها از `flowِ` پاسخِ موتور می‌آید، نه از یک فهرستِ دوم: درِ
 *  استراتژیِ «تکنیکال‌محور» گامِ تکنیکال گامِ ۱ است و تابلوخوانی گامِ ۲.
 *  شمارۀ هر تب هم همان‌جا بازنویسی می‌شود تا «گام ۲» دو معنی ندهد. */
export function funnelStagesFor(flow: FunnelFlow = 'tape_first') {
  const order = stageOrderOf(flow);
  return order.map((key, i) => {
    const base = FUNNEL_STAGES.find((s) => s.key === key) ?? FUNNEL_STAGES[0];
    return { ...base, index: i + 1, page: `گام ${toFaDigits(i + 1)}` };
  });
}

export function funnelStagePath(stage: FunnelStageKey, preset?: string, symbol?: string | null) {
  const q = new URLSearchParams({ stage });
  if (preset) q.set('preset', preset);
  if (symbol) q.set('symbol', symbol);
  return `/master?${q.toString()}`;
}

/** شمارندۀ هر تب = تعدادِ نمادهایی که **از همان گام عبور کرده‌اند** — یعنی
 *  `pass`ِ خودِ موتور رویِ جامعۀ غربالگری، نه شمارِ ردیف‌هایِ جدول و نه شمارِ
 *  بررسی‌شدگان. بارگذاری/خطا/خالی سه حالتِ جدا هستند تا هیچ‌کدام با «صفر
 *  عبوری» اشتباه نشود (رأیِ مالک ۱۴۰۵-۰۷-۲۱). */
function stageBadge(s: StageSummary | undefined, state: 'ready' | 'loading' | 'error') {
  if (state === 'error') return { text: '!', tone: 'border-accent-red/50 bg-accent-red/15 text-accent-red',
    title: 'داوریِ این گام از سرور نرسید — شمارندۀ گام پیشین را ندارد' };
  if (state === 'loading' && !s) return { text: '…', tone: 'border-border-c bg-bg-primary/60 text-text-muted',
    title: 'در حالِ محاسبه' };
  const pass = s?.pass ?? 0;
  return {
    text: toFaDigits(pass),
    tone: pass > 0
      ? 'border-accent-green/40 bg-accent-green/15 text-accent-green'
      : 'border-border-c bg-bg-primary/60 text-text-muted',
    title: s
      ? `${toFaDigits(pass)} عبوری از این گام — ${toFaDigits(s.reject)} رد، `
        + `${toFaDigits(s.pending)} سنجیده‌نشده، ${toFaDigits(s.unavailable)} بی‌منبع`
      : '',
  };
}

/** گام‌هایِ قیف — چهار تبِ خوانا با شمارندۀ عبوری‌هایِ همان گام.
 *
 *  پیشِ این هر گام کارتِ ۸×۸ با سطرِ دوم بود و `min-w-[720px]` می‌خواست؛ مالک آن
 *  را «navigationِ بزرگ» شمرد و به چهار برچسبِ فشرده رسیدیم (۱۴۰۵-۰۷-۱۹). درِ
 *  دورِ ۱۴۰۵-۰۷-۲۱ همان برچسب‌ها خیلی ریز بودند (text-2xs، py-1) و بی‌عدد؛
 *  حالا قدِ ثابتِ py-2 با متنِ ۱۳px و عددِ پرانتزی — نه کارتِ دوباره، نه نوارِ بلند. */
export function FtsProcessStepper({
  active,
  preset,
  symbol,
  counts,
  flow = 'tape_first',
  state = 'ready',
}: {
  active: FunnelStageKey;
  preset?: string;
  symbol?: string | null;
  counts?: Partial<Record<FunnelStageKey, StageSummary>>;
  flow?: FunnelFlow;
  state?: 'ready' | 'loading' | 'error';
}) {
  const stages = funnelStagesFor(flow);
  return (
    <nav aria-label="مراحل غربالگری FTS" data-testid="fts-process-stepper" className="w-full">
      <div className="flex flex-wrap items-stretch gap-1.5">
        {stages.map((stage) => {
          const isActive = stage.key === active;
          const badge = stageBadge(counts?.[stage.key], state);
          return (
            <Link
              key={stage.key}
              to={funnelStagePath(stage.key, preset, symbol)}
              aria-current={isActive ? 'step' : undefined}
              data-testid={`fts-step-${stage.key}`}
              title={`${stage.page}: ${stage.title} — ${badge.title}`}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs leading-none transition-colors ${
                isActive
                  ? 'border-accent-blue bg-accent-blue/15 font-black text-accent-blue'
                  : 'border-border-c bg-bg-card/60 font-bold text-text-secondary hover:border-accent-blue/50 hover:text-text-primary'
              }`}
            >
              <span className={`num grid h-4.5 w-4.5 shrink-0 place-items-center rounded-md border text-3xs font-black ${
                isActive ? 'border-accent-blue/50 bg-accent-blue/20 text-accent-blue'
                         : 'border-border-c bg-bg-primary/70 text-text-muted'
              }`}>
                {toFaDigits(stage.index)}
              </span>
              <span className="whitespace-nowrap">{stage.title}</span>
              <span data-testid={`fts-step-count-${stage.key}`}
                    className={`num shrink-0 rounded-md border px-1.5 py-0.5 text-3xs font-black ${badge.tone}`}>
                {badge.text}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
