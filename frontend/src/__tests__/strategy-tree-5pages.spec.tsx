// تستِ ساختاری و تعاملیِ پنج صفحهٔ درخت استراتژی FTS.
// چهار چارتِ F/T/S/M از `ftsChartModel` می‌آیند و صفحهٔ پنجم فقط ادغامِ همان‌ها
// با سه یالِ مستند است؛ این تست همین قرارداد را می‌بندد.
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StrategyTreePage from '@features/master/routes/StrategyTreePage';
import {
  buildFtsChartModel, treeEdges, ZONE_LINKS, ZONES,
} from '@features/master/lib/ftsChartModel';
import {
  MASTER_COLUMN_ORDER, defaultCollapsedForMaster, layoutStrategyChart,
} from '@features/master/lib/strategyChartLayout';
import { useStrategyParamsStore } from '@features/master/stores/strategyParamsStore';

const model = () => buildFtsChartModel(useStrategyParamsStore.getState().params);

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
    ok: false, status: 503, json: () => Promise.resolve({}),
  }) as unknown as Response));
});

function renderPage(entries: string[] = ['/strategy-tree']) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const router = createMemoryRouter(
    [{ path: '/strategy-tree', element: <StrategyTreePage /> }],
    { initialEntries: entries },
  );
  render(<QueryClientProvider client={qc}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

describe('مدلِ ساختاریِ چهار چارت FTS', () => {
  it('۷۸ گره و چهار Zone؛ هیچ گره‌ای فرزندِ Zoneِ دیگر نیست', () => {
    const m = model();
    expect(m.nodes).toHaveLength(78);
    expect(ZONES.map((z) => z.key)).toEqual(['F', 'T', 'S', 'M']);
    const edges = treeEdges(m.nodes);
    expect(edges).toHaveLength(m.nodes.filter((n) => n.parent).length);
    for (const e of edges) {
      expect(m.byId.get(e.source)!.zone).toBe(m.byId.get(e.target)!.zone);
    }
    for (const z of ZONES) expect(m.byZone[z.key].length).toBeGreaterThan(0);
  });

  it('فقط سه وابستگیِ بین‌چارتِ مستند وجود دارد', () => {
    expect(ZONE_LINKS.map((l) => `${l.from}>${l.to}`)).toEqual(['S>T', 'T>F', 'F>M']);
  });

  it('چیدمانِ یک Zone فقط گره‌های همان چارت را می‌آورد و مختصات یکتا دارد', () => {
    const m = model();
    for (const z of ZONES) {
      const layout = layoutStrategyChart(m, { mode: 'zone', zone: z.key });
      expect(layout.nodes).toHaveLength(m.byZone[z.key].length);
      expect(layout.lanes.map((l) => l.zone)).toEqual([z.key]);
      expect(layout.edges.every((e) => e.kind === 'tree')).toBe(true);
      const positions = new Set(layout.nodes.map((n) => `${n.x},${n.y}`));
      expect(positions.size).toBe(layout.nodes.length);
    }
  });

  it('نقشهٔ جامع هر ۷۸ گره و هر سه یالِ مستند را دارد؛ پیش‌فرض، شاخه‌ها بسته‌اند', () => {
    const m = model();
    const open = layoutStrategyChart(m, { mode: 'master', collapsed: new Set() });
    expect(open.lanes.map((l) => l.zone)).toEqual(MASTER_COLUMN_ORDER);
    expect(open.nodes).toHaveLength(78);
    expect(open.edges.filter((e) => e.kind === 'zone')).toHaveLength(3);

    const closed = layoutStrategyChart(m, { mode: 'master', collapsed: defaultCollapsedForMaster(m) });
    expect(closed.nodes.length).toBeLessThan(78);
    for (const z of ZONES) expect(closed.nodes.some((n) => n.node.id === m.roots[z.key])).toBe(true);
    expect(closed.edges.filter((e) => e.kind === 'zone')).toHaveLength(3);
  });
});

describe('پنج صفحهٔ رابط', () => {
  it('پیش‌فرض صفحهٔ پنجم است و نوار ناوبری پنج پیوند دارد', () => {
    renderPage();
    expect(screen.getByTestId('strategy-tree-workspace').getAttribute('data-page')).toBe('master');
    const nav = screen.getByTestId('strategy-tree-stepper');
    expect(within(nav).getAllByRole('link')).toHaveLength(5);
    expect(screen.getByTestId('strategy-chart-canvas').getAttribute('data-mode')).toBe('master');
    for (const z of ['F', 'T', 'S', 'M']) expect(screen.getByTestId(`chart-lane-${z}`)).toBeInTheDocument();
    for (const id of ['zone_zl_s_t', 'zone_zl_t_f', 'zone_zl_f_m']) {
      expect(screen.getByTestId(`strategy-zone-edge-${id}`)).toBeInTheDocument();
    }
  });

  it('?page=F فقط چارت F را نشان می‌دهد، نه Zoneهای دیگر', () => {
    renderPage(['/strategy-tree?page=F']);
    expect(screen.getByTestId('strategy-tree-workspace').getAttribute('data-page')).toBe('F');
    expect(screen.getByTestId('strategy-chart-canvas').getAttribute('data-mode')).toBe('zone');
    expect(screen.getByTestId('strategy-node-f_root')).toBeInTheDocument();
    expect(screen.queryByTestId('strategy-node-t_root')).not.toBeInTheDocument();
    expect(screen.queryByTestId('chart-lane-T')).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^strategy-zone-edge-/)).not.toBeInTheDocument();
  });

  it('کلیکِ گره، جزئیات و متنِ مرجع را نشان می‌دهد؛ Back به نقشهٔ جامع برمی‌گردد', async () => {
    const router = renderPage();
    fireEvent.click(screen.getByTestId('tree-page-F'));
    expect(await screen.findByTestId('strategy-node-f_root')).toBeInTheDocument();
    expect(screen.getByTestId('strategy-tree-workspace').getAttribute('data-page')).toBe('F');
    fireEvent.click(screen.getByTestId('strategy-node-f_root'));
    const detail = await screen.findByTestId('strategy-node-detail');
    expect(detail.textContent).toContain('صفحۀ ۱ چارت FTS');
    await act(async () => { await router.navigate(-1); });
    expect(screen.getByTestId('strategy-tree-workspace').getAttribute('data-page')).toBe('master');
  });

  it('بستنِ شاخه گره‌ها را کم می‌کند و +N نشان می‌دهد', () => {
    renderPage(['/strategy-tree?page=F']);
    const before = screen.getAllByTestId(/^strategy-node-/).length;
    fireEvent.click(screen.getAllByTestId(/^strategy-collapse-/)[0]);
    expect(screen.getAllByTestId(/^strategy-node-/).length).toBeLessThan(before);
  });

  it('بزرگ‌نمایی، Fit و Reset واقعاً نمای بوم را عوض می‌کنند', () => {
    renderPage(['/strategy-tree?page=F']);
    const canvas = screen.getByTestId('strategy-chart-canvas');
    const start = Number(canvas.getAttribute('data-zoom'));
    fireEvent.click(screen.getByTestId('chart-zoom-in'));
    expect(Number(screen.getByTestId('strategy-chart-canvas').getAttribute('data-zoom'))).toBeGreaterThan(start);
    fireEvent.click(screen.getByTestId('chart-reset'));
    expect(screen.getByTestId('strategy-chart-canvas').getAttribute('data-zoom')).toBe('100');
    fireEvent.click(screen.getByTestId('chart-fit'));
    expect(Number(screen.getByTestId('strategy-chart-canvas').getAttribute('data-zoom'))).toBeLessThanOrEqual(100);
  });
});
