// features/technical/nahayatnegar/lib/axisScaleLock.ts — قفلِ مقیاسِ عمودی هنگامِ جابه‌جایی
//
// شکایتِ مالک (#167): «درگِ افقی چارت را عمودی هم تکان می‌دهد». علتِ فنی این است
// که klinecharts محدودهٔ محورِ قیمت را به پنجرۀ دیدِ *بازشدید* گره می‌زند؛ پس با
// هر جابه‌جاییِ افقی، سقف و کفِ جدید وارد دید می‌شوند و کل چارت عمودی می‌پرد.
// ره‌آورد برای همین در تبِ «مقیاس‌ها» گزینه‌ای به نامِ «قفل قیمت به نسبت کندل»
// دارد (docs/CHART-PARITY-REFERENCE.md §۱۵).
//
// منطق:
//  - مقیاسِ عمودی «چسبنده» است: تا وقتی زومی رخ نداده و دید از محدودهٔ نگه‌داشته
//    دور نشده، همان سقف و کف برمی‌گردد؛ پس درگِ افقی چارت را عمودی نمی‌تکاند.
//  - اگر دید آن‌قدر برود که محدودهٔ خودش دیگر هم‌پوشانیِ کافی با آن نداشته
//    باشد، آزاد می‌شود و دوباره می‌چیند — وگرنه کندل‌ها از کادر بیرون
//    می‌افتادند (همان دامِ «قفلِ کور»).
//  - زوم ⇒ آزاد (مقیاس باید با بازهٔ تازه هم‌اندازه شود)، مگر قفلِ کامل روشن باشد.
//  - دادهٔ تازه/نشستِ تازه/مطالعۀ تازه ⇒ آزاد با release()؛ وگرنه عددِ زنده
//    پشتِ یک مقیاسِ کهنه می‌ماند.
//
// هیچ عددی اینجا ساخته نمی‌شود: تابع فقط یکی از دو محدودهٔ موجود را برمی‌گرداند.

export type AxisRange = {
  from: number;
  to: number;
  range?: number;
  realFrom?: number;
  realTo?: number;
  realRange?: number;
  displayFrom?: number;
  displayTo?: number;
  displayRange?: number;
};
export type VisibleWindow = { from: number; to: number };

/** فضایِ محورِ عمودی. `normal` همان ریال است؛ `logarithm` پیش ازِ نگاشتِ پیکسل،
 *  مقدار را به log10 می‌برد. `percentage` تبدیلِ خودش را دارد و ما درِ آن
 *  دخالتِ نمی‌کنیم (پایین توضیح داده شده). */
export type AxisSpace = 'normal' | 'logarithm' | 'percentage';

/**
 * قفلِ مقیاس فقط وقتی درست است که «همان» تبدیلِ خودِ محور را بسازد.
 *
 * چرا این سطر اینجا آمد (سنجشِ ۱۴۰-۰۷-۲۷، `_audit/chart_log_cause.js`):
 * `overrideYAxis({ createRange })` درِ v10 جایِ createRangeِ خودِ محور را
 * **می‌گیرد**، نه اینکه کنارش بنشیند. محورِ لگاریتمی درِ vendor همان‌جا
 * `realFrom/realTo` را به log10 تبدیل می‌کند (`index.esm.js:9493`)، ولی قفلِ ما
 * فقط `{from,to}` برمی‌گرداند؛ پس `realFrom/realTo` درِ فضایِ ریال می‌ماند و
 * `convertToPixel` مقدارِ log10 را با کرانِ ریالی مقایسه می‌کند
 * (`rate = (realValue - realFrom) / realRange`، `index.esm.js:1304`) ⇒ نرخِ
 * تقریباً ثابت و بیرونِ پن. نتیجه‌اش درِ مرورگر: همهٔ کندل‌ها به یکِ سطرِ
 * بیرونِ کادر (y=۷۱۷ برایِ پنِ ۴۳۹پیکسلی) وِ محورِ بی‌سرِ وِ انتهایِ معتبر.
 * درِ مقیاسِ خطی این نقص دیده نمی‌شد، چون آن‌جا real == display است.
 */
const toReal = (space: AxisSpace, v: number): number =>
  space === 'logarithm' ? (v < 0 ? -Math.log10(Math.abs(v)) : Math.log10(v)) : v;

/** شمارۀِ کاملِ بازۀِ محور، همان چیزی که vendor مصرف می‌کند */
export type FullAxisRange = AxisRange & {
  range: number;
  realFrom: number;
  realTo: number;
  realRange: number;
  displayFrom: number;
  displayTo: number;
  displayRange: number;
};

const fullRange = (space: AxisSpace, from: number, to: number): FullAxisRange => {
  const realFrom = toReal(space, from);
  const realTo = toReal(space, to);
  return {
    from, to, range: to - from,
    realFrom, realTo, realRange: realTo - realFrom,
    displayFrom: from, displayTo: to, displayRange: to - from,
  };
};

/** فاصلۀ امنِ انتهایِ مقیاس، بر حسبِ ارتفاعِ همان مقیاس. موتور معمولاً حدود
 *  ۱۵٪ فاصله می‌گذارد؛ با آستانۀ ۰.۷۵ یک پرشِ محاسبه‌شدۀ واقعی (≈۱.۲ برابر
 *  قدِ چارت) آزاد می‌شود، ولی کشیدنِ سادهٔ چارت هرگز. */
export const SCALE_DRIFT_RELEASE = 0.75;

type Params = {
  chart: { getVisibleRange: () => VisibleWindow };
  defaultRange: AxisRange;
};

export type ScaleLock = {
  /** مستقیم به `overrideYAxis({ createRange })` داده می‌شود */
  createRange: (params: Params) => AxisRange;
  /** نامِ محورِ فعال — بی‌این، قفل درِ لگاریتمی تبدیلِ خودِ محور را می‌بلعد */
  setSpace: (space: AxisSpace) => void;
  /** قفلِ کامل (معادلِ «قفل قیمت به نسبت کندل»): زوم هم مقیاس را نمی‌شکند */
  setFullLock: (on: boolean) => void;
  /** هرگونه تغییرِ ساختاری: نماد، بازهٔ زمانی، تعدیل، یا دادهٔ تازه */
  release: () => void;
  /** فقط برای آزمون/عیاریابی */
  peek: () => { kept: AxisRange | null; window: VisibleWindow | null; fullLock: boolean; space: AxisSpace };
};

/**تحملِ تغییرِ عرضِ پنجره. یک درگِ ساده در انتهایِ چارت گاهی یک-دو کندل به
 *  شمارۀ دید اضافه/کم می‌کند (کلاپسِ لبهٔ راست)؛ اگر این را «زوم» بشماریم،
 *  مقیاس بی‌دلیل از نو می‌چیند و پرش برمی‌گردد — همان چیزی که در ۱۹۲۰ دیده شد.
 *  زومِ واقعی ده‌ها کندل جابه‌جا می‌کند، پس این آستانه او را نمی‌خورد. */
export const SCALE_WIDTH_TOLERANCE = 0.03;

const finite = (r: AxisRange | undefined | null): r is AxisRange =>
  r != null && Number.isFinite(r.from) && Number.isFinite(r.to) && r.to > r.from;

const nearSameWidth = (a: VisibleWindow, b: VisibleWindow): boolean => {
  const wa = a.to - a.from;
  const wb = b.to - b.from;
  return Math.abs(wa - wb) <= Math.max(1.5, Math.abs(wa) * SCALE_WIDTH_TOLERANCE);
};

export function createScaleLock(): ScaleLock {
  let kept: AxisRange | null = null;
  let win: VisibleWindow | null = null;
  let fullLock = false;
  let space: AxisSpace = 'normal';

  const createRange = ({ chart, defaultRange }: Params): AxisRange => {
    // «درصدی» تبدیلِ خودش را درِ vendor دارد؛ دخالتِ ما آن را می‌شکند، پس اینجا
    // قفل بی‌عمل است و بازۀِ خودِ محور دست‌نخورده می‌ماند.
    if (space === 'percentage') return defaultRange;
    const next = chart.getVisibleRange();
    const prev = win;
    win = next;

    // «زوم» یعنی عرضِ پنجره عوض شده. جابه‌جاییِ صرفِ پنجره (درگ) عرض را عوض
    // نمی‌کند و به‌تنهایی دلیلِ دوباره‌چیدنِ مقیاس نیست.
    const zoomed = prev != null && !nearSameWidth(prev, next);
    if (kept != null && finite(defaultRange)) {
      const span = Math.max(kept.to - kept.from, Number.EPSILON);
      const drift = Math.max(
        Math.abs(defaultRange.from - kept.from),
        Math.abs(defaultRange.to - kept.to),
      );
      const driftedAway = drift / span > SCALE_DRIFT_RELEASE;
      // مقیاس «چسبنده» است: تا وقتی زومی رخ نداده و دید از آن دور نشده، همان
      // محدوده برمی‌گردد. اگر فقط در لحظهٔ جابه‌جایی نگهش می‌داشتیم، فراخوانیِ
      // بعدیِ موتور با همانِ پنجره مقیاسِ تازه می‌گرفت و پرش یک فریم دیرتر
      // برمی‌گشت (در ۱۹۲ زنده دیده شد).
      const hold = fullLock || (!zoomed && !driftedAway);
      if (hold) return fullRange(space, kept.from, kept.to);
    }
    kept = defaultRange;
    return fullRange(space, defaultRange.from, defaultRange.to);
  };

  return {
    createRange,
    setSpace: (next: AxisSpace) => {
      if (next === space) return;
      space = next;
      // بازۀِ نگه‌داشته درِ فضایِ نمایش است و هنوز معتبر؛ فقط real* بازمی‌سازد
    },
    setFullLock: (on: boolean) => {
      fullLock = on;
      if (!on) kept = null;
    },
    release: () => {
      kept = null;
      win = null;
    },
    peek: () => ({ kept, window: win, fullLock, space }),
  };
}
