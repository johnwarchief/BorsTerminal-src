// features/technical/components/SplitChartView.tsx -- چیدمان ۲/۴ چارت با همگام‌سازی کراس‌هیر/زوم
// همهٔ پنل‌ها یک نماد/داده را نشان می‌دهند و از طریق باس chartSync هم‌گروه‌اند؛
// اورلی‌های FTS فقط روی پنل اول کشیده می‌شوند تا شلوغی کم شود.
import { type ChartView } from '../stores/ftsConfigStore';
import { KLineChartWrapper, type ChartPalette, type FtsChartLayers } from './KLineChartWrapper';
import type { KLineData } from '../../../vendor/klinecharts';

export type SplitLayout = 1 | 2 | 4;
/** گروه ثابت همگام‌سازی چارت‌های Split View */
export const SPLIT_GROUP = 'technical-split';

export function splitPaneCount(layout: SplitLayout): number {
  return layout === 4 ? 4 : layout === 2 ? 2 : 1;
}

export function SplitChartView({
  layout,
  data,
  palette,
  layers,
  view,
  showRsi = false,
  showVolMa = false,
  height = 330,
}: {
  layout: SplitLayout;
  data: KLineData[];
  palette: ChartPalette;
  layers: FtsChartLayers;
  view?: ChartView;
  showRsi?: boolean;
  showVolMa?: boolean;
  height?: number;
}) {
  const panes = splitPaneCount(layout);
  return (
    <div
      data-testid="split-view"
      data-layout={String(layout)}
      className={`grid gap-2 ${panes === 1 ? 'grid-cols-1' : 'grid-cols-1 xl:grid-cols-2'}`}
    >
      {Array.from({ length: panes }, (_, i) => (
        <div key={i} data-testid="split-pane">
          <KLineChartWrapper
            data={data}
            palette={palette}
            layers={i === 0 ? layers : undefined}
            height={height}
            showRsi={showRsi}
            showVolMa={showVolMa}
            view={view}
            syncKey={SPLIT_GROUP}
          />
        </div>
      ))}
    </div>
  );
}
