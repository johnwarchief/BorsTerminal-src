// features/technical/components/TechnicalSidebar.tsx -- سایدبار راست به سبک Watchlist تریدینگ‌ویو
// ثابت و مستقل از اسکرول (sticky) با چهار تب: دیده‌بان · سیگنال‌های FTS · ترازها و
// حد ضرر (نماد فعال) · نبض کلان. کلیک روی نماد، چارت را عوض می‌کند (onSelect).
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

  return (
    <aside
      data-testid="technical-sidebar"
      aria-label="سایدبار تحلیل تکنیکال"
      className="glass-panel sticky top-16 z-30 flex h-[calc(100vh-4.5rem)] w-full shrink-0 flex-col gap-2 overflow-hidden rounded-2xl p-2 xl:w-[340px]"
    >
      <div className="flex flex-wrap gap-1" role="tablist" aria-label="تب‌های سایدبار تکنیکال">
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
              className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors ${
                on
                  ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
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
