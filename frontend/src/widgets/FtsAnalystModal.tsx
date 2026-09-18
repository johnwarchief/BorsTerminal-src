// widgets/FtsAnalystModal.tsx -- مودال گزارش تحلیلی و مشاور تشریحی FTS
import { useEffect, useId } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import {
  type PipelineEvaluation,
  type StrategyHorizon,
  HORIZON_LABELS,
} from '@features/master/lib/ftsPipelineEvaluator';

export function FtsAnalystModal({
  open,
  onClose,
  evaluation,
  onHorizonChange,
}: {
  open: boolean;
  onClose: () => void;
  evaluation: PipelineEvaluation;
  onHorizonChange: (h: StrategyHorizon) => void;
}) {
  const navigate = useNavigate();
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const { symbol, horizon, steps, overallStatus, overallHeadline, tradePlan, narrative } = evaluation;

  const statusColors = {
    pass: 'border-accent-green/40 bg-accent-green/10 text-accent-green',
    fail: 'border-accent-red/40 bg-accent-red/10 text-accent-red',
    wait: 'border-accent-yellow/40 bg-accent-yellow/10 text-accent-yellow',
  };

  const statusIcons = {
    pass: '✓',
    fail: '✗',
    wait: '⏳',
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-panel relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border-c bg-bg-primary shadow-2xl"
        data-testid="fts-analyst-modal"
      >
        {/* سربرگ مودال */}
        <div className="flex items-center justify-between border-b border-border-c/70 px-5 py-3.5 bg-bg-card/40">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-blue/20 text-sm font-black text-accent-blue">
              FTS
            </div>
            <div>
              <h2 id={titleId} className="text-sm font-black text-text-primary flex items-center gap-2">
                مشاور تحلیلی و گزارش تشریحی نماد {symbol}
                <span className={`rounded-full border px-2 py-0.5 text-2xs font-bold ${statusColors[overallStatus]}`}>
                  {overallHeadline}
                </span>
              </h2>
              <span className="text-2xs text-text-muted">
                کالبدشکافی منطبق با متدولوژی سند رسمی FTS Specification v2.1
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-border-c text-text-muted hover:border-accent-red hover:text-accent-red transition-colors"
          >
            ✕
          </button>
        </div>

        {/* محتوای اسکرول‌پذیر */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* ۱. سوییچ افق استراتژی (نوسانی / روندی / ساعت شنی) */}
          <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3.5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-text-secondary">افق و استراتژی معامله:</span>
              <span className="text-2xs text-accent-blue font-semibold">
                پیشنهاد سیستم: {HORIZON_LABELS[evaluation.recommendedHorizon].badge}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {(Object.keys(HORIZON_LABELS) as StrategyHorizon[]).map((h) => {
                const isCurrent = horizon === h;
                const info = HORIZON_LABELS[h];
                return (
                  <button
                    key={h}
                    type="button"
                    onClick={() => onHorizonChange(h)}
                    className={`flex flex-col items-start gap-1 rounded-xl border p-2.5 text-start transition-all ${
                      isCurrent
                        ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)]'
                        : 'border-border-c/70 bg-bg-primary hover:border-border-accent'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className={`text-xs font-black ${isCurrent ? 'text-accent-blue' : 'text-text-primary'}`}>
                        {info.title}
                      </span>
                      {evaluation.recommendedHorizon === h && (
                        <span className="text-3xs rounded bg-accent-green/20 px-1 text-accent-green">
                          پیشنهادی
                        </span>
                      )}
                    </div>
                    <span className="text-2xs text-text-muted leading-relaxed">
                      {info.desc}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ۱.۵. باکس ممیزی شروط و دلایل توقف (Explainable Decision Audit) */}
          <div className={`rounded-xl border p-3.5 ${
            overallStatus === 'fail'
              ? 'border-accent-red/50 bg-accent-red/5'
              : overallStatus === 'pass'
                ? 'border-accent-green/50 bg-accent-green/5'
                : 'border-accent-yellow/50 bg-accent-yellow/5'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-black text-text-primary flex items-center gap-1.5">
                <span>⚖</span>
                <span>دلایل توقف و ممیزی شروط (Explainable Decision Audit)</span>
              </span>
              <span className={`rounded-full border px-2 py-0.5 text-2xs font-bold ${statusColors[overallStatus]}`}>
                {overallStatus === 'fail' ? 'ورود مسدود (توقف در فیلترها)' : overallStatus === 'pass' ? 'ورود مجاز (فیلترها سبز)' : 'در انتظار تریگر'}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-2xs">
              <div className="rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-2.5">
                <span className="font-bold text-text-secondary block mb-1">۱. چرا ورود مجاز یا متوقف است؟</span>
                <p className="text-text-primary leading-relaxed">{narrative.why}</p>
              </div>
              <div className="rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-2.5">
                <span className="font-bold text-text-secondary block mb-1">۲. سد پیش‌رو چیست؟</span>
                {steps.filter(s => s.status !== 'pass').length === 0 ? (
                  <p className="text-accent-green font-bold leading-relaxed">تمامی فیلترهای ۴گانه تایید شده‌اند و سدی در مسیر قیمت نیست.</p>
                ) : (
                  <ul className="space-y-1">
                    {steps.filter(s => s.status !== 'pass').map(s => (
                      <li key={s.id} className="text-text-primary">
                        <strong className="text-accent-red">● {s.title}:</strong> {s.headline}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-2.5">
                <span className="font-bold text-text-secondary block mb-1">۳. مقاومت استاتیک و حد ضرر</span>
                <div className="space-y-1 text-text-primary">
                  {tradePlan.targetPrice && tradePlan.entryPrice ? (
                    <div>
                      فاصله تا مقاومت:{' '}
                      <strong className="text-accent-blue font-bold inline-flex items-center gap-1">
                        <span className="num">{toFaDigits(Math.max(0, tradePlan.targetPrice - tradePlan.entryPrice))}</span>
                        <span>ریال</span>
                      </strong>{' '}
                      ({toFaDigits((((tradePlan.targetPrice - tradePlan.entryPrice) / tradePlan.entryPrice) * 100).toFixed(1))}٪)
                    </div>
                  ) : (
                    <div>تارگت: {tradePlan.targetPrice ? `${toFaDigits(tradePlan.targetPrice)} ریال` : 'سقف استاتیک'}</div>
                  )}
                  {tradePlan.stopLossPrice && (
                    <div className="text-text-muted">
                      حد ضرر:{' '}
                      <strong className="text-accent-red font-bold inline-flex items-center gap-1">
                        <span className="num">{toFaDigits(tradePlan.stopLossPrice)}</span>
                        <span>ریال</span>
                      </strong>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* ۲. کارت‌های پاسخ به ۴ سوال اساسی تحلیلگر */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {/* سوال ۱: چرا بخریم یا نخریم؟ */}
            <div className="rounded-xl border border-border-c/70 bg-bg-card/30 p-3.5 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-md bg-accent-blue/20 text-xs font-black text-accent-blue">
                    ۱
                  </span>
                  <h3 className="text-xs font-black text-text-primary">
                    چرا بخریم یا نخریم؟ (حکم قطعی)
                  </h3>
                </div>
                <p className="text-xs leading-relaxed text-text-secondary">
                  {narrative.why}
                </p>
              </div>
            </div>

            {/* سوال ۲: تکنیکال و تابلو */}
            <div className="rounded-xl border border-border-c/70 bg-bg-card/30 p-3.5 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-md bg-neon-cyan/20 text-xs font-black text-neon-cyan">
                    ۲
                  </span>
                  <h3 className="text-xs font-black text-text-primary">
                    ستاپ تکنیکال و رفتار تابلوی سهم
                  </h3>
                </div>
                <p className="text-xs leading-relaxed text-text-secondary">
                  {narrative.technical}
                </p>
              </div>
            </div>

            {/* سوال ۳: وضعیت ۵ شاخص کدال */}
            <div className="rounded-xl border border-border-c/70 bg-bg-card/30 p-3.5 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-md bg-accent-green/20 text-xs font-black text-accent-green">
                    ۳
                  </span>
                  <h3 className="text-xs font-black text-text-primary">
                    عملکرد کدال و سلامت ۵ شاخص
                  </h3>
                </div>
                <p className="text-xs leading-relaxed text-text-secondary">
                  {narrative.fundamental}
                </p>
              </div>
            </div>

            {/* سوال ۴: پلن معامله و حد ضرر */}
            <div className="rounded-xl border border-border-c/70 bg-bg-card/30 p-3.5 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-md bg-accent-yellow/20 text-xs font-black text-accent-yellow">
                    ۴
                  </span>
                  <h3 className="text-xs font-black text-text-primary">
                    برنامه معامله و حد ضرر دقیق
                  </h3>
                </div>
                <p className="text-xs leading-relaxed text-text-secondary">
                  {narrative.tradePlan}
                </p>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border-c/50 pt-2 text-2xs">
                <span className="font-bold text-accent-red">
                  {tradePlan.stopLossPrice
                    ? `حد ضرر قطعی: ${toFaDigits(tradePlan.stopLossPrice)} ریال (-۵٪)`
                    : tradePlan.stopLossBasis}
                </span>
                <span className="text-text-muted">·</span>
                <span className="font-bold text-accent-green">
                  تارگت اول: {tradePlan.targetPrice ? `${toFaDigits(tradePlan.targetPrice)} ریال` : 'سقف استاتیک'}
                </span>
              </div>
            </div>
          </div>

          {/* ۳. گام‌های ۴‌گانه زنجیره FTS همراه با لینک ناوبری مستقیم */}
          <div>
            <h3 className="text-xs font-bold text-text-secondary mb-2.5">
              وضعیت گام‌های چهارگانه FTS:
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              {steps.map((s) => (
                <div
                  key={s.id}
                  className={`rounded-xl border p-3 flex flex-col justify-between ${
                    s.status === 'pass'
                      ? 'border-accent-green/30 bg-accent-green/5'
                      : s.status === 'fail'
                        ? 'border-accent-red/30 bg-accent-red/5'
                        : 'border-border-c/70 bg-bg-card/30'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-2xs font-bold text-text-muted">
                        گام {toFaDigits(s.step)}: {s.title}
                      </span>
                      <span
                        className={`flex h-4 w-4 items-center justify-center rounded-full text-2xs font-black ${
                          s.status === 'pass'
                            ? 'bg-accent-green text-black'
                            : s.status === 'fail'
                              ? 'bg-accent-red text-white'
                              : 'bg-accent-yellow/20 text-accent-yellow'
                        }`}
                      >
                        {statusIcons[s.status]}
                      </span>
                    </div>
                    <div className="text-xs font-bold text-text-primary mb-1">
                      {s.headline}
                    </div>
                    <p className="text-2xs text-text-muted line-clamp-2 leading-relaxed">
                      {s.detail}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      navigate(s.targetRoute);
                    }}
                    className="mt-3 inline-flex items-center justify-center rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-2xs font-semibold text-text-primary hover:border-accent-blue hover:text-accent-blue transition-colors"
                  >
                    مشاهده در {s.title} ↗
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* پاورقی مودال */}
        <div className="flex items-center justify-between border-t border-border-c/70 px-5 py-3 bg-bg-card/40 text-2xs text-text-muted">
          <span>قاعده FTS: بدون تایید هم‌زمان تابلو، تکنیکال و بنیاد هیچ موقعیتی وارد نشوید.</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-accent-blue px-3 py-1 font-bold text-black hover:bg-accent-blue/90 transition-colors"
          >
            متوجه شدم
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
