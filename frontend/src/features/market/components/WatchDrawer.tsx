// features/market/components/WatchDrawer.tsx -- دیده‌بان‌های تابلو در دراور تک‌خطی
// سه تریگر سریع (دیده‌بان ساعت / دیده‌بان حجم مشکوک / صنایع داغ) بالای هیچ‌کدام
// کنار جدول جا نمی‌شوند: جدول تمام‌عرض است و هر دیده‌بان در پنل بازشوی زیرش.
// الگو از MicroChartsDrawer تعمیم یافته: بسته = فقط ردیف دکمه‌ها (h-10).
import { useState } from 'react';
import type { MarketRow } from '@shared/types/marketRow';
import { IndustryScreener } from './IndustryScreener';
import { SuspiciousPanel, type SuspSection } from './SuspiciousPanel';

export type WatchTabId = 'clock' | 'susp' | 'industries';
type WatchTab = { id: WatchTabId; label: string; sections: SuspSection[] | null };

export const WATCH_TABS: WatchTab[] = [
  { id: 'clock', label: 'دیده‌بان ساعت', sections: ['clock'] },
  { id: 'susp', label: 'دیده‌بان حجم مشکوک', sections: ['susp', 'roobi'] },
  { id: 'industries', label: 'صنایع داغ', sections: null },
];

export function WatchDrawer({ rows, onSelect }: { rows: MarketRow[]; onSelect: (s: string) => void }) {
  const [tab, setTab] = useState<WatchTabId>('clock');
  const [open, setOpen] = useState(false);

  const activate = (t: WatchTabId) => {
    if (open && t === tab) setOpen(false);
    else {
      setTab(t);
      setOpen(true);
    }
  };

  const active = WATCH_TABS.find((t) => t.id === tab) ?? WATCH_TABS[0];

  return (
    <div data-testid="watch-drawer" className="glass-panel panel-in flex w-full max-w-none flex-col gap-2 rounded-2xl p-2">
      <div className="flex h-8 items-center gap-2" aria-label="دیده‌بان‌های تابلو">
        <span className="shrink-0 text-[11px] font-black text-text-muted">دیده‌بان‌ها</span>
        {WATCH_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={open && tab === t.id}
            data-testid={`watch-tab-${t.id}`}
            onClick={() => activate(t.id)}
            className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors ${
              open && tab === t.id
                ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
            }`}
          >
            {t.label}
          </button>
        ))}
        {open ? (
          <button
            type="button"
            data-testid="watch-close"
            onClick={() => setOpen(false)}
            className="mr-auto shrink-0 rounded-full border border-border-c px-2 py-0.5 text-[11px] text-text-secondary hover:border-accent-red/50 hover:text-accent-red"
          >
            بستن ✕
          </button>
        ) : null}
      </div>
      {open ? (
        <div role="tabpanel" data-testid="watch-body" className="min-w-0">
          {active.sections ? <SuspiciousPanel rows={rows} onSelect={onSelect} sections={active.sections} /> : <IndustryScreener />}
        </div>
      ) : null}
    </div>
  );
}
