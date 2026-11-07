// features/master/ui/FtsFunnelStages.tsx — پوستۀ «یک workspace» برایِ قیف FTS
//
// چرا این‌طور شد: `/master` اول یک صفحۀ جدا به نام «نقشۀ راه قیف FTS» باز می‌کرد
// و جدولِ واقعی دو کلیک آن‌طرف‌تر بود. گزارشِ مالک (۱۴۰۵-۰۷-۱۶) همین را می‌گفت:
// برایِ فهمیدنِ یک workflow نباید چهار صفحه رد کرد. آن صفحه حذف شده؛ حالا
// همان‌جا سه سیستمِ انتخاب + گام‌ها + جدولِ همان گام باز می‌شود.
//
// این فایل هیچ داوری‌ای حساب نمی‌کند و هیچ شمارشی هم نمی‌سازد: شمارش‌ها و
// «تکنیکال سنجیده‌شده» درِ سرخطِ خودِ جدول (`FtsFunnelAllStages`) می‌مانند —
// یک منبعِ عدد، نه دو تا. تب‌هایِ گام هم از *همان* پاسخِ `/api/funnel` می‌خوانند
// (کلیدِ کوئری یکی است، پس درخواستِ دومی زده نمی‌شود). اینجا فقط سیستمِ انتخاب
// و گام عوض می‌شوند.
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useFunnelPrefsStore, type FunnelPreset } from '../stores/funnelPrefsStore';
import { useActiveFunnelPreset } from '../lib/useActiveFunnelPreset';
import { useFunnelRegistry } from '../api/useFunnelRegistry';
import { useFtsFunnel } from '../api/useFtsFunnel';
import FtsFunnelStageView from './FtsFunnelStageView';
import FtsCustomChainBuilder from './FtsCustomChainBuilder';
import { FUNNEL_STAGES, FtsProcessStepper } from './FtsProcessStepper';
import { FtsFunnelHeader } from './FtsFunnelHeader';
import { FtsFunnelStages as FtsFunnelAllStages } from './FtsFunnelAllStages';
import { stageOrderOf, type FunnelFlow, type FunnelStageKey, type TreePreset } from '../lib/ftsFunnel';
import { FILTER_LABEL, PRESET_MOTIVE, PRESET_ENTRY } from '../lib/ftsFunnel';

export const FUNNEL_SNAP_KEY = 'bors.funnel.snapshot.v1';

const VALID_STAGES: readonly FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

/** سه سیستمِ انتخابیِ مالک — بزرگ، یک‌جا، بی‌صفحۀ جدا.
 *  «ساعت شنی» درِ این سه‌تا نیست: درِ هیچ منبعی فیلترِ تابلویی ندارد و
 *  تعریفش گیتِ تکنیکالِ هفتگی است (پرسشِ Q-1 درِ ممیزیِ قیف)؛ مسیرِ
 *  `?preset=hourglass` دست‌نخورده کار می‌کند، پس توانی حذف نشده است.
 *  «Custom» با رأیِ مالک برگشت (۱۴۰۵-۰۷-۲۰، دورِ دومِ همان رأی): چیپ‌هایِ
 *  نوارِ غربالگری مجموعه را روشن می‌کنند و همین سازنده ترتیبشان را — دو
 *  نمایی از یک زنجیره، نه دو منطقِ داوری. */
export const FUNNEL_MODES: readonly { key: FunnelPreset; label: string; hint: string }[] = [
  { key: 'swing', label: 'نوسان‌گیر', hint: 'الگوی ساعت + جت + حجم مشکوک' },
  { key: 'trend', label: 'روندگیر', hint: 'کف‌روبی + نقطه‌زنی' },
  { key: 'tech_first', label: 'تکنیکال‌محور', hint: 'تکنیکال ← تابلو ← بنیادی ← تحویل' },
  { key: 'custom', label: 'Custom', hint: 'خودت فیلتر را انتخاب و مرتب می‌کنی' },
];

export function FtsFunnelStages({
  preset,
  onPresetChange,
}: {
  preset?: TreePreset;
  onPresetChange?: (p: 'swing' | 'trend' | 'hourglass') => void;
}) {
  const [params, setSearchParams] = useSearchParams();
  const rawStage = params.get('stage') as FunnelStageKey | null;
  // گذرِ نماد از رویِ سطر، گام را درِ خودِ URL می‌نویسد؛ این شاخه فقط برایِ
  // «بازگشت» است: بی‌اش، برگشتن از صفحۀ نماد کاربر را از گام چهارم به گامِ اول
  // می‌انداخت (قراردادِ Task #78).
  const [snapStage] = useState<FunnelStageKey | null>(() => {
    try {
      const raw = sessionStorage.getItem(FUNNEL_SNAP_KEY);
      const st = raw ? (JSON.parse(raw) as { stage?: unknown }).stage : null;
      return typeof st === 'string' && VALID_STAGES.includes(st as FunnelStageKey)
        ? (st as FunnelStageKey)
        : null;
    } catch {
      return null;
    }
  });
  const setPreset = useFunnelPrefsStore((s) => s.setPreset);
  const setMode = useFunnelPrefsStore((s) => s.setMode);
  // presetِ فعال از تنها منبعِ مشترک (URL > انتخابِ کاربر > prop=افق) — همانی که
  // dossier و سایدبار می‌خوانند، پس یک درخواستِ canonical به هر سه سطح می‌رسد.
  const activePreset = useActiveFunnelPreset(preset);
  // شمارندۀ تب‌هایِ گام از *همان* پاسخِ سرور خوانده می‌شود که جدول می‌خواند
  // (TanStack Query با یک کلیدِ یکی، یک درخواست). اینجا هنوز هیچ داوری‌ای حساب
  // نمی‌شود — فقط `counts`ِ خودِ موتور به تب‌ها می‌رسد.
  const { funnel, mode, tape, scan, loading, error, hasData } = useFtsFunnel(activePreset);
  // ترتیبِ گام‌ها را پاسخِ موتور می‌گوید (`flow`). تا پاسخ نرسیده‌ایم از
  // رجیستریِ همان سرور می‌خوانیم که این شخص چه ترتیبی دارد — پس تب‌ها بی‌جهت
  // یک دور «تابلو» را گامِ اول نشان نمی‌دهند و بعد می‌پرند.
  const { presets: regPresets } = useFunnelRegistry();
  const presetFlow: FunnelFlow = regPresets.some(
    (p) => p.preset_id === activePreset && p.flow === 'tech_first') ? 'tech_first' : 'tape_first';
  const flow: FunnelFlow = hasData ? funnel.flow : presetFlow;
  const firstStage = stageOrderOf(flow)[0];
  const stage = rawStage && VALID_STAGES.includes(rawStage) ? rawStage : snapStage ?? firstStage;
  // ورودیِ هر گام ازِ خودِ پاسخ (`stages[k].input`) برداشته می‌شود؛ رابط هیچ
  // زنجیره‌ای ازِ عبوریِ گامِ پیشین نمی‌سازد، وگرنه دو عدد برایِ یک خط داریم.
  const stageInputs = {
    tape: funnel.stages.tape?.input,
    technical: funnel.stages.technical?.input,
    fundamental: funnel.stages.fundamental?.input,
    handover: funnel.stages.handover?.input,
  } as Partial<Record<FunnelStageKey, number>>;
  const stepperState: 'ready' | 'loading' | 'error' =
    error ? 'error' : (!hasData && loading ? 'loading' : 'ready');
  const choose = (p: FunnelPreset) => {
    setPreset(p);
    // «منبعِ واحدِ معتبر» یعنی URL برنده است؛ پس کلیکِ کاربر باید خودِ URL را
    // عوض کند، نه فقط store را. بی‌این، هرگاه صفحه با `?preset=` باز شده باشد
    // (لینکِ StrategyTree/stepper) activePreset رویِ مقدارِ URL قفل می‌ماند و
    // کلیکِ دکمهٔ Preset جدول را هرگز تازه نمی‌کند (باگِ P0). بقیۀ پارامترها
    // (symbol/stage) حفظ می‌شوند.
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('preset', p);
      return next;
    }, { replace: true });
    // «Custom» افقِ سراسری نیست (پلنِ معامله و وزنِ پله به افق نگاه می‌کنند)؛
    // سه افقِ واقعی درِ هر دو جا نوشته می‌شوند.
    if (p !== 'custom' && p !== 'tech_first') onPresetChange?.(p);
  };
  const symbol = params.get('symbol');
  // پیش‌نمایشِ هر شخص (رأیِ مالک ۱۴۰۵-۰۷-۲۰): با هاور یا فوکوس، فهرستِ فیلترها
  // و انگیزه‌اش خوانده شود — نه فقط یک `title` که درِ برنامه خوانده نمی‌شود.
  const [preview, setPreview] = useState<FunnelPreset | null>(null);
  // رأیِ ۱۴۰۵-۰۷-۱۹: «موس رو متن هم بیاد باز بمونه». بسته شدن با یک تأخیرِ کوتاه
  // رخ می‌دهد تا عبورِ موس از فاصلۀِ بینِ دکمه و متنِ پیش‌نمایش آن را نخوابد.
  const closeTimer = useRef<number | null>(null);
  const showPreview = (p: FunnelPreset) => {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    setPreview(p);
  };
  const scheduleClose = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => { setPreview(null); closeTimer.current = null; }, 160);
  };
  useEffect(() => () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
  }, []);

  return (
    <div className="flex w-full flex-col gap-2" data-testid="fts-funnel-workspace">
      {/* سربرگ: کدام استراتژی، چه می‌کند، الان در چه وضعیتی است، عدد از کِی است،
          و نتایج کجاست — پیش ازِ هر چیزِ دیگر و بی‌اسکرول. */}
      <FtsFunnelHeader preset={activePreset} mode={mode} onModeChange={setMode}
                       flow={flow} counts={funnel.counts} asOf={funnel.asOf}
                       tape={tape} computing={loading && !hasData}
                       scan={{ running: scan.running, done: scan.done, queued: scan.queued }} />

      <div
        className="flex flex-wrap items-center gap-1"
        role="group"
        aria-label="سیستم انتخاب"
        data-testid="funnel-mode-modes"
      >
        {FUNNEL_MODES.map((m) => {
          const on = activePreset === m.key;
          return (
            <button
              key={m.key}
              type="button"
              aria-pressed={on}
              title={m.hint}
              data-testid={`funnel-mode-${m.key}`}
              onClick={() => choose(m.key)}
              onMouseEnter={() => showPreview(m.key)}
              onMouseLeave={scheduleClose}
              onFocus={() => showPreview(m.key)}
              onBlur={() => setPreview((p) => (p === m.key ? null : p))}
              className={
                on
                  ? 'rounded-xl border border-accent-blue bg-accent-blue/15 px-4 py-2 text-sm font-black text-accent-blue'
                  : 'rounded-xl border border-border-c bg-bg-card/60 px-4 py-2 text-sm font-bold text-text-muted hover:border-accent-blue/40 hover:text-text-primary'
              }
            >
              {m.label}
            </button>
          );
        })}
      </div>

      {preview ? (
        <div
          className="glass-panel rounded-xl border border-border-c/70 px-3 py-2 text-2xs text-text-secondary"
          data-testid={`funnel-preset-preview-${preview}`}
          role="note"
          onMouseEnter={() => showPreview(preview)}
          onMouseLeave={scheduleClose}
        >
          <div className="font-bold text-text-primary">
            {PRESET_ENTRY[preview as keyof typeof PRESET_ENTRY]?.label ?? preview}
          </div>
          <div className="mt-0.5">
            فیلترها:
            {' '}
            {(PRESET_ENTRY[preview as keyof typeof PRESET_ENTRY]?.filters ?? [])
              .map((f) => FILTER_LABEL[f] ?? f).join(' + ') || 'بی‌فیلترِ تابلو'}
          </div>
          <div className="mt-0.5">
            {PRESET_MOTIVE[preview as keyof typeof PRESET_MOTIVE]}
          </div>
          <div className="mt-0.5 text-text-muted">
            چیپ‌هایِ بالایِ غربالگری همین فهرست را کم و زیاد می‌کنند؛ کلیدِ
            «اشتراک/اجتماع» هم همان‌جاست. درِ Custom همین چیپ‌ها زنجیرۀِ سازنده را روشن می‌کنند.
          </div>
        </div>
      ) : null}

      <FtsProcessStepper active={stage} preset={activePreset} symbol={symbol}
                         counts={funnel.counts} flow={flow} state={stepperState}
                         inputs={stageInputs} universe={funnel.total} />

      {/* Custom همان‌جا ویرایش می‌شود (§۲۹): نه صفحۀ تازه، نه drawerِ سنگین. */}
      {activePreset === 'custom' ? <FtsCustomChainBuilder /> : null}

      {stage === 'handover' ? (
        <div className="flex w-full flex-col gap-1" data-testid="fts-funnel-final-view">
          <FtsFunnelAllStages preset={activePreset} />
        </div>
      ) : (
        <FtsFunnelStageView stage={stage} preset={activePreset} />
      )}
    </div>
  );
}

export { FUNNEL_STAGES };
export default FtsFunnelStages;
