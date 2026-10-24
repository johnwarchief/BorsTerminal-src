import React, { useEffect, useRef } from 'react';
import { init, dispose } from 'klinecharts';

function palette(theme) {
  return theme === 'light'
    ? { bg: '#ffffff', grid: '#e5ebf3', text: '#64748b', up: '#16a34a', down: '#dc2626', accent: '#0284c7' }
    : { bg: '#0d121b', grid: '#1c2635', text: '#6f8199', up: '#22c55e', down: '#f43f5e', accent: '#38bdf8' };
}

function applyStyles(chart, theme) {
  const c = palette(theme);
  try {
    chart.setStyles({
      grid: {
        horizontal: { color: c.grid, style: 'dashed', size: 1 },
        vertical: { color: c.grid, style: 'dashed', size: 1 },
      },
      candle: {
        bar: {
          upColor: c.up,
          downColor: c.down,
          noChangeColor: c.text,
          upBorderColor: c.up,
          downBorderColor: c.down,
          upWickColor: c.up,
          downWickColor: c.down,
        },
        priceMark: {
          last: { text: { backgroundColor: c.accent } },
        },
      },
      xAxis: {
        axisLine: { color: c.grid },
        tickLine: { color: c.grid },
        tickText: { color: c.text, size: 10 },
      },
      yAxis: {
        axisLine: { color: c.grid },
        tickLine: { color: c.grid },
        tickText: { color: c.text, size: 10 },
      },
      separator: { color: c.grid },
      crosshair: {
        horizontal: { line: { color: c.accent, style: 'dashed' }, text: { backgroundColor: c.accent } },
        vertical: { line: { color: c.accent, style: 'dashed' }, text: { backgroundColor: c.accent } },
      },
      indicator: {
        lines: [
          { color: c.accent, size: 1.1 },
          { color: '#f59e0b', size: 1.1 },
          { color: '#a78bfa', size: 1.1 },
        ],
        bars: [{ upColor: c.up, downColor: c.down, noChangeColor: c.text }],
      },
    });
  } catch {
    /* older/newer style schema — the chart still renders with defaults */
  }
}

const PERIOD = { day: 'day', week: 'week', month: 'month' };

export function Chart({ candles, theme, symbol, timeframe, chartType, indicators, drawTool, onDrawError }) {
  const mountRef = useRef(null);
  const chartRef = useRef(null);
  const dataRef = useRef(candles);
  const rsiPaneRef = useRef(false);
  const overlayRef = useRef(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return undefined;
    let chart;
    try {
      chart = init(el);
    } catch (e) {
      onDrawError?.(`راه‌اندازی موتور چارت ناموفق بود: ${e?.message || e}`);
      return undefined;
    }
    chartRef.current = chart;
    dataRef.current = candles;
    applyStyles(chart, theme);
    try {
      chart.setDataLoader({
        getBars: ({ callback }) => callback(dataRef.current, { forward: false, backward: false }),
      });
      chart.setSymbol({ ticker: symbol || 'X', pricePrecision: 0, volumePrecision: 0 });
      chart.setPeriod({ span: 1, type: PERIOD[timeframe] || 'day' });
      chart.createIndicator({ name: 'VOL', id: 'vol', paneId: 'vol' }, false);
      chart.setPaneOptions({ id: 'vol', height: 78, minHeight: 56 });
      chart.resetData();
      chart.scrollToRealTime();
    } catch (e) {
      onDrawError?.(`تنظیم چارت ناموفق بود: ${e?.message || e}`);
    }
    rsiPaneRef.current = false;

    let ro = null;
    try {
      ro = new ResizeObserver(() => {
        try { chart.resize(); } catch { /* disposed */ }
      });
      ro.observe(el);
    } catch { /* no ResizeObserver */ }

    return () => {
      try { ro?.disconnect(); } catch { /* noop */ }
      try { dispose(el); } catch { /* noop */ }
      chartRef.current = null;
      rsiPaneRef.current = false;
    };
    // symbol/timeframe/theme intentionally re-init: it is the only path that is
    // verified stable across KLineCharts 10.0.3 for pane + style replacement.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme, symbol, timeframe]);

  useEffect(() => {
    dataRef.current = candles;
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.resetData();
      chart.scrollToRealTime();
    } catch { /* chart not ready */ }
  }, [candles]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try { chart.setStyles({ candle: { type: chartType === 'area' ? 'area' : 'candle' } }); } catch { /* noop */ }
  }, [chartType]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const name of ['MA', 'BOLL']) {
      try { chart.removeIndicator({ name }); } catch { /* absent */ }
    }
    try {
      if (indicators.ma) chart.createIndicator({ name: 'MA', id: 'ma', paneId: 'candle_pane', calcParams: [5, 10, 20] }, false);
      if (indicators.boll) chart.createIndicator({ name: 'BOLL', id: 'boll', paneId: 'candle_pane' }, false);
    } catch { /* unsupported */ }
    if (indicators.rsi && !rsiPaneRef.current) {
      try {
        chart.createIndicator({ name: 'RSI', id: 'rsi', paneId: 'rsi' });
        chart.setPaneOptions({ id: 'rsi', height: 72, minHeight: 52 });
        rsiPaneRef.current = true;
      } catch { /* unsupported */ }
    } else if (!indicators.rsi && rsiPaneRef.current) {
      try { chart.removeIndicator({ name: 'RSI' }); } catch { /* absent */ }
      rsiPaneRef.current = false;
    }
  }, [indicators]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !drawTool) return;
    try {
      if (overlayRef.current) {
        try { chart.removeOverlay({ id: overlayRef.current }); } catch { /* noop */ }
      }
      overlayRef.current = chart.createOverlay({ name: drawTool.name, paneId: 'candle_pane' }) || null;
    } catch (e) {
      onDrawError?.(`این ابزار ترسیم در موتور فعلی پشتیبانی نشد: ${drawTool.name}`);
    }
  }, [drawTool, onDrawError]);

  return (
    <div className="chart-host" data-testid="chart-host">
      <div ref={mountRef} style={{ position: 'absolute', inset: 0 }} />
    </div>
  );
}
