// features/market/components/MicroBadge.tsx -- پالتِ بج‌هایِ تابلو (منبعِ یکتا)
//
// ازِ `TapeTable.tsx` جدا شد تاِ نمایِ کارتِ موبایل (`TapeCards`) هم *همانِ* بج را
// بدهد، بی‌آنکه مجبور شود ازِ فایلِ والدِ خودش import بگیرد (دورۀِ import).
// رأیِ مالک ۱۴۰۵-۰۷-۱۹: «همون برچسب‌های تابلوخوانی» — جدولِ غربالگری وِ کارتِ
// گوشی وِ ردیفِ دسکتاپ همه ازِ همینِ یکِ پالت خوانده می‌شوند.
import type { ReactNode } from 'react';

export const MICRO_TONES = {
  violet: 'bg-purple-100 text-purple-950 border border-purple-300 dark:bg-[#8b5cf6]/25 dark:text-[#ddd6fe] dark:border-[#8b5cf6]/40',
  amber: 'bg-amber-100 text-amber-950 border border-amber-300 dark:bg-accent-yellow/25 dark:text-[#fef08a] dark:border-accent-yellow/45',
  cyan: 'bg-sky-100 text-sky-950 border border-sky-300 dark:bg-neon-cyan/20 dark:text-[#a5f3fc] dark:border-neon-cyan/40',
  emerald: 'bg-emerald-100 text-emerald-950 border border-emerald-300 dark:bg-accent-green/20 dark:text-[#bbf7d0] dark:border-accent-green/40',
  green: 'bg-green-100 text-green-950 border border-green-300 dark:bg-accent-green/20 dark:text-[#bbf7d0] dark:border-accent-green/40',
  red: 'bg-red-100 text-red-950 border border-red-300 dark:bg-accent-red/20 dark:text-[#fecaca] dark:border-accent-red/40',
  gray: 'bg-slate-200 text-slate-900 border border-slate-300 dark:bg-bg-card/90 dark:text-text-primary dark:border-border-c',
} as const;

export type MicroTone = keyof typeof MICRO_TONES;

/** میکرو-بج متنی های‌دنسیتی با کنتراست و خوانایی بالا؛ جزئیات عددی در title هر بج */
export function MicroBadge({ pattern, tone, title, children }: {
  pattern: string; tone: MicroTone; title: string; children: ReactNode;
}) {
  return (
    <span
      data-testid={`badge-${pattern}`}
      data-pattern={pattern}
      title={title}
      className={`shrink-0 inline-flex items-center justify-center rounded-md px-1 py-px text-3xs font-bold leading-none tracking-tight shadow-2xs whitespace-nowrap select-none ${MICRO_TONES[tone]}`}
    >
      {children}
    </span>
  );
}
