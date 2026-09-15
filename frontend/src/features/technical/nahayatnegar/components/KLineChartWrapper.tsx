import React, { useEffect, useRef, useState } from 'react';
// پورت‌شده به klinecharts v10: init/setDataLoader/resetData، createIndicator با امضای شیئی،
// overrideOverlay به‌جای setOverlayOptions، و formatter جلالی به‌جای customApi.
import { init, dispose } from 'klinecharts';
import type { Chart, KLineData, Styles, DeepPartial } from 'klinecharts';
import { nahayatNegarDarkTheme } from '../lib/chartTheme';
import { applyAdjustmentToCandles, type CorporateAction } from '../lib/adjustments';
import {
  IconCrosshair, IconTrendLine, IconRay, IconHorizontalLine, IconVerticalLine,
  IconParallelChannel, IconFibRetracement, IconPitchfork, IconRectangle,
  IconCircle, IconText, IconRuler, IconMagnet, IconLock, IconTrash,
  IconCandles, IconFx, IconSettings, IconCamera, IconFullscreen, IconChevronDown
} from './TradingViewIcons';
import { SymbolSearchModal, SymbolInfo } from './SymbolSearchModal';
import { FloatingPropertiesBar } from './FloatingPropertiesBar';
import '../styles/nahayatNegarStyles.css';

export interface ChartProps {
  initialSymbol?: string;
  initialName?: string;
  initialMarket?: string;
  data?: KLineData[];
  /** رویدادهای تعدیل (از adjustEvents اندپوینت /api/chart) برای موتور lib/adjustments */
  corporateActions?: CorporateAction[];
  onSymbolChange?: (sym: SymbolInfo) => void;
  onTimeframeChange?: (tf: string) => void;
  onAdjustmentChange?: (adj: string) => void;
}

export const KLineChartNahayatNegar: React.FC<ChartProps> = ({
  initialSymbol = 'خودرو',
  initialName = 'ایران خودرو',
  initialMarket = 'بورس',
  data = [],
  corporateActions = [],
  onSymbolChange,
  onTimeframeChange,
  onAdjustmentChange,
}) => {
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<Chart | null>(null);
  /** دادهٔ تعدیل‌شدهٔ جاری (v10 از dataLoader این ref را می‌خواند) */
  const adaptedRef = useRef<KLineData[]>([]);

  // States
  const [currentSymbol, setCurrentSymbol] = useState<string>(initialSymbol);
  const [currentName, setCurrentName] = useState<string>(initialName);
  const [currentMarket, setCurrentMarket] = useState<string>(initialMarket);

  const [activeTimeframe, setActiveTimeframe] = useState<string>('D');
  const [activeCandleType, setActiveCandleType] = useState<string>('candle_solid');
  const [activeAdjustment, setActiveAdjustment] = useState<string>('capital_cash');
  const [activeToolSlot, setActiveToolSlot] = useState<string>('crosshair');
  const [openFlyout, setOpenFlyout] = useState<string | null>(null);

  const [showSymbolSearch, setShowSymbolSearch] = useState<boolean>(false);
  const [showCandleMenu, setShowCandleMenu] = useState<boolean>(false);
  const [showAdjMenu, setShowAdjMenu] = useState<boolean>(false);
  const [showIndicatorsModal, setShowIndicatorsModal] = useState<boolean>(false);
  const [showFloatingProps, setShowFloatingProps] = useState<boolean>(false);

  const [isLogScale, setIsLogScale] = useState<boolean>(false);
  const [isAutoFit, setIsAutoFit] = useState<boolean>(true);
  const [isPctScale, setIsPctScale] = useState<boolean>(false);
  const [activeRange, setActiveRange] = useState<string>('1Y');

  // توجه: در سورس جمینای state «indicators/setIndicators» تعریف شده بود ولی هیچ‌جا استفاده نمی‌شد
  // (منوی اندیکاتورها در تولبار به handler وصل نبود) — در پورت حذف شد تا tsc سبز بماند.

  // Timeframes list
  const timeframes = ['1m', '5m', '15m', '30m', '1h', 'D', 'W', 'M'];

  // Adjustments list
  const adjustments = [
    { label: 'افزایش سرمایه و سود نقدی', value: 'capital_cash' },
    { label: 'بدون تعدیل', value: 'none' },
    { label: 'افزایش سرمایه', value: 'capital' },
    { label: 'سود نقدی', value: 'cash' },
    { label: 'تعدیل عملکردی', value: 'operational' },
  ];

  // Candle types list
  const candleTypes = [
    { label: 'کندل شمعی (Candles)', value: 'candle_solid' },
    { label: 'کندل توخالی (Hollow)', value: 'candle_stroke' },
    { label: 'میله‌ای (Bars)', value: 'ohlc' },
    { label: 'ناحیه‌ای (Area)', value: 'area' },
  ];

  // Initialize KlineChart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = init(chartContainerRef.current, {
      styles: nahayatNegarDarkTheme as unknown as DeepPartial<Styles>,
      timezone: 'Asia/Tehran',
      locale: 'fa-IR',
    });

    if (chart) {
      chartRef.current = chart;
      // v10: خوراک داده فقط از setDataLoader؛ applyNewData حذف شده است
      chart.setDataLoader({
        getBars: (req) => {
          if (req.type !== 'init') {
            req.callback([]);
            return;
          }
          req.callback(adaptedRef.current, false);
        },
      });
      chart.setSymbol({ ticker: currentSymbol || 'nn' });
      chart.setPeriod({ span: 1, type: 'day' });
      // formatter جلالی (جای customApi حذف‌شدهٔ v9)
      try {
        chart.setFormatter({
          formatDate: (p: { timestamp?: number | null; type?: string }) => {
            const ts = p?.timestamp;
            if (ts == null || !Number.isFinite(ts)) return '';
            try {
              return new Intl.DateTimeFormat('fa-IR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: p.type && (p.type.includes('minute') || p.type.includes('hour')) ? '2-digit' : undefined,
                minute: p.type && p.type.includes('minute') ? '2-digit' : undefined,
              }).format(new Date(ts));
            } catch {
              return new Date(ts).toLocaleDateString('fa-IR');
            }
          },
        });
      } catch {
        // formatter اختیاری است
      }
      // پنل حجم (امضای شیئی v10) + ارتفاع پنل
      try {
        chart.createIndicator({ name: 'VOL', id: 'sub_pane_vol', paneId: 'sub_pane_vol' }, false);
        chart.setPaneOptions({ id: 'sub_pane_vol', height: 95 });
      } catch {
        // اندیکاتور اختیاری است
      }
      chart.resetData();
    }

    const handleResize = () => chartRef.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartContainerRef.current) {
        dispose(chartContainerRef.current);
      }
      chartRef.current = null;
    };
  }, []);

  // Update Data (v10: داده از ref خوانده می‌شود و با resetData دوباره خوراک می‌گیرد)
  useEffect(() => {
    adaptedRef.current = applyAdjustmentToCandles(
      (data ?? []).map((c) => ({
        timestamp: c.timestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume ?? 0,
      })),
      corporateActions,
      activeAdjustment as 'none' | 'capital' | 'cash' | 'capital_cash' | 'operational',
    ) as unknown as KLineData[];
    try {
      chartRef.current?.resetData();
    } catch {
      // نادیده بگیر
    }
  }, [data, corporateActions, activeAdjustment]);

  // Symbol Selection
  const handleSelectSymbol = (s: SymbolInfo) => {
    setCurrentSymbol(s.symbol);
    setCurrentName(s.name);
    setCurrentMarket(s.market);
    onSymbolChange?.(s);
  };

  // Drawing overlay creation
  const triggerOverlay = (overlayName: string, slotId: string) => {
    if (!chartRef.current) return;
    setActiveToolSlot(slotId);
    setOpenFlyout(null);
    // v10: createOverlay شیء می‌گیرد (نه نام رشته‌ای)
    chartRef.current.createOverlay({ name: overlayName });
    setShowFloatingProps(true);
  };

  // Fullscreen
  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      chartContainerRef.current?.parentElement?.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  };

  // Log scale
  const toggleLog = () => {
    if (!chartRef.current) return;
    const next = !isLogScale;
    setIsLogScale(next);
    chartRef.current.setStyles({ yAxis: { type: next ? 'logarithm' : 'normal' } } as unknown as DeepPartial<Styles>);
  };

  return (
    <div className="nahayat-negar-container" onClick={() => { setOpenFlyout(null); setShowCandleMenu(false); setShowAdjMenu(false); }}>
      {/* 1. TOP TOOLBAR */}
      <header className="nn-top-toolbar" onClick={e => e.stopPropagation()}>
        <div className="nn-toolbar-group">
          {/* Symbol Search Capsule */}
          <div className="nn-symbol-badge" onClick={() => setShowSymbolSearch(true)} style={{ cursor: 'pointer' }} title="جستجوی نماد">
            <span>{currentSymbol}</span>
            <span style={{ color: '#787b86', fontWeight: 'normal' }}>({currentName})</span>
            <span className="market-state">{currentMarket}</span>
          </div>

          <div className="nn-separator" />

          {/* Timeframes */}
          <div className="nn-toolbar-group">
            {timeframes.map(tf => (
              <button
                key={tf}
                className={`nn-btn ${activeTimeframe === tf ? 'active' : ''}`}
                onClick={() => {
                  setActiveTimeframe(tf);
                  onTimeframeChange?.(tf);
                }}
              >
                {tf}
              </button>
            ))}
          </div>

          <div className="nn-separator" />

          {/* Candle Types */}
          <div className="nn-select-dropdown">
            <button className="nn-btn" onClick={() => setShowCandleMenu(!showCandleMenu)}>
              <IconCandles size={16} />
              <span>کندل</span>
              <IconChevronDown size={10} />
            </button>
            {showCandleMenu && (
              <div className="nn-dropdown-menu">
                {candleTypes.map(ct => (
                  <div
                    key={ct.value}
                    className={`nn-dropdown-item ${activeCandleType === ct.value ? 'selected' : ''}`}
                    onClick={() => {
                      setActiveCandleType(ct.value);
                      chartRef.current?.setStyles({ candle: { type: ct.value } } as unknown as DeepPartial<Styles>);
                      setShowCandleMenu(false);
                    }}
                  >
                    <span>{ct.label}</span>
                    {activeCandleType === ct.value && <span>✓</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="nn-separator" />

          {/* Adjustment Selector */}
          <div className="nn-select-dropdown">
            <button className="nn-btn" onClick={() => setShowAdjMenu(!showAdjMenu)}>
              <span>{adjustments.find(a => a.value === activeAdjustment)?.label}</span>
              <IconChevronDown size={10} />
            </button>
            {showAdjMenu && (
              <div className="nn-dropdown-menu" style={{ minWidth: '185px' }}>
                {adjustments.map(adj => (
                  <div
                    key={adj.value}
                    className={`nn-dropdown-item ${activeAdjustment === adj.value ? 'selected' : ''}`}
                    onClick={() => {
                      setActiveAdjustment(adj.value);
                      onAdjustmentChange?.(adj.value);
                      setShowAdjMenu(false);
                    }}
                  >
                    <span>{adj.label}</span>
                    {activeAdjustment === adj.value && <span>✓</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="nn-separator" />

          {/* Indicators Button */}
          <button
            className={`nn-btn ${showIndicatorsModal ? 'active' : ''}`}
            onClick={() => setShowIndicatorsModal(!showIndicatorsModal)}
            style={{ color: '#2962ff' }}
          >
            <IconFx size={16} />
            <span style={{ fontWeight: 'bold' }}>اندیکاتورها</span>
          </button>
        </div>

        {/* Right Tools */}
        <div className="nn-toolbar-group">
          <button className="nn-btn" title="ذخیره چارت">ذخیره <IconChevronDown size={10} /></button>
          <div className="nn-separator" />
          <button className="nn-btn nn-icon-btn" title="تنظیمات چارت"><IconSettings size={16} /></button>
          <button className="nn-btn nn-icon-btn" title="عکس چارت"><IconCamera size={16} /></button>
          <button className="nn-btn nn-icon-btn" title="تمام‌صفحه" onClick={handleToggleFullscreen}><IconFullscreen size={16} /></button>
        </div>
      </header>

      {/* 2. MAIN BODY */}
      <div className="nn-chart-body">
        {/* Left Drawing Toolbar */}
        <aside className="nn-left-toolbar" onClick={e => e.stopPropagation()}>
          {/* Crosshair Slot */}
          <div className="tv-tool-slot">
            <div
              className={`nn-left-toolbar-item ${activeToolSlot === 'crosshair' ? 'active' : ''}`}
              onClick={() => setActiveToolSlot('crosshair')}
              title="نشانگر چلیپایی"
            >
              <IconCrosshair size={18} />
            </div>
          </div>

          {/* Lines Slot */}
          <div className="tv-tool-slot">
            <div
              className={`nn-left-toolbar-item ${activeToolSlot === 'lines' ? 'active' : ''}`}
              onClick={() => setOpenFlyout(openFlyout === 'lines' ? null : 'lines')}
              title="خطوط روند"
            >
              <IconTrendLine size={18} />
              <span className="tv-tool-arrow" />
            </div>
            {openFlyout === 'lines' && (
              <div className="tv-flyout open">
                <div className="tv-flyout-item" onClick={() => triggerOverlay('segment', 'lines')}>
                  <IconTrendLine size={16} /> خط روند (Trend Line)
                </div>
                <div className="tv-flyout-item" onClick={() => triggerOverlay('rayLine', 'lines')}>
                  <IconRay size={16} /> پرتو (Ray)
                </div>
                <div className="tv-flyout-item" onClick={() => triggerOverlay('straightLine', 'lines')}>
                  <IconHorizontalLine size={16} /> خط افقی (Horizontal)
                </div>
                <div className="tv-flyout-item" onClick={() => triggerOverlay('verticalStraightLine', 'lines')}>
                  <IconVerticalLine size={16} /> خط عمودی (Vertical)
                </div>
                <div className="tv-flyout-item" onClick={() => triggerOverlay('priceChannelLine', 'lines')}>
                  <IconParallelChannel size={16} /> کانال موازی
                </div>
              </div>
            )}
          </div>

          {/* Fib Slot */}
          <div className="tv-tool-slot">
            <div
              className={`nn-left-toolbar-item ${activeToolSlot === 'fib' ? 'active' : ''}`}
              onClick={() => setOpenFlyout(openFlyout === 'fib' ? null : 'fib')}
              title="فیبوناچی و چنگال"
            >
              <IconFibRetracement size={18} />
              <span className="tv-tool-arrow" />
            </div>
            {openFlyout === 'fib' && (
              <div className="tv-flyout open">
                <div className="tv-flyout-item" onClick={() => triggerOverlay('fibonacciLine', 'fib')}>
                  <IconFibRetracement size={16} /> فیبوناچی ریتریسمنت
                </div>
                <div className="tv-flyout-item" onClick={() => triggerOverlay('parallelStraightLine', 'fib')}>
                  <IconPitchfork size={16} /> چنگال اندروز
                </div>
              </div>
            )}
          </div>

          {/* Shapes Slot */}
          <div className="tv-tool-slot">
            <div
              className={`nn-left-toolbar-item ${activeToolSlot === 'shapes' ? 'active' : ''}`}
              onClick={() => setOpenFlyout(openFlyout === 'shapes' ? null : 'shapes')}
              title="اشکال هندسی"
            >
              <IconRectangle size={18} />
              <span className="tv-tool-arrow" />
            </div>
            {openFlyout === 'shapes' && (
              <div className="tv-flyout open">
                <div className="tv-flyout-item" onClick={() => triggerOverlay('rect', 'shapes')}>
                  <IconRectangle size={16} /> مستطیل (Rectangle)
                </div>
                <div className="tv-flyout-item" onClick={() => triggerOverlay('circle', 'shapes')}>
                  <IconCircle size={16} /> دایره (Circle)
                </div>
              </div>
            )}
          </div>

          {/* Text Slot */}
          <div className="tv-tool-slot">
            <div
              className={`nn-left-toolbar-item ${activeToolSlot === 'text' ? 'active' : ''}`}
              onClick={() => setOpenFlyout(openFlyout === 'text' ? null : 'text')}
              title="متن و یادداشت"
            >
              <IconText size={18} />
              <span className="tv-tool-arrow" />
            </div>
            {openFlyout === 'text' && (
              <div className="tv-flyout open">
                <div className="tv-flyout-item" onClick={() => triggerOverlay('simpleAnnotation', 'text')}>
                  <IconText size={16} /> متن تحلیلی (Text)
                </div>
                <div className="tv-flyout-item" onClick={() => triggerOverlay('priceLine', 'text')}>
                  برچسب قیمت (Price Tag)
                </div>
              </div>
            )}
          </div>

          <div className="nn-tool-divider" />

          {/* Utilities */}
          <div className="tv-tool-slot">
            <div className="nn-left-toolbar-item" title="خط‌کش اندازه‌گیری"><IconRuler size={18} /></div>
          </div>
          <div className="tv-tool-slot">
            <div className="nn-left-toolbar-item" title="آهنربا"><IconMagnet size={18} /></div>
          </div>
          <div className="tv-tool-slot">
            <div className="nn-left-toolbar-item" title="قفل کردن"><IconLock size={18} /></div>
          </div>

          <div className="nn-tool-divider" />

          {/* Trash */}
          <div className="tv-tool-slot">
            <div
              className="nn-left-toolbar-item"
              title="حذف تمام ترسیمات"
              style={{ color: '#f23645' }}
              onClick={() => {
                chartRef.current?.removeOverlay();
                setShowFloatingProps(false);
              }}
            >
              <IconTrash size={18} />
            </div>
          </div>
        </aside>

        {/* Canvas Area */}
        <main className="nn-canvas-area">
          <div ref={chartContainerRef} className="nn-kline-chart" />

          {/* Floating Tool Properties Bar */}
          <FloatingPropertiesBar
            visible={showFloatingProps}
            onColorChange={c => {
              // v10: setOverlayOptions حذف شده؛ overrideOverlay جای آن است (روی همهٔ ترسیم‌ها)
              chartRef.current?.overrideOverlay({ styles: { color: c } });
            }}
            onWidthChange={w => {
              chartRef.current?.overrideOverlay({ styles: { size: w } });
            }}
            onDelete={() => {
              chartRef.current?.removeOverlay();
              setShowFloatingProps(false);
            }}
          />
        </main>
      </div>

      {/* 3. BOTTOM BAR */}
      <footer className="nn-bottom-bar">
        <div className="nn-range-buttons">
          <span style={{ marginLeft: '6px' }}>بازه زمانی:</span>
          {['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', '5Y', 'All'].map(rng => (
            <button
              key={rng}
              className={`nn-range-btn ${activeRange === rng ? 'active' : ''}`}
              onClick={() => setActiveRange(rng)}
            >
              {rng}
            </button>
          ))}
        </div>

        <div className="nn-scale-controls">
          <span>تهران (UTC+3:30)</span>
          <div className="nn-separator" />
          <button className={`nn-scale-toggle ${isPctScale ? 'active' : ''}`} onClick={() => setIsPctScale(!isPctScale)}>%</button>
          <button className={`nn-scale-toggle ${isLogScale ? 'active' : ''}`} onClick={toggleLog}>log</button>
          <button className={`nn-scale-toggle ${isAutoFit ? 'active' : ''}`} onClick={() => setIsAutoFit(!isAutoFit)}>auto</button>
        </div>
      </footer>

      {/* 4. MODALS */}
      <SymbolSearchModal
        isOpen={showSymbolSearch}
        onClose={() => setShowSymbolSearch(false)}
        onSelectSymbol={handleSelectSymbol}
      />
    </div>
  );
};

export default KLineChartNahayatNegar;
