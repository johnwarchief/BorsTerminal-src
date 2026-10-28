import { useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import type { TapeFilterConfig } from '../lib/tapeAlgorithms';
import { IndustryScreener } from '../components/IndustryScreener';
import { SuspiciousPanel, type SuspSection } from '../components/SuspiciousPanel';

type WatchTabId = 'clock' | 'susp' | 'industries';

const TABS: { id: WatchTabId; label: string; sections: SuspSection[] | null }[] = [
  { id: 'clock', label: 'دیده‌بان ساعت', sections: ['clock'] },
  { id: 'susp', label: 'دیده‌بان حجم مشکوک', sections: ['susp', 'roobi'] },
  { id: 'industries', label: 'صنایع داغ', sections: null },
];

export function WatchPanel({ rows, filterConfig, onSelect, onPickSector }: {
  rows: MarketRow[];
  filterConfig: TapeFilterConfig;
  onSelect: (insCode: string) => void;
  onPickSector?: (industry: string) => void;
}) {
  const [tab, setTab] = useState<WatchTabId>('clock');
  const active = TABS.find((item) => item.id === tab) ?? TABS[0]!;

  return (
    <div data-testid="watch-panel" className="flex h-full min-h-0 flex-col">
      <div className="flex flex-none items-center gap-1 overflow-x-auto border-b border-line px-2 py-0.5" role="tablist" aria-label="دیده‌بان‌ها">
        <span data-testid="watch-scope-label" className="shrink-0 t-9 text-text-3">
          دیده‌بان‌ها <span className="text-text-3/70">· کل تابلو</span>
        </span>
        {TABS.map((item) => (
          <button key={item.id} type="button" role="tab" aria-selected={tab === item.id}
            data-testid={`watch-tab-${item.id}`}
            onClick={() => setTab(item.id)}
            className="tape-btn ms-1 whitespace-nowrap">
            {item.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-1">
        {active.sections
          ? <SuspiciousPanel rows={rows} filterConfig={filterConfig} onSelect={onSelect} sections={active.sections} />
          : <IndustryScreener onPick={onPickSector} />}
      </div>
    </div>
  );
}
