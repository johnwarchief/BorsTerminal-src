import { Link, useNavigate, useSearchParams } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import { useFtsFunnel } from '../api/useFtsFunnel';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { FUNNEL_STAGES, funnelStagePath, FtsProcessStepper } from './FtsProcessStepper';
import { FtsFunnelStages as FtsFunnelAllStages } from './FtsFunnelAllStages';
import type { FunnelStageKey, TreePreset } from '../lib/ftsFunnel';

const INFO: Record<Exclude<FunnelStageKey, 'handover'>, { title: string; purpose: string; rules: string[]; tone: string }> = {
  tape: { title: 'تابلوخوانی و انتخاب', purpose: 'ورودی‌های این مرحله و دلیل عبور آن‌ها از فیلترهای سبک انتخابی را ببینید.', rules: ['نوسان‌گیر: ساعت + جت + حجم مشکوک', 'روندگیر: کف‌روبی + نقطه‌زنی'], tone: 'accent-yellow' },
  technical: { title: 'تکنیکال دو زمانه', purpose: 'ابتدا هفتگی، سپس روزانه؛ بعد شاخهٔ درست و شواهد همان شاخه.', rules: ['هفتگی نزولی/خنثی = وتو', 'روزانه صعودی = جت/پولبک', 'روزانه نزولی = فیبوناچی/CHoCH', 'روزانه خنثی = کف دوقلو/آخرین ساختار'], tone: 'accent-blue' },
  fundamental: { title: 'بنیادی پنج‌شاخصه', purpose: 'پنج شاخص کنار هم دیده می‌شوند تا دلیل امتیاز هر شرکت روشن باشد.', rules: ['رشد فروش', 'EPS سه‌ساله', 'حاشیه سود ناخالص', 'فروش ۱۲ ماهه ÷ ارزش بازار', 'نرخ‌گذاری'], tone: 'accent-green' },
};

/** نمای یک مرحلۀ قیف: سرصفحۀ همان در + جدولِ خودِ قیف (یک پیاده‌سازی، دو رندر). */
export default function FtsFunnelStageView({
  stage,
  onPresetChange,
}: {
  stage: Exclude<FunnelStageKey, 'handover'>;
  onPresetChange?: (p: Exclude<TreePreset, 'custom'>) => void;
}) {
  const [params] = useSearchParams();
  const horizon = useStrategyStore((s) => s.horizon);
  const preset = (['swing', 'trend', 'hourglass', 'custom'] as const).includes(params.get('preset') as never)
    ? params.get('preset') as TreePreset
    : horizon;
  const selected = useSymbolStore((s) => s.symbol);
  const navigate = useNavigate();
  const { funnel, loading, mode } = useFtsFunnel(preset);
  const data = funnel.stages[stage];
  const info = INFO[stage];
  const stats = data.summary;
  const idx = FUNNEL_STAGES.findIndex((s) => s.key === stage);
  const prev = FUNNEL_STAGES[Math.max(0, idx - 1)]?.key ?? 'tape';
  const next = FUNNEL_STAGES[Math.min(FUNNEL_STAGES.length - 1, idx + 1)]?.key ?? 'handover';

  return (
    <div className="flex w-full flex-col gap-4" data-testid={`fts-stage-${stage}`}>
      <FtsProcessStepper active={stage} preset={preset} symbol={selected || null} />
      <section className="rounded-3xl border border-border-c bg-bg-card/80 p-4 shadow-sm sm:p-6">
        <div className={`text-3xs font-black uppercase tracking-[0.18em] text-${info.tone}`}>FTS · {stage.toUpperCase()}</div>
        <h1 className="mt-1 text-xl font-black text-text-primary sm:text-2xl">{info.title}</h1>
        <p className="mt-2 max-w-4xl text-xs leading-6 text-text-secondary">{info.purpose}</p>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div className="rounded-2xl border border-border-c p-3"><div className="text-3xs text-text-muted">کل</div><div className="mt-1 text-lg font-black num">{toFaDigits(data.entries.length)}</div></div>
          <div className="rounded-2xl border border-accent-green/20 bg-accent-green/5 p-3"><div className="text-3xs text-accent-green">تأیید</div><div className="mt-1 text-lg font-black num text-accent-green">{toFaDigits(stats.pass)}</div></div>
          <div className="rounded-2xl border border-accent-red/20 bg-accent-red/5 p-3"><div className="text-3xs text-accent-red">رد</div><div className="mt-1 text-lg font-black num text-accent-red">{toFaDigits(stats.reject)}</div></div>
          <div className="rounded-2xl border border-accent-yellow/20 bg-accent-yellow/5 p-3"><div className="text-3xs text-accent-yellow">سایر</div><div className="mt-1 text-lg font-black num text-accent-yellow">{toFaDigits(stats.pending + stats.unavailable)}</div></div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {info.rules.map((r) => <span key={r} className="rounded-xl border border-border-c bg-bg-primary/40 px-2.5 py-1.5 text-2xs font-bold text-text-secondary">{r}</span>)}
        </div>
        <div className="mt-4 text-3xs text-text-muted">حالت: {mode === 'review' ? 'مرور کامل بازار' : 'مهندسی معکوس'}{loading ? ' · در حال تازه‌سازی' : ''}</div>
      </section>

      <FtsFunnelAllStages
        preset={preset}
        onPresetChange={onPresetChange}
        only={stage}
        onStageSelect={(k) => navigate(funnelStagePath(k, preset, selected || null))}
      />

      <div className="flex items-center justify-between gap-2 text-2xs">
        <Link to={funnelStagePath(prev, preset, selected || null)} className="text-text-muted hover:text-accent-blue">← مرحله قبل</Link>
        <Link to={funnelStagePath(next, preset, selected || null)} className="font-black text-accent-blue hover:text-accent-blue/80">مرحلۀ بعد ←</Link>
      </div>
    </div>
  );
}
