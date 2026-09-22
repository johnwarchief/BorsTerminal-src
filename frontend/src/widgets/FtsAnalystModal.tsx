// widgets/FtsAnalystModal.tsx -- مودال گزارش تحلیلی و مشاور تشریحی FTS
// بر پایه جزوه دوره نوسان‌گیری و سرمایه‌گذاری به سبک FTS (عرفان نصرتی) و چارت‌های درختی
import { useEffect, useId, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import {
  type PipelineEvaluation,
  type StrategyHorizon,
  HORIZON_LABELS,
} from '@features/master/lib/ftsPipelineEvaluator';

type AnalystTab = 'narrative' | 'scenarios' | 'liquidity' | 'pipeline';

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
  const [activeTab, setActiveTab] = useState<AnalystTab>('narrative');

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
      className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/80 p-3 sm:p-4 backdrop-blur-md animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-panel relative flex max-h-[94vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border-c bg-bg-primary shadow-2xl"
        data-testid="fts-analyst-modal"
      >
        {/* ۱. سربرگ مودال */}
        <div className="flex items-center justify-between border-b border-border-c/70 px-5 py-3.5 bg-bg-card/50">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-blue/20 text-sm font-black text-accent-blue shadow-[0_0_10px_rgba(56,189,248,0.2)]">
              FTS
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 id={titleId} className="text-sm font-black text-text-primary">
                  مشاور تحلیلی و گزارش تشریحی نماد {symbol}
                </h2>
                <span className={`rounded-full border px-2 py-0.5 text-2xs font-bold ${statusColors[overallStatus]}`}>
                  {overallHeadline}
                </span>
              </div>
              <span className="text-2xs text-text-muted">
                مطابق با روش آموزشی دوره نوسان‌گیری و سرمایه‌گذاری به سبک FTS
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

        {/* ۲. نوار انتخاب افق معامله (نوسان‌گیر / روندگیر / ساعت شنی) */}
        <div className="border-b border-border-c/60 bg-bg-card/25 px-5 py-2.5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 text-2xs text-text-secondary">
              <span className="font-bold">سبک و افق معامله:</span>
              <span className="text-accent-blue font-semibold">
                پیشنهاد سیستم: {HORIZON_LABELS[evaluation.recommendedHorizon].badge}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {(Object.keys(HORIZON_LABELS) as StrategyHorizon[]).map((h) => {
                const isCurrent = horizon === h;
                const info = HORIZON_LABELS[h];
                return (
                  <button
                    key={h}
                    type="button"
                    onClick={() => onHorizonChange(h)}
                    className={`flex items-center justify-center gap-1 rounded-lg border px-2 py-1 text-2xs font-bold transition-all ${
                      isCurrent
                        ? 'border-accent-blue bg-accent-blue/20 text-accent-blue shadow-[0_0_8px_rgba(56,189,248,0.2)]'
                        : 'border-border-c/60 bg-bg-primary text-text-muted hover:border-border-accent hover:text-text-primary'
                    }`}
                  >
                    <span>{info.title.split(' ')[1] || info.badge}</span>
                    {evaluation.recommendedHorizon === h && (
                      <span className="h-1.5 w-1.5 rounded-full bg-accent-green" title="پیشنهادی" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ۳. زبانه‌های ناوبری داخلی مودال */}
        <div className="flex items-center gap-1 border-b border-border-c/60 bg-bg-card/40 px-5 pt-2">
          <button
            type="button"
            onClick={() => setActiveTab('narrative')}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'narrative'
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            <span>📋</span>
            <span>گزارش مشاور FTS</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('scenarios')}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'scenarios'
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            <span>🎯</span>
            <span>سناریوهای ۳‌گانه بازار</span>
            <span className="rounded bg-accent-blue/15 px-1 py-0.2 text-3xs font-black text-accent-blue">۳ حالت</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('liquidity')}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'liquidity'
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            <span>📊</span>
            <span>تابلو و نقدشوندگی</span>
            {narrative.liquidity.clockPattern && (
              <span className="rounded bg-accent-green/20 px-1 py-0.2 text-3xs font-black text-accent-green">ساعت فعال</span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('pipeline')}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'pipeline'
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            <span>⚖</span>
            <span>گام‌های ۴‌گانه FTS</span>
          </button>
        </div>

        {/* ۴. محتوای تب‌ها */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* ═══════════ تب ۱: گزارش مشاور FTS ═══════════ */}
          {activeTab === 'narrative' && (
            <div className="space-y-4 animate-fade-in">
              {/* باکس شرط شفاف ورود یا رفع وتو */}
              <div
                className={`rounded-xl border p-3.5 ${
                  overallStatus === 'pass'
                    ? 'border-accent-green/50 bg-accent-green/10'
                    : overallStatus === 'fail'
                      ? 'border-accent-red/50 bg-accent-red/10'
                      : 'border-accent-yellow/50 bg-accent-yellow/10'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-black flex items-center gap-1.5 text-text-primary">
                    <span>🎯</span>
                    <span>شرط فعال‌سازی ورود و اقدام عملیاتی FTS:</span>
                  </span>
                  <span className={`rounded-full border px-2 py-0.5 text-2xs font-bold ${statusColors[overallStatus]}`}>
                    {overallStatus === 'pass' ? 'آماده ورود' : overallStatus === 'fail' ? 'ورود مسدود' : 'در انتظار تریگر'}
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-text-primary font-medium">
                  {narrative.readinessCondition}
                </p>
              </div>

              {/* ۴ کارت پاسخ به سوالات اساسی تحلیلگر */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {/* سوال ۱: چرا بخریم یا نخریم؟ */}
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
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
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
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

                {/* سوال ۳: عملکرد ۵ شاخص کدال */}
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
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

                {/* سوال ۴: برنامه ورود و حد ضرر دقیق */}
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
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
                      هدف اول: {tradePlan.targetPrice ? `${toFaDigits(tradePlan.targetPrice)} ریال` : 'مقاومت استاتیک'}
                    </span>
                  </div>
                </div>
              </div>

              {/* باکس توصیه اختصاصی نوسان‌گیر و روندگیر */}
              <div className="rounded-xl border border-border-c/70 bg-bg-card/30 p-3.5">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-sm">💡</span>
                  <span className="text-xs font-black text-text-primary">
                    توصیه مدیریت سرمایه و رفتار معامله‌گر بر اساس جزوه FTS:
                  </span>
                </div>
                <p className="text-2xs leading-relaxed text-text-secondary">
                  {narrative.traderAdvice}
                </p>
              </div>
            </div>
          )}

          {/* ═══════════ تب ۲: سناریوهای ۳‌گانه معامله ═══════════ */}
          {activeTab === 'scenarios' && (
            <div className="space-y-3.5 animate-fade-in">
              <div className="rounded-lg border border-border-c/60 bg-bg-card/30 p-2.5 text-2xs text-text-muted">
                طبق آموزه‌های دوره FTS، بازار ماهیت احتمالی دارد. همیشه پیش از ورود، هر ۳ سناریوی صعودی، رنج و حد ابطال را بسنجید:
              </div>

              {/* ۱. سناریوی صعودی */}
              <div className="rounded-xl border border-accent-green/40 bg-accent-green/5 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-green/20 text-xs font-black text-accent-green">
                      ▲
                    </span>
                    <h4 className="text-xs font-black text-accent-green">
                      {narrative.scenarios.bullish.title}
                    </h4>
                  </div>
                  <span className="rounded-full bg-accent-green/20 px-2.5 py-0.5 text-2xs font-black text-accent-green">
                    {toFaDigits(narrative.scenarios.bullish.probabilityPct)}٪ شانس وقوع
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 pt-1 text-2xs">
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">شرط وقوع (تریگر):</span>
                    <p className="text-text-primary leading-relaxed">{narrative.scenarios.bullish.trigger}</p>
                  </div>
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">هدف و قانون ذخیره سود ۵۰٪:</span>
                    <p className="text-text-primary leading-relaxed">{narrative.scenarios.bullish.targetOrStop}</p>
                  </div>
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">دستور اقدام FTS:</span>
                    <p className="text-accent-green font-bold leading-relaxed">{narrative.scenarios.bullish.action}</p>
                  </div>
                </div>
              </div>

              {/* ۲. سناریوی رنج و خنثی */}
              <div className="rounded-xl border border-accent-blue/40 bg-accent-blue/5 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-blue/20 text-xs font-black text-accent-blue">
                      ■
                    </span>
                    <h4 className="text-xs font-black text-accent-blue">
                      {narrative.scenarios.neutral.title}
                    </h4>
                  </div>
                  <span className="rounded-full bg-accent-blue/20 px-2.5 py-0.5 text-2xs font-black text-accent-blue">
                    {toFaDigits(narrative.scenarios.neutral.probabilityPct)}٪ شانس وقوع
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 pt-1 text-2xs">
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">رفتار در محدوده باکس:</span>
                    <p className="text-text-primary leading-relaxed">{narrative.scenarios.neutral.trigger}</p>
                  </div>
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">ترازهای حمایت و مقاومت:</span>
                    <p className="text-text-primary leading-relaxed">{narrative.scenarios.neutral.targetOrStop}</p>
                  </div>
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">دستور برخورد FTS:</span>
                    <p className="text-accent-blue font-bold leading-relaxed">{narrative.scenarios.neutral.action}</p>
                  </div>
                </div>
              </div>

              {/* ۳. سناریوی نزولی و حد ابطال */}
              <div className="rounded-xl border border-accent-red/40 bg-accent-red/5 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-red/20 text-xs font-black text-accent-red">
                      ▼
                    </span>
                    <h4 className="text-xs font-black text-accent-red">
                      {narrative.scenarios.bearish.title}
                    </h4>
                  </div>
                  <span className="rounded-full bg-accent-red/20 px-2.5 py-0.5 text-2xs font-black text-accent-red">
                    {toFaDigits(narrative.scenarios.bearish.probabilityPct)}٪ شانس وقوع
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 pt-1 text-2xs">
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">شرط ابطال ستاپ:</span>
                    <p className="text-text-primary leading-relaxed">{narrative.scenarios.bearish.trigger}</p>
                  </div>
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">حد ضرر نوسان‌گیر / روندگیر:</span>
                    <p className="text-accent-red font-bold leading-relaxed">{narrative.scenarios.bearish.targetOrStop}</p>
                  </div>
                  <div className="rounded-lg border border-border-c/50 bg-bg-primary/70 p-2.5">
                    <span className="font-bold text-text-secondary block mb-1">دستور خروج اضطراری FTS:</span>
                    <p className="text-text-primary leading-relaxed">{narrative.scenarios.bearish.action}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════ تب ۳: تابلو و نقدشوندگی ═══════════ */}
          {activeTab === 'liquidity' && (
            <div className="space-y-4 animate-fade-in">
              {/* وضعیت کلی نقدشوندگی و صفوف */}
              <div
                className={`rounded-xl border p-4 ${
                  narrative.liquidity.status === 'safe'
                    ? 'border-accent-green/40 bg-accent-green/5'
                    : narrative.liquidity.status === 'warning'
                      ? 'border-accent-yellow/40 bg-accent-yellow/5'
                      : 'border-accent-red/40 bg-accent-red/5'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-black text-text-primary flex items-center gap-1.5">
                    <span>⚡</span>
                    <span>{narrative.liquidity.headline}</span>
                  </span>
                  <span className="text-2xs font-bold text-text-muted">
                    {narrative.liquidity.queueNote}
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-text-secondary">
                  {narrative.liquidity.detail}
                </p>
                <div className="mt-3 rounded-lg border border-border-c/60 bg-bg-primary/80 p-2.5 text-2xs">
                  <span className="font-bold text-accent-blue">راهنمای معامله در صف: </span>
                  <span className="text-text-primary">{narrative.liquidity.actionAdvice}</span>
                </div>
              </div>

              {/* ۴ کارت سنجش تابلویی FTS */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {/* کارت ۱: الگوی ساعت */}
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3 flex flex-col justify-between">
                  <div>
                    <span className="text-2xs text-text-muted block mb-1">الگوی ساعت FTS</span>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className={`text-xs font-black ${narrative.liquidity.clockPattern ? 'text-accent-green' : 'text-text-muted'}`}>
                        {narrative.liquidity.clockPattern ? '✓ فعال (آخرین > پایانی)' : '— غیرفعال'}
                      </span>
                    </div>
                  </div>
                  <span className="text-3xs text-text-muted">
                    {narrative.liquidity.clockDiffPct != null
                      ? `اختلاف: ${toFaDigits(narrative.liquidity.clockDiffPct.toFixed(1))}٪`
                      : 'اختلاف کمتر از ۱٪'}
                  </span>
                </div>

                {/* کارت ۲: حجم مشکوک */}
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3 flex flex-col justify-between">
                  <div>
                    <span className="text-2xs text-text-muted block mb-1">حجم معاملات ماهانه</span>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className={`text-xs font-black ${narrative.liquidity.volRatio && narrative.liquidity.volRatio >= 3.0 ? 'text-accent-green' : 'text-text-secondary'}`}>
                        {narrative.liquidity.volRatio != null ? `${toFaDigits(narrative.liquidity.volRatio.toFixed(1))} برابر میانگین` : 'در حد نرمال'}
                      </span>
                    </div>
                  </div>
                  <span className="text-3xs text-text-muted">
                    معیار FTS: حداقل ۳ برابر میانگین ۲۱ روزه
                  </span>
                </div>

                {/* کارت ۳: قدرت خریدار */}
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3 flex flex-col justify-between">
                  <div>
                    <span className="text-2xs text-text-muted block mb-1">قدرت سرانه خریدار</span>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-xs font-black text-text-primary">
                        {narrative.liquidity.buyerPower != null
                          ? `${toFaDigits(narrative.liquidity.buyerPower.toFixed(2))} برابری`
                          : 'متعادل'}
                      </span>
                    </div>
                  </div>
                  <span className="text-3xs text-text-muted">
                    برتری کدهای درشت حقیقی
                  </span>
                </div>

                {/* کارت ۴: صف خرید / صف فروش */}
                <div className="rounded-xl border border-border-c/70 bg-bg-card/40 p-3 flex flex-col justify-between">
                  <div>
                    <span className="text-2xs text-text-muted block mb-1">وضعیت صفوف بازار</span>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className={`text-xs font-black ${
                        narrative.liquidity.queueStatus === 'buy_queue'
                          ? 'text-accent-green'
                          : narrative.liquidity.queueStatus === 'sell_queue'
                            ? 'text-accent-red'
                            : 'text-text-primary'
                      }`}>
                        {narrative.liquidity.queueStatus === 'buy_queue'
                          ? 'صف خرید'
                          : narrative.liquidity.queueStatus === 'sell_queue'
                            ? 'صف فروش'
                            : 'معاملات متعادل'}
                      </span>
                    </div>
                  </div>
                  <span className="text-3xs text-text-muted">
                    {narrative.liquidity.queueStatus === 'sell_queue' ? 'بررسی احتمال کف‌روبی' : 'بررسی حجم مبنا'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════ تب ۴: گام‌های ۴‌گانه FTS ═══════════ */}
          {activeTab === 'pipeline' && (
            <div className="space-y-4 animate-fade-in">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {steps.map((s) => (
                  <div
                    key={s.id}
                    className={`rounded-xl border p-3 flex flex-col justify-between ${
                      s.status === 'pass'
                        ? 'border-accent-green/40 bg-accent-green/5'
                        : s.status === 'fail'
                          ? 'border-accent-red/40 bg-accent-red/5'
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
                                ? 'bg-accent-red text-on-accent'
                                : 'bg-accent-yellow/20 text-accent-yellow'
                          }`}
                        >
                          {statusIcons[s.status]}
                        </span>
                      </div>
                      <div className="text-xs font-bold text-text-primary mb-1">
                        {s.headline}
                      </div>
                      <p className="text-2xs text-text-muted leading-relaxed line-clamp-3">
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
                      مشاهده در {s.title.split(' ')[0]} ↗
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ۵. پاورقی مودال */}
        <div className="flex items-center justify-between border-t border-border-c/70 px-5 py-3 bg-bg-card/50 text-2xs text-text-muted">
          <span>قاعده FTS: بدون تایید هم‌زمان تابلو، تکنیکال و بنیاد هیچ موقعیتی وارد نشوید.</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-accent-blue px-3.5 py-1 font-bold text-black hover:bg-accent-blue/90 transition-colors shadow-sm"
          >
            متوجه شدم
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
