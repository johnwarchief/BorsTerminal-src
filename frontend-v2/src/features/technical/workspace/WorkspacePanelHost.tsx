/**
 * frontend-v2/src/features/technical/workspace/WorkspacePanelHost.tsx
 *
 * میزبان پایدار هر پنل؛ `data-testid="panel-<kind>"` قرارداد تست/پذیرش است.
 */

import React from 'react';
import { PANEL_REGISTRY, type TechnicalPanelKind } from './panelRegistry';

export interface WorkspacePanelHostProps {
  kind: TechnicalPanelKind;
}

export const WorkspacePanelHost: React.FC<WorkspacePanelHostProps> = ({ kind }) => {
  const Panel = PANEL_REGISTRY[kind];
  return (
    <div
      data-testid={`panel-${kind}`}
      data-panel-kind={kind}
      className="h-full min-h-0 min-w-0 overflow-hidden bg-bg"
    >
      <Panel />
    </div>
  );
};
