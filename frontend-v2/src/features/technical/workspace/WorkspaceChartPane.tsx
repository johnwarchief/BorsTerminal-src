/**
 * frontend-v2/src/features/technical/workspace/WorkspaceChartPane.tsx
 *
 * پنل چارت میزکار ۲.۰. `KLineChartWrapper` دست‌نخورده می‌ماند؛ همان نوار
 * رسم و کنترل‌های پیش‌بینی که پیش‌تر در ناحیهٔ چارت بودند این‌جا سوار می‌شوند
 * تا قابلیت موجود حذف نشود.
 */

import React from 'react';
import { useTechnicalStore } from '../model/technicalStore';
import { KLineChartWrapper } from '../ui/KLineChartWrapper';
import { DrawingToolbar } from '../ui/DrawingToolbar';
import { ForecastControls } from '../ui/ForecastControls';

export interface WorkspaceChartPaneProps {
  /** نماد صریح؛ در نبود آن نماد فعال استور خوانده می‌شود. */
  symbol?: string;
}

export const WorkspaceChartPane: React.FC<WorkspaceChartPaneProps> = ({ symbol }) => {
  const storedSymbol = useTechnicalStore((s) => s.selectedSymbol);
  const activeSymbol = symbol || storedSymbol || '';

  return (
    <div
      data-testid="workspace-chart-pane"
      className="flex h-full min-h-0 min-w-0 overflow-hidden"
      dir="rtl"
    >
      <DrawingToolbar />
      <div className="flex-1 flex flex-col h-full min-w-0 min-h-0 overflow-hidden">
        <ForecastControls compact />
        <div className="flex-1 w-full min-h-0 relative overflow-hidden bg-bg">
          <KLineChartWrapper symbol={activeSymbol} />
        </div>
      </div>
    </div>
  );
};
