// features/technical/components/TechnicalSidebar.tsx -- سایدبار راست چارت (جمع‌شو، سبک Watchlist)
// برای جلوگیری از فشرده‌کردن دوسویهٔ چارت، در حالت جمع فقط یک ریل باریک می‌ماند.
import { useState } from 'react';
import { SidebarWatchlist } from './SidebarWatchlist';
import { SidebarFtsSignals } from './SidebarFtsSignals';
import { SidebarActiveLevels, type ActiveLevelsView } from './SidebarActiveLevels';
import { SidebarMacroPulse } from './SidebarMacroPulse';

export type SidebarTabId = 'watch' | 'fts' | 'levels' | 'macro';

const TABS: { id: SidebarTabId; label: string }[] = [
  { id: 'watch', label: 'دیده‌بان' },
  { id: 'fts', label: 'سیگنال‌های FTS' },
  { id: 'levels', label: 'ترازها و حد ضرر' },
  { id: 'macro', label: 'نبض کلان' },
];

export function TechnicalSidebar({
  active,
  onSelect,
  defaultTab = 'watch',
}: {
  active: ActiveLevelsView;
  onSelect: (s: string) => void;
  defaultTab?: SidebarTabId;
}) {
  const [tab, setTab] = useState<SidebarTabId>(defaultTab);
  const [collapsed, setCollapsed] = useState(false);

  if (collapsed) {
    return (
      <aside
        data-testid="technical-sidebar-collapsed"
        className="glass-panel flex w-8 shrink-0 flex-col items-center gap-1 self-start rounded-xl p-1"
      >
        <button
          type="button"
          data-testid="sidebar-expand"
          onClick={() => setCollapsed(false)}
          title="باز کردن سایدبار"
          className="rounded border border-border-c bg-bg-card px-1 py-1 text-[10px] text-text-secondary hover:text-accent-blue"
        >
          ‹
        </button>
        <span className="text-[10px] text-text-muted" style={{ writingMode: 'vertical-rl' }}>
          دیده‌بان
        </span>
      </aside>
    );
  }

  return (
    <aside
      data-testid="technical-sidebar"
      aria-label="سایدبار تحلیل تکنیکال"
      className="glass-panel flex h-full min-h-0 w-[300px] shrink-0 flex-col gap-1 overflow-hidden rounded-xl p-1.5"
    >
      <div className="flex shrink-0 items-center gap-0.5" role="tablist" aria-label="تب‌های سایدبار تکنیکال">
        <button
          type="button"
          data-testid="sidebar-collapse"
          onClick={() => setCollapsed(true)}
          title="جمع کردن سایدبار"
          className="rounded border border-border-c bg-bg-card px-1.5 py-0.5 text-[11px] text-text-muted hover:text-accent-blue"
        >
          ›
        </button>
        {TABS.map((t) => {
          const on = t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={on}
              data-testid={`sidebar-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={`rounded px-2 py-0.5 text-[11px] font-semibold transition-colors ${
                on ? 'bg-accent-blue/15 text-accent-blue' : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" className="min-h-0 flex-1 overflow-y-auto pr-0.5" data-testid="sidebar-body">
        {tab === 'watch' ? <SidebarWatchlist onSelect={onSelect} /> : null}
        {tab === 'fts' ? <SidebarFtsSignals onSelect={onSelect} /> : null}
        {tab === 'levels' ? <SidebarActiveLevels active={active} /> : null}
        {tab === 'macro' ? <SidebarMacroPulse /> : null}
      </div>
    </aside>
  );
}
