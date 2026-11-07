/**
 * frontend-v2/src/features/technical/ui/workspace/WorkspaceTopbar.tsx
 *
 * نوار بالای میزکار تازه (B1) — مطابق §3 سند طراحی:
 *   نماد │ تایم‌فریم │ تعدیل (۳ = عملکردی) │ نوع چارت
 * فقط همان فیلدهای استور موجود را می‌خواند/می‌نویسد؛ هیچ وضعیت تازه‌ای
 * برای این نوار ساخته نمی‌شود. ForecastControls فعلی هم دست‌نخورده در
 * ناحیهٔ چارت سوار می‌ماند تا تسک‌های بعدی آن را جابه‌جا کنند.
 */

import React, { useEffect, useState } from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import { TIMEFRAME_OPTIONS } from '../../model/timeframeAggregation';
import { useTechnicalWorkspaceStore } from '../../workspace/technicalWorkspaceStore';
import { MODE_LABEL, WORKSPACE_MODES } from '../../workspace/presets';
import { LayoutMenu } from './LayoutMenu';

interface AdjustmentOption {
  value: number;
  labelFa: string;
}

const ADJUSTMENT_OPTIONS: AdjustmentOption[] = [
  { value: 3, labelFa: 'عملکردی' },
  { value: 1, labelFa: 'افزایش سرمایه' },
  { value: 2, labelFa: 'سود نقدی' },
  { value: 0, labelFa: 'بدون تعدیل' },
];

/**
 * نوع چارت در KLineChartWrapper فعلی ثابت (شمعی توپر) است؛ این اسلات
 * قرارداد §3 را نگه می‌دارد تا وقتی موتور نوع‌های بیشتر را expose کند.
 */
const CHART_TYPES = [{ id: 'candle', labelFa: 'شمعی' }] as const;

export interface WorkspaceTopbarProps {
  className?: string;
  /** باز کردن پالت دستور از دکمهٔ Ctrl+K. */
  onOpenPalette?: () => void;
}

export const WorkspaceTopbar: React.FC<WorkspaceTopbarProps> = ({
  className = '',
  onOpenPalette,
}) => {
  const selectedSymbol = useTechnicalStore((s) => s.selectedSymbol);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);
  const timeframe = useTechnicalStore((s) => s.timeframe);
  const setTimeframe = useTechnicalStore((s) => s.setTimeframe);
  const adjustmentMode = useTechnicalStore((s) => s.adjustmentMode);
  const setAdjustmentMode = useTechnicalStore((s) => s.setAdjustmentMode);
  const mode = useTechnicalWorkspaceStore((s) => s.mode);
  const setMode = useTechnicalWorkspaceStore((s) => s.setMode);

  const [symbolInput, setSymbolInput] = useState(selectedSymbol || 'فولاد');

  useEffect(() => {
    if (selectedSymbol) {
      setSymbolInput(selectedSymbol);
    }
  }, [selectedSymbol]);

  const submitSymbol = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = symbolInput.trim();
    if (!trimmed) return;
    setSelectedSymbol(trimmed);
    if (typeof window !== 'undefined') {
      window.location.hash = `#/technical/${encodeURIComponent(trimmed)}`;
    }
  };

  return (
    <header
      data-testid="workspace-topbar"
      aria-label="نوار بالای میزکار تکنیکال"
      style={{ gridArea: 'topbar' }}
      className={`h-14 px-3 bg-panel border-b border-line flex items-center gap-3 select-none ${className}`}
      dir="rtl"
    >
      {/* هویت میزکار */}
      <div className="flex items-center gap-2 shrink-0">
        <span aria-hidden className="w-2 h-2 rounded-full bg-accent" />
        <h1 className="text-sm font-medium text-accent whitespace-nowrap">میزکار تکنیکال</h1>
      </div>

      <span aria-hidden className="h-6 w-px bg-line shrink-0" />

      {/* مودهای میزکار: تحلیل | اسکن | پژوهش */}
      <div
        role="group"
        aria-label="حالت میزکار"
        data-testid="workspace-mode-switcher"
        className="flex items-center h-9 p-1 bg-panel-2 rounded-[var(--radius-md)] border border-line shrink-0"
      >
        {WORKSPACE_MODES.map((item) => {
          const isSelected = mode === item;
          return (
            <button
              key={item}
              type="button"
              data-testid={`workspace-mode-${item}`}
              aria-pressed={isSelected}
              title={`حالت ${MODE_LABEL[item]}`}
              onClick={() => setMode(item)}
              className={`h-7 px-2 rounded-[var(--radius-md)] text-xs transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                isSelected
                  ? 'bg-panel-3 text-accent font-medium'
                  : 'text-text-3 hover:text-text'
              }`}
            >
              {MODE_LABEL[item]}
            </button>
          );
        })}
      </div>

      <span
        data-testid="workspace-mode-label"
        className="text-xs text-text-3 whitespace-nowrap shrink-0"
      >
        حالت: {MODE_LABEL[mode]}
      </span>

      <span aria-hidden className="h-6 w-px bg-line shrink-0" />

      {/* نماد */}
      <form
        onSubmit={submitSymbol}
        data-testid="workspace-symbol-form"
        className="flex items-center gap-2 h-9 px-2 bg-panel-2 rounded-[var(--radius-md)] border border-line focus-within:border-accent shrink-0"
      >
        <label htmlFor="workspace-symbol-input" className="text-xs text-text-3">
          نماد
        </label>
        <input
          id="workspace-symbol-input"
          data-testid="workspace-symbol-input"
          type="text"
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          placeholder="فولاد"
          className="w-24 bg-transparent text-xs font-medium text-accent focus:outline-none"
        />
        <button
          type="submit"
          title="بارگذاری نماد"
          className="h-7 px-2 rounded-[var(--radius-md)] text-xs text-text-3 hover:text-accent hover:bg-panel transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          اعمال
        </button>
      </form>

      {/* تایم‌فریم */}
      <div
        role="group"
        aria-label="تایم‌فریم"
        data-testid="workspace-timeframe"
        className="flex items-center h-9 p-1 bg-panel-2 rounded-[var(--radius-md)] border border-line shrink-0"
      >
        {TIMEFRAME_OPTIONS.map((tf) => {
          const isSelected = timeframe === tf.id;
          return (
            <button
              key={tf.id}
              type="button"
              data-testid={`workspace-timeframe-${tf.id}`}
              aria-pressed={isSelected}
              title={tf.tooltipFa}
              onClick={() => setTimeframe(tf.id)}
              className={`h-7 px-2 rounded-[var(--radius-md)] text-xs transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                isSelected
                  ? 'bg-panel-3 text-accent font-medium'
                  : 'text-text-3 hover:text-text'
              }`}
            >
              {tf.labelFa}
            </button>
          );
        })}
      </div>

      {/* تعدیل */}
      <div
        data-testid="workspace-adjustment"
        className="flex items-center gap-2 h-9 px-2 bg-panel-2 rounded-[var(--radius-md)] border border-line shrink-0"
      >
        <label htmlFor="workspace-adjustment-select" className="text-xs text-text-3">
          تعدیل
        </label>
        <select
          id="workspace-adjustment-select"
          data-testid="workspace-adjustment-select"
          value={adjustmentMode}
          onChange={(e) => setAdjustmentMode(Number(e.target.value))}
          className="h-7 bg-transparent text-xs text-text cursor-pointer outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {ADJUSTMENT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-panel-2 text-text">
              {opt.labelFa}
            </option>
          ))}
        </select>
      </div>

      {/* نوع چارت */}
      <div
        role="group"
        aria-label="نوع چارت"
        data-testid="chart-type-selector"
        className="flex items-center h-9 p-1 bg-panel-2 rounded-[var(--radius-md)] border border-line shrink-0"
      >
        {CHART_TYPES.map((type) => (
          <span
            key={type.id}
            title="نوع چارت فعلی میزکار؛ گزینه‌های بیشتر در تسک‌های بعدی"
            className="h-7 px-2 flex items-center rounded-[var(--radius-md)] text-xs bg-panel-3 text-accent font-medium"
          >
            {type.labelFa}
          </span>
        ))}
      </div>

      {/* چیدمان‌های نام‌دار + پالت دستور */}
      <div className="ms-auto flex items-center gap-2 shrink-0">
        <LayoutMenu />
        <button
          type="button"
          data-testid="workspace-command-btn"
          onClick={onOpenPalette}
          title="همهٔ کارها (Ctrl+K)"
          aria-label="باز کردن پالت دستور"
          className="h-9 px-2 rounded-[var(--radius-md)] border border-line bg-panel-2 text-xs text-text-3 hover:text-accent hover:bg-panel-3 transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent shrink-0"
        >
          Ctrl+K
        </button>
      </div>
    </header>
  );
};
