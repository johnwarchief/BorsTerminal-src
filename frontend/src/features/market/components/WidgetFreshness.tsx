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

export function WidgetFreshness({ label, input, testId = 'widget-freshness' }: {
  label: string; input: WidgetFreshInput;
  /** درِ صفحه‌ای که ده برچسب دارد، testidِ تکراری یعنی «همهٔ اینها یک چیزند»;
   *  میزبان نامِ خودِ بخش را می‌دهد (`${testId}-fresh`). */
  testId?: string;
}) {
  const v = freshnessOf(input);
  return (
    <span
      data-testid={testId}
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

export type FreshItem = { label: string; input: WidgetFreshInput };

export type FreshGroup = { labels: string[]; view: WidgetFreshnessView };

export type FreshSummary = {
  total: number;
  ok: number;
  /** گروه‌هایِ یکسان ادغام می‌شوند، ولی هرِ ویجت باِ نامِ خودش خوانده می‌شود:
   *  «یکی به‌ازایِ هرِ ویجت» یعنی هرِ ویجت داوریِ خودش را دارد، نه اینکه هرِ
   *  ویجت یکِ DOMِ جدا بگیرد. */
  groups: FreshGroup[];
  /** کهنه‌ترینِ سنِ پاسخ‌هایِ سالم — صادقانۀ‌ترین کران برایِ «همه تازه است» */
  oldestTs: number | null;
};

/** منطقِ خالصِ جمع‌بندی (بازطراحیِ صفحات): گرفتنیِ ۱۳۶ نشان داد چهارِ برچسبِ کاملِ
 *  تازگی درِ یکِ بخش بهِ دیوارِ چیپ تبدیل می‌شوند — همانِ نقصِ «شلوغیِ خوانایی» که
 *  برایِ رابطِ مرجع نوشته شده بود. آستانه اختراع نمی‌شود: فقط وضعیت‌هایِ موجود
 *  دسته‌بندی می‌شوند وِ فقطِ یکسان‌ها ادغام می‌یابند. */
export function summarizeFreshness(items: FreshItem[], now = Date.now()): FreshSummary {
  const groups: FreshGroup[] = [];
  let ok = 0;
  let oldestTs: number | null = null;
  for (const it of items) {
    const view = freshnessOf({ ...it.input, now });
    if (view.state === 'ok') {
      ok += 1;
      const ts = it.input.dataUpdatedAt;
      if (Number.isFinite(ts) && ts > 0 && (oldestTs == null || ts < oldestTs)) oldestTs = ts;
    }
    const key = `${view.state}|${view.ageText ?? ''}|${view.sourceText}`;
    const hit = groups.find((g) => `${g.view.state}|${g.view.ageText ?? ''}|${g.view.sourceText}` === key);
    if (hit) hit.labels.push(it.label);
    else groups.push({ labels: [it.label], view });
  }
  return { total: items.length, ok, groups, oldestTs };
}

export function FreshnessSummary({ items }: { items: FreshItem[] }) {
  // ساعت از خودِ ورودی خوانده می‌شود (همانِ درزِ آزمونِ `freshnessOf`)؛ بی‌این،
  // «کهنه‌ترین» باِ ساعتِ واقعیِ ماشین حساب می‌شد وِ آزمونِ زمان‌ثابت شکست می‌خورد.
  const now = items[0]?.input.now ?? Date.now();
  const sum = summarizeFreshness(items, now);
  if (!sum.total) return null;
  return (
    <span
      data-testid="freshness-summary"
      data-state={sum.groups.every((g) => g.view.state === 'ok') ? 'all-ok' : 'attention'}
      data-widgets={sum.total}
      className="contents"
    >
      {sum.groups.map((g) => (
        <span
          key={g.labels.join('|')}
          data-testid="widget-freshness"
          data-widgets={g.labels.length}
          title={`تازگیِ «${g.labels.join('، ')}» — سنِ رسیدنِ پاسخ، نه ساعتِ خودِ صفحه`}
          className={`num-text inline-flex items-center gap-1 whitespace-nowrap rounded border border-border-c bg-bg-card/70 px-1.5 py-px text-3xs leading-4 ${g.view.toneClass}`}
        >
          <span className="font-bold text-text-secondary">{g.labels.join('، ')}</span>
          <span>{g.view.label}</span>
          {g.view.ageText ? <span className="text-text-muted">· {g.view.ageText}</span> : null}
          {g.view.sourceText ? <span className="text-text-muted">· {g.view.sourceText}</span> : null}
        </span>
      ))}
    </span>
  );
}
