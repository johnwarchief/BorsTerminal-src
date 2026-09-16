import React, { useState } from 'react';
import {
  IconCandles, IconHollowCandles, IconBars, IconLine, IconHeikinAshi,
  IconAdjustments, IconFx, IconFts, IconSettings, IconCamera,
  IconFullscreen, IconExitFullscreen, IconChevronDown, IconCheck, IconSearch
} from './TradingViewIcons';
import type { AdjustmentMode } from '../lib/adjustments';

interface FtsToolbarProps {
  symbolName: string;
  companyName: string;
  marketName: string;
  onOpenSymbolSearch: () => void;
  activeTimeframe: string;
  onTimeframeChange: (tf: string) => void;
  activeCandleType: string;
  onCandleTypeChange: (type: string) => void;
  activeAdjustment: AdjustmentMode;
  onAdjustmentChange: (adj: AdjustmentMode) => void;
  onOpenIndicators: () => void;
  isFtsActive: boolean;
  onToggleFts: () => void;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
  onOpenSettings?: () => void;
  onTakeSnapshot?: () => void;
}

export const FtsToolbar: React.FC<FtsToolbarProps> = ({
  symbolName,
  companyName,
  marketName,
  onOpenSymbolSearch,
  activeTimeframe,
  onTimeframeChange,
  activeCandleType,
  onCandleTypeChange,
  activeAdjustment,
  onAdjustmentChange,
  onOpenIndicators,
  isFtsActive,
  onToggleFts,
  isFullscreen,
  onToggleFullscreen,
  onOpenSettings,
  onTakeSnapshot
}) => {
  const [showCandleMenu, setShowCandleMenu] = useState(false);
  const [showAdjMenu, setShowAdjMenu] = useState(false);

  const timeframes = ['1m', '5m', '15m', '30m', '1h', 'D', 'W', 'M'];

  const candleTypes = [
    { label: 'کندل شمعی (Solid)', value: 'candle_solid', icon: <IconCandles size={16} /> },
    { label: 'کندل توخالی (Hollow)', value: 'candle_stroke', icon: <IconHollowCandles size={16} /> },
    { label: 'میله‌ای (OHLC)', value: 'ohlc', icon: <IconBars size={16} /> },
    { label: 'خطی / ناحیه‌ای (Area)', value: 'area', icon: <IconLine size={16} /> },
    { label: 'هایکن آشی (Heikin Ashi)', value: 'heikin_ashi', icon: <IconHeikinAshi size={16} /> },
  ];

  const adjustments: { label: string; value: AdjustmentMode; desc: string }[] = [
    { label: 'تعدیل عملکردی (نهایت‌نگر)', value: 'operational', desc: 'مبنای قیمت بازگشایی مجمع بورس تهران' },
    { label: 'افزایش سرمایه و سود نقدی', value: 'capital_cash', desc: 'تعدیل استاندارد مجموع بازده تئوریک' },
    { label: 'با احتساب آورده', value: 'with_rights', desc: 'با لحاظ ارزش اسمی ۱۰۰۰ ریالی حق‌تقدم' },
    { label: 'افزایش سرمایه', value: 'capital', desc: 'فقط سهام جایزه و تجدید ارزیابی' },
    { label: 'سود نقدی', value: 'cash', desc: 'فقط سود نقدی تقسیمی (DPS)' },
    { label: 'بدون تعدیل', value: 'none', desc: 'قیمت‌های خام و واقعی تابلوی معاملات' },
  ];

  const currentAdj = adjustments.find(a => a.value === activeAdjustment) || adjustments[0];
  const currentCandle = candleTypes.find(c => c.value === activeCandleType) || candleTypes[0];

  return (
    <header className="nn-top-toolbar" onClick={() => { setShowCandleMenu(false); setShowAdjMenu(false); }}>
      {/* سمت راست: بج نماد، تایم‌فریم، نوع کندل، تعدیل، اندیکاتورها و تحلیل FTS */}
      <div className="nn-toolbar-group">
        {/* بج نماد - کلیک برای باز شدن جستجو */}
        <div
          className="nn-symbol-badge"
          onClick={(e) => { e.stopPropagation(); onOpenSymbolSearch(); }}
          title="کلیک برای جستجوی نماد در بازار"
        >
          <span style={{ fontWeight: 'bold', color: '#ffffff' }}>{symbolName}</span>
          <span style={{ color: '#787b86', fontSize: '12px' }}>({companyName})</span>
          <span className="market-state">{marketName}</span>
          <IconSearch size={14} color="#787b86" />
        </div>

        <div className="nn-separator" />

        {/* بازه‌های زمانی */}
        <div className="nn-toolbar-group">
          {timeframes.map(tf => (
            <button
              key={tf}
              className={`nn-btn ${activeTimeframe === tf ? 'active' : ''}`}
              onClick={() => onTimeframeChange(tf)}
            >
              {tf}
            </button>
          ))}
        </div>

        <div className="nn-separator" />

        {/* منوی انواع نمودار */}
        <div className="nn-select-dropdown">
          <button
            className="nn-btn"
            onClick={(e) => {
              e.stopPropagation();
              setShowCandleMenu(!showCandleMenu);
              setShowAdjMenu(false);
            }}
            title="نوع نمایش نمودار"
          >
            {currentCandle.icon}
            <span>{currentCandle.label.split(' ')[0]}</span>
            <IconChevronDown size={8} className="nn-chevron" />
          </button>
          {showCandleMenu && (
            <div className="nn-dropdown-menu" style={{ minWidth: '180px' }}>
              {candleTypes.map(ct => (
                <div
                  key={ct.value}
                  className={`nn-dropdown-item ${activeCandleType === ct.value ? 'selected' : ''}`}
                  onClick={() => {
                    onCandleTypeChange(ct.value);
                    setShowCandleMenu(false);
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {ct.icon}
                    <span>{ct.label}</span>
                  </div>
                  {activeCandleType === ct.value && <IconCheck size={14} color="#2962ff" />}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="nn-separator" />

        {/* منوی ۶‌گانه تعدیل قیمت بورس تهران */}
        <div className="nn-select-dropdown">
          <button
            className="nn-btn"
            onClick={(e) => {
              e.stopPropagation();
              setShowAdjMenu(!showAdjMenu);
              setShowCandleMenu(false);
            }}
            title="نوع تعدیل قیمت"
          >
            <IconAdjustments size={16} />
            <span>{currentAdj.label}</span>
            <IconChevronDown size={8} className="nn-chevron" />
          </button>
          {showAdjMenu && (
            <div className="nn-dropdown-menu" style={{ minWidth: '250px' }}>
              {adjustments.map(adj => (
                <div
                  key={adj.value}
                  className={`nn-dropdown-item ${activeAdjustment === adj.value ? 'selected' : ''}`}
                  onClick={() => {
                    onAdjustmentChange(adj.value);
                    setShowAdjMenu(false);
                  }}
                  style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '2px' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                    <span style={{ fontWeight: '500' }}>{adj.label}</span>
                    {activeAdjustment === adj.value && <IconCheck size={14} color="#2962ff" />}
                  </div>
                  <span style={{ fontSize: '10px', color: '#787b86' }}>{adj.desc}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="nn-separator" />

        {/* اندیکاتورها */}
        <button className="nn-btn" onClick={onOpenIndicators} title="پنل اندیکاتورها">
          <IconFx size={16} />
          <span>اندیکاتورها</span>
        </button>

        {/* کلید تحلیل FTS (زون‌های فیبو، میانگین‌های FTS و ستاپ‌ها) */}
        <button
          className={`nn-btn ${isFtsActive ? 'warning-active' : ''}`}
          onClick={onToggleFts}
          title="فعال‌سازی لایه‌های تحلیلی استراتژی FTS"
        >
          <IconFts size={16} color={isFtsActive ? '#ffab00' : 'currentColor'} />
          <span>تحلیل FTS</span>
        </button>
      </div>

      {/* سمت چپ: تنظیمات، عکاسی و تمام‌صفحه */}
      <div className="nn-toolbar-group">
        {onOpenSettings && (
          <button className="nn-btn nn-icon-btn" onClick={onOpenSettings} title="تنظیمات چارت">
            <IconSettings size={16} />
          </button>
        )}
        {onTakeSnapshot && (
          <button className="nn-btn nn-icon-btn" onClick={onTakeSnapshot} title="ذخیره تصویر چارت">
            <IconCamera size={16} />
          </button>
        )}
        <button className="nn-btn nn-icon-btn" onClick={onToggleFullscreen} title="تمام‌صفحه">
          {isFullscreen ? <IconExitFullscreen size={16} /> : <IconFullscreen size={16} />}
        </button>
      </div>
    </header>
  );
};
