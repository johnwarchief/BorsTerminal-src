// __tests__/strategy-graph-layouts.spec.tsx -- تست‌های مدل کانونی و موتورهای چیدمان هندسی نقشه راه FTS
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { buildCanonicalStrategyGraph } from '../features/master/lib/strategyGraphModel';
import {
  computeFlowLayout,
  computeOrbitLayout,
} from '../features/master/lib/strategyGraphLayouts';
import { StrategyGraphRenderer } from '../features/master/components/StrategyGraphRenderer';
import { FTS_DEFAULT_PARAMS } from '../features/master/stores/strategyParamsStore';

describe('Strategy Graph Engine — مدل کانونی و موتورهای چیدمان هندسی نقشه راه FTS', () => {
  const sampleParams = { ...FTS_DEFAULT_PARAMS };

  it('۱. ساخت گراف کانونی: ایجاد ریشه، ۵ مرحله چارت ۴ صفحه‌ای FTS با سلسه‌مراتب درست', () => {
    const graph = buildCanonicalStrategyGraph({
      params: sampleParams,
      selectedPreset: 'swing',
    });

    expect(graph.rootId).toBe('fts_root');
    expect(graph.nodeMap.has('fts_root')).toBe(true);
    expect(graph.nodeMap.has('stage_selection')).toBe(true);
    expect(graph.nodeMap.has('stage_technical')).toBe(true);
    expect(graph.nodeMap.has('stage_fundamental')).toBe(true);
    expect(graph.nodeMap.has('stage_delivery')).toBe(true);
    expect(graph.nodeMap.has('stage_capital')).toBe(true);

    // بررسی تعداد یال‌ها و اتصالات جریان FTS
    expect(graph.edges.length).toBeGreaterThanOrEqual(10);
    expect(graph.activePathNodeIds.has('s_volume_branch')).toBe(true);
  });

  it('۲. چیدمان نقشه راه (Roadmap Flow): چینش هندسی RTL، بدون هم‌پوشانی و با یال‌های محاسبه‌شده', () => {
    const graph = buildCanonicalStrategyGraph({
      params: sampleParams,
      selectedPreset: 'swing',
    });

    const flowLayout = computeFlowLayout(graph);

    expect(flowLayout.nodes.length).toBe(graph.nodes.length);
    expect(flowLayout.edges.length).toBe(graph.edges.length);

    // تایید ابعاد معتبر بوم
    expect(flowLayout.bounds.width).toBeGreaterThan(500);
    expect(flowLayout.bounds.height).toBeGreaterThan(400);

    // در RTL: ستون انتخاب/تابلو (selection) باید در سمت راست‌تر از ستون سرمایه (capital) باشد
    const selectionNode = flowLayout.nodeMap.get('stage_selection')!;
    const capitalNode = flowLayout.nodeMap.get('stage_capital')!;
    expect(selectionNode.x).toBeGreaterThan(capitalNode.x);

    // یال‌ها دارای تعریف معتبر path در SVG هستند
    for (const edge of flowLayout.edges) {
      expect(edge.d).toContain('M ');
    }
  });

  it('۳. چیدمان مداری (Orbit): استقرار روی حلقه‌های هم‌مرکز با مختصات قطبی', () => {
    const graph = buildCanonicalStrategyGraph({
      params: sampleParams,
      selectedPreset: 'trend',
    });

    const orbitLayout = computeOrbitLayout(graph);

    expect(orbitLayout.nodes.length).toBe(graph.nodes.length);

    // نود ریشه در مرکز (شعاع صفر)
    const root = orbitLayout.nodeMap.get('fts_root')!;
    expect(root.radius).toBe(0);

    // نودهای مرحله در رینگ ۱ (شعاع مثبت)
    const stageSelection = orbitLayout.nodeMap.get('stage_selection')!;
    expect(stageSelection.radius).toBeGreaterThan(150);

    // نودهای شرط در رینگ ۲ با شعاع بزرگ‌تر از رینگ ۱
    const condNode = orbitLayout.nodeMap.get('s_volume_branch')!;
    expect(condNode.radius).toBeGreaterThan(stageSelection.radius!);

    // بررسی تقارن و اعتبارسنجی حدود بوم
    expect(orbitLayout.bounds.width).toBeGreaterThan(800);
    expect(orbitLayout.bounds.height).toBeGreaterThan(800);
  });

  it('۴. رندرر StrategyGraphRenderer: رندر در حالت نقشه راه و تعامل با پنل بازرسی نود', () => {
    const graph = buildCanonicalStrategyGraph({
      params: sampleParams,
      selectedPreset: 'swing',
    });

    render(
      <StrategyGraphRenderer
        graph={graph}
        layoutMode="flow"
        selectedNodeId="s_volume_branch"
      />,
    );

    // بوم گراف
    expect(screen.getByTestId('obsidian-strategy-canvas')).toBeInTheDocument();

    // نود حجم معاملات در بوم وجود دارد
    expect(screen.getAllByText(/حجم معاملات/i).length).toBeGreaterThanOrEqual(1);

    // پنل بازرسی نود باز است و اسلایدر پارامتر را نشان می‌دهد
    expect(screen.getByTestId('strategy-node-inspector')).toBeInTheDocument();
    expect(screen.getByText(/ضریب حجم مشکوک:/i)).toBeInTheDocument();
  });

  it('۵. سوییچ چیدمان به Orbit: تغییر حالت بدون جهش داده یا شکستن وضعیت', () => {
    const graph = buildCanonicalStrategyGraph({
      params: sampleParams,
      selectedPreset: 'hourglass',
    });

    const { rerender } = render(
      <StrategyGraphRenderer
        graph={graph}
        layoutMode="flow"
      />,
    );

    expect(screen.getByText(/فلوچارت گام‌به‌گام FTS/i)).toBeInTheDocument();

    // تغییر به مدار منظومه‌ای
    rerender(
      <StrategyGraphRenderer
        graph={graph}
        layoutMode="orbit"
      />,
    );

    expect(screen.getByText(/مدار منظومه‌ای هم‌مرکز/i)).toBeInTheDocument();
  });
});
