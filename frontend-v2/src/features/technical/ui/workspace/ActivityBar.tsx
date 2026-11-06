/**
 * frontend-v2/src/features/technical/ui/workspace/ActivityBar.tsx
 *
 * نوار فعالیت ۴۰px (B1، اصلاح R-PB-4) — دقیقاً بخش‌های §3 سند طراحی:
 *   chart | scanner | indicators | settings
 * آیکن‌های SVG از ستِ موجود `@app/shell/icons`؛ هیچ تبِ فیدی اینجا نیست
 * (تب‌های فید در EventFeed زندگی می‌کنند).
 *
 * رفتار بخش‌ها:
 * - chart: فید جمع می‌شود و تمرکز به چارت برمی‌گردد.
 * - scanner: فید روی تبِ رویدادها باز می‌شود.
 * - indicators: فید روی تبِ اندیکاتورها باز می‌شود.
 * - settings: محتوای تنظیماتِ موجود در ریل بازرس نمایش داده می‌شود.
 */

import React from 'react';
import { Icon } from '@app/shell/icons';
import { useTechnicalStore } from '../../model/technicalStore';
import type { WorkspacePanel, WorkspaceSection } from '../../model/types';

interface ActivityItem {
  id: WorkspaceSection;
  labelFa: string;
  icon: string;
}

const ACTIVITY_ITEMS: ActivityItem[] = [
  { id: 'chart', labelFa: 'چارت', icon: 'chart' },
  { id: 'scanner', labelFa: 'اسکنر', icon: 'pulse' },
  { id: 'indicators', labelFa: 'اندیکاتورها', icon: 'compass' },
  { id: 'settings', labelFa: 'تنظیمات', icon: 'sliders' },
];

/** بخش‌هایی که فید را روی یک پنل مشخص باز می‌کنند. */
const FEED_PANEL_BY_SECTION: Partial<Record<WorkspaceSection, WorkspacePanel>> = {
  scanner: 'events',
  indicators: 'indicators',
};

export interface ActivityBarProps {
  className?: string;
}

export const ActivityBar: React.FC<ActivityBarProps> = ({ className = '' }) => {
  const activeSection = useTechnicalStore((s) => s.activeSection);
  const setActiveSection = useTechnicalStore((s) => s.setActiveSection);
  const setActivePanel = useTechnicalStore((s) => s.setActivePanel);
  const feedOpen = useTechnicalStore((s) => s.isLeftDrawerOpen);
  const toggleFeed = useTechnicalStore((s) => s.toggleFeed);

  const handleSelect = (section: WorkspaceSection) => {
    setActiveSection(section);

    const panel = FEED_PANEL_BY_SECTION[section];
    if (panel) {
      setActivePanel(panel);
      if (!feedOpen) toggleFeed();
      return;
    }

    if (section === 'chart' && feedOpen) {
      toggleFeed();
    }
    // settings: فید دست‌نخورده می‌ماند؛ محتوای تنظیمات در InspectorRail می‌آید.
  };

  return (
    <nav
      data-testid="workspace-activity"
      aria-label="نوار فعالیت میزکار"
      style={{ gridArea: 'activity' }}
      className={`flex flex-col items-center gap-2 py-2 bg-panel border-e border-line select-none ${className}`}
      dir="rtl"
    >
      {ACTIVITY_ITEMS.map((item) => {
        const isActive = activeSection === item.id;
        return (
          <button
            key={item.id}
            type="button"
            data-testid={`activity-section-${item.id}`}
            title={item.labelFa}
            aria-label={item.labelFa}
            // برای بخش فعال از aria-current استفاده می‌شود، نه aria-pressed.
            aria-current={isActive ? 'true' : undefined}
            onClick={() => handleSelect(item.id)}
            className={`flex items-center justify-center w-8 h-8 rounded-[var(--radius-md)] border transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
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
