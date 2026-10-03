import React, { useState } from 'react';
import {
  IconCandles, IconHollowCandles, IconBars, IconLine, IconHeikinAshi,
  IconAdjustments, IconFx, IconFts, IconSettings, IconCamera,
  IconFullscreen, IconExitFullscreen, IconChevronDown, IconCheck, IconSearch
} from './TradingViewIcons';
import { toFaDigits } from '@shared/lib/fmt';
import type { AdjustmentMode } from '../lib/adjustments';
import { SUPPORTED_TIMEFRAMES, TIMEFRAME_LABELS, type Timeframe } from '../lib/timeframe';
import { ENGINE_REGISTRY, type ChartEngineId } from '../../engine';
import { usePriceAlertStore } from '../../stores/priceAlertStore';
import { PriceAlertsPanel } from './PriceAlertsPanel';

interface FtsToolbarProps {
  symbolName: string;
  companyName: string;
  boardRow?: { p_last?: number | null; p_closing?: number | null; percent_change?: number | null } | null;
  onOpenSymbolSearch: () => void;
  activeTimeframe: Timeframe;
  onTimeframeChange: (tf: Timeframe) => void;
  activeCandleType: string;
  onCandleTypeChange: (type: string) => void;
  activeAdjustment: AdjustmentMode;
  onAdjustmentChange: (adj: AdjustmentMode) => void;
  onOpenIndicators: () => void;
  isFtsActive: boolean;
  onToggleFts: () => void;
  replayActive?: boolean;
  onToggleReplay?: () => void;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
  onOpenSettings?: () => void;
  onTakeSnapshot?: () => void;
  /** همسنجیِ دو نماد روی همین چارت */
  compareSymbol?: string | null;
  compareBusy?: boolean;
  compareNoOverlap?: boolean;
  /** اختلافِ بازدهیِ همسنج با این نماد، به برچسبِ درصدِ فارسی */
  compareGap?: string | null;
  onOpenCompareSearch?: () => void;
  onClearCompare?: () => void;
  /** موتورِ رندر؛ فهرست از رجیستری می‌آید، نه از نامِ کتابخانه */
  chartEngine?: ChartEngineId;
  onEngineChange?: (id: ChartEngineId) => void;
}

export const FtsToolbar: React.FC<FtsToolbarProps> = ({
  symbolName,
  companyName,
  boardRow,
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
  replayActive,
  onToggleReplay,
  isFullscreen,
  onToggleFullscreen,
  onOpenSettings,
  onTakeSnapshot,
  compareSymbol,
  compareBusy,
  compareNoOverlap,
  compareGap,
  onOpenCompareSearch,
  onClearCompare,
  chartEngine,
  onEngineChange,
}) => {
  const [showCandleMenu, setShowCandleMenu] = useState(false);
  const [showAdjMenu, setShowAdjMenu] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  // شمارش‌ها از خودِ استور: نوارِ بالا هیچ آستانه‌ای را داوری نمی‌کند
  const armedCount = usePriceAlertStore((s) => s.alerts.filter((a) => a.active).length);
  const hasUnseenFired = usePriceAlertStore((s) => s.alerts.some((a) => a.firedAt != null && !a.seen));

  const timeframes: Timeframe[] = [...SUPPORTED_TIMEFRAMES];

  const candleTypes = [
    { label: 'کندل شمعی (Solid)', value: 'candle_solid', icon: <IconCandles size={16} /> },
    { label: 'کندل توخالی (Hollow)', value: 'candle_stroke', icon: <IconHollowCandles size={16} /> },
    { label: 'میله‌ای (OHLC)', value: 'ohlc', icon: <IconBars size={16} /> },
    { label: 'خطی / ناحیه‌ای (Area)', value: 'area', icon: <IconLine size={16} /> },
    { label: 'هایکن آشی (Heikin Ashi)', value: 'heikin_ashi', icon: <IconHeikinAshi size={16} /> },
  ];

  // فهرستِ کاملِ حالت‌های نهایات‌نگار/ره‌آورد؛ سه‌تا با دادهٔ سرورِ ما ساختنی‌اند.
  // سرور فقط «نسبت گسست قیمت پایه» را می‌دهد = اثرِ ترکیبیِ افزایش سرمایه و سود نقدی
  // (همان حالتِ پیش‌فرضِ نهایات‌نگار). تفکیکِ سودِ نقدی از سهامِ جایزه از یک نسبتِ واحد
  // استخراج نمی‌شود، پس دو حالتِ آخر غیرفعال‌اند (نه عددِ ساختگی).
  // شماره‌هایِ adjustmentType و سنجشِ کمیِ فاکتورِ ما با هر پنج حالت:
  // docs/CHART-PARITY-REFERENCE.md §۸ (ابزار: tools/nn_adjust_parity.py).
  const adjustments: { label: string; value: AdjustmentMode | 'capital' | 'cash'; desc: string }[] = [
    { label: 'افزایش سرمایه و سود نقدی', value: 'combined', desc: 'حالتِ پیش‌فرضِ نهایت‌نگار — مبنای گسست قیمتِ پایهٔ TSETMC' },
    { label: 'بدون تعدیل', value: 'none', desc: 'قیمت‌های خام و واقعی تابلوی معاملات' },
    {
      label: 'تعدیل عملکردی',
      value: 'performance',
      desc: 'نمایِ بازدهی رویِ سریِ تعدیل‌شده — نخستین کندل = ۱۰۰ و محور Percent است. ' +
            'افزایشِ سرمایه و سودِ نقدی هر دو لحاظ می‌شوند، اما سودِ نقدی اینجا ' +
            'سرمایه‌گذاریِ دوباره نمی‌شود (آن کار به DPSِ تفکیکیِ هر رویداد نیاز دارد ' +
            'که در بانکِ ما نیست)، پس عدد با «عملکردیِ» ره‌آورد و نهایت‌نگر یک‌سان نیست.',
    },
    { label: 'افزایش سرمایه', value: 'capital', desc: 'نهی — به دادهٔ تفکیکیِ درصدِ افزایش سرمایه نیاز دارد' },
    { label: 'سود نقدی', value: 'cash', desc: 'نهی — به دادهٔ تفکیکیِ DPS نیاز دارد' },
  ];
  const AVAILABLE_MODES: AdjustmentMode[] = ['combined', 'none', 'performance'];
  const currentAdj = adjustments.find(a => a.value === activeAdjustment) || adjustments[0];
  const currentCandle = candleTypes.find(c => c.value === activeCandleType) || candleTypes[0];

  return (
    <header className="nn-top-toolbar" onClick={() => { setShowCandleMenu(false); setShowAdjMenu(false); setShowAlerts(false); }}>
      {/* سمت راست: نماد، تایم‌فریم، نوع کندل، تعدیل، اندیکاتورها و تحلیل FTS */}
      <div className="nn-toolbar-group">
        {/* بج نماد + قیمت لحظه‌ای + تغییرات - کلیک برای باز شدن جستجو */}
        <div
          className="nn-symbol-badge"
          onClick={(e) => { e.stopPropagation(); onOpenSymbolSearch(); }}
          title="کلیک برای جستجوی نماد در بازار"
        >
          <span style={{ fontWeight: '800', color: 'var(--nn-text-primary)', fontSize: '13px' }}>{symbolName}</span>
          {companyName && (
            <span className="hidden xl:inline" style={{ color: 'var(--nn-text-secondary)', fontSize: '11px', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              ({companyName})
            </span>
          )}
          {boardRow && (boardRow.p_last != null || boardRow.p_closing != null) && (
            <div className="flex items-center gap-1.5 border-r border-[var(--nn-border)] pr-2">
              <span className="font-mono tabular-nums text-xs font-bold text-[var(--nn-text-primary)]">
                {toFaDigits(Math.round(boardRow.p_last ?? boardRow.p_closing ?? 0).toLocaleString('en-US'))}
              </span>
              {boardRow.percent_change != null && (
                <span
                  className="font-mono tabular-nums text-[10px] font-bold px-1.5 py-0.5 rounded"
                  style={{
                    backgroundColor: boardRow.percent_change >= 0 ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)',
                    color: boardRow.percent_change >= 0 ? '#089981' : '#f23645',
                  }}
                >
                  {boardRow.percent_change >= 0 ? '+' : ''}{toFaDigits(boardRow.percent_change.toFixed(2))}%
                </span>
              )}
            </div>
          )}
          <IconSearch size={13} color="var(--nn-text-secondary)" />
        </div>

        <div className="nn-separator" />

        {/* بازه‌های زمانی */}
        <div className="nn-toolbar-group">
          {timeframes.map(tf => (
            <button
              key={tf}
              className={`nn-btn ${activeTimeframe === tf ? 'active' : ''}`}
              onClick={() => onTimeframeChange(tf)}
              title={`نمای ${TIMEFRAME_LABELS[tf]}`}
              data-testid={`timeframe-${tf}`}
            >
              {TIMEFRAME_LABELS[tf]}
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
              {adjustments.map(adj => {
                const available = AVAILABLE_MODES.includes(adj.value as AdjustmentMode);
                return (
                <div
                  key={adj.value}
                  className={`nn-dropdown-item ${activeAdjustment === adj.value ? 'selected' : ''} ${!available ? 'nn-disabled' : ''}`}
                  title={available ? adj.desc : 'این حالت به دادهٔ تفکیکیِ سود نقدی و سهام جایزه نیاز دارد که TSETMC آن را منتشر نمی‌کند'}
                  onClick={() => {
                    if (!available) return;
                    onAdjustmentChange(adj.value as AdjustmentMode);
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
                );
              })}
            </div>
          )}
        </div>

        <div className="nn-separator" />

        {/* اندیکاتورها */}
        <button className="nn-btn" onClick={onOpenIndicators} title="پنل اندیکاتورها">
          <IconFx size={16} />
          <span>اندیکاتورها</span>
        </button>

        {/* همسنجی: نمادِ دوم روی همان چارت، با مبنایِ بازدهیِ مشترک */}
        {onOpenCompareSearch ? (
          compareSymbol ? (
            <span
              className="nn-btn"
              data-testid="compare-chip"
              style={{ gap: '6px' }}
              title={
                compareNoOverlap
                  ? 'هیچ میلۀ مشترکی با این نماد نیست — خطی رسم نمی‌شود'
                  : compareBusy
                    ? 'در حالِ خواندنِ سریِ دوم…'
                    : 'نمادِ همسنج — کلیک برای انتخابِ دیگری'
              }
            >
              <span>همسنج: {compareSymbol}</span>
              {compareGap != null && !compareNoOverlap ? (
                <span
                  data-testid="compare-gap"
                  style={{ color: 'var(--nn-text-secondary)', fontSize: '10px' }}
                  title="بازدهٔ همسنج نسبت به این نماد، از نخستین میلۀ دید"
                >
                  {compareGap}
                </span>
              ) : null}
              {compareBusy ? <span style={{ color: 'var(--nn-text-secondary)' }}>…</span> : null}
              {compareNoOverlap ? (
                <span data-testid="compare-no-overlap" style={{ color: '#f23645', fontSize: '10px' }}>
                  بی‌میلهٔ مشترک
                </span>
              ) : null}
              <button
                type="button"
                data-testid="compare-open"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenCompareSearch();
                }}
                style={{ background: 'none', border: 'none', color: 'var(--nn-text-secondary)', cursor: 'pointer' }}
                title="تغییرِ نمادِ همسنج"
              >
                ⇄
              </button>
              {onClearCompare ? (
                <button
                  type="button"
                  data-testid="compare-clear"
                  onClick={(e) => {
                    e.stopPropagation();
                    onClearCompare();
                  }}
                  style={{ background: 'none', border: 'none', color: '#f23645', cursor: 'pointer' }}
                  title="برداشتنِ همسنج"
                >
                  ✕
                </button>
              ) : null}
            </span>
          ) : (
            <button
              type="button"
              className="nn-btn"
              data-testid="compare-open"
              onClick={(e) => {
                e.stopPropagation();
                onOpenCompareSearch();
              }}
              title="یک نمادِ دیگر را روی همین چارت همسنجی کن"
            >
              <span>همسنجی</span>
            </button>
          )
        ) : null}

        {/* کلید تحلیل FTS (زون‌های فیبو، میانگین‌های FTS و ستاپ‌ها) */}
        <button
          className={`nn-btn ${isFtsActive ? 'warning-active' : ''}`}
          onClick={onToggleFts}
          data-testid="nn-fts-layer-toggle"
          aria-pressed={isFtsActive}
          title="لایۀ سطوحِ تحلیل FTS (فیبو، کمربندها، خط‌هایِ ماژور). الگوها از «الگوهای FTS» روشن/خاموش می‌شوند."
        >
          <IconFts size={16} color={isFtsActive ? '#ffab00' : 'currentColor'} />
          <span>تحلیل FTS</span>
        </button>
      </div>

      {/* موتورِ رندر: همان داده و همان لایه‌ها، موتورِ دیگر. انتخاب اینجا
          ذخیره می‌شود و چارتِ اصلی (klinecharts) پیش‌فرض می‌ماند. */}
      {onEngineChange && chartEngine ? (
        <div className="nn-toolbar-group" role="group" aria-label="موتور چارت" data-testid="nn-engine-switch">
          {ENGINE_REGISTRY.filter((e) => e.production).map((e) => (
            <button
              key={e.id}
              type="button"
              className={`nn-btn ${chartEngine === e.id ? 'active' : ''}`}
              aria-pressed={chartEngine === e.id}
              data-testid={`nn-engine-${e.id}`}
              title={e.id === 'ffc' ? 'موتورِ دوم (WebGL2 لازم دارد)' : e.title}
              onClick={() => onEngineChange(e.id)}
            >
              <span>{e.id === 'ffc' ? 'موتور دوم' : 'KLineCharts'}</span>
            </button>
          ))}
        </div>
      ) : null}

      {/* سمت چپ: بازپخش، تنظیمات، عکاسی و تمام‌صفحه */}
      <div className="nn-toolbar-group">
        {onToggleReplay && (
          <button
            type="button"
            className={`nn-btn ${replayActive ? 'active' : ''}`}
            onClick={onToggleReplay}
            title={replayActive ? 'پایان بازپخش کندل‌ها' : 'شروع بازپخش کندل‌ها'}
          >
            <span>{replayActive ? 'پایان بازپخش' : 'بازپخش'}</span>
          </button>
        )}
        {onOpenSettings && (
          <button
            type="button"
            className="nn-btn nn-icon-btn"
            data-testid="open-chart-settings"
            onClick={onOpenSettings}
            title="تنظیمات چارت"
          >
            <IconSettings size={16} />
          </button>
        )}
        {/* هشدارِ قیمتی: آستانه‌هایِ کاربر روی نمادها، داوری‌شده روی فیدِ تابلو */}
        <div className="relative">
          <button
            type="button"
            className="nn-btn nn-icon-btn"
            data-testid="price-alert-bell"
            onClick={(e) => {
              e.stopPropagation();
              setShowAlerts((v) => !v);
            }}
            title="هشدارهایِ قیمتی"
          >
            <span style={{ color: hasUnseenFired ? '#ffab00' : 'currentColor' }}>🔔</span>
            {armedCount > 0 ? (
              <span
                className="num"
                style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  color: 'var(--nn-text-secondary)',
                }}
              >
                {toFaDigits(armedCount)}
              </span>
            ) : null}
          </button>
          {showAlerts ? <PriceAlertsPanel symbol={symbolName} boardRow={boardRow} /> : null}
        </div>
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
