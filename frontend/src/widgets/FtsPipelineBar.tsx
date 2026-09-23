// widgets/FtsPipelineBar.tsx -- نوار سراسری زنجیره ۴ مرحله‌ای FTS
import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import { ftsScoreOf } from '@contracts/fundamental';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { runStrictGates, definiteDecision } from '@features/master/lib/strictGates';
import {
  evaluateFtsPipeline,
  HORIZON_LABELS,
} from '@features/master/lib/ftsPipelineEvaluator';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useMarketCloses } from '@features/portfolio/api/usePortfolio';
import { useFtsPlan } from '@features/master/api/useFtsPlan';
import { FtsAnalystModal } from './FtsAnalystModal';

export function FtsPipelineBar() {
  const symbol = useSymbolStore((s) => s.symbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);
  const navigate = useNavigate();
  const location = useLocation();

  const horizon = useStrategyStore((s) => s.horizon);
  const setHorizon = useStrategyStore((s) => s.setHorizon);
  const [modalOpen, setModalOpen] = useState(false);

  const entry = useSignalStore((s) => (symbol ? s.bus[symbol] : undefined));
  const inputs = useMemo(() => (symbol ? getActiveSignals(symbol) : {}), [symbol, entry]);

  const closes = useMarketCloses();
  const ftsPlan = useFtsPlan(symbol);
  const currentPrice = (symbol ? closes.data?.get(symbol) : null) ?? null;
  const resistance = ftsPlan.data?.fts?.jet?.resistance ?? null;
  const support = ftsPlan.data?.fts?.fib?.zone_33_40?.lo ?? null;
  const fundScore = ftsScoreOf(inputs.fundamental);

  const strict = useMemo(
    () =>
      runStrictGates(inputs, {
        inBasket: null,
        industryUsedPct: null,
        industryCapPct: 20,
        warRegime: false,
        symbolWeightPct: null,
      }),
    [inputs],
  );

  const decision = useMemo(() => definiteDecision(strict), [strict]);

  const evaluation = useMemo(
    () =>
      evaluateFtsPipeline({
        symbol: symbol || '',
        horizon,
        inputs,
        strict,
        decision,
        currentPrice,
        resistancePrice: resistance,
        supportPrice: support,
        fundScore,
      }),
    [symbol, horizon, inputs, strict, decision, currentPrice, resistance, support, fundScore],
  );

  if (!symbol) return null;

  const statusIcons = {
    pass: '✓',
    fail: '✗',
    wait: '⏳',
  };

  return (
    <>
      <div
        data-testid="fts-pipeline-bar"
        className="glass-panel sticky top-0 z-30 mx-auto my-1 flex h-8 min-h-8 w-[calc(100%-1.5rem)] max-w-4xl items-center justify-between gap-2 rounded-xl border border-border-c/80 bg-bg-card/85 px-2.5 py-1 shadow-md backdrop-blur-md transition-all"
      >
        {/* سمت راست (RTL): نماد و ۴ مرحله */}
        <div className="flex items-center gap-1.5 overflow-hidden">
          <div className="flex items-center gap-1 rounded-md border border-accent-blue/30 bg-accent-blue/10 px-1.5 py-0.5 text-[11px] font-black text-accent-blue shrink-0">
            <span>{symbol}</span>
          </div>

          <div className="flex items-center gap-1 overflow-x-auto text-3xs py-0.5 scrollbar-none">
            {evaluation.steps.map((s) => {
              const isCurrent = location.pathname.startsWith(s.targetRoute);
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => navigate(s.targetRoute)}
                  title={`${s.title}: ${s.headline}`}
                  data-testid={`fts-pipeline-step-${s.id}`}
                  className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-bold text-[10.5px] transition-all whitespace-nowrap shrink-0 ${
                    isCurrent
                      ? 'border-accent-blue bg-accent-blue/20 text-text-primary shadow-[0_0_6px_rgba(56,189,248,0.25)]'
                      : 'border-border-c/70 bg-bg-primary/80 text-text-secondary hover:border-border-accent hover:text-text-primary'
                  }`}
                >
                  <span className="text-text-muted">{toFaDigits(s.step)}.</span>
                  <span>{s.title}</span>
                  <span
                    className={`flex h-3 w-3 items-center justify-center rounded-full text-[9px] font-black ${
                      s.status === 'pass'
                        ? 'bg-accent-green text-black'
                        : s.status === 'fail'
                          ? 'bg-accent-red text-on-accent'
                          : 'bg-accent-yellow/30 text-accent-yellow'
                    }`}
                  >
                    {statusIcons[s.status]}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* سمت چپ (RTL): افق معاملاتی و دکمه باز کردن مشاور تشریحی */}
        <div className="flex items-center gap-1.5 ms-auto shrink-0">
          <span className="hidden md:inline text-[10px] text-text-muted">
            افق: <span className="font-bold text-accent-blue">{HORIZON_LABELS[horizon].badge}</span>
          </span>

          <button
            type="button"
            onClick={() => setModalOpen(true)}
            data-testid="fts-open-copilot-btn"
            className="flex items-center gap-1 rounded-md border border-accent-blue/50 bg-accent-blue/20 px-2 py-0.5 text-[11px] font-black text-accent-blue hover:bg-accent-blue hover:text-black transition-all shadow-[0_0_8px_rgba(56,189,248,0.15)]"
          >
            <span className="text-xs">🧠</span>
            <span className="hidden sm:inline">مشاور تحلیلی FTS</span>
            <span className="sm:hidden">مشاور</span>
          </button>

          <button
            type="button"
            onClick={clearSymbol}
            title="بستن نماد انتخابی"
            className="flex h-5 w-5 items-center justify-center rounded border border-border-c/60 text-text-muted hover:border-accent-red hover:text-accent-red transition-colors text-[10px]"
          >
            ✕
          </button>
        </div>
      </div>

      <FtsAnalystModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        evaluation={evaluation}
        onHorizonChange={(h) => setHorizon(h)}
      />
    </>
  );
}
