// features/technical/components/TechnicalSidebar.tsx -- سایدبار راست چندمنظوره سبک تریدینگ‌ویو (Right Icon Rail + Collapsible Drawer)
import { useState } from 'react';
import { SidebarWatchlist } from './SidebarWatchlist';
import { SidebarFtsSignals } from './SidebarFtsSignals';
import { SidebarOrderBook } from './SidebarOrderBook';
import { SidebarActiveLevels, type ActiveLevelsView } from './SidebarActiveLevels';

export type SidebarTabId = 'watch' | 'fts' | 'book' | 'levels';

const TABS: { id: SidebarTabId; label: string; icon: React.ReactNode }[] = [
  {
    id: 'watch',
    label: 'دیده‌بان',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
        <line x1="9" y1="9" x2="15" y2="9" />
        <line x1="9" y1="13" x2="13" y2="13" />
      </svg>
    ),
  },
  {
    id: 'fts',
    label: 'سیگنال‌های FTS',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
  {
    id: 'book',
    label: 'پنج مظنه',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <line x1="4" y1="6" x2="13" y2="6" />
        <line x1="4" y1="10" x2="17" y2="10" />
        <line x1="4" y1="14" x2="10" y2="14" />
        <line x1="4" y1="18" x2="15" y2="18" />
      </svg>
    ),
  },
  {
    id: 'levels',
    label: 'ترازها و حد ضرر',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="6" />
        <circle cx="12" cy="12" r="2" />
      </svg>
    ),
  },
];

export function TechnicalSidebar({
  active,
  symbol,
  onSelect,
  defaultTab = 'fts',
}: {
  active: ActiveLevelsView;
  /** همان نمادی که رویِ چارت است، حتی اگر کاربر هنوز چیزی انتخاب نکرده باشد */
  symbol: string;
  onSelect: (s: string) => void;
  defaultTab?: SidebarTabId;
}) {
  const [tab, setTab] = useState<SidebarTabId>(defaultTab);
  const [collapsed, setCollapsed] = useState(false);

  const handleTabClick = (id: SidebarTabId) => {
    if (tab === id && !collapsed) {
      setCollapsed(true);
    } else {
      setTab(id);
      setCollapsed(false);
    }
  };

  const activeTabDef = TABS.find((t) => t.id === tab) ?? TABS[0];

  return (
    <aside
      data-testid={collapsed ? 'technical-sidebar-collapsed' : 'technical-sidebar'}
      aria-label="سایدبار تحلیل تکنیکال"
      className="flex h-full min-h-0 shrink-0 select-none border-l border-[var(--hairline)] bg-[var(--bg-secondary)]"
    >
      {/* دراور بازشونده کشویی */}
      {/* عرض دیگر ثابت نیست: رویِ لپ‌تاپِ ۱۳۶۶ این پنل ۲۸۵ پیکسل می‌گرفت و
          با ریلِ آیکون‌ها ~۳۳۰ می‌شد — چارت را به ~۷۰۰ پیکسل می‌رساند. حالا
          تا ۱۵۳۶ پیکسل باریک‌تر است و از آن به بالا همان ۲۸۵. */}
      {!collapsed && (
        <div className="flex h-full w-[228px] 2xl:w-[285px] min-h-0 flex-col border-r border-[var(--hairline)] bg-[var(--bg-card)]">
          {/* هدر دراور ۴۰ پیکسلی هماهنگ با نوار بالا */}
          <div className="flex h-10 shrink-0 items-center justify-between border-b border-[var(--hairline)] px-3 bg-[var(--bg-secondary)]">
            <span className="text-xs font-bold text-[var(--text-primary)]">{activeTabDef.label}</span>
            <button
              type="button"
              data-testid="sidebar-collapse"
              onClick={() => setCollapsed(true)}
              title="بستن پنل"
              className="flex h-6 w-6 items-center justify-center rounded text-sm text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors"
            >
              ✕
            </button>
          </div>

          {/* بدنه دراور */}
          <div role="tabpanel" className="min-h-0 flex-1 overflow-y-auto p-2" data-testid="sidebar-body">
            {tab === 'watch' ? <SidebarWatchlist onSelect={onSelect} /> : null}
            {tab === 'fts' ? <SidebarFtsSignals onSelect={onSelect} /> : null}
            {tab === 'book' ? <SidebarOrderBook symbol={symbol} /> : null}
            {tab === 'levels' ? <SidebarActiveLevels active={active} /> : null}
          </div>
        </div>
      )}

      {/* نوار باریک آیکونی لبه بیرونی راست (Right Icon Rail) */}
      <nav
        className="flex w-11 shrink-0 flex-col items-center gap-1.5 py-2 bg-[var(--bg-secondary)]"
        role="tablist"
        aria-label="تب‌های سایدبار تکنیکال"
      >
        {collapsed && (
          <button
            type="button"
            data-testid="sidebar-expand"
            onClick={() => setCollapsed(false)}
            title="باز کردن سایدبار"
            className="hidden"
          >
            ‹
          </button>
        )}
        {TABS.map((t) => {
          const isActive = !collapsed && t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-label={t.label}
              data-testid={`sidebar-tab-${t.id}`}
              onClick={() => handleTabClick(t.id)}
              title={t.label}
              className={`relative flex h-8 w-8 items-center justify-center rounded transition-all cursor-pointer ${
                isActive
                  ? 'bg-[#2962ff]/15 text-[#2962ff]'
                  : 'text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
              }`}
            >
              {t.icon}
              {isActive && (
                <span className="absolute right-0 top-1 bottom-1 w-0.5 rounded-l bg-[#2962ff]" />
              )}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
