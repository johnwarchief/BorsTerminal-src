// features/master/ui/FtsFunnelHeader.tsx — سربرگِ «استراتژی FTS»: یک نگاه، چهار جواب
//
// سؤال‌هایی که این سربرگ باید بی‌اسکرول جواب بدهد: کدام استراتژی انتخاب شده؟
// این استراتژی چه می‌کند؟ الان در چه وضعیتی است و عددی که می‌بینم متعلق به کِی
// است؟ نتایج کجاست؟
//
// دو قیدِ تاریخ‌دار:
//  • رأیِ مالک ۱۴۰۵-0۷-۱۶: «جدول مهم‌تر از کارت و تزئینات است» — پس اینجا هیچ
//    کارتِ آماریِ تزئینی نیست؛ فقط عنوان، شرحِ یک‌خطی، و وضعیتِ واقعی.
//  • مأموریتِ ۲۰۲۶-۱۰-۱۸: راهنمایِ شروعِ سریع + «چطور کار می‌کند؟» بازشونده.
//    متنِ تخصصیِ موجود حذف نشده — به درونِ همان بازشونده رفته است.
//
// هیچ عددی اینجا ساخته نمی‌شود: همه از پاسخِ `/api/funnel` (همان شیئی که جدول
// می‌خواند) می‌آید. `asOf` اگر نباشد صریح «گزارش نشده» می‌نویسیم، نه ساعتِ ماشین.
import { useEffect, useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { FILTER_LABEL, MODE_LABEL, MODE_PATH, PRESET_ENTRY, PRESET_MOTIVE,
  TAPE_FRESHNESS_LABEL } from '../lib/ftsFunnel';
import type { FunnelFlow, FunnelStageKey, StageSummary, TapeFreshness } from '../lib/ftsFunnel';
import { funnelStagesFor } from './FtsProcessStepper';

const GUIDE_KEY = 'bors.fts-guide-dismissed.v1';

const STAGE_ONELINE: Record<FunnelStageKey, string> = {
  tape: 'نشانه‌هایِ تابلویِ امروز (چیپ‌هایِ فیلتر)',
  technical: 'گیتِ روندِ هفتگی و شرط‌هایِ انتخابیِ شما',
  fundamental: 'پنج شاخصِ بنیادی از کدال',
  handover: 'فهرستِ نهایی + برنامهٔ پیگیری',
};

function fmtTime(epochSec: number | null | undefined): string {
  if (!epochSec) return 'گزارش نشده';
  try {
    return new Date(epochSec * 1000).toLocaleTimeString('fa-IR',
      { hour: '2-digit', minute: '2-digit' });
  } catch {
    return 'گزارش نشده';
  }
}

export function FtsFunnelHeader({
  preset,
  mode,
  stage,
  flow,
  counts,
  universe,
  asOf,
  tape,
  computing,
  scan,
  techResolved = 0,
  techWanted = 0,
  stageInput,
}: {
  preset: keyof typeof PRESET_ENTRY;
  mode: 'reverse' | 'review';
  stage: FunnelStageKey;
  flow: FunnelFlow;
  counts: Partial<Record<FunnelStageKey, StageSummary>>;
  universe: number;
  asOf: number | null;
  tape: TapeFreshness;
  computing: boolean;
  scan: { running: boolean; done: number; queued: number };
  techResolved?: number;
  techWanted?: number;
  /** `stages[current].input` ازِ خودِ موتور — رابط آن را از گامِ پیشین نمی‌سازد */
  stageInput?: number;
}) {
  const [howOpen, setHowOpen] = useState(false);
  const [guide, setGuide] = useState(false);
  useEffect(() => {
    try {
      setGuide(localStorage.getItem(GUIDE_KEY) !== '1');
    } catch {
      setGuide(true);
    }
  }, []);
  const dismissGuide = () => {
    setGuide(false);
    try {
      localStorage.setItem(GUIDE_KEY, '1');
    } catch { /* بی‌حافظه هم فقط یک‌بارِ همین نشست می‌ماند */ }
  };

  const order = funnelStagesFor(flow);
  const idx = Math.max(0, order.findIndex((s) => s.key === stage));
  const cur = order[idx];
  const curSum = counts[stage];
  const inferred = idx === 0
    ? universe
    : (counts[order[idx - 1].key]?.pass ?? 0);
  const input = typeof stageInput === 'number' ? stageInput : inferred;
  const entry = PRESET_ENTRY[preset];
  const filters = (entry?.filters ?? []).map((f) => FILTER_LABEL[f] ?? f);
  const status = useMemo(() => {
    if (computing || scan.running || scan.queued > 0) {
      return { text: 'در حالِ محاسبه', tone: 'border-accent-yellow/60 bg-accent-yellow/15 text-accent-yellow' };
    }
    return { text: 'آماده', tone: 'border-accent-green/60 bg-accent-green/15 text-accent-green' };
  }, [computing, scan.running, scan.queued]);

  return (
    <header className="flex w-full flex-col gap-1.5" data-testid="fts-funnel-header">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-base font-black text-text-primary">استراتژی FTS</h1>
        <span className="rounded-lg border border-accent-blue/50 bg-accent-blue/10 px-2 py-0.5
                         text-xs font-black text-accent-blue"
              data-testid="fts-active-strategy">
          {entry?.label ?? preset}
        </span>
        <span className="rounded-lg border border-border-c bg-bg-card px-2 py-0.5 text-2xs font-bold text-text-secondary"
              data-testid="fts-active-mode" title={MODE_PATH[mode]}>
          {MODE_LABEL[mode]}
        </span>
        <button
          type="button"
          data-testid="fts-how-it-works-toggle"
          aria-expanded={howOpen}
          onClick={() => setHowOpen((v) => !v)}
          className="ms-auto rounded-lg border border-border-c bg-bg-card px-2.5 py-1 text-2xs font-bold
                     text-text-secondary transition-colors hover:border-accent-blue/60 hover:text-accent-blue"
        >
          {howOpen ? 'بستنِ «چطور کار می‌کند؟»' : 'چطور کار می‌کند؟'}
        </button>
      </div>

      <p className="max-w-[110ch] text-xs leading-5 text-text-secondary" data-testid="fts-strategy-purpose">
        {PRESET_MOTIVE[preset] ?? ''}
      </p>

      {/* یک خطِ وضعیت: چه‌اتفاقی دارد می‌افتد، عدد از کِی است، و کجا ایستاده‌ایم */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs"
           data-testid="fts-status-line">
        <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-black ${status.tone}`}
              data-testid="fts-status">
          {computing || scan.running || scan.queued > 0
            ? <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" /> : null}
          {status.text}
        </span>
        <span className="num text-text-secondary" data-testid="fts-as-of">
          آخرین محاسبه: {fmtTime(asOf)}
        </span>
        <span className="num text-text-secondary" data-testid="fts-tape-freshness"
              title="تازگیِ خوراکِ تابلو — دادهٔ آخرین روز معاملاتی جایِ زنده خوانده نمی‌شود">
          {TAPE_FRESHNESS_LABEL[tape]}
        </span>
        <span className="text-text-secondary" data-testid="fts-current-step">
          گام {toFaDigits(cur.index)} از {toFaDigits(order.length)}: <b className="text-text-primary">{cur.title}</b>
        </span>
        <span className="num text-text-secondary" data-testid="fts-stage-flow">
          ورودیِ این گام: {toFaDigits(input)} · عبوری: {toFaDigits(curSum?.pass ?? 0)}
        </span>
        {scan.queued > 0 ? (
          <span className="num text-accent-yellow" data-testid="fts-scan-progress">
            در صفِ محاسبه: {toFaDigits(scan.queued)} · ساخته‌شده: {toFaDigits(scan.done)}
          </span>
        ) : null}
        {/* پوششِ رأیِ تکنیکال پنهان نمی‌ماند: «سنجیده نشد» با «رد شده» یکی نیست. */}
        {techWanted > 0 ? (
          <span className="num text-text-secondary" data-testid="fts-tech-coverage"
                title="داوریِ تکنیکال برایِ هر نمادی که به این گام رسیده ساخته شده">
            تکنیکال سنجیده‌شده: {toFaDigits(techResolved)} از {toFaDigits(techWanted)}
          </span>
        ) : null}
      </div>

      {howOpen ? (
        <div className="glass-panel rounded-xl border border-border-c/70 px-3 py-2"
             role="region" aria-label="چطور کار می‌کند" data-testid="fts-how-it-works">
          <p className="text-xs leading-5 text-text-primary" data-testid="fts-flow-sentence">
            {MODE_PATH[mode]}
          </p>
          <ol className="mt-1.5 flex flex-col gap-1">
            {order.map((s) => {
              const c = counts[s.key];
              return (
                <li key={s.key} className="flex flex-wrap items-baseline gap-x-2 text-2xs"
                    data-testid={`fts-how-stage-${s.key}`}>
                  <span className="num font-black text-accent-blue">{toFaDigits(s.index)}</span>
                  <b className="text-xs text-text-primary">{s.title}</b>
                  <span className="text-text-secondary">{STAGE_ONELINE[s.key]}</span>
                  <span className="num text-text-muted">
                    {c ? `→ ${toFaDigits(c.pass)} عبور · ${toFaDigits(c.reject)} رد · ${toFaDigits(c.pending)} سنجیده‌نشده` : '→ بی‌عدد'}
                  </span>
                </li>
              );
            })}
          </ol>
          <p className="mt-1.5 text-2xs leading-5 text-text-secondary" data-testid="fts-how-filters">
            فیلترهایِ این استراتژی: {filters.length ? filters.join(' + ') : 'بی‌فیلترِ تابلو'} —
            چیپ‌هایِ «فیلترها» همین فهرست را کم و زیاد می‌کنند و کلیدِ «اشتراک/اجتماع» تعیین می‌کند همه باید باشند یا یکی کافی است.
            نتیجهٔ هر گام درِ جدولِ پایینِ همین صفحه است؛ با کلیکِ هر سطر، جزئیاتِ همان نماد باز می‌شود.
          </p>
        </div>
      ) : null}

      {guide ? (
        <div className="rounded-xl border border-accent-blue/40 bg-accent-blue/5 px-3 py-2"
             role="note" aria-label="شروعِ سریع" data-testid="fts-quick-guide">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-black text-text-primary">شروعِ سریع — سه قدم</p>
              <ol className="mt-1 flex flex-col gap-0.5 text-2xs leading-5 text-text-secondary">
                <li>۱. یکِ استراتژی ازِ بالایِ همین صفحه انتخاب کنید (نوسان‌گیر، روندگیر، تکنیکال‌محور، یا Custom).</li>
                <li>۲. ازِ چهار گام، گامی را باز کنید که می‌خواهید ببینید چه چیزی رد یا قبول شد؛ «فیلترها» را همان‌جا کم و زیاد کنید.</li>
                <li>۳. درِ «نتایجِ گامِ جاری» رویِ یکِ نماد کلیک کنید تا دلیلِ عبور/رد و برنامهٔ معاملاتی‌اش باز شود.</li>
              </ol>
            </div>
            <button type="button" onClick={dismissGuide} data-testid="fts-guide-close"
                    className="shrink-0 rounded-lg border border-border-c bg-bg-card px-2 py-1 text-2xs
                               font-bold text-text-secondary hover:border-accent-blue/60 hover:text-text-primary">
              متوجه شدم
            </button>
          </div>
        </div>
      ) : (
        <button type="button" onClick={() => setGuide(true)} data-testid="fts-guide-open"
                className="self-start text-2xs font-bold text-text-muted underline hover:text-accent-blue">
          راهنمایِ شروعِ سریع
        </button>
      )}
    </header>
  );
}

export default FtsFunnelHeader;
