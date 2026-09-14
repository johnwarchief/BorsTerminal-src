// features/fundamental/components/DataGapBanner.tsx -- دلیل و راه نبود داده
// متون خام موتور بک‌اند (fts_engine، annualize و…) هرگز به کاربر نشان
// داده نمی‌شوند — هر شکاف به علتِ کوتاه + راه‌حل ترجمه می‌شود
// (منبع یکتای متون: lib/gapReason تا در کل ویژگی یکدست بماند).
import type { FtsCard } from '../api/useFtsCard';
import { standardizeGap } from '../lib/gapReason';

export function DataGapBanner({ gaps }: { gaps: NonNullable<FtsCard['data_gaps']> }) {
  if (!gaps || gaps.length === 0) return null;
  const items = gaps.map(standardizeGap);
  return (
    <div className="rounded-2xl border border-accent-yellow/40 bg-accent-yellow/10 p-4" data-testid="data-gap-banner">
      <h3 className="mb-2 text-sm font-black text-accent-yellow">
        دادهٔ کدال برای {items.length} شاخص کامل نیست
      </h3>
      <ul className="flex flex-col gap-2">
        {items.map((g, i) => (
          <li key={`${g.layer}-${i}`} className="text-xs text-text-primary" title={`${g.why} — راه‌حل: ${g.fix}`} data-testid="data-gap-item">
            <span className="font-bold">شاخص {g.layer}: </span>
            {g.why} <span className="text-text-secondary">راه‌حل: {g.fix}</span>
            <span aria-hidden className="text-[9px] leading-none text-text-muted"> ⓘ</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
