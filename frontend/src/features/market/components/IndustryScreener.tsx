// features/market/components/IndustryScreener.tsx -- اسکرینر صنعت داغ (۳ صنعت پیشرو)
// دو نمای سورت: «ورود پول حقیقی» (flow_b_toman) و «بیشترین درصد» (avg_pct).
// بدون داده = حالت خالی صریح، نه ردیف ساختگی.
import { useState } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { topIndustriesByFlow, topIndustriesByPct, useIndustries, type IndustryRow } from '../api/useIndustries';

type Mode = 'flow' | 'pct';

const fa1 = (x: number): string => toFaDigits(x.toFixed(1));

function IndustryLine({ row, leader }: { row: IndustryRow; leader: string | null }) {
  const flow = typeof row.flow_b_toman === 'number' ? row.flow_b_toman : null;
  return (
    <li className="flex items-center justify-between gap-2 px-1 py-1">
      <span className="min-w-0 truncate text-sm font-bold text-text-primary">
        {row.industry}
        {leader && row.industry === leader ? <span className="mr-1 text-2xs text-accent-yellow">★ پیشرو</span> : null}
      </span>
      <span className="num shrink-0 text-xs">
        {flow != null ? (
          <span className={flow >= 0 ? 'text-accent-green' : 'text-accent-red'}>
            {flow >= 0 ? '▲' : '▼'} {fmtInt(Math.abs(flow))} ب.ت
          </span>
        ) : (
          '—'
        )}
        <span className="mr-2 text-text-secondary">
          {typeof row.avg_pct === 'number' ? `٪${fa1(row.avg_pct)}` : '—'}
        </span>
      </span>
    </li>
  );
}

export function IndustryScreener() {
  const { data, isLoading, isError } = useIndustries();
  const [mode, setMode] = useState<Mode>('flow');

  const rows = data?.rows ?? null;
  const top = (mode === 'flow' ? topIndustriesByFlow(rows) : topIndustriesByPct(rows)) ?? [];

  return (
    <div data-testid="industry-screener" className="glass-panel panel-in flex flex-col gap-2 rounded-2xl p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-black text-text-primary">صنعت داغ</h3>
        <div className="flex gap-1" role="group" aria-label="مبنای سورت صنایع">
          <button
            type="button"
            onClick={() => setMode('flow')}
            aria-pressed={mode === 'flow'}
            className={`rounded-full border px-2 py-0.5 text-2xs font-semibold ${
              mode === 'flow' ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c text-text-secondary'
            }`}
          >
            ورود پول حقیقی
          </button>
          <button
            type="button"
            onClick={() => setMode('pct')}
            aria-pressed={mode === 'pct'}
            className={`rounded-full border px-2 py-0.5 text-2xs font-semibold ${
              mode === 'pct' ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c text-text-secondary'
            }`}
          >
            بیشترین درصد
          </button>
        </div>
      </div>
      {isLoading && !data ? (
        <span className="text-2xs text-text-secondary">در حال دریافت صنایع...</span>
      ) : isError || !rows || rows.length === 0 ? (
        <span className="text-2xs text-text-muted">بدون داده</span>
      ) : (
        <ul className="flex flex-col divide-y divide-border-c/40">
          {top.map((r) => (
            <IndustryLine key={r.industry} row={r} leader={data?.leader ?? null} />
          ))}
        </ul>
      )}
    </div>
  );
}
