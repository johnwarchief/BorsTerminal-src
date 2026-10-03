// RA-3: قالبِ چارت — ذخیره و اعمالِ همان مطالعه‌هایی که روشن‌اند
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useChartTemplateStore,
  CHART_TEMPLATE_KEY,
} from '@features/technical/stores/chartTemplateStore';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

let lastChartInstance: ReturnType<typeof chartStub> | null = null;

const chartStub = () => {
  const instance = {
    setDataLoader: vi.fn(),
    setSymbol: vi.fn(),
    setPeriod: vi.fn(),
    setFormatter: vi.fn(),
    createIndicator: vi.fn(),
    removeIndicator: vi.fn(),
    setPaneOptions: vi.fn(),
    setStyles: vi.fn(),
    overrideYAxis: vi.fn(),
    overrideOverlay: vi.fn(),
    removeOverlay: vi.fn(),
    createOverlay: vi.fn(() => 'ov-1'),
    resetData: vi.fn(),
    resize: vi.fn(),
    getConvertPictureUrl: vi.fn(() => ''),
    subscribeAction: vi.fn(),
    scrollToRealTime: vi.fn(),
    getDataList: vi.fn(() => []),
    setScrollEnabled: vi.fn(),
    getOverlays: vi.fn(() => [] as Record<string, unknown>[]),
    getSupportedIndicators: vi.fn(() => [] as string[]),
    setOffsetRightDistance: vi.fn(),
  };
  lastChartInstance = instance;
  return instance;
};

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(),
  registerOverlay: vi.fn(),
  registerIndicator: vi.fn(),
  getSupportedOverlays: vi.fn(() => []),
  getSupportedIndicators: vi.fn(() => []),
}));

const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');

function chart() {
  if (!lastChartInstance) throw new Error('chart stub هنوز ساخته نشده');
  return lastChartInstance;
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  lastChartInstance = null;
  useChartTemplateStore.setState({ templates: [] });
  useFtsConfigStore.getState().setPriceScale('normal');
});

describe('استورِ قالب', () => {
  it('بی‌نام ذخیره نمی‌شود', () => {
    expect(useChartTemplateStore.getState().saveTemplate({ name: '  ', indicators: ['MA'] })).toBeNull();
    expect(useChartTemplateStore.getState().templates).toHaveLength(0);
  });

  it('همان نام بازنویسی می‌شود، نه ردیفِ دوم', () => {
    useChartTemplateStore.getState().saveTemplate({ name: 'روزانه', indicators: ['MA'] });
    useChartTemplateStore.getState().saveTemplate({ name: 'روزانه', indicators: ['MA', 'RSI'] });
    const t = useChartTemplateStore.getState().templates;
    expect(t).toHaveLength(1);
    expect(t[0].indicators).toEqual(['MA', 'RSI']);
  });

  it('روی localStorage می‌نشیند و ردیفِ خرابِ ذخیره‌شده بارگذاری نمی‌شود', async () => {
    useChartTemplateStore.getState().saveTemplate({
      name: 'فنی',
      indicators: ['VOL', 'MA'],
      timeframe: 'D',
      candleType: 'candle_solid',
      adjustment: 'combined',
      priceScale: 'normal',
    });
    const raw = JSON.parse(localStorage.getItem(CHART_TEMPLATE_KEY) ?? '{}');
    expect(raw.templates).toHaveLength(1);
    localStorage.setItem(
      CHART_TEMPLATE_KEY,
      JSON.stringify({ templates: [...raw.templates, { name: '', indicators: ['X'] }, { nope: 1 }, '_hi_'] }),
    );
    vi.resetModules();
    const mod = await import('@features/technical/stores/chartTemplateStore');
    const loaded = mod.useChartTemplateStore.getState().templates;
    expect(loaded).toHaveLength(1);
    expect(loaded[0].name).toBe('فنی');
    // نامِ مطالعۀ ناشناخته هم حفظ می‌شود؛ حذفش معنی‌اش این است که قالبِ کاربر
    // با هر بارِ راه‌اندازی یک مطالعه کم بیاورد
    expect(loaded[0].indicators).toEqual(['VOL', 'MA']);
  });
});

describe('قالب در منوی اندیکاتورها', () => {
  const openModal = () => {
    fireEvent.click(screen.getByTitle('پنل اندیکاتورها'));
  };

  it('ذخیره، مطالعه‌هایِ روشنِ همین چارت را برداشته و اعمال دوباره روشنشان می‌کند', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" initialName="فولاد مبارکه" />);
    openModal();
    expect(screen.getByTestId('template-empty')).toBeInTheDocument();

    // MA را روشن کن (پنلِ کندل ⇒ createIndicator با paneId کندل)
    fireEvent.click(screen.getByText('میانگین متحرک ساده (MA 14/100)'));
    expect(chart().createIndicator).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'MA', paneId: 'candle_pane' }),
      true,
    );

    fireEvent.change(screen.getByTestId('template-name'), { target: { value: 'قالبِ من' } });
    fireEvent.click(screen.getByTestId('template-save'));

    const saved = useChartTemplateStore.getState().templates;
    expect(saved).toHaveLength(1);
    expect(saved[0].name).toBe('قالبِ من');
    expect(saved[0].indicators).toEqual(expect.arrayContaining(['MA', 'VOL']));
    expect(saved[0].timeframe).toBe('D');

    // MA را خاموش کن، بعد قالب را اعمال ⇒ دوباره ساخته می‌شود
    fireEvent.click(screen.getByText('میانگین متحرک ساده (MA 14/100)'));
    expect(chart().removeIndicator).toHaveBeenCalledWith({ name: 'MA' });
    chart().createIndicator.mockClear();

    fireEvent.click(screen.getByTestId(`template-apply-${saved[0].id}`));
    expect(chart().createIndicator).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'MA', paneId: 'candle_pane' }),
      true,
    );
  });

  it('نامِ مطالعۀ ثبت‌نشده در قالب، چارت را نمی‌شکند و ساخته نمی‌شود', () => {
    // پیش از mount ذخیره می‌شود تا اشتراکِ زندهٔ کامپوننت هشدار act ندهد
    const saved = useChartTemplateStore.getState().saveTemplate({
      name: 'با نامِ جعلی',
      indicators: ['NOT_REGISTERED_AT_ALL', 'VOL'],
    })!;
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    openModal();
    chart().createIndicator.mockClear();
    fireEvent.click(screen.getByTestId(`template-apply-${saved.id}`));
    const names = chart().createIndicator.mock.calls.map((c) => (c[0] as { name?: string })?.name);
    expect(names).not.toContain('NOT_REGISTERED_AT_ALL');
  });

  it('حذفِ قالب، ردیفش را از فهرست می‌برد', () => {
    const saved = useChartTemplateStore.getState().saveTemplate({ name: 'موقت', indicators: ['VOL'] })!;
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    openModal();
    expect(screen.getByTestId(`template-row-${saved.id}`)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId(`template-remove-${saved.id}`));
    expect(screen.getByTestId('template-empty')).toBeInTheDocument();
  });

  // capabilityِ منبع: بازۀ درون‌روزی سورسِ داده ندارد، پس قالبِ کهنه آن را
  // «سرو» نمی‌کند — تنزلِ صریح به روزانه با دلیلِ خوانا.
  it('قالبِ با بازۀ درون‌روزی ⇒ تنزلِ صریح به روزانه و نمایشِ دلیل، نه برچسبِ جعلی', () => {
    // هر دو قالب پیش از mount ذخیره می‌شوند (اشتراکِ زندهٔ منو وسطِ تست هشدار act می‌دهد)
    const saved = useChartTemplateStore.getState().saveTemplate({
      name: 'دقیقه‌ایِ قدیمی', indicators: ['VOL'], timeframe: '1m',
    })!;
    const w = useChartTemplateStore.getState().saveTemplate({
      name: 'هفتگی', indicators: ['VOL'], timeframe: 'W',
    })!;
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    openModal();
    expect(screen.queryByTestId('chart-timeframe-note')).toBeNull();

    fireEvent.click(screen.getByTestId(`template-apply-${saved.id}`));
    const note = screen.getByTestId('chart-timeframe-note');
    expect(note.textContent).toContain('1m');
    expect(note.textContent).toContain('روزانه');

    // هیچ دوره‌ای جز روز/هفته/ماه به موتور نمی‌رود — یعنی کندلِ روزانه زیرِ
    // برچسبِ «دقیقه‌ای» سرو نمی‌شود (دو فراخوانِ mount حداقلِ پوشش است)
    const periods = chart().setPeriod.mock.calls.map(([p]) => (p as { type?: string })?.type);
    expect(periods.length).toBeGreaterThan(0);
    for (const p of periods) expect(['day', 'week', 'month']).toContain(p);
    expect(periods).not.toContain('minute');
    expect(periods).not.toContain('hour');

    // کنترلِ مثبت: قالبِ با بازۀ واقعی همان بازه را می‌گیرد و یادداشت می‌رود
    fireEvent.click(screen.getByTestId(`template-apply-${w.id}`));
    expect(screen.queryByTestId('chart-timeframe-note')).toBeNull();
    expect(
      chart().setPeriod.mock.calls.some(([p]) => (p as { type?: string })?.type === 'week'),
    ).toBe(true);
  });
});
