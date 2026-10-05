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

export type AxisRange = { from: number; to: number };
export type VisibleWindow = { from: number; to: number };

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
  /** قفلِ کامل (معادلِ «قفل قیمت به نسبت کندل»): زوم هم مقیاس را نمی‌شکند */
  setFullLock: (on: boolean) => void;
  /** هرگونه تغییرِ ساختاری: نماد، بازهٔ زمانی، تعدیل، یا دادهٔ تازه */
  release: () => void;
  /** فقط برای آزمون/عیاریابی */
  peek: () => { kept: AxisRange | null; window: VisibleWindow | null; fullLock: boolean };
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

  const createRange = ({ chart, defaultRange }: Params): AxisRange => {
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
      if (hold) return kept;
    }
    kept = defaultRange;
    return defaultRange;
  };

  return {
    createRange,
    setFullLock: (on: boolean) => {
      fullLock = on;
      if (!on) kept = null;
    },
    release: () => {
      kept = null;
      win = null;
    },
    peek: () => ({ kept, window: win, fullLock }),
  };
}
