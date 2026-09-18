// features/master/ui/StrategyHorizonSelector.tsx -- انتخابگر افق استراتژی FTS
// نوسان‌گیر (زیر ۳ ماه) / روندگیر (بالای ۳ ماه) / ساعت شنی (۳ تا ۱۰ ساله)
import {
  type StrategyHorizon,
  HORIZON_LABELS,
} from '../lib/ftsPipelineEvaluator';

export function StrategyHorizonSelector({
  horizon,
  recommendedHorizon,
  onSelectHorizon,
  onOpenAnalystModal,
  onOpenTreeModal,
}: {
  horizon: StrategyHorizon;
  recommendedHorizon: StrategyHorizon;
  onSelectHorizon: (h: StrategyHorizon) => void;
  onOpenAnalystModal?: () => void;
  onOpenTreeModal?: () => void;
}) {
  const horizons: StrategyHorizon[] = ['swing', 'trend', 'hourglass'];

  const horizonIcons: Record<StrategyHorizon, string> = {
    swing: '⚡',
    trend: '📈',
    hourglass: '⏳',
  };

  return (
    <div
      data-testid="strategy-horizon-selector"
      className="glass-panel relative overflow-hidden p-4"
    >
      <div className="pointer-events-none absolute -end-12 -top-12 h-32 w-32 rounded-full bg-accent-blue/10 blur-3xl" aria-hidden />

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-black text-text-primary">افق معاملاتی و استراتژی انتخابی</h3>
          <span className="rounded-full border border-accent-blue/40 bg-accent-blue/10 px-2 py-0.5 text-2xs font-bold text-accent-blue">
            پیشنهاد سیستم: {HORIZON_LABELS[recommendedHorizon].badge}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {onOpenTreeModal && (
            <button
              type="button"
              onClick={onOpenTreeModal}
              data-testid="open-strategy-tree-btn"
              className="flex items-center gap-1.5 rounded-lg border border-border-c bg-bg-card/60 px-2.5 py-1 text-2xs font-bold text-text-secondary hover:border-accent-blue hover:text-text-primary transition-all"
            >
              <span>🌳</span>
              <span>نمودار درختی استراتژی</span>
            </button>
          )}

          {onOpenAnalystModal && (
            <button
              type="button"
              onClick={onOpenAnalystModal}
              className="flex items-center gap-1.5 rounded-lg border border-neon-cyan/40 bg-neon-cyan/15 px-3 py-1 text-2xs font-bold text-neon-cyan hover:border-neon-cyan hover:bg-neon-cyan/25 transition-all shadow-[0_0_10px_rgba(6,182,212,0.15)]"
            >
              <span>🧠</span>
              <span>مشاور تشریحی FTS</span>
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {horizons.map((h) => {
          const isSelected = horizon === h;
          const isRecommended = recommendedHorizon === h;
          const info = HORIZON_LABELS[h];

          return (
            <button
              key={h}
              type="button"
              onClick={() => onSelectHorizon(h)}
              data-testid={`strategy-btn-${h}`}
              className={`relative flex flex-col items-start gap-1 rounded-xl border p-3 text-start transition-all ${
                isSelected
                  ? 'border-accent-blue bg-accent-blue/15 text-text-primary shadow-[0_0_12px_rgba(56,189,248,0.2)]'
                  : 'border-border-c bg-bg-secondary/40 text-text-muted hover:border-border-accent hover:bg-bg-secondary/70 hover:text-text-secondary'
              }`}
            >
              <div className="flex w-full items-center justify-between">
                <span className="text-xs font-black flex items-center gap-1.5 text-text-primary">
                  <span>{horizonIcons[h]}</span>
                  <span>{info.title}</span>
                </span>
                {isRecommended && (
                  <span className="rounded border border-accent-green/40 bg-accent-green/15 px-1.5 py-0.5 text-3xs font-black text-accent-green">
                    پیشنهادی
                  </span>
                )}
              </div>
              <p className="text-2xs leading-5 text-text-secondary mt-1">
                {info.desc}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
