// تست چیدمان Split View و همگام‌سازی کراس‌هیر/زوم (T-10 قطعهٔ ۲)
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ChartSyncBus, resetSyncBuses, syncBus } from '@features/technical/lib/chartSync';
import { SPLIT_GROUP, SplitChartView, splitPaneCount } from '@features/technical/components/SplitChartView';
import { FtsToolbar } from '@features/technical/components/FtsToolbar';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

vi.mock('@features/technical/components/KLineChartWrapper', () => ({
  KLineChartWrapper: (props: { syncKey?: string; layers?: unknown; height?: number }) => (
    <div
      data-testid="pane-stub"
      data-sync={props.syncKey ?? ''}
      data-layers={props.layers ? 'yes' : 'no'}
      data-height={String(props.height)}
    />
  ),
}));

const PALETTE = { up: '#10b981', down: '#f43f5e', grid: '#000', text: '#fff', background: '#0a0e17' };
const LAYERS = { maPeriods: null, jet: null, choch: null, fib: null, markers: [] };

afterEach(() => resetSyncBuses());

describe('باس همگام‌سازی چارت', () => {
  it('فرمان به همهٔ اعضای دیگر می‌رسد و فرستنده حذف می‌شود', () => {
    const bus = new ChartSyncBus();
    const a = vi.fn();
    const b = vi.fn();
    bus.register('a', a);
    bus.register('b', b);
    expect(bus.size()).toBe(2);
    bus.broadcast('a', { kind: 'crosshair', timestamp: 123 });
    expect(a).not.toHaveBeenCalled();
    expect(b).toHaveBeenCalledWith({ kind: 'crosshair', timestamp: 123 });
  });

  it('لغو ثبت و پاک‌سازی', () => {
    const bus = new ChartSyncBus();
    const off = bus.register('a', vi.fn());
    off();
    expect(bus.size()).toBe(0);
    bus.register('b', vi.fn());
    bus.clear();
    expect(bus.size()).toBe(0);
  });

  it('عضو خراب بقیه را متوقف نمی‌کند', () => {
    const bus = new ChartSyncBus();
    const ok = vi.fn();
    bus.register('bad', () => {
      throw new Error('boom');
    });
    bus.register('ok', ok);
    bus.broadcast('src', { kind: 'range', barSpace: 8, anchorTimestamp: 5 });
    expect(ok).toHaveBeenCalled();
  });

  it('syncBus برای یک گروه همان نمونه را می‌دهد', () => {
    expect(syncBus('g1')).toBe(syncBus('g1'));
    expect(syncBus('g1')).not.toBe(syncBus('g2'));
  });
});

describe('SplitChartView', () => {
  it('تعداد پنل‌ها بر اساس چیدمان', () => {
    expect(splitPaneCount(1)).toBe(1);
    expect(splitPaneCount(2)).toBe(2);
    expect(splitPaneCount(4)).toBe(4);
  });

  it('چیدمان ۴ ⇒ چهار پنل هم‌گروه و اورلی فقط روی پنل اول', () => {
    render(<SplitChartView layout={4} data={[]} palette={PALETTE} layers={LAYERS} />);
    const panes = screen.getAllByTestId('pane-stub');
    expect(panes).toHaveLength(4);
    expect(screen.getByTestId('split-view').getAttribute('data-layout')).toBe('4');
    for (const p of panes) expect(p.getAttribute('data-sync')).toBe(SPLIT_GROUP);
    expect(panes[0].getAttribute('data-layers')).toBe('yes');
    expect(panes[1].getAttribute('data-layers')).toBe('no');
    expect(panes[3].getAttribute('data-layers')).toBe('no');
  });

  it('چیدمان تک ⇒ یک پنل', () => {
    render(<SplitChartView layout={1} data={[]} palette={PALETTE} layers={LAYERS} />);
    expect(screen.getAllByTestId('pane-stub')).toHaveLength(1);
  });
});

describe('انتخاب چیدمان از تولبار', () => {
  it('کلیک روی «۲ چارت» چیدمان را در استور عوض می‌کند', () => {
    useFtsConfigStore.getState().setView({ splitLayout: 1 });
    render(<FtsToolbar />);
    fireEvent.click(screen.getByRole('button', { name: '۲ چارت' }));
    expect(useFtsConfigStore.getState().view.splitLayout).toBe(2);
    fireEvent.click(screen.getByRole('button', { name: 'تک' }));
    expect(useFtsConfigStore.getState().view.splitLayout).toBe(1);
  });
});
