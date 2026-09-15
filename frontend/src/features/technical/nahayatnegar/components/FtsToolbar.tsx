import React, { useState } from 'react';
import {
  IconCandles, IconFx, IconSettings, IconCamera, IconFullscreen, IconChevronDown
} from './TradingViewIcons';

interface FtsToolbarProps {
  symbolName: string;
  companyName: string;
  marketName: string;
  onOpenSymbolSearch: () => void;
  activeTimeframe: string;
  onTimeframeChange: (tf: string) => void;
  activeCandleType: string;
  onCandleTypeChange: (type: string) => void;
  activeAdjustment: string;
  onAdjustmentChange: (adj: string) => void;
  onOpenIndicators: () => void;
  onToggleFullscreen: () => void;
  onSave?: () => void;
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
  onToggleFullscreen,
  onSave,
  onOpenSettings,
  onTakeSnapshot
}) => {
  const [showCandleMenu, setShowCandleMenu] = useState(false);
  const [showAdjMenu, setShowAdjMenu] = useState(false);

  const timeframes = ['1m', '5m', '15m', '30m', '1h', 'D', 'W', 'M'];

  const adjustments = [
    { label: 'تعدیل عملکردی (پیش‌فرض)', value: 'operational' },
    { label: 'افزایش سرمایه و سود نقدی', value: 'capital_cash' },
    { label: 'بدون تعدیل', value: 'none' },
    { label: 'افزایش سرمایه', value: 'capital' },
    { label: 'سود نقدی', value: 'cash' },
  ];

  const candleTypes = [
    { label: 'کندل شمعی (Candles)', value: 'candle_solid' },
    { label: 'کندل توخالی (Hollow)', value: 'candle_stroke' },
    { label: 'میله‌ای (Bars)', value: 'ohlc' },
    { label: 'ناحیه‌ای (Area)', value: 'area' },
  ];

  return (
    <header className="nn-top-toolbar" onClick={() => { setShowCandleMenu(false); setShowAdjMenu(false); }}>
      <div className="nn-toolbar-group">
        <div
          className="nn-symbol-badge"
          onClick={onOpenSymbolSearch}
          title="جستجوی نماد در بازار"
          style={{ cursor: 'pointer' }}
        >
          <span>{symbolName}</span>
          <span style={{ color: '#787b86', fontWeight: 'normal' }}>({companyName})</span>
          <span className="market-state">{marketName}</span>
        </div>

        <div className="nn-separator" />

        <div className="nn-toolbar-group">
          {timeframes.map(tf => (
            <button
              key={tf}
              className={'nn-btn ' + (activeTimeframe === tf ? 'active' : '')}
              onClick={() => onTimeframeChange(tf)}
            >
              {tf}
            </button>
          ))}
        </div>

        <div className="nn-separator" />

        <div className="nn-select-dropdown">
          <button
            className="nn-btn"
            onClick={(e) => { e.stopPropagation(); setShowCandleMenu(!showCandleMenu); setShowAdjMenu(false); }}
          >
            <IconCandles size={16} />
            <span>کندل</span>
            <IconChevronDown size={10} />
          </button>
          {showCandleMenu && (
            <div className="nn-dropdown-menu">
              {candleTypes.map(ct => (
                <div
                  key={ct.value}
                  className={'nn-dropdown-item ' + (activeCandleType === ct.value ? 'selected' : '')}
                  onClick={() => { onCandleTypeChange(ct.value); setShowCandleMenu(false); }}
                >
                  <span>{ct.label}</span>
                  {activeCandleType === ct.value && <span>✓</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="nn-separator" />

        <div className="nn-select-dropdown">
          <button
            className="nn-btn"
            onClick={(e) => { e.stopPropagation(); setShowAdjMenu(!showAdjMenu); setShowCandleMenu(false); }}
            style={{ color: activeAdjustment === 'operational' ? '#2962ff' : 'inherit' }}
          >
            <span>⚖️ {adjustments.find(a => a.value === activeAdjustment)?.label}</span>
            <IconChevronDown size={10} />
          </button>
          {showAdjMenu && (
            <div className="nn-dropdown-menu" style={{ minWidth: '190px' }}>
              {adjustments.map(adj => (
                <div
                  key={adj.value}
                  className={'nn-dropdown-item ' + (activeAdjustment === adj.value ? 'selected' : '')}
                  onClick={() => { onAdjustmentChange(adj.value); setShowAdjMenu(false); }}
                >
                  <span>{adj.label}</span>
                  {activeAdjustment === adj.value && <span>✓</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="nn-separator" />

        <button
          className="nn-btn"
          onClick={onOpenIndicators}
          style={{ color: '#2962ff' }}
        >
          <IconFx size={16} />
          <span style={{ fontWeight: 'bold' }}>اندیکاتورها</span>
        </button>
      </div>

      <div className="nn-toolbar-group">
        <button className="nn-btn" onClick={onSave} title="ذخیره چارت">ذخیره <IconChevronDown size={10} /></button>
        <div className="nn-separator" />
        <button className="nn-btn nn-icon-btn" onClick={onOpenSettings} title="تنظیمات چارت"><IconSettings size={16} /></button>
        <button className="nn-btn nn-icon-btn" onClick={onTakeSnapshot} title="عکس چارت"><IconCamera size={16} /></button>
        <button className="nn-btn nn-icon-btn" onClick={onToggleFullscreen} title="تمام‌صفحه"><IconFullscreen size={16} /></button>
      </div>
    </header>
  );
};
