// features/technical/components/SidebarFtsSignals.tsx -- تب ۲ سایدبار: سیگنال‌های FTS
// نمادهای دارای ستاپ/الگو (جت، پولبک، CHoCH، نقطه‌زنی، کف دوقلو، خروج از انباشت)،
// وتوی هفتگی، یا هشدارِ موتور خروج. فیلترهای کشویی فقط روی ستون‌های tech_* همان
// /api/screener کار می‌کنند؛ گزینهٔ ساختگی برای نوعی که در پاسخ نیست ساخته نمی‌شود.
import { useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { FTS_SIGNAL_LABEL } from '@shared/lib/ftsSignals';
import {
  FTS_FILTERS_DEFAULT,
  filterFtsSignalRows,
  ftsSignalTags,
  isFtsSignalRow,
  useFtsScreener,
  type FtsKindFilter,
  type FtsSignalFilters,
  type FtsVerdictFilter,
  type FtsWeeklyFilter,
} from '../api/useScreener';
import { MATRIX_DECISION_FA } from '../lib/ftsMatrixLabels';
import { TREND_FA } from './FtsBadgeStrip';

const EXIT_FA: Record<string, string> = { stop: 'حد ضرر', exit: 'خروج', caution: 'احتیاط', hold: 'نگهداری' };

const KIND_OPTIONS: { value: FtsKindFilter; label: string }[] = [
  { value: 'all', label: 'همه' },
  { value: 'hourglass', label: FTS_SIGNAL_LABEL.tech_hourglass_active },
  { value: 'jet', label: FTS_SIGNAL_LABEL.tech_jet },
  { value: 'choch_bull', label: FTS_SIGNAL_LABEL.tech_choch_bull },
  { value: 'choch_bear', label: FTS_SIGNAL_LABEL.tech_choch_bear },
  { value: 'double_bottom', label: FTS_SIGNAL_LABEL.tech_double_bottom },
  { value: 'range_break', label: FTS_SIGNAL_LABEL.tech_range_break },
  { value: 'weekly_veto', label: 'وتوی هفتگی' },
  { value: 'exit_signal', label: 'سیگنال خروج' },
];

const WEEKLY_OPTIONS: { value: FtsWeeklyFilter; label: string }[] = [
  { value: 'all', label: 'همه' },
  { value: 'up', label: TREND_FA.up },
  { value: 'down', label: TREND_FA.down },
  { value: 'range', label: TREND_FA.range },
  { value: 'na', label: TREND_FA.na },
  { value: 'not_reported', label: 'گزارش نشده' },
];

const VERDICT_OPTIONS: { value: FtsVerdictFilter; label: string }[] = [
  { value: 'all', label: 'همه' },
  { value: 'PERMITTED', label: MATRIX_DECISION_FA.PERMITTED },
  { value: 'REJECT', label: MATRIX_DECISION_FA.REJECT },
  { value: 'UNKNOWN', label: MATRIX_DECISION_FA.UNKNOWN },
  { value: 'not_reported', label: 'گزارش نشده' },
];

function FilterSelect({
  label,
  value,
  onChange,
  options,
  testId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  testId: string;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-0.5 text-3xs text-text-muted">
      <span>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full rounded-lg border border-border-c bg-bg-card px-1.5 py-1 text-xs text-text-primary outline-none focus:border-border-accent"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SidebarFtsSignals({ onSelect }: { onSelect: (s: string) => void }) {
  const [q, setQ] = useState('');
  const [filters, setFilters] = useState<FtsSignalFilters>(FTS_FILTERS_DEFAULT);
  const { data, isLoading, isError } = useFtsScreener();
  const rows = data?.data ?? [];
  const baseCount = useMemo(() => rows.filter(isFtsSignalRow).length, [rows]);
  const result = useMemo(() => filterFtsSignalRows(rows, q, filters), [rows, q, filters]);

  const filtersActive =
    filters.kind !== 'all' || filters.weekly !== 'all' || filters.verdict !== 'all' || q.trim().length > 0;
  const reset = () => {
    setQ('');
    setFilters(FTS_FILTERS_DEFAULT);
  };

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

      <div className="flex flex-col gap-1.5" data-testid="sidebar-fts-filters">
        <FilterSelect
          label="سیگنال / ستاپ"
          value={filters.kind}
          onChange={(v) => setFilters((f) => ({ ...f, kind: v as FtsKindFilter }))}
          options={KIND_OPTIONS}
          testId="sidebar-fts-filter-kind"
        />
        <div className="grid grid-cols-2 gap-1.5">
          <FilterSelect
            label="روند هفتگی"
            value={filters.weekly}
            onChange={(v) => setFilters((f) => ({ ...f, weekly: v as FtsWeeklyFilter }))}
            options={WEEKLY_OPTIONS}
            testId="sidebar-fts-filter-weekly"
          />
          <FilterSelect
            label="رأی FTS"
            value={filters.verdict}
            onChange={(v) => setFilters((f) => ({ ...f, verdict: v as FtsVerdictFilter }))}
            options={VERDICT_OPTIONS}
            testId="sidebar-fts-filter-verdict"
          />
        </div>
      </div>

      {isLoading ? <span className="px-1 text-3xs text-text-secondary">در حال اسکن سیگنال‌های FTS...</span> : null}
      {isError ? <span className="px-1 text-3xs text-accent-red">خطا در دریافت اسکرینر</span> : null}

      {!isLoading && !isError ? (
        <div className="flex items-center justify-between gap-2 px-1" data-testid="sidebar-fts-count">
          <span className="text-3xs text-text-secondary">
            {toFaDigits(result.total)} نماد
            {result.truncated ? ` · نمایش ${toFaDigits(result.rows.length)} از ${toFaDigits(result.total)}` : ''}
          </span>
          {filtersActive ? (
            <button
              type="button"
              onClick={reset}
              data-testid="sidebar-fts-reset"
              className="shrink-0 text-3xs text-accent-blue hover:underline"
            >
              بازنشانی
            </button>
          ) : null}
        </div>
      ) : null}

      {!isLoading && !isError && result.total === 0 ? (
        <span className="px-1 text-3xs text-text-muted" data-testid="sidebar-fts-empty">
          {baseCount === 0
            ? 'در ردیف‌های تحلیل‌شدۀ اسکرینر، سیگنال یا هشدار فعالی گزارش نشده'
            : `هیچ نمادی با این فیلترها نیست (از ${toFaDigits(baseCount)} نمادِ دارایِ سیگنال/هشدار)`}
        </span>
      ) : null}

      <ul className="flex flex-col gap-1" data-testid="sidebar-fts-list">
        {result.rows.map((r) => {
          const tags = ftsSignalTags(r);
          return (
            <li key={r.symbol_norm ?? r.symbol}>
              <button
                type="button"
                onClick={() => onSelect(r.symbol)}
                className="flex w-full flex-col gap-1 rounded-lg border border-transparent px-2 py-1.5 text-start transition-colors hover:border-border-c hover:bg-bg-card"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-xs font-bold text-text-primary">
                    {r.symbol} <span className="font-normal text-text-muted">{r.name ?? ''}</span>
                  </span>
                  {r.score != null ? <span className="num shrink-0 text-3xs text-text-muted">امتیاز {toFaDigits(r.score)}</span> : null}
                </span>
                <span className="flex flex-wrap gap-1">
                  {tags.map((t) => (
                    <Badge key={t.label} tone={t.tone}>
                      {t.label}
                    </Badge>
                  ))}
                  {r.tech_exit_verdict && r.tech_exit_verdict !== 'hold' && r.tech_exit_verdict !== 'unknown' ? (
                    <Badge tone={r.tech_exit_verdict === 'stop' || r.tech_exit_verdict === 'exit' ? 'red' : 'yellow'}>
                      خروج: {EXIT_FA[r.tech_exit_verdict] ?? r.tech_exit_verdict}
                    </Badge>
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
