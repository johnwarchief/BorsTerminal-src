// features/master/ui/FtsFunnelStages.tsx — پوستۀ «یک workspace» برایِ قیف FTS
//
// چرا این‌طور شد: `/master` اول یک صفحۀ جدا به نام «نقشۀ راه قیف FTS» باز می‌کرد
// و جدولِ واقعی دو کلیک آن‌طرف‌تر بود. گزارشِ مالک (۱۴۰۵-۰۷-۱۶) همین را می‌گفت:
// برایِ فهمیدنِ یک workflow نباید چهار صفحه رد کرد. آن صفحه حذف شده؛ حالا
// همان‌جا سه سیستمِ انتخاب + گام‌ها + جدولِ همان گام باز می‌شود.
//
// این فایل هیچ داوری‌ای حساب نمی‌کند و هیچ شمارشی هم نمی‌سازد: شمارش‌ها و
// «تکنیکال سنجیده‌شده» درِ سرخطِ خودِ جدول (`FtsFunnelAllStages`) می‌مانند —
// یک منبعِ عدد، نه دو تا. اینجا فقط سیستمِ انتخاب و گام عوض می‌شوند.
import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { useFunnelPrefsStore, type FunnelPreset } from '../stores/funnelPrefsStore';
import { useActiveFunnelPreset } from '../lib/useActiveFunnelPreset';
import FtsFunnelStageView from './FtsFunnelStageView';
import FtsCustomChainBuilder from './FtsCustomChainBuilder';
import { FUNNEL_STAGES, FtsProcessStepper } from './FtsProcessStepper';
import { FtsFunnelStages as FtsFunnelAllStages } from './FtsFunnelAllStages';
import type { FunnelStageKey, TreePreset } from '../lib/ftsFunnel';

export const FUNNEL_SNAP_KEY = 'bors.funnel.snapshot.v1';

const VALID_STAGES: readonly FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

/** سه سیستمِ انتخابیِ مالک — بزرگ، یک‌جا، بی‌صفحۀ جدا.
 *  «ساعت شنی» درِ این سه‌تا نیست: درِ هیچ منبعی فیلترِ تابلویی ندارد و
 *  تعریفش گیتِ تکنیکالِ هفتگی است (پرسشِ Q-1 درِ ممیزیِ قیف)؛ مسیرِ
 *  `?preset=hourglass` دست‌نخورده کار می‌کند، پس توانی حذف نشده است. */
export const FUNNEL_MODES: readonly { key: FunnelPreset; label: string; hint: string }[] = [
  { key: 'swing', label: 'نوسان‌گیر', hint: 'الگوی ساعت + جت + حجم مشکوک' },
  { key: 'trend', label: 'روندگیر', hint: 'کف‌روبی + نقطه‌زنی' },
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
  const stage = rawStage && VALID_STAGES.includes(rawStage) ? rawStage : snapStage ?? 'tape';

  const setPreset = useFunnelPrefsStore((s) => s.setPreset);
  // presetِ فعال از تنها منبعِ مشترک (URL > انتخابِ کاربر > prop=افق) — همانی که
  // dossier و سایدبار می‌خوانند، پس یک درخواستِ canonical به هر سه سطح می‌رسد.
  const activePreset = useActiveFunnelPreset(preset);
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
    if (p !== 'custom') onPresetChange?.(p);
  };
  const symbol = params.get('symbol');

  return (
    <div className="flex w-full flex-col gap-2" data-testid="fts-funnel-workspace">
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

      <FtsProcessStepper active={stage} preset={activePreset} symbol={symbol} />

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
