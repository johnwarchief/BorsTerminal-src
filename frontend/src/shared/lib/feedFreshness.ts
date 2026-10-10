// shared/lib/feedFreshness.ts — تفکیکِ «اتصال» از «تازگیِ داده» برایِ نشانگرِ تابلو
//
// چرا این فایل هست: نشانگرِ Topbar تا این دور صرفاً `status==='success'` بود، یعنی
// «آخرینِ درخواست موفق آمد» — که با «دادهٔ بازار تازه است» یکی نیست. درِ بازارِ
// بسته پولینگِ unchanged موفق می‌آید و آن نشان سبزِ تپنده می‌ماند درحالی‌که هیچ‌چیز
// زنده نیست. اینجا دو مفهوم جدا حساب می‌شوند:
//   connection = وضعیتِ انتقالِ داده (خطا / در حالِ دریافت / سالم)
//   freshness  = تازگیِ منبع (مستقیم / بسته / کهنه / نامشخص)
// سیگنال‌ها همه از خودِ فیدِ canonical‌اند: `status`/`dataUpdatedAt` (ساعتِ کلاینت،
// clock-safe)، شمارندۀ ردیفهایِ نشستِ جاری از `is_live` (live_count)، و `marketOpen`
// از marketHours. هیچِ timestampِ ساختگی و هیچ آستانۀ اختراعی نیست؛ تنها مرزِ
// «متوقف» از عددِ موجودِ `CLOSED_POLL_MS` می‌آید (اگر درِ بازارِ باز بیش از ریتمِ
//ِ بسته از فید خبری نشد، تازه‌سازی خوابیده است).
import { CLOSED_POLL_MS, isMarketOpen } from './marketHours';

export type Connection = 'error' | 'connecting' | 'ok';
export type Freshness = 'live' | 'closed' | 'stale' | 'unknown';

export type FeedFreshnessInput = {
  /** وضعیتِ کوئریِ TanStack: 'idle' | 'pending' | 'loading' | 'success' | 'error'. */
  status: string;
  /** زمانِ دریافتِ آخرینِ پاسخِ موفق (epoch ms، ساعتِ خودِ کلاینت). */
  dataUpdatedAt: number;
  /** زمانِ آخرینِ عوض‌شدنِ *خودِ داده* (revِ تازه؛ epoch msِ کلاینت)؛ null یعنی
   *  منبعِ ما (نسخۀ قدیمیِ بک‌اند بی‌`rev_at`) این را گزارش نمی‌کند.
   *  چرا لازم شد: هر دورِ «unchanged» هم `dataUpdatedAt` را نو می‌کند، پس با
   *  سنجشِ زنده ۹۴۵ ثانیه بی‌تغییریِ revision، نشانگر «لحظاتی پیش» می‌گفت. */
  dataChangedAt?: number | null;
  /** چند ردیف به نشستِ جاری تعلق دارند (`is_live`)؛ null یعنی گزارش نشده. */
  liveCount?: number | null;
  /** کلِ ردیفها؛ برایِ بافت. */
  totalCount?: number | null;
  /** الان (epoch ms) — تزریقِ time برایِ تست‌پذیری. */
  now: number;
  /** ساعتِ بازار؛ تزریقِ marketHours.isMarketOpen() درِ محصول، ثابت درِ تست. */
  marketOpen?: boolean;
};

export type FeedStatus = {
  connection: Connection;
  freshness: Freshness;
  /** برچسبِ فارسیِ واحدِ نشانگر — ترکیبِ اتصال و تازگی. */
  label: string;
  /** کلاسِ رنگِ tone (پسوندِ bg-*). */
  tone: string;
  /** فقط درِ «مستقیمِ بازارِ باز» تپش دارد؛ نه برایِ دادهٔ بی‌تغییری. */
  pulse: boolean;
  /** سنِ آخرینِ دریافت بر حسبِ میلی‌ثانیه؛ null یعنی چیزی دریافت نشده. */
  ageMs: number | null;
  /** سنِ آخرینِ عوض‌شدنِ *داده*؛ null یعنی هنوز داده‌ای نبوده. این عدد با
   *  `ageMs` فرق دارد: «درخواست رسید» پاسخِ HTTP است، «عدد عوض شد» بازار. */
  dataAgeMs?: number | null;
};

/**
 * داوریِ اتصال و تازگی. ترتیبِ اولویت:
 *   ۱) خطایِ انتقال ⇒ connection=error (بر «خالی» و «کهنه» غالب است — قطعی ≠ بی‌داده).
 *   ۲) هنوز هیچِ پاسخِ موفق نیامده ⇒ connecting.
 *   ۳) بازارِ بسته ⇒ freshness=closed (نبودِ تغییرِ داده درِ تعطیلی، کهنه یا خطا نیست).
 *   ۴) بازارِ باز و ردیفِ نشستِ جاری هست و تازه‌سازی جریان دارد ⇒ live.
 *   ۵) بازارِ باز ولی ردیفِ جاری ندارد یا تازه‌سازی بیش از ریتمِ بسته خوابیده ⇒ stale.
 *   ۶) پاسخِ موفق ولی شمارندۀ live گزارش نشده ⇒ unknown (تازگی قابلِ داوری نیست).
 */
export function computeFeedStatus(s: FeedFreshnessInput): FeedStatus {
  const open = s.marketOpen ?? isMarketOpen(new Date(s.now));
  const hasData = s.dataUpdatedAt > 0;
  const ageMs = hasData ? Math.max(0, s.now - s.dataUpdatedAt) : null;
  // سنِ *داده*: اگر بک‌اند rev_at داد، از همان؛ وگرنه از رسیدنِ پاسخ (رفتارِ
  // پیشین، با نسخۀ قدیمیِ نصبی). دو چیزِ جدا را فقط وقتی خلط می‌کنیم که منبعِ
  // درستش موجود نباشد — و آن را درِ `dataAgeSource` صادقانه می‌گوییم.
  const changedKnown = s.dataChangedAt != null && s.dataChangedAt > 0;
  const dataAgeMs = changedKnown ? Math.max(0, s.now - (s.dataChangedAt as number)) : ageMs;

  if (s.status === 'error') {
    return {
      connection: 'error', freshness: 'stale', pulse: false, ageMs, dataAgeMs,
      tone: 'bg-accent-red', label: 'دادهٔ تابلو نمی‌رسد — اتصال بک‌اند را بررسی کن',
    };
  }
  if (!hasData) {
    const connecting = s.status === 'loading' || s.status === 'pending';
    return {
      connection: 'connecting', freshness: 'unknown', pulse: false, ageMs: null,
      dataAgeMs: null,
      tone: connecting ? 'bg-accent-yellow' : 'bg-text-muted',
      label: connecting ? 'در حالِ دریافتِ داده' : 'در انتظارِ رسیدنِ دادهٔ تابلو',
    };
  }

  // بازار بسته: تابلوی آخرینِ نشست نشان داده می‌شود؛ این «زنده» نیست و «خطا» هم نیست.
  if (!open) {
    return {
      connection: 'ok', freshness: 'closed', pulse: false, ageMs, dataAgeMs,
      tone: 'bg-accent-blue', label: 'بازار بسته — تابلوی آخرینِ نشست',
    };
  }

  // بازار باز: آیا ردیفهایِ همان نشستِ جاری (is_live) حاضر‌اند؟
  const liveKnown = s.liveCount != null;
  const stalled = dataAgeMs != null && dataAgeMs > CLOSED_POLL_MS;

  if (!liveKnown) {
    return {
      connection: 'ok', freshness: 'unknown', pulse: false, ageMs, dataAgeMs,
      tone: 'bg-text-muted', label: 'متصل — تازگیِ داده نامشخص',
    };
  }
  if ((s.liveCount ?? 0) === 0) {
    return {
      connection: 'ok', freshness: 'stale', pulse: false, ageMs, dataAgeMs,
      tone: 'bg-accent-yellow', label: 'کهنه — ردیفی از نشستِ جاری در تابلو نیست',
    };
  }
  if (stalled) {
    return {
      connection: 'ok', freshness: 'stale', pulse: false, ageMs, dataAgeMs,
      tone: 'bg-accent-yellow',
      label: changedKnown
        ? 'ایستاده — هیچ عددی از تازۀِ این پنجره عوض نشده (درخواست‌ها می‌رسند)'
        : 'کهنه — تازه‌سازیِ تابلو متوقف شده',
    };
  }
  return {
    connection: 'ok', freshness: 'live', pulse: true, ageMs, dataAgeMs,
    tone: 'bg-accent-green', label: 'مستقیم — بازار باز',
  };
}
