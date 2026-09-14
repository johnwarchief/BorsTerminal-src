// features/technical/components/SidebarFtsSignals.tsx -- تب ۲ سایدبار: سیگنال‌های FTS
// نمادهای دارای ستاپ/الگو (جت، پولبک، CHoCH، نقطه‌زنی، کف دوقلو، خروج از انباشت)
// با برچسب شاخص‌های FTS. سبک و سریع: فیلتر روی ستون‌های tech_* همان /api/screener.
import { useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { filterFtsSignals, ftsSignalTags, useFtsScreener } from '../api/useScreener';

const EXIT_FA: Record<string, string> = { stop: 'حد ضرر', exit: 'خروج', caution: 'احتیاط', hold: 'نگهداری' };

export function SidebarFtsSignals({ onSelect }: { onSelect: (s: string) => void }) {
  const [q, setQ] = useState('');
  const { data, isLoading, isError } = useFtsScreener();
  const rows = useMemo(() => filterFtsSignals(data?.data ?? [], q), [data, q]);

  return (
    <div className="flex flex-col gap-2" data-testid="sidebar-fts">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="جستجو در سیگنال‌ها..."
        aria-label="جستجوی نماد در سیگنال‌های FTS"
        data-testid="sidebar-fts-search"
        className="w-full rounded-lg border border-border-c bg-bg-card px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-border-accent"
      />

      {isLoading ? <span className="px-1 text-[11px] text-text-secondary">در حال اسکن سیگنال‌های FTS...</span> : null}
      {isError ? <span className="px-1 text-[11px] text-accent-red">خطا در دریافت اسکرینر</span> : null}

      {!isLoading && !isError && rows.length === 0 ? (
        <span className="px-1 text-[11px] text-text-muted" data-testid="sidebar-fts-empty">
          ستاپ فعالی برای کل بازار گزارش نشده
        </span>
      ) : null}

      <ul className="flex flex-col gap-1" data-testid="sidebar-fts-list">
        {rows.map((r) => {
          const tags = ftsSignalTags(r);
          return (
            <li key={r.symbol_norm ?? r.symbol}>
              <button
                type="button"
                onClick={() => onSelect(r.symbol)}
                className="flex w-full flex-col gap-1 rounded-lg border border-transparent px-2 py-1.5 text-right transition-colors hover:border-border-c hover:bg-bg-card"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-xs font-bold text-text-primary">
                    {r.symbol} <span className="font-normal text-text-muted">{r.name ?? ''}</span>
                  </span>
                  {r.score != null ? <span className="num shrink-0 text-[10px] text-text-muted">امتیاز {toFaDigits(r.score)}</span> : null}
                </span>
                <span className="flex flex-wrap gap-1">
                  {tags.map((t) => (
                    <Badge key={t.label} tone={t.tone}>
                      {t.label}
                    </Badge>
                  ))}
                  {r.tech_exit_verdict && r.tech_exit_verdict !== 'hold' ? (
                    <Badge tone="yellow">خروج: {EXIT_FA[r.tech_exit_verdict] ?? r.tech_exit_verdict}</Badge>
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
