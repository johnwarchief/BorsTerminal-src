import { Link } from 'react-router';
import type { FtsZone } from '../lib/ftsChartModel';
import { useTreeFlowStore } from '../stores/treeFlowStore';

export const TREE_STAGES = [
  { zone: 'S' as FtsZone, short: 'S', title: 'تابلوخوانی', page: 'صفحه ۳' },
  { zone: 'T' as FtsZone, short: 'T', title: 'تکنیکال', page: 'صفحه ۲' },
  { zone: 'F' as FtsZone, short: 'F', title: 'بنیادی', page: 'صفحه ۱' },
  { zone: 'M' as FtsZone, short: 'M', title: 'مدیریت و استراتژی', page: 'صفحه ۴' },
] as const;

export function treeStagePath(zone: FtsZone, preset?: string, symbol?: string | null) {
  const q = new URLSearchParams();
  q.set('page', zone);
  if (preset) q.set('preset', preset);
  if (symbol) q.set('symbol', symbol);
  return `/strategy-tree?${q.toString()}`;
}

export function StrategyTreeStepper({ active, preset, symbol }: { active: FtsZone | null; preset: string; symbol?: string | null }) {
  // جریانِ مسیر از همان تنظیمِ درون‌برنامه خوانده می‌شود (پیش‌فرض «همیشه»):
  // فلگِ `html[data-tree-flow-running]` را خودِ استور می‌زند؛ بی‌این import
  // انیمیشنِ درخت بی‌صدا از UI رفته بود (گاردِ flash-idle همان را می‌گیرد).
  const mode = useTreeFlowStore((s) => s.mode);
  const flowing = mode !== 'off';
  return (
    <nav aria-label="صفحات درخت استراتژی FTS" data-testid="strategy-tree-stepper" className="w-full overflow-x-auto pb-1">
      <div className="flex min-w-[760px] items-center gap-2">
        {TREE_STAGES.map((stage, i) => {
          const selected = stage.zone === active;
          return (
            <div key={stage.zone} className="flex flex-1 items-center gap-2">
              <Link
                to={treeStagePath(stage.zone, preset, symbol)}
                aria-current={selected ? 'page' : undefined}
                className={selected
                  ? 'flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-accent-blue/60 bg-accent-blue/10 px-3 py-2'
                  : 'flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-border-c bg-bg-card/60 px-3 py-2 text-text-muted hover:border-accent-blue/40 hover:text-text-primary'}
              >
                <span className={selected ? 'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent-blue/20 text-xs font-black text-accent-blue' : 'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-border-c bg-bg-primary text-xs font-black'}>
                  {stage.short}
                </span>
                <span className="min-w-0">
                  <span className="block text-2xs font-black">{stage.title}</span>
                  <span className="block text-3xs text-text-muted">{stage.page}</span>
                </span>
              </Link>
              {i < TREE_STAGES.length - 1 ? (
                <span
                  className="relative flex h-6 w-7 shrink-0 items-center text-accent-blue/70"
                  aria-hidden
                  data-testid={`tree-flow-rail-${stage.zone}`}
                >
                  {flowing ? (
                    <span className="fts-path-flow" style={{ width: '100%', height: 2, background: 'currentColor' }} />
                  ) : (
                    <span style={{ width: '100%', height: 2, background: 'currentColor', opacity: 0.35 }} />
                  )}
                  {flowing && TREE_STAGES[i + 1].zone === active ? (
                    <span
                      className="fts-comet"
                      style={{ position: 'absolute', insetInlineEnd: 0, width: 6, height: 6, borderRadius: 9999, background: 'currentColor' }}
                    />
                  ) : null}
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </nav>
  );
}
