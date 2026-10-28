import { useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import type { TapeFilterConfig } from '../lib/tapeAlgorithms';
import { IndustryScreener } from './IndustryScreener';
import { SuspiciousPanel, type SuspSection } from './SuspiciousPanel';

export type WatchTabId = 'clock' | 'susp' | 'industries';

const WATCH_TABS: { id: WatchTabId; label: string; sections: SuspSection[] | null }[] = [
  { id: 'clock', label: 'دیده‌بان ساعت', sections: ['clock'] },
  { id: 'susp', label: 'دیده‌بان حجم مشکوک', sections: ['susp', 'roobi'] },
  { id: 'industries', label: 'صنایع داغ', sections: null },
];

export function WatchDock({ rows, filterConfig, onSelect, onPickSector }: {
  rows: MarketRow[];
  filterConfig: TapeFilterConfig;
  onSelect: (symbol: string) => void;
  onPickSector?: (industry: string) => void;
}) {
  const [tab, setTab] = useState<WatchTabId>('clock');
  const [open, setOpen] = useState(false);
  const active = WATCH_TABS.find((item) => item.id === tab) ?? WATCH_TABS[0];

  function activate(next: WatchTabId) {
    if (open && next === tab) setOpen(false);
    else {
      setTab(next);
      setOpen(true);
    }
  }

  return (
    <div data-testid="watch-dock" className="flex max-h-[310px] min-w-0 flex-col border-b border-line bg-panel px-2 py-1">
      <div className="flex h-7 flex-none items-center gap-1.5 overflow-x-auto" role="tablist" aria-label="دیده‌بان‌های تابلو">
        <span data-testid="watch-scope-label" className="shrink-0 t-9 font-bold text-text-3">
          دیده‌بان‌ها <span className="font-normal text-text-3/70">· کل تابلو</span>
        </span>
        {WATCH_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={open && tab === item.id}
            aria-expanded={open && tab === item.id}
            data-testid={`watch-tab-${item.id}`}
            onClick={() => activate(item.id)}
            className="tape-btn"
          >
            {item.label}
          </button>
        ))}
        {open ? <button type="button" data-testid="watch-close" onClick={() => setOpen(false)} className="tape-btn ms-auto">بستن</button> : null}
      </div>
      {open ? (
        <div role="tabpanel" data-testid="watch-body" className="min-h-0 overflow-y-auto border-t border-line/60 py-2">
          {active.sections ? (
            <SuspiciousPanel rows={rows} filterConfig={filterConfig} onSelect={onSelect} sections={active.sections} />
          ) : <IndustryScreener onPick={onPickSector} />}
        </div>
      ) : null}
    </div>
  );
}
