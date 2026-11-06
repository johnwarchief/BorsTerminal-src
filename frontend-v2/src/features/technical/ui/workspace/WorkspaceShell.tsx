/**
 * frontend-v2/src/features/technical/ui/workspace/WorkspaceShell.tsx
 *
 * پوستهٔ میزکار تازه (B1) — قراردادِ شبکهٔ §3 سند طراحی:
 *   ستون‌ها: 40px | minmax(0,1fr) | 280px
 *   ردیف‌ها: 56px | minmax(0,1fr) | auto
 *   نواحی:  topbar topbar topbar
 *          activity chart rail
 *          feed feed feed
 *
 * چارتِ مرکزی و DrawingToolbar/ForecastControls دقیقاً همان‌جا سوار می‌مانند؛
 * پنل‌ها در فید میزبان‌اند و پاپ‌اوتِ کشوی بازنشسته (B4) در سربرگ فید زندگی می‌کند.
 */

import React from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import { KLineChartWrapper } from '../KLineChartWrapper';
import { DrawingToolbar } from '../DrawingToolbar';
import { ForecastControls } from '../ForecastControls';
import { WorkspaceTopbar } from './WorkspaceTopbar';
import { ActivityBar } from './ActivityBar';
import { InspectorRail } from './InspectorRail';
import { EventFeed } from './EventFeed';

/**
 * قراردادِ چیدمان به‌صورت رشته‌های صریح نگه داشته می‌شود تا تست‌های پذیرش
 * بتوانند همان مقادیر §3 را ببینند (بدون بازنویسی در کلاس‌های دلخواه).
 * B5: ستون‌ها از متغیرِ --ws-grid-columns می‌آیند؛ در عرض‌های ≤1440px ریل
 * به ۲۴۰px باریک می‌شود تا سهمِ چارت از ویوپورت زیرِ ۶۰٪ نیفتد.
 */
export const WORKSPACE_GRID_TEMPLATE_COLUMNS = '40px minmax(0,1fr) 280px';
export const WORKSPACE_GRID_TEMPLATE_ROWS = '56px minmax(0,1fr) auto';
export const WORKSPACE_GRID_TEMPLATE_AREAS =
  '"topbar topbar topbar" "activity chart rail" "feed feed feed"';

export interface WorkspaceShellProps {
  /** نماد فعال؛ اگر نرسد از استور خوانده می‌شود. */
  activeSymbol?: string;
  className?: string;
}

export const WorkspaceShell: React.FC<WorkspaceShellProps> = ({
  activeSymbol,
  className = '',
}) => {
  const storedSymbol = useTechnicalStore((s) => s.selectedSymbol);
  const symbol = activeSymbol || storedSymbol;

  return (
    <div
      data-testid="workspace-shell"
      className={`workspace-grid w-full h-full min-h-0 min-w-0 ${className}`}
      // شبکه عمداً LTR است تا نواحی با قرارداد §3 یکی بمانند
      // (فعالیت چپ، چارت مرکز، ریل راست). هر ناحیه خودش RTL است.
      dir="ltr"
      style={{
        display: 'grid',
        gridTemplateColumns: `var(--ws-grid-columns, ${WORKSPACE_GRID_TEMPLATE_COLUMNS})`,
        gridTemplateRows: WORKSPACE_GRID_TEMPLATE_ROWS,
        gridTemplateAreas: WORKSPACE_GRID_TEMPLATE_AREAS,
      }}
    >
      <WorkspaceTopbar />

      <ActivityBar />

      {/* ناحیهٔ چارت: همان DrawingToolbar + ForecastControls + KLineChartWrapper */}
      <section
        aria-label="ناحیهٔ چارت"
        style={{ gridArea: 'chart' }}
        className="flex h-full min-h-0 min-w-0 overflow-hidden border-x border-line"
        dir="rtl"
      >
        <DrawingToolbar />
        <div className="flex-1 flex flex-col h-full min-w-0 min-h-0 overflow-hidden">
          <ForecastControls compact />
          <div className="flex-1 w-full min-h-0 relative overflow-hidden bg-bg">
            <KLineChartWrapper symbol={symbol} />
          </div>
        </div>
      </section>

      <InspectorRail />

      <EventFeed activeSymbol={symbol} />
    </div>
  );
};
