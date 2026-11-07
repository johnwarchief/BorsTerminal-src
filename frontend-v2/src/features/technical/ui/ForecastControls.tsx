/**
 * frontend-v2/src/features/technical/ui/ForecastControls.tsx
 *
 * نوار ابزار کنترل پیش‌بینی و تنظیمات چارت تکنیکال (پالایش‌شده بر اساس Unslop):
 * - رنگ‌ها بر پایه توکن‌های برنجی (panel, panel-2, line, text, accent)
 * - کروم آرام با تمرکز کامل روی چارت مرکزی
 * - حذف پالس‌های لوپ‌دار، حذف پس‌زمینه‌های نئونی چندرنگ
 * - اعداد کاملاً جدول‌بندی‌شده (tabular-nums)
 */

import React, { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import { toFaDigits, faNum } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import { TIMEFRAME_OPTIONS } from '../model/timeframeAggregation';
import { ADVANCED_INDICATORS_REGISTRY } from '../overlays/advancedTradingIndicators';
import { USER_INDICATORS_REGISTRY } from '../overlays/userIndicators';

export interface ForecastControlsProps {
  className?: string;
  onHorizonChange?: (horizon: number) => void;
  /** R-PB-10: میزکار تازه نماد/تایم‌فریم/تعدیل را در نوار بالا دارد؛ این ردیف فقط ابزارها را نگه می‌دارد. */
  compact?: boolean;
}

const QUICK_HORIZONS = [3, 6, 12];

const MODEL_OPTIONS: Array<{ id: 'mini' | 'small' | 'base'; labelFa: string }> = [
  { id: 'mini', labelFa: 'مینی (۴M)' },
  { id: 'small', labelFa: 'استاندارد (۲۵M)' },
  { id: 'base', labelFa: 'پایه (۱۰۲M)' },
];

const ADJUSTMENT_OPTIONS = [
  { value: 3, labelFa: 'عملکردی' },
  { value: 1, labelFa: 'افزایش سرمایه' },
  { value: 2, labelFa: 'سود نقدی' },
  { value: 0, labelFa: 'بدون تعدیل' },
];

export const ForecastControls: React.FC<ForecastControlsProps> = ({
  className = '',
  onHorizonChange,
  compact = false,
}) => {
  const selectedSymbol = useTechnicalStore((s) => s.selectedSymbol);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);
  const [symbolInput, setSymbolInput] = useState(selectedSymbol || 'فولاد');

  useEffect(() => {
    if (selectedSymbol) {
      setSymbolInput(selectedSymbol);
    }
  }, [selectedSymbol]);

  const timeframe = useTechnicalStore((s) => s.timeframe);
  const setTimeframe = useTechnicalStore((s) => s.setTimeframe);
  const showPredictionCone = useTechnicalStore((s) => s.showPredictionCone);
  const togglePredictionCone = useTechnicalStore((s) => s.togglePredictionCone);
  const predictionData = useTechnicalStore((s) => s.predictionData);
  const isLoading = useTechnicalStore((s) => s.isLoadingForecast);
  const horizon = useTechnicalStore((s) => s.forecastHorizon);
  const setForecastHorizon = useTechnicalStore((s) => s.setForecastHorizon);
  const forecastModel = useTechnicalStore((s) => s.forecastModel);
  const setForecastModel = useTechnicalStore((s) => s.setForecastModel);
  const adjustmentMode = useTechnicalStore((s) => s.adjustmentMode);
  const setAdjustmentMode = useTechnicalStore((s) => s.setAdjustmentMode);
  const showCorporateEvents = useTechnicalStore((s) => s.showCorporateEvents);
  const toggleCorporateEvents = useTechnicalStore((s) => s.toggleCorporateEvents);
  const showSMCZones = useTechnicalStore((s) => s.showSMCZones);
  const toggleSMCZones = useTechnicalStore((s) => s.toggleSMCZones);
  const activeUserIndicators = useTechnicalStore((s) => s.activeUserIndicators);
  const toggleUserIndicator = useTechnicalStore((s) => s.toggleUserIndicator);

  const [isIndicatorMenuOpen, setIsIndicatorMenuOpen] = useState(false);
  const [indicatorSearchQuery, setIndicatorSearchQuery] = useState('');
  const indicatorMenuRef = useRef<HTMLDivElement>(null);

  // بستن منو با کلیک بیرون
  useEffect(() => {
    if (!isIndicatorMenuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (indicatorMenuRef.current && !indicatorMenuRef.current.contains(e.target as Node)) {
        setIsIndicatorMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isIndicatorMenuOpen]);

  const clearAllIndicators = useCallback(() => {
    useTechnicalStore.setState({ activeUserIndicators: [] });
  }, []);

  const telegramIndicators = useMemo(() => {
    const q = indicatorSearchQuery.trim().toLowerCase();
    if (!q) return ADVANCED_INDICATORS_REGISTRY;
    return ADVANCED_INDICATORS_REGISTRY.filter(
      (ind) =>
        ind.name.toLowerCase().includes(q) ||
        ind.nameFa.toLowerCase().includes(q) ||
        ind.descriptionFa.toLowerCase().includes(q)
    );
  }, [indicatorSearchQuery]);

  const customIndicators = useMemo(() => {
    const q = indicatorSearchQuery.trim().toLowerCase();
    if (!q) return USER_INDICATORS_REGISTRY;
    return USER_INDICATORS_REGISTRY.filter(
      (ind) =>
        ind.name.toLowerCase().includes(q) ||
        ind.nameFa.toLowerCase().includes(q) ||
        ind.descriptionFa.toLowerCase().includes(q)
    );
  }, [indicatorSearchQuery]);

  const handleSelectHorizon = useCallback(
    (h: number) => {
      setForecastHorizon(h);
      onHorizonChange?.(h);
    },
    [setForecastHorizon, onHorizonChange],
  );

  const isLiquid = predictionData ? predictionData.isLiquid : true;
  const upsideProb = predictionData?.upsideProbability ?? 0.56;
  const volAmp = predictionData?.volatilityAmplification ?? 1.15;
  const modelUsed = predictionData?.modelUsed;

  return (
    <header
      data-testid="forecast-controls"
      aria-label="کنترل‌های پیش‌بینی و ابزار تکنیکال"
      className={`h-9 px-3 bg-panel border-b border-line text-text flex items-center justify-between text-xs select-none gap-2 ${className}`}
      dir="rtl"
    >
      {/* منطقه ۱ (راست): هسته معاملاتی - نماد، تایم‌فریم، نوع تعدیل، رویدادهای شرکتی و زون‌های SMC */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* جستجو و سوییچ نماد با پالت تمیز و بدون شلوغی */}
        {!compact && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const trimmed = symbolInput.trim();
            if (trimmed) {
              setSelectedSymbol(trimmed);
              window.location.hash = `#/technical/${encodeURIComponent(trimmed)}`;
            }
          }}
          className="flex items-center h-6.5 px-2 bg-panel-2 rounded-[var(--radius-sm)] border border-line focus-within:border-accent"
        >
          <span className="t-9 text-text-3 me-1">نماد:</span>
          <input
            type="text"
            data-testid="symbol-search-input"
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            placeholder="فولاد"
            className="w-13 bg-transparent t-10 text-accent font-bold focus:outline-none"
          />
          <button
            type="submit"
            title="بارگذاری نماد"
            className="text-text-3 hover:text-accent t-9 px-0.5 transition-colors duration-150"
          >
            ↵
          </button>
        </form>
        )}

        {!compact && (
        <div
          data-testid="timeframe-selector"
          className="flex items-center h-6.5 bg-panel-2 p-0.5 rounded-[var(--radius-sm)] border border-line shrink-0"
        >
          {TIMEFRAME_OPTIONS.map((tf) => {
            const isSelected = timeframe === tf.id;
            return (
              <button
                key={tf.id}
                type="button"
                data-testid={`timeframe-btn-${tf.id}`}
                title={tf.tooltipFa}
                onClick={() => setTimeframe(tf.id)}
                className={`h-5 px-1.5 rounded-[var(--radius-xs)] t-9 font-medium transition-colors duration-150 ${
                  isSelected
                    ? 'bg-panel-3 text-accent font-semibold shadow-xs'
                    : 'text-text-3 hover:text-text'
                }`}
              >
                {tf.labelFa}
              </button>
            );
          })}
        </div>
        )}
        {!compact && <div className="h-3.5 w-px bg-line/60 shrink-0 mx-0.5" />}

        {!compact && (
        <div className="flex items-center h-6.5 bg-panel-2 px-1.5 rounded-[var(--radius-sm)] border border-line shrink-0">
          <span className="t-9 text-text-3 me-1">تعدیل:</span>
          <select
            data-testid="adjustment-mode-select"
            value={adjustmentMode}
            onChange={(e) => setAdjustmentMode(Number(e.target.value))}
            className="bg-transparent text-text t-10 font-medium focus:outline-none cursor-pointer"
          >
            {ADJUSTMENT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-panel-2 text-text">
                {opt.labelFa}
              </option>
            ))}
          </select>
        </div>
        )}

        {/* رویدادهای شرکتی (M, D, E) با بج نقطه فعال */}
        <button
          type="button"
          onClick={toggleCorporateEvents}
          title="رویدادهای مجمع و افزایش سرمایه روی محور زمان"
          className={`h-6.5 px-2 rounded-[var(--radius-sm)] t-10 border transition-colors duration-150 flex items-center gap-1 shrink-0 ${
            showCorporateEvents
              ? 'bg-panel-3 text-accent border-accent/40 font-medium'
              : 'bg-panel-2 text-text-3 border-line hover:text-text'
          }`}
        >
          <span>رویدادها</span>
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              showCorporateEvents ? 'bg-accent' : 'bg-line-strong'
            }`}
          />
        </button>

        {/* زون‌های SMC و نقدینگی */}
        <button
          type="button"
          data-testid="toggle-smc-zones-topbar-btn"
          onClick={toggleSMCZones}
          title="نمایش یا پنهان‌سازی زون‌های نقدینگی SMC و FVG"
          className={`h-6.5 px-2 rounded-[var(--radius-sm)] t-10 border transition-colors duration-150 flex items-center gap-1 shrink-0 ${
            showSMCZones
              ? 'bg-panel-3 text-accent border-accent/40 font-medium'
              : 'bg-panel-2 text-text-3 border-line hover:text-text'
          }`}
        >
          <span>زون‌های SMC</span>
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              showSMCZones ? 'bg-accent' : 'bg-line-strong'
            }`}
          />
        </button>

        {/* منوی کشویی اندیکاتورهای تلگرام و تکنیکال */}
        <div className="relative shrink-0" ref={indicatorMenuRef}>
          <button
            type="button"
            data-testid="indicator-dropdown-btn"
            aria-haspopup="true"
            aria-expanded={isIndicatorMenuOpen}
            onClick={() => setIsIndicatorMenuOpen((prev) => !prev)}
            title="انتخاب و فعال‌سازی اندیکاتورهای تلگرام و تکنیکال"
            className={`h-6.5 px-2 rounded-[var(--radius-sm)] t-10 border transition-colors duration-150 flex items-center gap-1.5 shrink-0 ${
              activeUserIndicators.length > 0 || isIndicatorMenuOpen
                ? 'bg-panel-3 text-accent border-accent/40 font-medium'
                : 'bg-panel-2 text-text-3 border-line hover:text-text'
            }`}
          >
            <span className="font-mono text-accent text-xs font-bold">fx</span>
            <span>اندیکاتورها</span>
            {activeUserIndicators.length > 0 && (
              <span className="px-1 py-0.2 rounded-full bg-accent/20 text-accent font-bold text-[10px] font-mono">
                {toFaDigits(activeUserIndicators.length)}
              </span>
            )}
            <svg
              className={`w-3 h-3 text-text-3 transition-transform duration-150 ${isIndicatorMenuOpen ? 'rotate-180 text-accent' : ''}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {isIndicatorMenuOpen && (
            <div
              data-testid="indicator-dropdown-menu"
              className="absolute right-0 top-full mt-1 w-84 max-h-[460px] bg-panel border border-line rounded-[var(--radius-md)] shadow-2xl z-50 flex flex-col overflow-hidden text-text text-right"
              dir="rtl"
            >
              {/* هدر دراپ‌داون با جستجو و کلید پاک‌سازی */}
              <div className="p-2 border-b border-line bg-panel-2 flex flex-col gap-1.5 shrink-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="t-10 font-bold text-accent">اندیکاتورهای تکنیکال و تلگرام</span>
                    {activeUserIndicators.length > 0 && (
                      <span className="t-85 px-1.5 py-0.2 rounded-full bg-accent/20 text-accent font-mono font-bold">
                        {toFaDigits(activeUserIndicators.length)} فعال
                      </span>
                    )}
                  </div>
                  {activeUserIndicators.length > 0 && (
                    <button
                      type="button"
                      data-testid="clear-all-indicators-btn"
                      onClick={clearAllIndicators}
                      className="t-85 text-rose-400 hover:text-rose-300 transition-colors"
                    >
                      خاموش‌کردن همه
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-1.5 bg-panel px-2 py-1 rounded-[var(--radius-sm)] border border-line">
                  <svg className="w-3.5 h-3.5 text-text-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                  <input
                    type="text"
                    data-testid="indicator-search-input"
                    value={indicatorSearchQuery}
                    onChange={(e) => setIndicatorSearchQuery(e.target.value)}
                    placeholder="جستجوی نام یا الگوی اندیکاتور..."
                    className="w-full bg-transparent t-9 text-text focus:outline-none"
                    autoFocus
                  />
                  {indicatorSearchQuery && (
                    <button
                      type="button"
                      onClick={() => setIndicatorSearchQuery('')}
                      className="text-text-3 hover:text-text t-85 px-1"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>

              {/* فهرست آیتم‌های اندیکاتور */}
              <div className="flex-1 overflow-y-auto divide-y divide-line/40 p-1">
                {/* گروه ۱: اندیکاتورهای تلگرام @IndicatorsforTV */}
                {telegramIndicators.length > 0 && (
                  <div className="py-1">
                    <div className="px-2 py-1 t-8 font-bold text-text-3 bg-panel-2/50 rounded flex items-center justify-between">
                      <span>اندیکاتورهای هوشمند تلگرام (@IndicatorsforTV)</span>
                      <span className="text-[10px] text-accent">الگوریتمی</span>
                    </div>
                    {telegramIndicators.map((ind) => {
                      const isActive = activeUserIndicators.includes(ind.id);
                      return (
                        <div
                          key={ind.id}
                          data-testid={`indicator-option-${ind.id}`}
                          onClick={() => toggleUserIndicator(ind.id)}
                          className={`p-2 rounded-[var(--radius-sm)] flex items-start justify-between cursor-pointer transition-colors duration-100 ${
                            isActive
                              ? 'bg-accent/10 border border-accent/30 text-text'
                              : 'hover:bg-panel-2 text-text-2 hover:text-text border border-transparent'
                          }`}
                        >
                          <div className="flex flex-col gap-0.5 min-w-0 flex-1 me-2">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-bold t-95 text-text">{ind.nameFa}</span>
                              <span className="t-8 px-1 py-0.2 rounded bg-panel-3 text-text-3 font-mono">
                                {ind.id}
                              </span>
                            </div>
                            <span className="t-8 text-text-3 line-clamp-1">{ind.descriptionFa}</span>
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                            <span
                              className={`w-4 h-4 rounded flex items-center justify-center border text-[10px] transition-colors ${
                                isActive
                                  ? 'bg-accent text-bg border-accent font-bold'
                                  : 'border-line text-transparent hover:border-text-3'
                              }`}
                            >
                              ✓
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* گروه ۲: اندیکاتورهای تخصصی سورس */}
                {customIndicators.length > 0 && (
                  <div className="py-1">
                    <div className="px-2 py-1 t-8 font-bold text-text-3 bg-panel-2/50 rounded flex items-center justify-between">
                      <span>اندیکاتورهای تخصصی سورس و اسکریپت</span>
                      <span className="text-[10px] text-accent">پرایس‌اکشن</span>
                    </div>
                    {customIndicators.map((ind) => {
                      const isActive = activeUserIndicators.includes(ind.id);
                      return (
                        <div
                          key={ind.id}
                          data-testid={`indicator-option-${ind.id}`}
                          onClick={() => toggleUserIndicator(ind.id)}
                          className={`p-2 rounded-[var(--radius-sm)] flex items-start justify-between cursor-pointer transition-colors duration-100 ${
                            isActive
                              ? 'bg-accent/10 border border-accent/30 text-text'
                              : 'hover:bg-panel-2 text-text-2 hover:text-text border border-transparent'
                          }`}
                        >
                          <div className="flex flex-col gap-0.5 min-w-0 flex-1 me-2">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-bold t-95 text-text">{ind.nameFa}</span>
                              <span className="t-8 px-1 py-0.2 rounded bg-panel-3 text-text-3 font-mono">
                                {ind.name}
                              </span>
                            </div>
                            <span className="t-8 text-text-3 line-clamp-1">{ind.descriptionFa}</span>
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                            <span
                              className={`w-4 h-4 rounded flex items-center justify-center border text-[10px] transition-colors ${
                                isActive
                                  ? 'bg-accent text-bg border-accent font-bold'
                                  : 'border-line text-transparent hover:border-text-3'
                              }`}
                            >
                              ✓
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {telegramIndicators.length === 0 && customIndicators.length === 0 && (
                  <div className="p-4 text-center t-9 text-text-3">
                    اندیکاتوری منطبق با عبارت جستجو یافت نشد.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* منطقه ۲ (وسط): ماژول فشرده پیش‌بینی هوش مصنوعی */}
      <div className="flex items-center gap-1.5 py-0.5 shrink-0">
        <div className="flex items-center gap-1.5 px-2 py-0.5 bg-panel-2/70 rounded-[var(--radius-sm)] border border-line shrink-0">
          <span className="t-9 font-semibold text-text-2 shrink-0 flex items-center gap-1">
            <span>🤖</span>
            <span>پیش‌بینی هوش مصنوعی</span>
          </span>

          {/* سوئیچ روشن/خاموش کان پیش‌بینی */}
          <button
            type="button"
            role="switch"
            aria-checked={showPredictionCone}
            onClick={togglePredictionCone}
            className={`h-5 px-1.5 rounded-[var(--radius-xs)] t-9 font-medium border transition-colors duration-150 flex items-center gap-1 shrink-0 ${
              showPredictionCone
                ? 'bg-panel-3 text-accent border-accent/40'
                : 'bg-panel text-text-3 border-line hover:text-text'
            }`}
          >
            <span>کان پیش‌بینی</span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                showPredictionCone ? 'bg-accent' : 'bg-line-strong'
              }`}
            />
          </button>

          {/* انتخاب نسخه مدل مینی / استاندارد / پایه */}
          <div className="flex items-center h-5 bg-panel p-0.5 rounded-[var(--radius-xs)] border border-line shrink-0">
            {MODEL_OPTIONS.map((m) => {
              const isSelected = forecastModel === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setForecastModel(m.id)}
                  className={`h-4 px-1 rounded-[var(--radius-xs)] t-85 transition-colors duration-150 ${
                    isSelected
                      ? 'bg-panel-3 text-accent font-semibold'
                      : 'text-text-3 hover:text-text'
                  }`}
                >
                  {m.labelFa}
                </button>
              );
            })}
          </div>

          {/* افق پیش‌بینی */}
          <div className="flex items-center h-5 bg-panel p-0.5 rounded-[var(--radius-xs)] border border-line shrink-0">
            {QUICK_HORIZONS.map((h) => {
              const isSelected = horizon === h;
              return (
                <button
                  key={h}
                  type="button"
                  onClick={() => handleSelectHorizon(h)}
                  className={`h-4 px-1.5 rounded-[var(--radius-xs)] t-85 num transition-colors duration-150 ${
                    isSelected
                      ? 'bg-panel-3 text-accent font-semibold'
                      : 'text-text-3 hover:text-text'
                  }`}
                >
                  {toFaDigits(h)} کندل
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* منطقه ۳ (چپ): متریک‌های آماری، نقدشوندگی و لبه سودآوری به سبک Kraken Pro */}
      <div className="flex items-center gap-1.5 shrink-0">
        {isLoading ? (
          <span className="t-9 text-text-3 animate-pulse">محاسبه مدل...</span>
        ) : null}

        {modelUsed ? (
          <span className="h-5 px-1.5 rounded-[var(--radius-xs)] bg-panel-2 border border-line text-text-3 t-85 flex items-center font-mono">
            {modelUsed}
          </span>
        ) : null}

        {/* هشدار نقدشوندگی یا کارت خروجی احتمال */}
        {!isLiquid ? (
          <div
            role="alert"
            className="h-6.5 px-2 rounded-[var(--radius-sm)] bg-panel-2 border border-down/30 text-down t-9 flex items-center gap-1 font-medium"
          >
            <span>هشدار نقدشوندگی: ارزش معاملات روزانه زیر ۵ میلیارد تومان است</span>
          </div>
        ) : (
          <div className="flex items-center h-6.5 px-2 rounded-[var(--radius-sm)] bg-panel-2 border border-line gap-2 shrink-0">
            {/* احتمال صعود */}
            <div className="flex items-center gap-1">
              <span className="t-9 text-text-3">احتمال صعود:</span>
              <span
                className={`t-10 font-bold num ${
                  upsideProb >= 0.5 ? 'text-up' : 'text-down'
                }`}
              >
                {toFaDigits(Math.round(upsideProb * 100))}٪
              </span>
            </div>

            <div className="h-3 w-px bg-line/60" />

            {/* تشدید نوسان */}
            <div className="flex items-center gap-1">
              <span className="t-9 text-text-3">تشدید نوسان:</span>
              <span className="t-10 font-bold num text-warn">
                {faNum(volAmp, 2)}×
              </span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
