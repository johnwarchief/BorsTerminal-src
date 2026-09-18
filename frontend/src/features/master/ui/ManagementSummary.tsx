// features/master/ui/ManagementSummary.tsx -- باکس «خلاصهٔ تحلیلی مدیریتی»
// متن کاملاً آفلاین و قاعده‌محور (Rule-Based NLG) — بدون API/مدل بیرونی.
import type { SummaryLine } from '../lib/managementSummary';

const TONE_TEXT: Record<SummaryLine['tone'], string> = {
  green: 'text-accent-green',
  red: 'text-accent-red',
  yellow: 'text-accent-yellow',
  blue: 'text-accent-blue',
  gray: 'text-text-secondary',
};

export function ManagementSummary({ lines }: { lines: SummaryLine[] }) {
  return (
    <section
      aria-label="خلاصهٔ تحلیلی مدیریتی"
      className="glass-panel relative h-full p-4"
    >
      <h3 className="mb-2 text-sm font-black text-text-primary">خلاصهٔ تحلیلی مدیریتی</h3>
      <ul className="flex flex-col gap-2">
        {lines.map((l) => (
          <li key={l.id} className="rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-3 py-2">
            <div className={`mb-0.5 text-2xs font-black ${TONE_TEXT[l.tone]}`}>{l.title}</div>
            <p className="text-2xs leading-5 text-text-secondary">{l.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
