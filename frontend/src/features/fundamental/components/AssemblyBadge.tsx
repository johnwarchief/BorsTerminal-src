// features/fundamental/components/AssemblyBadge.tsx -- badge «مجمع نزدیک»
// در هدر صفحهٔ بنیادی کنار نماد. منطق انتخاب رویداد و متن برچسب در
// lib/assemblyEvent.ts است؛ این کامپوننت فقط داده را می‌کشد و رندر می‌کند.
// بدون رویداد مجمع (یا خطای شبکه) هیچ چیزی رندر نمیشود — بدون دادهٔ ساختگی.
import { useCalendarEvents } from '../api/useCalendarEvents';
import { pickAssemblyBadge } from '../lib/assemblyEvent';

export function AssemblyBadge({ symbol, now }: { symbol: string; now?: Date }) {
  const cal = useCalendarEvents(symbol);
  /** هر رندر بازمحاسبه می‌شود تا «امروز» کهنه نشود (محاسبه روی چند رویداد، سبک است) */
  const badge = pickAssemblyBadge(cal.data?.events ?? [], now);
  if (!badge) return null;
  const tone =
    badge.kind === 'near'
      ? 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue'
      : 'border-accent-yellow/40 bg-accent-yellow/10 text-accent-yellow';
  return (
    <span
      data-testid={badge.testId}
      title={badge.detail ? `${badge.detail} · تاریخ رویداد: ${badge.jalali}` : undefined}
      className={`inline-flex max-w-[24rem] shrink-0 items-center rounded-full border px-2.5 py-1 text-2xs font-bold leading-snug ${tone}`}
    >
      {badge.label}
    </span>
  );
}
