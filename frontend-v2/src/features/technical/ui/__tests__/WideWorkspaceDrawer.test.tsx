/**
 * frontend-v2/src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx
 *
 * آزمون‌های یکپارچگی ستون عریض میزکارهای متنوع (WideWorkspaceDrawer):
 * ۱. رندر جدول ۵۰ نماد برتر بازار و سوییچ نماد با کلیک
 * ۲. فیلتر کردن نمادها در باکس جستجو
 * ۳. سوییچ میان تب‌های میزکار (۵۰ نماد، اندیکاتورها، اسکنر الگوها، لبه آماری)
 * ۴. تغییر مدهای کانال چندحالته و انتخاب‌گر دراپ‌داون فرمول‌های RSI
 * ۵. نمایش پنجره شناور پورتال با createPortal
 * ۶. جمع و باز شدن نوار با حفظ وضعیت
 */

import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WideWorkspaceDrawer } from '../WideWorkspaceDrawer';
import { useTechnicalStore } from '../../model/technicalStore';

vi.mock('@features/market/api/useBoard', () => ({
  useBoard: vi.fn(() => ({
    data: {
      data: [
        { symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات', p_last: 5850, percent_last: 2.5, q_tot_cap: 900_000_000_000, tvol: 150_000_000 },
        { symbol: 'فملی', name: 'ملی مس', sector_name: 'فلزات', p_last: 7420, percent_last: 1.8, q_tot_cap: 800_000_000_000, tvol: 100_000_000 },
        { symbol: 'شپنا', name: 'پالایش نفت', sector_name: 'نفت', p_last: 4610, percent_last: -0.6, q_tot_cap: 700_000_000_000, tvol: 120_000_000 },
      ],
    },
    isLoading: false,
    isError: false,
  })),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderDrawer(isOpen = true, onToggle = vi.fn()) {
  return render(
    <QueryClientProvider client={queryClient}>
      <WideWorkspaceDrawer
        activeSymbol="فولاد"
        isOpen={isOpen}
        onToggleOpen={onToggle}
      />
    </QueryClientProvider>
  );
}

describe('WideWorkspaceDrawer Component', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
    useTechnicalStore.getState().enableDefaultIndicators();
  });

  afterEach(cleanup);

  it('renders top 50 symbols tab by default with ranks, ticker, price and change', () => {
    renderDrawer();

    expect(screen.getByTestId('wide-workspace-drawer')).toBeDefined();
    expect(screen.getByTestId('top50-panel')).toBeDefined();
    expect(screen.getByTestId('top50-row-فولاد')).toBeDefined();
    expect(screen.getByTestId('top50-row-فملی')).toBeDefined();
  });

  it('filters symbols when user types into search input', () => {
    renderDrawer();

    const searchInput = screen.getByTestId('top50-search-input') as HTMLInputElement;
    fireEvent.change(searchInput, { target: { value: 'فملی' } });

    expect(screen.getByTestId('top50-row-فملی')).toBeDefined();
    expect(screen.queryByTestId('top50-row-فولاد')).toBeNull();
  });

  it('switches symbol in technicalStore on clicking a symbol row', () => {
    renderDrawer();

    const rowFmelli = screen.getByTestId('top50-row-فملی');
    fireEvent.click(rowFmelli);

    expect(useTechnicalStore.getState().selectedSymbol).toBe('فملی');
  });

  it('switches tabs and displays indicator catalog and mode switchers', () => {
    renderDrawer();

    const indTab = screen.getByTestId('drawer-tab-indicators');
    fireEvent.click(indTab);

    expect(screen.getByTestId('indicators-panel')).toBeDefined();
    expect(screen.queryByTestId('top50-panel')).toBeNull();

    // بررسی وجود اندیکاتورهای هوشمند
    expect(screen.getByTestId('toggle-indicator-DoubleTap3D')).toBeDefined();
    expect(screen.getByTestId('toggle-indicator-SuperTrendPullback')).toBeDefined();
    expect(screen.getByTestId('toggle-indicator-AutoTrendlineCHoCH')).toBeDefined();
    expect(screen.getByTestId('toggle-indicator-MultiModeChannel')).toBeDefined();
  });

  it('shows the telegram catalog as the third block of the indicators tab', () => {
    renderDrawer();
    fireEvent.click(screen.getByTestId('drawer-tab-indicators'));

    expect(screen.getByTestId('indicators-panel')).toBeDefined();
    expect(screen.getByTestId('telegram-catalog-list')).toBeDefined();
    expect(screen.getAllByTestId(/telegram-row-p\d{2}/).length).toBe(64);

    // بلوک سوم: پس از دو بخشِ موجود و درون خودِ پنل
    const blocks = Array.from(screen.getByTestId('indicators-panel').children);
    expect(blocks.length).toBe(3);
    expect(blocks[2].contains(screen.getByTestId('telegram-catalog-list'))).toBe(true);
  });

  it('toggles channel modes on button click in indicators panel', () => {
    renderDrawer();

    fireEvent.click(screen.getByTestId('drawer-tab-indicators'));

    // سوئیچر مد کانال
    const retestBtn = screen.getByTestId('channel-mode-btn-retest_channel');
    fireEvent.click(retestBtn);
    expect(useTechnicalStore.getState().channelMode).toBe('retest_channel');

    const donchianBtn = screen.getByTestId('channel-mode-btn-donchian');
    fireEvent.click(donchianBtn);
    expect(useTechnicalStore.getState().channelMode).toBe('donchian');
  });

  it('switches to scanner tab and displays detected patterns', () => {
    useTechnicalStore.getState().setDetectedDoubleTapPatterns([
      {
        id: 'pat-1',
        type: 'DOUBLE_TOP',
        peak1: { index: 5, price: 1200, timestamp: 1730000000000 },
        neckline: { index: 10, price: 1050, timestamp: 1730100000000 },
        peak2: { index: 15, price: 1205, timestamp: 1730200000000 },
        target1: 900,
        target2: 800,
        stopLoss: 1250,
        score: 92,
        quality: 92,
        height: 150,
        status: 'active',
      },
    ]);

    renderDrawer();

    fireEvent.click(screen.getByTestId('drawer-tab-scanner'));
    expect(screen.getByTestId('scanner-panel')).toBeDefined();
    expect(screen.getByText('سقف دوقلو (M)')).toBeDefined();
  });

  it('keeps every tab label at the 11px floor', () => {
    renderDrawer();
    for (const id of ['top50', 'indicators', 'scanner', 'patterns', 'edge']) {
      const tab = screen.getByTestId(`drawer-tab-${id}`);
      expect(tab.className).toContain('text-[11px]');
      expect(tab.className).not.toContain('t-95');
    }
  });

  it('renders collapsed mini-bar when isOpen is false', () => {
    const onToggle = vi.fn();
    renderDrawer(false, onToggle);

    expect(screen.getByTestId('wide-workspace-drawer-collapsed')).toBeDefined();
    expect(screen.queryByTestId('wide-workspace-drawer')).toBeNull();

    const openBtn = screen.getByTitle('باز کردن سایدبار لبه آماری');
    fireEvent.click(openBtn);
    expect(onToggle).toHaveBeenCalled();
  });

  it('opens portal modal backdrop when portal button is clicked', () => {
    renderDrawer();

    const portalBtn = screen.getByTestId('portal-modal-btn');
    fireEvent.click(portalBtn);

    expect(screen.getByTestId('portal-modal-backdrop')).toBeDefined();
  });

  it('resizes drawer when resizer handle is dragged to the right', () => {
    useTechnicalStore.getState().setLeftDrawerWidth(400);
    renderDrawer();

    const handle = screen.getByTestId('drawer-resizer-handle');
    fireEvent.mouseDown(handle, { clientX: 400 });

    fireEvent(window, new MouseEvent('mousemove', { clientX: 470 }));
    expect(useTechnicalStore.getState().leftDrawerWidth).toBe(470);

    fireEvent(window, new MouseEvent('mouseup'));
  });

  it('falls back to 50 top market symbols when board query data is unavailable', async () => {
    const { useBoard } = await import('@features/market/api/useBoard');
    vi.mocked(useBoard).mockReturnValueOnce({
      data: undefined,
      isLoading: true,
      isError: false,
    } as any);

    renderDrawer();
    const tabBtn = screen.getByTestId('drawer-tab-top50');
    expect(tabBtn.textContent).toContain('۵۰');
  });

  it('renders category filter chips and filters symbol list by category', () => {
    renderDrawer();

    expect(screen.getByTestId('category-filter-all')).toBeDefined();
    expect(screen.getByTestId('category-filter-stock')).toBeDefined();
    expect(screen.getByTestId('category-filter-right')).toBeDefined();
    expect(screen.getByTestId('category-filter-fund')).toBeDefined();

    // فیلتر سهام عادی (فولاد، فملی، شپنا همه سهام عادی هستند)
    fireEvent.click(screen.getByTestId('category-filter-stock'));
    expect(screen.getByTestId('top50-row-فولاد')).toBeDefined();

    // فیلتر حق تقدم (در دیتای ماک حق تقدم نیست)
    fireEvent.click(screen.getByTestId('category-filter-right'));
    expect(screen.queryByTestId('top50-row-فولاد')).toBeNull();

    // بازگشت به همه
    fireEvent.click(screen.getByTestId('category-filter-all'));
    expect(screen.getByTestId('top50-row-فولاد')).toBeDefined();
  });

  it('renders signal column and signal badges for symbols in top 50 table', () => {
    renderDrawer();

    // سرستون سیگنال
    expect(screen.getByText('سیگنال')).toBeDefined();

    // ردیف فولاد با مقدار مثبت ۲.۵ درصد سیگنال تولید می‌کند
    const signalCell = screen.getByTestId('top50-signal-فولاد');
    expect(signalCell).toBeDefined();
    expect(signalCell.textContent).toBeTruthy();
  });

  it('renders slim activity bar with 4 icons and allows switching / collapsing tabs', () => {
    const onToggle = vi.fn();
    renderDrawer(true, onToggle);

    // نوار فعالیت باریک
    expect(screen.getByTestId('slim-activity-bar')).toBeDefined();
    expect(screen.getByTestId('activity-bar-icon-top50')).toBeDefined();
    expect(screen.getByTestId('activity-bar-icon-indicators')).toBeDefined();
    expect(screen.getByTestId('activity-bar-icon-scanner')).toBeDefined();
    expect(screen.getByTestId('activity-bar-icon-edge')).toBeDefined();

    // کلیک روی آیکون اندیکاتور در نوار باریک
    fireEvent.click(screen.getByTestId('activity-bar-icon-indicators'));
    expect(screen.getByTestId('indicators-panel')).toBeDefined();

    // کلیک مجدد روی تب فعال جهت جمع شدن نوار
    fireEvent.click(screen.getByTestId('activity-bar-icon-indicators'));
    expect(onToggle).toHaveBeenCalled();
  });
});
