import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { calcFibPrice, TV_FIB_LEVELS } from '@features/technical/lib/ftsOverlays';
import {
  saveSymbolDrawings,
  loadSymbolDrawings,
  clearSymbolDrawings,
  symbolDrawKey,
  SYMBOL_DRAW_PREFIX,
  type StoredOverlay,
} from '@features/technical/lib/drawStore';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';
import { MarketDepthWidget } from '@features/technical/components/MarketDepthWidget';

// Mock klinecharts API for testing KLineChartWrapper
const mockChartInstance = {
  setDataLoader: vi.fn(),
  setSymbol: vi.fn(),
  setPeriod: vi.fn(),
  resetData: vi.fn(),
  scrollToRealTime: vi.fn(),
  setStyles: vi.fn(),
  createIndicator: vi.fn(),
  setPaneOptions: vi.fn(),
  createOverlay: vi.fn((opts) => opts?.id || 'overlay_1'),
  overrideOverlay: vi.fn(),
  removeOverlay: vi.fn(),
  getOverlays: vi.fn(() => []),
  overrideYAxis: vi.fn(),
  resize: vi.fn(),
  getConvertPictureUrl: vi.fn(() => 'data:image/png;base64,'),
  getCrosshair: vi.fn(() => ({
    dataIndex: 5,
    kLineData: { timestamp: 1700000000000, open: 1000, high: 1200, low: 950, close: 1100, volume: 100000 },
  })),
};

vi.mock('klinecharts', () => ({
  init: vi.fn(() => mockChartInstance),
  dispose: vi.fn(),
  registerOverlay: vi.fn(),
}));

// سه عضو کافی است؛ بقیۀ KLineChartsApi در این تست ساخته نمی‌شود،
// پس روی نوعِ کاملِ window نمی‌نشیند و از یک رکوردِ آزاد خوانده می‌شود.
const fakeGlobal = window as unknown as { klinecharts: Record<string, unknown> };
fakeGlobal.klinecharts = {
  init: vi.fn(() => mockChartInstance),
  dispose: vi.fn(),
  registerOverlay: vi.fn(),
};

// این اسپک KLineChartWrapperِ کامل را با importِ پویا می‌سازد؛ زیرِ بارِ موازی
// ۵ ثانیۀ پیش‌فرض کم است و تستِ سوخته DOM را برای تستِ بعدی باز می‌گذارد
// («Found multiple elements by [data-testid=axis-btn-log]»).
describe('۷ قابلیت کلیدی چارت سامانه نهایت‌نگر (TradingView Standards)', { timeout: 20_000 }, () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  // فاز ۱: کلیدهای مینیاتوری محور قیمت (Log / Auto / %)
  describe('فاز ۱: کلیدهای مینیاتوری محور قیمت (Price Axis Quick Buttons)', () => {
    it('کلیدهای مینیاتوری %, log, auto در گوشه چارت رندر می‌شوند', async () => {
      const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
      render(<KLineChartWrapper initialSymbol="فولاد" />);

      const axisBtns = screen.getByTestId('price-axis-buttons');
      expect(axisBtns).toBeTruthy();

      const btnPercent = screen.getByTestId('axis-btn-percent');
      const btnLog = screen.getByTestId('axis-btn-log');
      const btnAuto = screen.getByTestId('axis-btn-auto');

      expect(btnPercent).toBeTruthy();
      expect(btnLog).toBeTruthy();
      expect(btnAuto).toBeTruthy();
    });

    it('کلیک روی کلید log مقیاس را لگاریتمی کرده و به overrideYAxis ارسال می‌کند', async () => {
      const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
      render(<KLineChartWrapper initialSymbol="فولاد" />);

      const btnLog = screen.getByTestId('axis-btn-log');
      fireEvent.click(btnLog);

      expect(mockChartInstance.overrideYAxis).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'logarithm' })
      );
      expect(useFtsConfigStore.getState().priceScale).toBe('logarithm');
    });

    it('کلیک روی کلید % مقیاس را درصدی (percentage) می‌کند', async () => {
      const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
      render(<KLineChartWrapper initialSymbol="فولاد" />);

      const btnPercent = screen.getByTestId('axis-btn-percent');
      fireEvent.click(btnPercent);

      expect(mockChartInstance.overrideYAxis).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'percentage' })
      );
      expect(useFtsConfigStore.getState().priceScale).toBe('percentage');
    });

    it('کلیک روی کلید auto اسکیل خودکار و scrollToRealTime را فعال می‌کند', async () => {
      const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
      render(<KLineChartWrapper initialSymbol="فولاد" />);

      const btnAuto = screen.getByTestId('axis-btn-auto');
      fireEvent.click(btnAuto);

      expect(mockChartInstance.scrollToRealTime).toHaveBeenCalled();
    });
  });

  // فاز ۲: ابزار خط‌کش / اندازه‌گیری (Measure / Ruler Tool)
  describe('فاز ۲: ابزار خط‌کش / اندازه‌گیری (Measure / Ruler Tool)', () => {
    it('کشیدن ماوس با کلید Shift ابزار خط‌کش را فعال کرده و محاسبات درصد، قیمت، کندل و زمان را نشان می‌دهد', async () => {
      const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
      const { container } = render(<KLineChartWrapper initialSymbol="فولاد" />);

      const canvasArea = container.querySelector('.nn-canvas-area') as HTMLElement;
      expect(canvasArea).toBeTruthy();

      // ماک کراس‌هیر برای نقطه اول (قیمت ۱۰۰۰ ریال)
      mockChartInstance.getCrosshair.mockReturnValueOnce({
        dataIndex: 10,
        kLineData: { timestamp: 1700000000000, open: 980, high: 1020, low: 970, close: 1000, volume: 10000 },
      });

      // شروع درگ با Shift
      fireEvent.mouseDown(canvasArea, { shiftKey: true, clientX: 100, clientY: 200 });

      // نقطه دوم درگ (قیمت ۱۱۵۰ ریال، ۵ کندل بعد)
      mockChartInstance.getCrosshair.mockReturnValueOnce({
        dataIndex: 15,
        kLineData: { timestamp: 1700000000000 + (5 * 24 * 60 * 60 * 1000), open: 1100, high: 1180, low: 1090, close: 1150, volume: 12000 },
      });

      fireEvent.mouseMove(canvasArea, { clientX: 250, clientY: 100 });

      // بررسی حضور تولتیپ اندازه‌گیری
      const badge = screen.getByTestId('measure-badge');
      expect(badge).toBeTruthy();
      expect(badge.textContent).toContain('+15.00%'); // درصد تغییرات
      expect(badge.textContent).toContain('۱۵۰'); // اختلاف قیمت ریالی
      expect(badge.textContent).toContain('۶ کندل'); // تعداد کندل‌ها
      expect(badge.textContent).toContain('۵ روز'); // بازه تقویمی
    });

    it('فشردن کلید Escape یا کلیک ساده، ابزار خط‌کش را می‌بندد', async () => {
      const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
      const { container } = render(<KLineChartWrapper initialSymbol="فولاد" />);

      const canvasArea = container.querySelector('.nn-canvas-area') as HTMLElement;
      fireEvent.mouseDown(canvasArea, { shiftKey: true, clientX: 50, clientY: 50 });
      fireEvent.mouseMove(canvasArea, { clientX: 150, clientY: 150 });
      expect(screen.queryByTestId('measure-badge')).toBeTruthy();

      // فشردن Escape
      fireEvent.keyDown(window, { key: 'Escape' });
      expect(screen.queryByTestId('measure-badge')).toBeNull();
    });
  });

  // فاز ۳: ماندگاری ترسیم‌ها به ازای هر نماد (Per-Symbol Drawings Persistence)
  describe('فاز ۳: ماندگاری تفکیک‌شده ترسیم‌ها برای هر نماد (Per-Symbol Persistence)', () => {
    it('کلید اختصاصی نماد fts.drawings.v1.{symbol} ایجاد و ذخیره می‌شود', () => {
      expect(symbolDrawKey('فولاد')).toBe(`${SYMBOL_DRAW_PREFIX}.فولاد`);

      const drawing: StoredOverlay = {
        name: 'straightLine',
        groupId: 'fts-draw',
        points: [{ timestamp: 1000, value: 5000 }],
      };

      saveSymbolDrawings('فولاد', [drawing]);
      const saved = loadSymbolDrawings('فولاد');
      expect(saved).toHaveLength(1);
      expect(saved[0].name).toBe('straightLine');

      // نماد دیگر باید خالی باشد
      expect(loadSymbolDrawings('شپنا')).toEqual([]);
    });

    it('پاک‌سازی ترسیم‌های یک نماد، داده‌های نماد دیگر را دستکاری نمی‌کند', () => {
      saveSymbolDrawings('فولاد', [{ name: 'ray' }]);
      saveSymbolDrawings('خودرو', [{ name: 'ray' }]);

      clearSymbolDrawings('فولاد');
      expect(loadSymbolDrawings('فولاد')).toEqual([]);
      expect(loadSymbolDrawings('خودرو')).toHaveLength(1);
    });
  });

  // فاز ۴: فیبوناچی لگاریتمی (Logarithmic Fibonacci Retracement)
  describe('فاز ۴: فرمول لگاریتمی فیبوناچی بر پایه تریدینگ‌ویو', () => {
    it('ترازهای تریدینگ‌ویو شامل سطوح ۲۳.۶٪، ۳۸.۲٪، ۵۰٪، ۶۱.۸٪، ۷۸.۶٪ و ۱۶۱.۸٪ است', () => {
      expect(TV_FIB_LEVELS).toContain(0.236);
      expect(TV_FIB_LEVELS).toContain(0.382);
      expect(TV_FIB_LEVELS).toContain(0.5);
      expect(TV_FIB_LEVELS).toContain(0.618);
      expect(TV_FIB_LEVELS).toContain(0.786);
      expect(TV_FIB_LEVELS).toContain(1.618);
    });

    it('فرمول لگاریتمی Low * (High/Low)^Ratio را با دقت بالا محاسبه می‌کند', () => {
      // در حالت خطی بین ۱۰۰ و ۲۰۰ در تراز ۵۰٪ مقدار ۱۵۰ است
      const linearPrice = calcFibPrice(200, 100, 0.5, false);
      expect(linearPrice).toBe(150);

      // در حالت لگاریتمی ۱۰۰ * (۲۰۰/۱۰۰)^۰.۵ = ۱۰۰ * ۱.۴۱۴۲ = ۱۴۱.۴۲
      const logPrice = calcFibPrice(200, 100, 0.5, true);
      expect(Math.round(logPrice)).toBe(141);

      // تراز ۰٪ و ۱۰۰٪
      expect(calcFibPrice(200, 100, 0, true)).toBe(100);
      expect(calcFibPrice(200, 100, 1, true)).toBe(200);
    });
  });

  // فاز ۵: رویدادهای شرکتی (Corporate Actions D / S)
  describe('فاز ۵: کنترل و نمایش رویدادهای شرکتی (Corporate Actions)', () => {
    it('فیلدهای کنترل رویدادهای شرکتی در استور پیکربندی ftsConfigStore فعال هستند', () => {
      const state = useFtsConfigStore.getState();
      expect(state.view.showCorporateActions).toBe(true);

      useFtsConfigStore.getState().setView({ showCorporateActions: false });
      expect(useFtsConfigStore.getState().view.showCorporateActions).toBe(false);

      useFtsConfigStore.getState().setView({ showCorporateActions: true });
    });
  });

  // فاز ۶: ویجت ۵ مظنه برتر عمق بازار (Top 5 Quotes Widget)
  describe('فاز ۶: ویجت ۵ مظنه برتر عمق بازار (MarketDepthWidget)', () => {
    it('در صورت isOpen=true پنجره ۵ مظنه با جدول تقاضا و عرضه و نسبت کل رندر می‌شود', () => {
      const onClose = vi.fn();
      render(
        <MarketDepthWidget
          symbol="فولاد"
          isOpen={true}
          onClose={onClose}
          boardRow={{ p_last: 5000, p_closing: 4950, tvol: 1000000 }}
        />
      );

      const widget = screen.getByTestId('market-depth-widget');
      expect(widget).toBeTruthy();
      expect(screen.getByText('عمق بازار — نمایش تقریبی')).toBeTruthy();
      expect(screen.getByText('فولاد')).toBeTruthy();

      // دکمه بستن
      const closeBtn = screen.getByLabelText('بستن عمق بازار');
      fireEvent.click(closeBtn);
      expect(onClose).toHaveBeenCalled();
    });

    it('در صورت isOpen=false ویجت هیچ DOMای تولید نمی‌کند', () => {
      const { container } = render(
        <MarketDepthWidget symbol="فولاد" isOpen={false} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('کلید ۵ مظنه در تولبار چارت، پنجره عمق بازار را باز و بسته می‌کند', async () => {
      const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
      render(<KLineChartWrapper initialSymbol="فولاد" />);

      const toggleDepthBtn = screen.getByTestId('toggle-depth-btn');
      expect(toggleDepthBtn).toBeTruthy();

      // ویجت در ابتدا بسته است
      expect(screen.queryByTestId('market-depth-widget')).toBeNull();

      // کلیک برای باز شدن
      fireEvent.click(toggleDepthBtn);
      expect(screen.getByTestId('market-depth-widget')).toBeTruthy();

      // کلیک مجدد برای بسته شدن
      fireEvent.click(toggleDepthBtn);
      expect(screen.queryByTestId('market-depth-widget')).toBeNull();
    });
  });
});
