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
    text: 'text-accent-green',
    bg: 'bg-accent-green/15',
    border: 'border-accent-green/40',
    dot: 'bg-accent-green',
    fill: 'fill-accent-green/35',
    fillText: 'fill-accent-green',
  },
  neg: {
    text: 'text-accent-red',
    bg: 'bg-accent-red/15',
    border: 'border-accent-red/40',
    dot: 'bg-accent-red',
    fill: 'fill-accent-red/35',
    fillText: 'fill-accent-red',
  },
  zero: {
    text: 'text-text-secondary',
    bg: 'bg-bg-card',
    border: 'border-border-c',
    dot: 'bg-text-muted',
    fill: 'fill-text-secondary/25',
    fillText: 'fill-text-secondary',
  },
  nodata: {
    text: 'text-text-muted',
    bg: 'bg-bg-card',
    border: 'border-dashed border-border-c',
    dot: 'bg-border-c',
    fill: 'fill-border-c',
    fillText: 'fill-text-muted',
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
