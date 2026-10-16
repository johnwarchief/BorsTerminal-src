// features/market/components/WidgetFreshness.tsx -- تازگی **به‌ازایِ ویجت**
//
// چرا این فایل هست (فاز D، بندِ ۱ مأموریت): «وضعیت بازار» یکِ ساعتِ سراسری داشت —
// پنلِ `MarketStatusPanel` که از `/api/live-stats` می‌خواند و برایِ *کلِ صفحه*
// می‌گفت داده چه وقت تازه شده. ولی هشت بخشِ اینِ صفحه از هشت کوئریِ مستقل می‌آیند
// (`useMstatHistogram`, `useMstatTops`, `useMstatOwnership`, `useIndustries`,
// `useMarketPulse`, …) وِ هر کدام پنجرۀِ پاسخِ خودشان را دارند. یکِ برچسبِ سراسری
// یعنی نقشۀِ بازاری که سه دورِ پیش خوانده شده، زیرِ «لحظاتیِ پیش» خوانده شود.
//
// سه قاعده که عمداً رعایت شده:
// ۱) **بی‌اختراعِ آستانه:** اینِ کامپوننت نمی‌داند هرِ ویجت باِ چه ریتمی polling
//    می‌شود، پس «کهنه» را از هیچِ عددِ ثابتی نتیجه نمی‌گیرد. وضعیت فقط از
//    `status`ِ واقعیِ TanStack می‌آید وِ سنِ دریافت عیناً نشان داده می‌شود؛ قضاوتِ
//    «اینِ ۴ دقیقه برایِ اینِ جدول زیاد است» مالِ خودِ ویجت است وِ درِ همینِ فایل
//    نبودنِ آن، درستِ همانِ بی‌داده است.
// ۲) **اتصال ≠ تازگی ≠ عوض‌شدنِ عدد:** اینجا دو تایِ اولِ اینِ سه خوانده می‌شود (سنِ
//    رسیدنِ پاسخ، وِ اگرِ منبع خودش را گزارش کرده باشد ساعتِ خودِ منبع). سنِ
//    *عوض‌شدنِ* داده درِ `MarketStatusPanel` می‌ماند، چون فقط فیدِ تابلو `rev_at`
//    دارد وِ اختراعش برایِ بقیه یعنی عددِ ساختگی (همان قاعدۀ «بی‌داده ≠ صفر»).
// ۳) **بی‌timerِ تازه:** سن درِ همانِ رندرِ کوئری حساب می‌شود؛ هرِ ویجت باِ pollingِ
//    خودش دوباره render می‌شود. تیکِ یک‌ثانیه‌ای برایِ متنی که دقیقه عوض می‌شود،
//    همانِ رندرِ بی‌موردی است که مأموریت رد می‌کند.
import { toFaDigits } from '@shared/lib/fmt';
import { fmtAge } from '@shared/lib/time';

export type WidgetFreshInput = {
  /** `status`ِ خودِ useQuery: 'idle' | 'pending' | 'running' | 'success' | 'error' */
  status: string;
  /** آخرینِ پاسخِ موفق (epoch msِ همینِ کلاینت)؛ 0 یعنی هنوز هیچ پاسخی نرسیده */
  dataUpdatedAt: number;
  /** خطا دیده شد؟ (برایِ جداکردنِ «خطا رویِ دادهٔ قدیم» از «خطایِ بی‌داده») */
  error?: boolean;
  /** ساعتِ خودِ منبع، آن‌طور که درِ پاسخ آمده (مثلِ `asOfText`); null یعنی منبع
   *  اینِ را گزارش نمی‌کند — وِ آنِ باید صریح دیده شود، نه پنهان یا جایگزین. */
  sourceAsOf?: string | null;
  /** تزریقِ زمان برایِ آزمون؛ درِ محصول `Date.now()` */
  now?: number;
};

export type WidgetFreshnessView = {
  state: 'ok' | 'error' | 'pending';
  /** برچسبِ کوتاهِ وضعیت */
  label: string;
  /** سنِ دریافت باِ رقمِ فارسی؛ null یعنی هنوز پاسخی نبوده */
  ageText: string | null;
  /** خطِ ساعتِ منبع، یا صریحِ «نیامد» */
  sourceText: string;
  /** کلاسِ رنگِ لایۀ tone (بی‌رنگِ اختصاصیِ تازه) */
  toneClass: string;
};

function ageOf(ts: number, now: number): string | null {
  if (!ts || !Number.isFinite(ts) || ts > now) return null;
  return toFaDigits(fmtAge(ts, now));
}

/** منطقِ خالص، بی‌React — تاِ آزمونِ واحدِ ممکن باشد وِ کامپوننت فقط رندر کند. */
export function freshnessOf(input: WidgetFreshInput): WidgetFreshnessView {
  const now = input.now ?? Date.now();
  const failed = input.status === 'error' || input.error === true;
  const ageText = input.dataUpdatedAt ? ageOf(input.dataUpdatedAt, now) : null;

  if (failed) {
    return {
      state: 'error',
      label: ageText ? 'بی‌پاسخ (دادهٔ پیشین)' : 'بی‌پاسخ',
      ageText,
      sourceText: 'زمانِ داده از منبع نیامد',
      toneClass: 'text-tone-err',
    };
  }
  if (input.status === 'pending' || input.status === 'idle' || !ageText) {
    return {
      state: 'pending',
      label: 'در حالِ خواندن',
      ageText,
      sourceText: 'زمانِ داده از منبع نیامد',
      toneClass: 'text-tone-unknown',
    };
  }
  return {
    state: 'ok',
    label: 'خوانده شد',
    ageText,
    sourceText: input.sourceAsOf ? `ساعتِ منبع: ${input.sourceAsOf}` : 'زمانِ داده از منبع نیامد',
    toneClass: 'text-tone-neutral',
  };
}

export function WidgetFreshness({ label, input }: { label: string; input: WidgetFreshInput }) {
  const v = freshnessOf(input);
  return (
    <span
      data-testid="widget-freshness"
      title={`تازگیِ «${label}» — سنِ رسیدنِ پاسخ، نه ساعتِ خودِ صفحه`}
      // قالبِ «pill» عمدی است: گرفتنیِ ۱۳۶۶×۷۶۸ نشان داد وقتی ده برچسب بی‌حاشیه درِ
      // یکِ خط کنارِ هم می‌نشینند، بهِ یکِ پاراگرافِ ناخوانا تبدیل می‌شوند (عددِ DOM
      // اینِ نقص را نمی‌بیند: نه سرریز است وِ نه بریدگی).
      className={`num-text inline-flex items-center gap-1 whitespace-nowrap rounded border border-border-c bg-bg-card/70 px-1.5 py-px text-3xs leading-4 ${v.toneClass}`}
    >
      {/* نامِ ویجت درِ متن می‌ماند (نه فقط درِ title): وقتی ششِ برچسب درِ یکِ صفحه
          دیده می‌شود، صفحه‌خوان باید بداند کدامِ سن مالِ کدامِ بخش است. */}
      <span className="font-bold text-text-secondary">{label}</span>
      <span>{v.label}</span>
      {v.ageText ? <span className="text-text-muted">· {v.ageText}</span> : null}
      {v.sourceText ? <span className="text-text-muted">· {v.sourceText}</span> : null}
    </span>
  );
}
