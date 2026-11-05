/**
 * frontend-v2/src/features/technical/ui/workspace/ActivityBar.tsx
 *
 * نوار فعالیت ۴۰px (B1) — مطابق §3: آیکن‌های SVG از ستِ موجود `@app/shell/icons`.
 * هر دکمه پنلِ فید را انتخاب می‌کند (WorkspacePanel) و فید را باز می‌کند؛
 * کلیک دوباره روی پنلِ فعال، فید را جمع می‌کند. تبِ کشوی موجود هم هم‌گام
 * می‌شود تا محتوای امروزِ کشو تا تسک B3 در دسترس بماند.
 */

import React from 'react';
import { Icon } from '@app/shell/icons';
import { useTechnicalStore } from '../../model/technicalStore';
import type { WorkspacePanel } from '../../model/types';

interface ActivityItem {
  id: WorkspacePanel;
  labelFa: string;
  icon: string;
}

const ACTIVITY_ITEMS: ActivityItem[] = [
  { id: 'events', labelFa: 'رویدادها', icon: 'pulse' },
  { id: 'top50', labelFa: '۵۰ نماد برتر', icon: 'grid' },
  { id: 'indicators', labelFa: 'اندیکاتورها و کانال', icon: 'chart' },
  { id: 'edge', labelFa: 'لبه آماری', icon: 'bolt' },
];

/** نگاشتِ پنلِ تازه به تبِ کشوی موجود؛ `events` همان اسکنر است. */
const LEGACY_DRAWER_TAB_BY_PANEL: Record<WorkspacePanel, 'top50' | 'indicators' | 'scanner' | 'edge'> = {
  events: 'scanner',
  top50: 'top50',
  indicators: 'indicators',
  edge: 'edge',
};

export interface ActivityBarProps {
  className?: string;
}

export const ActivityBar: React.FC<ActivityBarProps> = ({ className = '' }) => {
  const activePanel = useTechnicalStore((s) => s.activePanel);
  const setActivePanel = useTechnicalStore((s) => s.setActivePanel);
  const feedOpen = useTechnicalStore((s) => s.isLeftDrawerOpen);
  const toggleFeed = useTechnicalStore((s) => s.toggleFeed);
  const setActiveDrawerTab = useTechnicalStore((s) => s.setActiveDrawerTab);

  const handleSelect = (panel: WorkspacePanel) => {
    // کلیک دوباره روی پنلِ فعال، فید را جمع می‌کند.
    if (feedOpen && activePanel === panel) {
      toggleFeed();
      return;
    }
    setActivePanel(panel);
    setActiveDrawerTab(LEGACY_DRAWER_TAB_BY_PANEL[panel]);
    if (!feedOpen) {
      toggleFeed();
    }
  };

  return (
    <nav
      data-testid="workspace-activity"
      aria-label="نوار فعالیت میزکار"
      style={{ gridArea: 'activity' }}
      className={`flex flex-col items-center gap-1.5 py-2 bg-panel border-e border-line select-none ${className}`}
      dir="rtl"
    >
      {ACTIVITY_ITEMS.map((item) => {
        const isActive = activePanel === item.id;
        return (
          <button
            key={item.id}
            type="button"
            data-testid={`activity-panel-${item.id}`}
            title={item.labelFa}
            aria-label={item.labelFa}
            aria-pressed={isActive}
            onClick={() => handleSelect(item.id)}
            className={`flex items-center justify-center w-8 h-8 rounded-[var(--radius-sm)] border transition-colors ${
              isActive
                ? 'bg-panel-3 text-accent border-accent/40'
                : 'bg-transparent text-text-3 border-transparent hover:text-text hover:bg-panel-2'
            }`}
          >
            <Icon name={item.icon} size={16} />
          </button>
        );
      })}
    </nav>
  );
};
