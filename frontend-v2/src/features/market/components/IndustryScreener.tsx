import { useState } from 'react';
import clsx from 'clsx';
import { fmtInt, fmtPct, tone } from '@shared/lib/fa';
import { topIndustriesByFlow, topIndustriesByPct, useIndustries, type IndustryRow } from '../api/useIndustries';

type Mode = 'flow' | 'pct';

function IndustryLine({ row, leader, onPick }: {
  row: IndustryRow;
  leader: string | null;
  onPick?: (industry: string) => void;
}) {
  const flow = typeof row.flow_b_toman === 'number' ? row.flow_b_toman : null;
  const average = typeof row.avg_pct === 'number' ? row.avg_pct : null;
  const pctTone = tone(average);
  const body = (
    <>
      <span className="min-w-0 truncate t-105 font-bold text-text">
        {row.industry}
        {leader === row.industry ? <span className="ms-1 t-85 text-warn">پیشرو</span> : null}
      </span>
      <span className="flex shrink-0 items-center gap-2 t-10">
        {flow != null ? (
          <span data-testid={`industry-flow-${row.industry}`} className={flow >= 0 ? 'text-up' : 'text-down'}>
            <span aria-hidden>{flow >= 0 ? '▲' : '▼'}</span> <span className="num">{fmtInt(Math.abs(flow))}</span> <span className="t-85 text-text-3">ب.ت</span>
          </span>
        ) : <span className="t-9 text-text-3">بدون داده</span>}
        <span
          data-testid={`industry-pct-${row.industry}`}
          className={clsx('num', pctTone === 'up' ? 'text-up' : pctTone === 'down' ? 'text-down' : 'text-flat')}
        >
          {fmtPct(average, 1)}
        </span>
      </span>
    </>
  );
  return (
    <li>
      {onPick ? (
        <button
          type="button"
          data-testid={`industry-pick-${row.industry}`}
          onClick={() => onPick(row.industry)}
          title={`فیلتر تابلو روی ${row.industry}`}
          className="flex min-h-7 w-full items-center justify-between gap-2 rounded-[var(--radius-sm)] px-1 py-1 text-start hover:bg-panel-2"
        >
          {body}
        </button>
      ) : <div className="flex items-center justify-between gap-2 px-1 py-1">{body}</div>}
    </li>
  );
}

export function IndustryScreener({ onPick }: { onPick?: (industry: string) => void }) {
  const query = useIndustries();
  const [mode, setMode] = useState<Mode>('flow');
  const rows = query.data?.rows ?? null;
  const top = mode === 'flow' ? topIndustriesByFlow(rows) : topIndustriesByPct(rows);

  return (
    <div data-testid="sector-inflow" className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="t-105 font-bold text-text">صنعت داغ</h3>
        <div className="flex gap-1" role="group" aria-label="مبنای مرتب‌سازی صنایع">
          <button type="button" onClick={() => setMode('flow')} aria-pressed={mode === 'flow'} className="tape-btn">ورود پول حقیقی</button>
          <button type="button" onClick={() => setMode('pct')} aria-pressed={mode === 'pct'} className="tape-btn">بیشترین درصد</button>
        </div>
      </div>
      {query.isError && rows && rows.length > 0 ? (
        <div className="flex items-center justify-between gap-2 t-9 text-warn" data-testid="industries-degraded">
          <span>به‌روزرسانی ناموفق بود؛ آخرین دریافت موفق نمایش داده می‌شود.</span>
          <button type="button" onClick={() => void query.refetch()} className="tape-btn">تلاش دوباره</button>
        </div>
      ) : null}
      {query.isPending && !query.data ? <span className="t-95 text-text-3">در حال دریافت صنایع…</span>
        : query.isError && (!rows || rows.length === 0) ? (
          <div className="flex items-center gap-2 t-95 text-text-3">
            <span>صنایع دریافت نشد</span>
            <button type="button" data-testid="industries-retry" onClick={() => void query.refetch()} className="tape-btn">تلاش دوباره</button>
          </div>
        ) : !rows || rows.length === 0 ? <span className="t-95 text-text-3">بدون داده</span> : (
          <ul className="grid gap-0.5 lg:grid-cols-3">
            {top.map((row) => <IndustryLine key={row.industry} row={row} leader={query.data?.leader ?? null} onPick={onPick} />)}
          </ul>
        )}
      {onPick && rows && rows.length > 0 ? <span className="t-85 text-text-3">انتخاب صنعت، تابلو را روی همان صنعت فیلتر می‌کند.</span> : null}
    </div>
  );
}
