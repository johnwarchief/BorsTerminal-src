import { Link, useSearchParams } from 'react-router';
import { useMemo } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useFtsFunnel } from '../api/useFtsFunnel';
import {
  activeIdsForPreset,
  buildFtsChartModel,
  descendantsOf,
  ZONE_BY_KEY,
  type FtsPreset,
  type FtsZone,
  type FtsChartNode,
} from '../lib/ftsChartModel';
import { useStrategyParamsStore } from '../stores/strategyParamsStore';
import { StrategyTreeStepper, treeStagePath, TREE_STAGES } from './StrategyTreeStepper';

const TONE: Record<FtsZone, { border: string; text: string; soft: string; dot: string }> = {
  S: { border: 'border-amber-500/40', text: 'text-amber-400', soft: 'bg-amber-500/7', dot: 'bg-amber-400' },
  T: { border: 'border-sky-500/40', text: 'text-sky-400', soft: 'bg-sky-500/7', dot: 'bg-sky-400' },
  F: { border: 'border-emerald-500/40', text: 'text-emerald-400', soft: 'bg-emerald-500/7', dot: 'bg-emerald-400' },
  M: { border: 'border-rose-500/40', text: 'text-rose-400', soft: 'bg-rose-500/7', dot: 'bg-rose-400' },
};

function presetFrom(value: string | null, fallback: FtsPreset): FtsPreset {
  return value === 'swing' || value === 'trend' || value === 'hourglass' || value === 'custom' ? value : fallback;
}

function leaves(model: ReturnType<typeof buildFtsChartModel>, id: string): FtsChartNode[] {
  return descendantsOf(model, id).map((x) => model.byId.get(x)).filter((x): x is FtsChartNode => Boolean(x && x.kind === 'leaf'));
}

export default function StrategyTreeStageView({ zone }: { zone: FtsZone }) {
  const [params] = useSearchParams();
  const horizon = useStrategyStore((s) => s.horizon);
  const symbolStore = useSymbolStore((s) => s.symbol);
  const symbol = params.get('symbol') || symbolStore || '';
  const preset = presetFrom(params.get('preset'), horizon);
  const strategyParams = useStrategyParamsStore((s) => s.params);
  const model = useMemo(() => buildFtsChartModel(strategyParams), [strategyParams]);
  const active = useMemo(() => activeIdsForPreset(preset, model), [preset, model]);
  const { funnel } = useFtsFunnel(preset);
  const root = model.byId.get(model.roots[zone]);
  const tone = TONE[zone];
  const mainBranches = root ? model.childrenOf.get(root.id) ?? [] : [];
  const branchNodes = mainBranches.map((id) => model.byId.get(id)).filter((x): x is FtsChartNode => Boolean(x));

  const candidate = useMemo(() => {
    if (!symbol) return null;
    const all = [
      ...funnel.stages.tape.entries,
      ...funnel.stages.technical.entries,
      ...funnel.stages.fundamental.entries,
      ...funnel.stages.handover.entries,
    ];
    return all.find((c) => c.symbol === symbol) ?? null;
  }, [funnel, symbol]);

  const currentBranchId = zone === 'T' && candidate
    ? candidate.trendD === 'up'
      ? 't_daily_up'
      : candidate.trendD === 'down'
        ? 't_daily_down'
        : candidate.trendD === 'range'
          ? 't_daily_neutral'
          : null
    : null;

  const activeBranchCount = branchNodes.filter((n) => active.has(n.id) || n.id === currentBranchId).length;

  const index = TREE_STAGES.findIndex((x) => x.zone === zone);
  const prev = TREE_STAGES[index - 1]?.zone;
  const next = TREE_STAGES[index + 1]?.zone;

  return (
    <div className="flex w-full flex-col gap-4" data-testid={`strategy-tree-page-${zone}`}>
      <StrategyTreeStepper active={zone} preset={preset} symbol={symbol || null} />

      <section className={`rounded-3xl border ${tone.border} ${tone.soft} p-4 shadow-sm sm:p-6`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className={`text-3xs font-black uppercase tracking-[0.18em] ${tone.text}`}>{ZONE_BY_KEY[zone].page}</div>
            <h1 className="mt-1 text-xl font-black text-text-primary sm:text-2xl">{ZONE_BY_KEY[zone].stageName}</h1>
            <p className="mt-2 max-w-4xl text-xs leading-6 text-text-secondary">
              {root?.description}
            </p>
          </div>
          <div className="rounded-2xl border border-border-c bg-bg-card/55 px-4 py-3">
            <div className="text-3xs text-text-muted">مسیر فعلی</div>
            <div className={`mt-1 text-sm font-black ${tone.text}`}>{toFaDigits(activeBranchCount)} شاخه روشن از {toFaDigits(branchNodes.length)}</div>
            <div className="mt-1 text-3xs text-text-muted">شاخه‌های کم‌رنگ هنوز ممکن‌اند؛ فقط مسیر انتخاب‌شده پررنگ است.</div>
          </div>
        </div>

        {candidate ? (
          <div className="mt-4 rounded-2xl border border-accent-blue/30 bg-accent-blue/5 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-black text-text-primary">نماد فعال: {candidate.symbol}</span>
              <span className="text-2xs text-accent-blue font-bold">
                {zone === 'T' ? `W: ${candidate.trendW || '—'} · D: ${candidate.trendD || '—'} · ${candidate.dailyStrategy || '—'}` : 'وضعیت این صفحه از قیف زنده خوانده می‌شود'}
              </span>
            </div>
          </div>
        ) : null}
      </section>

      <section className="space-y-3">
        {branchNodes.map((branch) => {
          const isPath = active.has(branch.id) || branch.id === currentBranchId;
          const branchLeaves = leaves(model, branch.id);
          return (
            <article
              key={branch.id}
              data-node-id={branch.id}
              className={`rounded-3xl border p-4 sm:p-5 transition-opacity ${isPath ? `border ${tone.border} bg-bg-card` : 'border-border-c bg-bg-card/45 opacity-45'}`}
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${isPath ? tone.dot : 'bg-text-muted/30'}`} />
                    <h2 className="text-sm font-black text-text-primary">{branch.label}</h2>
                  </div>
                  <p className="mt-1 text-2xs leading-5 text-text-muted">{branch.description}</p>
                </div>
                <div className="shrink-0 rounded-xl border border-border-c bg-bg-primary/50 px-2.5 py-1.5 text-3xs font-bold text-text-muted">
                  {toFaDigits(branchLeaves.length)} مسیر داخلی
                </div>
              </div>

              {branchLeaves.length ? (
                <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {branchLeaves.map((node) => {
                    const leafActive = active.has(node.id) || node.id === currentBranchId;
                    return (
                      <details key={node.id} className={`group rounded-2xl border p-3 ${leafActive ? 'border-border-accent bg-bg-primary/45' : 'border-border-c/70 bg-bg-primary/20'}`}>
                        <summary className="cursor-pointer list-none">
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-2xs font-black text-text-primary">{node.label}</span>
                            <span className="text-3xs text-text-muted">{leafActive ? 'مسیر روشن' : 'آینده'}</span>
                          </div>
                        </summary>
                        <div className="mt-3 space-y-2 border-t border-border-c/50 pt-3 text-3xs leading-5">
                          <p className="text-text-secondary">{node.description}</p>
                          {node.ruleFormula ? <div className="rounded-xl border border-border-c bg-bg-secondary/40 p-2 font-mono text-text-muted">{node.ruleFormula}</div> : null}
                          <div className="text-text-muted">{node.page} · {node.origin === 'chart' ? 'قاعدهٔ چارت' : 'منطق برنامه'}</div>
                        </div>
                      </details>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-3 rounded-xl border border-dashed border-border-c px-3 py-2 text-3xs text-text-muted">
                  این گره خودش یک تصمیم/قاعده است.
                </div>
              )}
            </article>
          );
        })}
      </section>

      <div className="flex items-center justify-between gap-2">
        {prev ? <Link to={treeStagePath(prev, preset, symbol || null)} className="rounded-xl border border-border-c bg-bg-card px-3 py-2 text-2xs font-bold text-text-secondary hover:border-accent-blue/50 hover:text-accent-blue">← صفحه قبل</Link> : <span />}
        {next ? <Link to={treeStagePath(next, preset, symbol || null)} className="rounded-xl border border-accent-blue/40 bg-accent-blue/10 px-3 py-2 text-2xs font-black text-accent-blue hover:bg-accent-blue/15">صفحه بعد →</Link> : <Link to="/master" className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-2xs font-black text-emerald-400">رفتن به قیف FTS</Link>}
      </div>
    </div>
  );
}
