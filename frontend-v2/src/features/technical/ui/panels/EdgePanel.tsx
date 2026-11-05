/**
 * frontend-v2/src/features/technical/ui/panels/EdgePanel.tsx
 *
 * پنل لبه آماری کندل‌ها (منتقل‌شده از کشوی میزکار عریض، بدون تغییر رفتار):
 * همیشه سوار در DOM می‌ماند و فقط با کلاس hidden پنهان می‌شود (آزمون‌های سیستمی).
 */

import React from 'react';
import { CandleEdgeCard } from '../CandleEdgeCard';

export interface EdgePanelProps {
  symbol: string;
  /** تب لبه آماری فعال است؟ (پنل برای آزمون‌های سیستمی همیشه در DOM می‌ماند) */
  active: boolean;
}

export const EdgePanel: React.FC<EdgePanelProps> = ({ symbol, active }) => {
  return (
    <div
      data-testid="edge-tab-panel"
      className={active ? 'block p-3' : 'hidden'}
    >
      <CandleEdgeCard symbol={symbol} />
    </div>
  );
};
