/**
 * frontend-v2/src/features/technical/workspace/panelRegistry.tsx
 *
 * رجیستری پنل‌های میزکار ۲.۰. هر پنل همان کامپوننت موجود را دوباره سوار
 * می‌کند؛ هیچ‌کدام از چارت/بازرس/فید ویرایش نمی‌شوند. پنل‌های نیازمند
 * prop (فید، ۵۰ نماد، بنیادی) این‌جا در پوسته‌های کوچک wrap می‌شوند.
 */

import React, { useState } from 'react';
import { useTechnicalStore } from '../model/technicalStore';
import type { AssetCategoryFilter } from '../ui/panels/Top50Panel';
import { Top50Panel } from '../ui/panels/Top50Panel';
import { IndicatorsPanel } from '../ui/panels/IndicatorsPanel';
import { FundamentalSummary } from '@features/fundamental/ui/FundamentalSummary';
import { InspectorRail } from '../ui/workspace/InspectorRail';
import { EventFeed } from '../ui/workspace/EventFeed';
import { WorkspaceChartPane } from './WorkspaceChartPane';
import type { TechnicalPanelKind } from './presets';

export type { TechnicalPanelKind } from './presets';

const WorkspaceEventFeedPane: React.FC = () => {
  const symbol = useTechnicalStore((s) => s.selectedSymbol) || '';
  return <EventFeed activeSymbol={symbol} />;
};

const WorkspaceScannerPane: React.FC = () => {
  const activeSymbol = useTechnicalStore((s) => s.selectedSymbol) || '';
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<AssetCategoryFilter>('all');

  const handleSelect = (symbol: string) => {
    setSelectedSymbol(symbol);
    if (typeof window !== 'undefined') {
      window.location.hash = `#/technical/${encodeURIComponent(symbol)}`;
    }
  };

  return (
    <div data-testid="workspace-scanner-pane" className="h-full overflow-y-auto">
      <Top50Panel
        activeSymbol={activeSymbol}
        onSelect={handleSelect}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        selectedCategory={selectedCategory}
        onCategoryChange={setSelectedCategory}
      />
    </div>
  );
};

const WorkspaceFundamentalPane: React.FC = () => {
  const symbol = useTechnicalStore((s) => s.selectedSymbol);
  return (
    <div data-testid="workspace-fundamental-pane" className="h-full overflow-y-auto p-3">
      <FundamentalSummary symbol={symbol} />
    </div>
  );
};

const WorkspaceInspectorPane: React.FC = () => <InspectorRail />;

const WorkspaceIndicatorsPane: React.FC = () => (
  <div className="h-full overflow-y-auto">
    <IndicatorsPanel />
  </div>
);

export const PANEL_REGISTRY: Record<TechnicalPanelKind, React.ComponentType> = {
  chart: WorkspaceChartPane,
  inspector: WorkspaceInspectorPane,
  feed: WorkspaceEventFeedPane,
  scanner: WorkspaceScannerPane,
  fundamental: WorkspaceFundamentalPane,
  indicators: WorkspaceIndicatorsPane,
};
