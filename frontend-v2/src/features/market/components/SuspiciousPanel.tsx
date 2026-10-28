import { useMemo } from 'react';
import type { MarketRow } from '@shared/types/market';
import { faNum, fmtPct } from '@shared/lib/fa';
import { buyerPowerRatio, detectClockPattern, detectSuspiciousVolume } from '../lib/tapeMath';
import { tapeFilterVerdict, type TapeFilterConfig } from '../lib/tapeAlgorithms';
import { detectStrongHour, STRONG_HOUR_LABEL } from '../lib/tapePatterns';

const MAX_ITEMS = 15;
export const ROOBI_LABEL = 'در صف فروش قفل + خریدار درشت در حال جمع‌آوری';

export type SuspSection = 'clock' | 'susp' | 'roobi';

type Item = {
  insCode: string;
  symbol: string;
  name: string;
  metric: number;
  power: number | null;
  extra: string;
  strong: boolean;
  title?: string;
};

function identity(row: MarketRow): string {
  return row.ins_code?.trim() || row.symbol;
}

export function SuspiciousPanel({ rows, filterConfig, onSelect, sections }: {
  rows: MarketRow[];
  filterConfig: TapeFilterConfig;
  onSelect: (insCode: string) => void;
  sections: SuspSection[];
}) {
  const clocks = useMemo<Item[]>(() => rows.flatMap((row) => {
    if (!row.symbol || !tapeFilterVerdict(row, 'f_clock', filterConfig)) return [];
    const clock = detectClockPattern(row);
    if (clock.gap == null) return [];
    return [{
      insCode: identity(row),
      symbol: row.symbol,
      name: row.name ?? '',
      metric: clock.gap,
      power: buyerPowerRatio(row.buy_i_vol, row.buy_count_i, row.sell_i_vol, row.sell_count_i),
      extra: fmtPct(clock.gap * 100),
      strong: detectStrongHour(row),
    }];
  }).sort((a, b) => b.metric - a.metric), [rows, filterConfig]);

  const suspicious = useMemo<Item[]>(() => rows.flatMap((row) => {
    if (!row.symbol || !tapeFilterVerdict(row, 'f_susp', filterConfig)) return [];
    const volume = detectSuspiciousVolume(row);
    if (volume.multiple == null) return [];
    return [{
      insCode: identity(row),
      symbol: row.symbol,
      name: row.name ?? '',
      metric: volume.multiple,
      power: buyerPowerRatio(row.buy_i_vol, row.buy_count_i, row.sell_i_vol, row.sell_count_i),
      extra: `${faNum(volume.multiple, 1)} برابر`,
      strong: detectStrongHour(row),
    }];
  }).sort((a, b) => b.metric - a.metric), [rows, filterConfig]);

  const sweeps = useMemo<Item[]>(() => rows.flatMap((row) => {
    if (!row.symbol || !tapeFilterVerdict(row, 'f_roobi', filterConfig)) return [];
    return [{
      insCode: identity(row),
      symbol: row.symbol,
      name: row.name ?? '',
      metric: row.percent_change ?? 0,
      power: buyerPowerRatio(row.buy_i_vol, row.buy_count_i, row.sell_i_vol, row.sell_count_i),
      extra: row.percent_change != null ? fmtPct(row.percent_change) : '—',
      strong: false,
      title: ROOBI_LABEL,
    }];
  }).sort((a, b) => a.metric - b.metric), [rows, filterConfig]);

  function section(id: SuspSection, title: string, items: Item[], total: number) {
    return (
      <section className="min-w-0" data-testid={`watch-section-${id}`}>
        <h3 className="mb-1 t-105 font-bold text-text">
          {title}{' '}
          <span data-testid={`watch-count-${id}`} className="num text-text-3">
            ({items.length < total ? `${faNum(items.length)} از ${faNum(total)}` : faNum(total)})
          </span>
        </h3>
        {items.length === 0 ? (
          <div className="rounded-[var(--radius-sm)] border border-dashed border-line p-2 text-center t-95 text-text-3">موردی نیست</div>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {items.map((item) => (
              <li key={item.insCode}>
                <button
                  type="button"
                  data-testid={`watch-row-${id}-${item.insCode}`}
                  onClick={() => onSelect(item.insCode)}
                  title={item.title}
                  className="flex min-h-7 w-full items-center justify-between gap-2 rounded-[var(--radius-sm)] border border-transparent px-2 py-1 text-start hover:border-line hover:bg-panel-2"
                >
                  <span className="min-w-0 t-10 font-bold text-text">
                    {item.symbol} <span className="font-normal text-text-3">{item.name}</span>
                    {item.title ? <span className="mt-0.5 block t-85 font-normal text-text-3">{item.title}</span> : null}
                  </span>
                  <span className="flex flex-none items-center gap-2">
                    {item.strong ? <span className="sym-badge" title={STRONG_HOUR_LABEL}>ساعت قوی</span> : null}
                    <span className="num t-10 text-text-2">{item.extra}</span>
                    {item.power != null && item.power >= 1.5 ? <span className="sym-badge">{faNum(item.power, 1)}</span> : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    );
  }

  return (
    <div className="grid min-w-0 gap-3 md:grid-cols-2">
      {sections.includes('clock') ? section('clock', 'الگوی ساعت', clocks.slice(0, MAX_ITEMS), clocks.length) : null}
      {sections.includes('susp') ? section('susp', 'حجم مشکوک', suspicious.slice(0, MAX_ITEMS), suspicious.length) : null}
      {sections.includes('roobi') ? section('roobi', 'کف‌روبی', sweeps.slice(0, MAX_ITEMS), sweeps.length) : null}
    </div>
  );
}
