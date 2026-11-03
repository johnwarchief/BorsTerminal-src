// features/portfolio/components/sarkhati/SarkhatiProTools.tsx — ردیفِ ابزارهایِ
// حرفه‌ای، با لایۀ ارائهٔ jev-ui
//
// مرزِ این مؤلفه عمداً باریک است: **فقط** ردیفِ ثانویِ «ابزارهایِ حرفه‌ای» و یک
// خطِ راهنمایِ *اضافه*. فرمِ سفارش، اعتبارسنجی، مجوزِ ارسال، انتخابِ حساب و هیچ
// چیز درِ `ExecutionPanel` به این فایل راه ندارد؛ حتی متنِ راهنما هم ازِ parent
// (از فیلدهایِ خودِ پاسخِ سرویس) می‌آید و این‌جا فقط دو چیز تصمیم گرفته می‌شود:
// «دیدنی است یا نه» و «چقدر پر باشد».
//
// سه قابلیتِ jev-ui که واقعاً اینجا کار می‌کنند:
//  • `Rank` (mode=compete) — آرایشِ سه پنلِ ثانویه. `take` ندارد، پس هیچ‌کدام
//    حذف نمی‌شود؛ و قاعدۀ بی‌شرطِ `jevRuleAnswer` همان بردارِ ترتیبِ امروز را
//    می‌دهد، پس «بدونِ وضعیتِ خاص» یعنی «هیچ جابه‌جایی» — آزمونِ
//    `jev-sarkhati.spec.tsx` هر دو حالت را می‌سنجد.
//  • `Gate` — خطِ راهنما را *اضافه* می‌کند؛ درِ pending و error بسته است، پس
//    چشمک نمی‌زند و چیزی را از primary نمی‌گیرد.
//  • `useScore` — فقط بلندیِ همان راهنما را می‌راند (props، نه منطق).
//
// fallback قطعی و آفلاین: provider همین‌جا `resolveJevRules` را می‌گیرد؛ هیچ
// شبکه، هیچ کلید، هیچ Next.js. اگر قاعده پاسخِ ناشناس بدهد `Rank` ترتیبِ خام را
// نگه می‌دارد و `Gate` بسته می‌ماند — هر دو درِ `jev-ui-compat.spec.tsx` سنجیده
// شده‌اند، نه فقط ادعا.
import { useMemo } from 'react';
import { Gate, JevProvider, Rank, useJevState, useScore, useTimeOnScreen } from 'jev-ui';
import type { ResolveFn } from 'jev-ui';
import { HELP_LEVELS, PRO_IDS, resolveJevRules, type JevAppState, type ProId }
  from '../../lib/jevSarkhati';
import { chipClass } from './parts';

export type ProItem = { id: ProId; label: string; testId: string };

type Props = {
  items: ProItem[];
  /** فقط پرچم‌هایِ غیرحساس؛ سازنده‌اش `appStateForJev` درِ lib/jevSarkhati است */
  app: JevAppState;
  /** پنلِ فعلی، برایِ data-panel و برایِ تشخیصِ کلیکِ تکراری */
  panel: string;
  /** مقصدِ پیشنهادیِ «قدمِ شما» — همان چیزی که دکمهٔ «برو به …» باز می‌کند */
  suggestedGo: string;
  /** سه بریدهٔ متن، همگی از فیلدهایِ خودِ پاسخِ سرویس درِ parent ساخته شده‌اند */
  hint: { short: string; extra: string; detail: string };
  onSelect: (id: ProId) => void;
  /** خاموش‌کردنِ تایمرِ dwell برایِ آزمونِ قطعی؛ درِ محصول روشن است */
  trackDwell?: boolean;
  /** تزریقِ ترانسپورت درِ آزمون؛ درِ محصول همان resolveJevRules است */
  resolve?: ResolveFn;
};

function ProRow({ items, panel, suggestedGo, onSelect, trackDwell }: {
  items: ProItem[]; panel: string; suggestedGo: string;
  onSelect: (id: ProId) => void; trackDwell: boolean;
}) {
  const { track } = useJevState();
  useTimeOnScreen(trackDwell);
  return (
    <>
      <span className="text-3xs font-bold text-text-muted" data-testid="sarkhati-pro-label">
        ابزارهایِ حرفه‌ای:
      </span>
      <div className="flex flex-wrap items-center gap-1" role="tablist"
        aria-label="ابزارهایِ حرفه‌ای" data-testid="sarkhati-pro-sections" data-panel={panel}>
        <Rank
          id="sarkhati_pro_rank"
          items={items}
          ask="با توجه به وضعیتِ فعلیِ سرویس، کدام ابزارِ حرفه‌ای الان مرتبط‌تر است؟"
          idOf={(i) => i.id}
          labelOf={(i) => i.label}
        >
          {(ranked) => ranked.map(({ item }) => (
            <button key={item.id} type="button" role="tab" aria-selected={panel === item.id}
              data-testid={item.testId} data-ranked-id={item.id}
              data-suggested={suggestedGo === item.id ? 'true' : 'false'}
              className={chipClass(panel === item.id, suggestedGo === item.id)}
              onClick={() => { track(`pro:${item.id}`); onSelect(item.id); }}>
              {item.label}
            </button>
          ))}
        </Rank>
      </div>
    </>
  );
}

/** راهنما: دیدنی‌بودن از `Gate`، بلندی از `useScore`؛ متن از parent. */
function HintLine({ hint }: { hint: { short: string; extra: string; detail: string } }) {
  const { score } = useScore({
    id: 'sarkhati_hint_level',
    ask: 'کاربر در همین خط به چقدر توضیح نیاز دارد؟',
    levels: [...HELP_LEVELS],
  });
  const level = Math.max(0, Math.min(2, Math.round(score)));
  const text = [hint.short, level >= 1 ? hint.extra : '', level >= 2 ? hint.detail : '']
    .filter(Boolean).join(' · ');
  return (
    <span className="min-w-0 flex-1 truncate text-3xs text-accent-yellow"
      data-testid="sarkhati-hint" data-level={String(level)} title={text}>
      راهنما: {text}
    </span>
  );
}

export function SarkhatiProTools(props: Props) {
  const { app, trackDwell = true } = props;
  const state = useMemo(() => ({ app }), [app]);
  return (
    <JevProvider resolve={props.resolve ?? resolveJevRules} state={state} track={{ cap: 4 }}>
      <ProRow items={props.items} panel={props.panel} suggestedGo={props.suggestedGo}
        onSelect={props.onSelect} trackDwell={trackDwell} />
      <Gate id="sarkhati_hint"
        ask="آیا کاربر الان در همین مسیر گیر کرده و به یک خط راهنما نیاز دارد؟"
        otherwise={null}>
        <HintLine hint={props.hint} />
      </Gate>
    </JevProvider>
  );
}

/** ترتیبِ پیش‌فرضِ همان سه id؛ برایِ آزمونِ «بدونِ داوری هیچ چیز جابه‌جا نمی‌شود». */
export const DEFAULT_PRO_IDS: readonly ProId[] = PRO_IDS;
