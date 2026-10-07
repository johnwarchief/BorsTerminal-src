import { Link, useSearchParams, useNavigate } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import { useFtsFunnel } from '../api/useFtsFunnel';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { FUNNEL_STAGES, funnelStagePath, FtsProcessStepper } from './FtsProcessStepper';
import { STATUS_LABEL, trendLabel, type FunnelStageKey, type StageStatus } from '../lib/ftsFunnel';

const INFO: Record<Exclude<FunnelStageKey, 'handover'>, { title: string; purpose: string; rules: string[]; tone: string }> = {
  tape: { title: 'تابلوخوانی و انتخاب', purpose: 'ورودی‌های این مرحله و دلیل عبور آن‌ها از فیلترهای سبک انتخابی را ببینید.', rules: ['نوسان‌گیر: ساعت + جت + حجم مشکوک', 'روندگیر: کف‌روبی + نقطه‌زنی'], tone: 'accent-yellow' },
  technical: { title: 'تکنیکال دو زمانه', purpose: 'ابتدا هفتگی، سپس روزانه؛ بعد شاخهٔ درست و شواهد همان شاخه.', rules: ['هفتگی نزولی/خنثی = وتو', 'روزانه صعودی = جت/پولبک', 'روزانه نزولی = فیبوناچی/CHoCH', 'روزانه خنثی = کف دوقلو/آخرین ساختار'], tone: 'accent-blue' },
  fundamental: { title: 'بنیادی پنج‌شاخصه', purpose: 'پنج شاخص کنار هم دیده می‌شوند تا دلیل امتیاز هر شرکت روشن باشد.', rules: ['رشد فروش', 'EPS سه‌ساله', 'حاشیه سود ناخالص', 'فروش ۱۲ ماهه ÷ ارزش بازار', 'نرخ‌گذاری'], tone: 'accent-green' },
};

const STATUS_CLASS: Record<StageStatus, string> = {
  pass: 'border-accent-green/40 bg-accent-green/10 text-accent-green',
  reject: 'border-accent-red/40 bg-accent-red/10 text-accent-red',
  pending: 'border-accent-yellow/40 bg-accent-yellow/10 text-accent-yellow',
  unavailable: 'border-border-c bg-bg-secondary text-text-muted',
};

function CandidateCard({ stage, candidate }: { stage: Exclude<FunnelStageKey, 'handover'>; candidate: import('../lib/ftsFunnel').Candidate }) {
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const navigate = useNavigate();
  const st = candidate.status[stage];
  return (
    <button
      type="button"
      onClick={() => { setSymbol(candidate.symbol); navigate('/master/' + encodeURIComponent(candidate.symbol)); }}
      className="group w-full text-start rounded-2xl border border-border-c bg-bg-primary/35 p-3 transition-all hover:border-accent-blue/40 hover:bg-bg-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-black text-text-primary">{candidate.symbol}</div>
          <div className="mt-0.5 max-w-[260px] truncate text-3xs text-text-muted">{candidate.name}</div>
        </div>
        <span className={`rounded-lg border px-2 py-1 text-3xs font-black ${STATUS_CLASS[st]}`}>{STATUS_LABEL[st]}</span>
      </div>
      {stage === 'tape' ? (
        <div className="mt-2 text-2xs text-text-secondary">{candidate.patterns.length ? candidate.patterns.join(' · ') : 'نشانهٔ ویژه‌ای ثبت نشده است'}</div>
      ) : null}
      {stage === 'technical' ? (
        <div className="mt-2 flex flex-wrap gap-1.5 text-2xs">
          <span className="rounded-lg border border-border-c px-2 py-1 text-text-secondary">W: {trendLabel(candidate.trendW)}</span>
          <span className="rounded-lg border border-border-c px-2 py-1 text-text-secondary">D: {trendLabel(candidate.trendD)}</span>
          <span className="rounded-lg border border-accent-blue/20 bg-accent-blue/5 px-2 py-1 font-bold text-accent-blue">{candidate.dailyStrategy || 'شاخه نامشخص'}</span>
          {candidate.setups ? <span className="rounded-lg border border-border-c px-2 py-1 text-text-secondary">{candidate.setups}</span> : null}
        </div>
      ) : null}
      {stage === 'fundamental' ? (
        <div className="mt-2 text-2xs font-bold text-text-secondary">امتیاز: {candidate.score == null ? '—' : `${toFaDigits(candidate.score)} از ۵`}</div>
      ) : null}
      <div className="mt-2 border-t border-border-c/50 pt-2 text-2xs leading-5 text-text-muted">
        <span className="font-black text-text-secondary">چرا؟ </span>{candidate.why[stage] || 'دلیل ثبت نشده است.'}
      </div>
    </button>
  );
}

export default function FtsFunnelStageView({ stage }: { stage: Exclude<FunnelStageKey, 'handover'> }) {
  const [params] = useSearchParams();
  const horizon = useStrategyStore((s) => s.horizon);
  const preset = (['swing', 'trend', 'hourglass', 'custom'] as const).includes(params.get('preset') as never)
    ? params.get('preset') as 'swing' | 'trend' | 'hourglass' | 'custom'
    : horizon;
  const selected = useSymbolStore((s) => s.symbol);
  const { funnel, loading, mode } = useFtsFunnel(preset);
  const data = funnel.stages[stage];
  const info = INFO[stage];
  const stats = data.summary;

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

      <section className="rounded-3xl border border-border-c bg-bg-card/70 p-3 sm:p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-black text-text-primary">فهرست کامل این مرحله</h2>
          <span className="text-3xs text-text-muted">روی هر کارت = بازکردن جزئیات همان نماد</span>
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {data.entries.map((candidate) => <CandidateCard key={candidate.symbol} stage={stage} candidate={candidate} />)}
        </div>
      </section>

      <div className="flex items-center justify-between gap-2 text-2xs">
        <Link to={funnelStagePath(FUNNEL_STAGES[Math.max(0, FUNNEL_STAGES.findIndex((s) => s.key === stage) - 1)]?.key || 'tape', preset, selected || null)} className="text-text-muted hover:text-accent-blue">← مرحله قبل</Link>
        <Link to={funnelStagePath('handover', preset, selected || null)} className="font-black text-emerald-400 hover:text-emerald-300">نمای کامل قیف →</Link>
      </div>
    </div>
  );
}
