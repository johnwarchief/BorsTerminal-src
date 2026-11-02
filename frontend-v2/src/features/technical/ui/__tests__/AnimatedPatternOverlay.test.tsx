import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { AnimatedPatternOverlay } from '../AnimatedPatternOverlay';
import type { DoubleTapPattern } from '../../model/types';

describe('AnimatedPatternOverlay', () => {
  afterEach(cleanup);

  const mockChart: any = {
    convertToPixel: vi.fn(({ dataIndex, value }: any) => {
      return { x: dataIndex * 50 + 20, y: Math.max(10, 500 - value * 0.2) };
    }),
    subscribeAction: vi.fn(),
    unsubscribeAction: vi.fn(),
  };

  const samplePattern: DoubleTapPattern = {
    id: 'dt-1',
    type: 'DOUBLE_TOP',
    origin: { index: 2, price: 950, timestamp: 1729900000000 },
    peak1: { index: 5, price: 1200, timestamp: 1730000000000 },
    neckline: { index: 10, price: 1050, timestamp: 1730100000000 },
    peak2: { index: 15, price: 1205, timestamp: 1730200000000 },
    retest: { index: 18, price: 1050, timestamp: 1730300000000 },
    breakoutIndex: 18,
    target1: 900,
    target2: 800,
    stopLoss: 1250,
    score: 88,
    height: 150,
    status: 'active',
  };

  it('renders nothing when active is false or patterns is empty or chart is null', () => {
    const { container: c1 } = render(
      <AnimatedPatternOverlay chart={mockChart} patterns={[]} active={true} />
    );
    expect(c1.firstChild).toBeNull();

    const { container: c2 } = render(
      <AnimatedPatternOverlay chart={mockChart} patterns={[samplePattern]} active={false} />
    );
    expect(c2.firstChild).toBeNull();

    const { container: c3 } = render(
      <AnimatedPatternOverlay chart={null} patterns={[samplePattern]} active={true} />
    );
    expect(c3.firstChild).toBeNull();
  });

  it('renders animated SVG neckline, 5 halos, 5-point polyline, and badge with chart event subscriptions', () => {
    render(
      <AnimatedPatternOverlay chart={mockChart} patterns={[samplePattern]} active={true} />
    );

    // بررسی اشتراک در رویدادهای زوم و اسکرول چارت
    expect(mockChart.subscribeAction).toHaveBeenCalledWith('onZoom', expect.any(Function));
    expect(mockChart.subscribeAction).toHaveBeenCalledWith('onScroll', expect.any(Function));

    const overlay = screen.getByTestId('animated-pattern-overlay');
    expect(overlay).toBeDefined();

    const patternGroup = screen.getByTestId('animated-pattern-dt-1');
    expect(patternGroup).toBeDefined();

    // بررسی خط گردن نئونی متحرک
    const neckline = patternGroup.querySelector('.double-tap-neckline-animated');
    expect(neckline).toBeDefined();

    // بررسی ۵ حلقه هاله پالس برای ۵ نقطه الگوی کامل M
    const halos = patternGroup.querySelectorAll('.double-tap-halo-animated');
    expect(halos.length).toBe(5);

    // بررسی ساقه ۵ نقطه‌ای M با انیمیشن شارش خط‌چین
    const legPolyline = patternGroup.querySelector('.double-tap-leg-animated');
    expect(legPolyline).toBeDefined();
    const pointsAttr = legPolyline?.getAttribute('points');
    expect(pointsAttr?.trim().split(' ').length).toBe(5);

    // بررسی برچسب شناور
    const badge = patternGroup.querySelector('.double-tap-badge-animated');
    expect(badge).toBeDefined();
    expect(badge?.textContent).toContain('الگوی M');
  });
});
