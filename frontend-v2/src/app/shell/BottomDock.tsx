import { useRef } from 'react';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { FundamentalCards } from '@features/fundamental/ui/FundamentalCards';
import { LayoutResizer } from '@shared/workspace/LayoutResizer';
import { CHART_SHARE, DOCK_HEIGHT } from '@shared/workspace/sizes';

export interface BottomDockProps {
  symbol: string | null;
  chartOpen: boolean;
  fundamentalsOpen: boolean;
  height: number;
  chartShare: number;
  onToggleChart: () => void;
  onToggleFundamentals: () => void;
  onHeightChange: (height: number) => void;
  onChartShareChange: (share: number) => void;
}

export function BottomDock(props: BottomDockProps) {
  const {
    symbol, chartOpen, fundamentalsOpen, height, chartShare,
    onToggleChart, onToggleFundamentals, onHeightChange, onChartShareChange,
  } = props;
  const host = useRef<HTMLElement>(null);

  if (!chartOpen && !fundamentalsOpen) {
    return (
      <div data-testid="dock-collapsed"
        className="flex h-6 flex-none items-center gap-1 border-t border-line bg-panel px-2">
        <span className="t-85 text-text-3">داک بسته است</span>
        <button type="button" data-testid="dock-open-chart" className="tape-btn" onClick={onToggleChart}>چارت</button>
        <button type="button" data-testid="dock-open-fundamental" className="tape-btn" onClick={onToggleFundamentals}>بنیادی</button>
      </div>
    );
  }

  return (
    <section ref={host} data-testid="bottom-dock" style={{ height }}
      className="relative flex min-h-0 flex-none flex-col border-t border-line bg-panel">
      <LayoutResizer
        orientation="horizontal"
        value={height}
        min={DOCK_HEIGHT.min}
        max={DOCK_HEIGHT.max}
        step={8}
        defaultValue={DOCK_HEIGHT.default}
        label="ارتفاع داک پایین"
        testId="resize-dock"
        increaseKey="ArrowUp"
        decreaseKey="ArrowDown"
        fromPointer={(rect, _x, y) => rect.top + rect.height - y}
        measure={() => host.current?.getBoundingClientRect() ?? null}
        onChange={onHeightChange}
      />

      <div className="flex min-h-0 flex-1">
        {chartOpen ? (
          <div
            data-testid="dock-chart"
            style={fundamentalsOpen ? { width: `${Number((chartShare * 100).toFixed(2))}%` } : undefined}
            className={fundamentalsOpen ? 'min-h-0 min-w-0 flex-none' : 'min-h-0 min-w-0 flex-1'}
          >
            {symbol ? <ChartPanel symbol={symbol} /> : (
              <p data-testid="dock-chart-empty" className="grid h-full place-items-center px-2 t-95 text-text-3">
                برای چارت، نمادی را از تابلو انتخاب کن.
              </p>
            )}
          </div>
        ) : null}

        {chartOpen && fundamentalsOpen ? (
          <LayoutResizer
            orientation="vertical"
            value={chartShare}
            min={CHART_SHARE.min}
            max={CHART_SHARE.max}
            step={0.02}
            defaultValue={CHART_SHARE.default}
            label="عرض چارت"
            testId="resize-chart"
            increaseKey="ArrowLeft"
            decreaseKey="ArrowRight"
            fromPointer={(rect, x) => (rect.left + rect.width - x) / Math.max(1, rect.width)}
            measure={() => host.current?.getBoundingClientRect() ?? null}
            onChange={onChartShareChange}
          />
        ) : null}

        {fundamentalsOpen ? (
          <div data-testid="dock-fundamentals" className="min-h-0 min-w-0 flex-1 overflow-x-auto">
            {symbol ? <FundamentalCards symbol={symbol} /> : (
              <p data-testid="dock-fundamentals-empty" className="grid h-full place-items-center px-2 t-95 text-text-3">
                برای کارت‌های بنیادی، نمادی را از تابلو انتخاب کن.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
