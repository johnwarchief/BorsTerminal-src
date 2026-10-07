import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useFtsFunnel } from '../api/useFtsFunnel';
import { FUNNEL_STAGES, funnelStagePath, FtsProcessStepper } from './FtsProcessStepper';
import type { FunnelStageKey } from '../lib/ftsFunnel';
import { MODE_LABEL } from '../lib/ftsFunnel';

const PRESETS = [
  { key: 'swing' as const, label: 'نوسان‌گیر', hint: 'ساعت + جت + حجم مشکوک' },
  { key: 'trend' as const, label: 'روندگیر', hint: 'کف‌روبی + نقطه‌زنی' },
  { key: 'hourglass' as const, label: 'ساعت شنی', hint: 'افق بلندمدت' },
];

const STAGE_COPY: Record<FunnelStageKey, { title: string; desc: string; color: string; icon: string }> = {
  tape: { title: 'تابلوخوانی (S)', desc: 'از نشانه‌های امروز بازار شروع می‌کنیم و کاندیدهای سبک انتخابی را پیدا می‌کنیم.', color: 'accent-yellow', icon: '۰۱' },
  technical: { title: 'تکنیکال دو زمانه (T)', desc: 'اول هفتگی، بعد روزانه؛ سپس شاخه و شواهد ستاپ روشن می‌شود.', color: 'accent-blue', icon: '۰۲' },
  fundamental: { title: 'بنیادی پنج‌شاخصه (F)', desc: 'پنج شاخص کدالی روی کاندیدهای عبوری سنجیده می‌شود؛ دلیل هر رأی کنار همان نماد است.', color: 'accent-green', icon: '۰۳' },
  handover: { title: 'تحویل و جمع‌بندی (M)', desc: 'نمای کامل چهار در و فهرست نهایی آماده بررسی معامله‌گر.', color: 'emerald-500', icon: '۰۴' },
};

function StageCard({
  stage,
  total,
  counts,
  loading,
}: {
  stage: FunnelStageKey;
  total: number;
  counts: { pass: number; reject: number; pending: number; unavailable: number };
  loading: boolean;
}) {
  const copy = STAGE_COPY[stage];
  const passPct = total ? Math.round((counts.pass / total) * 100) : 0;
  return (
    <div data-testid={`overview-stage-${stage}`} className="flex min-h-[230px] flex-col justify-between rounded-3xl border border-border-c bg-bg-card/75 p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-border-accent hover:shadow-lg">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className={`flex h-10 w-10 items-center justify-center rounded-2xl bg-${copy.color}/12 text-sm font-black text-${copy.color}`}>{copy.icon}</span>
            <div>
              <div className="text-sm font-black text-text-primary">{copy.title}</div>
              <div className="text-3xs text-text-muted">{FUNNEL_STAGES.find((s) => s.key === stage)?.page}</div>
            </div>
          </div>
          <span className="rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-3xs font-bold text-text-muted">
            {loading ? 'در حال بررسی' : `${toFaDigits(total)} نماد`}
          </span>
        </div>
        <p className="mt-4 text-xs leading-6 text-text-secondary">{copy.desc}</p>
      </div>
      <div className="mt-5 space-y-2">
        <div className="flex items-center justify-between text-2xs">
          <span className="font-bold text-accent-green">تأیید: {toFaDigits(counts.pass)}</span>
          <span className="font-bold text-accent-red">رد: {toFaDigits(counts.reject)}</span>
          <span className="text-text-muted">سایر: {toFaDigits(counts.pending + counts.unavailable)}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-bg-primary">
          <div className="h-full rounded-full bg-accent-green transition-[width]" style={{ width: `${passPct}%` }} />
        </div>
      </div>
    </div>
  );
}

export function FtsFunnelOverview() {
  const navigate = useNavigate();
  const horizon = useStrategyStore((s) => s.horizon);
  const setHorizon = useStrategyStore((s) => s.setHorizon);
  const { funnel, mode, loading } = useFtsFunnel(horizon);
  const stageCounts = useMemo(() => funnel.counts, [funnel.counts]);

  return (
    <div className="flex w-full flex-col gap-5" data-testid="fts-funnel-overview">
      <section className="rounded-3xl border border-border-c bg-bg-card/80 p-4 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="text-3xs font-black uppercase tracking-[0.18em] text-accent-blue">FTS · Funnel Control</div>
            <h1 className="mt-1 text-xl font-black text-text-primary sm:text-2xl">نقشه راه قیف FTS</h1>
            <p className="mt-2 text-xs leading-6 text-text-secondary">
              اینجا فقط مرکز کنترل است. هر گام صفحهٔ جداگانهٔ خودش را دارد تا معلوم باشد چه کسی وارد شد، چه کسی عبور کرد و چرا.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.key}
                type="button"
                onClick={() => setHorizon(preset.key)}
                aria-pressed={horizon === preset.key}
                title={preset.hint}
                className={horizon === preset.key ? 'rounded-xl border border-accent-blue/50 bg-accent-blue/15 px-3 py-2 text-2xs font-black text-accent-blue' : 'rounded-xl border border-border-c bg-bg-primary px-3 py-2 text-2xs font-bold text-text-muted hover:border-accent-blue/40 hover:text-text-primary'}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5">
          <FtsProcessStepper active="tape" preset={horizon} />
        </div>

        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-text-muted">
          <span>حالت: <b className="text-text-primary">{MODE_LABEL[mode]}</b></span>
          <span>Universe: <b className="num text-text-primary">{toFaDigits(funnel.total)}</b></span>
          <span>مرحله جاری: <b className="text-accent-yellow">تابلوخوانی</b></span>
        </div>
      </section>

      <section className="grid gap-3 xl:grid-cols-4">
        {FUNNEL_STAGES.map((stage) => (
          <button
            key={stage.key}
            type="button"
            className="text-start"
            onClick={() => navigate(funnelStagePath(stage.key, horizon))}
          >
            <StageCard stage={stage.key} total={funnel.stages[stage.key]?.entries.length ?? 0} counts={stageCounts[stage.key]} loading={loading} />
          </button>
        ))}
      </section>

      <section className="rounded-3xl border border-border-c bg-bg-secondary/40 p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-black text-text-primary">نمای کامل کجاست؟</div>
            <div className="mt-1 text-xs leading-6 text-text-secondary">
              گام چهارم همان نمای چهارمرحله‌ای قبلی است؛ حالا در انتهای مسیر قرار گرفته تا اول مراحل را جداگانه بفهمید و بعد یک‌جا مرور کنید.
            </div>
          </div>
          <button type="button" onClick={() => navigate(funnelStagePath('handover', horizon))} className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-2xs font-black text-emerald-400 hover:bg-emerald-500/15">
            رفتن به نمای کامل قیف ←
          </button>
        </div>
      </section>
    </div>
  );
}
