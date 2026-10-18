// features/market/lib/tones.ts -- تک‌منبعِ رنگِ مثبت/منفی/خنثی/بی‌دادۀ «وضعیت بازار»
//
// مرحلۀ ۱ مأموریت صریح است: «رنگِ مثبت/منفی/خنثی/بی‌داده در کل صفحه یکسان
// باشد». کلیدِ رنگی درِ خودِ پاسخِ سرور (`tone`) می‌آید — نه از مقایسه‌یِ دوبارۀ
// عدد در رابط — پس دو پنل نمی‌توانند یک نماد را یکی سبز و دیگری قرمز کنند.
//
// بی‌داده عمداً خاکستریِ بی‌مرجع است و نه سبزِ کم‌رنگ: سِانجِ نشده نباید
// «تقریباً مثبت» به نظر برسد (همان قاعده‌ای که `countOrDash` درِ پنل‌هایِ قبلی
// با خط‌تیره نگه می‌دارد).
export type PanelTone = 'pos' | 'neg' | 'zero' | 'nodata';

/**
 * تک‌منبعِ کلاس‌ها. دو نکته که عمدی است:
 * · `fill` و `fillText` برایِ SVGاند (نقشۀ بازار). این رشته‌ها **باید کاملِ
 *   literal** باشند: Tailwind v4 منبع را می‌خواند و نامِ کلاس را نمی‌سازد، پس
 *   `bg-x`.replace('bg-','fill-') کلاسی نمی‌سازد و خانه بی‌رنگ می‌ماند — همان
 *   نقصِ `accent-amber` که گاردِ `design-token-guard.spec.ts` برایش نوشته شده.
 * · شدتِ fill کمی پرتر از bg است، چون خانه‌های نقشه کنارِ هم خوانده می‌شوند و
 *   شفافیتِ کم یعنی «بی‌تغییر» در برابر «مثبتِ کم».
 */
export const TONE_CLASS: Record<
  PanelTone,
  { text: string; bg: string; border: string; dot: string; fill: string; fillText: string }
> = {
  pos: {
    text: 'text-tone-pos',
    bg: 'bg-tone-pos/15',
    border: 'border-tone-pos/40',
    dot: 'bg-tone-pos',
    fill: 'fill-tone-pos/35',
    fillText: 'fill-tone-pos',
  },
  neg: {
    text: 'text-tone-neg',
    bg: 'bg-tone-neg/15',
    border: 'border-tone-neg/40',
    dot: 'bg-tone-neg',
    fill: 'fill-tone-neg/35',
    fillText: 'fill-tone-neg',
  },
  zero: {
    text: 'text-tone-neutral',
    bg: 'bg-bg-card',
    border: 'border-border-c',
    dot: 'bg-tone-neutral',
    fill: 'fill-tone-neutral/25',
    fillText: 'fill-tone-neutral',
  },
  nodata: {
    text: 'text-tone-unknown',
    bg: 'bg-bg-card',
    border: 'border-dashed border-border-c',
    dot: 'bg-tone-unknown',
    fill: 'fill-tone-unknown',
    fillText: 'fill-tone-unknown',
  },
};

/** راهنمایِ رنگِ یکسانِ کلِ صفحه (نقشۀ بازار و پنل‌های رتبه‌ای یک کلید می‌خوانند) */
export const TONE_LEGEND: { tone: PanelTone; label: string }[] = [
  { tone: 'pos', label: 'مثبت' },
  { tone: 'zero', label: 'بی‌تغییر' },
  { tone: 'neg', label: 'منفی' },
  { tone: 'nodata', label: 'بی‌داده' },
];

/** هر کلیدی که سرور به‌جای tone داد — بی‌داده، نه مثبتِ پیش‌فرض */
export function toneOf(v: unknown): PanelTone {
  return v === 'pos' || v === 'neg' || v === 'zero' ? v : 'nodata';
}
