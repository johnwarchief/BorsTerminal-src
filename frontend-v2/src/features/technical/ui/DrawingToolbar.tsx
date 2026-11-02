/**
 * frontend-v2/src/features/technical/ui/DrawingToolbar.tsx
 *
 * نوار ابزار رسم عمودی در سمت راست میزکار (پالایش‌شده بر اساس Unslop):
 * - رنگ‌ها متصل به توکن‌های برنجی (panel, panel-2, line, text, accent)
 * - شبکه ۴px و دکمه‌های ۳۲px تراز
 * - بدون پالس و بدون پس‌زمینه‌های بنفش/کهربایی نئونی
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useTechnicalStore } from '../model/technicalStore';
import {
  DRAWING_CATEGORIES,
  getDrawingToolsByCategory,
  type DrawingCategoryMeta,
} from '../model/drawingCatalog';
import type { DrawingCategory, DrawingToolItem, DrawingToolType } from '../model/types';

export interface DrawingToolbarProps {
  className?: string;
  onClearDrawings?: () => void;
}

export const DrawingToolbar: React.FC<DrawingToolbarProps> = ({
  className = '',
  onClearDrawings,
}) => {
  const activeTool = useTechnicalStore((s) => s.activeDrawingTool);
  const setActiveTool = useTechnicalStore((s) => s.setActiveDrawingTool);
  const isMagnetMode = useTechnicalStore((s) => s.isMagnetMode);
  const toggleMagnetMode = useTechnicalStore((s) => s.toggleMagnetMode);
  const isLockedAllDrawings = useTechnicalStore((s) => s.isLockedAllDrawings);
  const toggleLockAllDrawings = useTechnicalStore((s) => s.toggleLockAllDrawings);
  const isHideAllDrawings = useTechnicalStore((s) => s.isHideAllDrawings);
  const toggleHideAllDrawings = useTechnicalStore((s) => s.toggleHideAllDrawings);

  const [openCategory, setOpenCategory] = useState<DrawingCategory | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpenCategory(null);
      }
    };
    if (openCategory) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [openCategory]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (openCategory) {
          setOpenCategory(null);
        } else if (activeTool) {
          setActiveTool(null);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [openCategory, activeTool, setActiveTool]);

  const toggleCategory = useCallback((catId: DrawingCategory) => {
    setOpenCategory((prev) => (prev === catId ? null : catId));
  }, []);

  const handleSelectTool = useCallback(
    (toolId: DrawingToolType) => {
      setActiveTool(activeTool === toolId ? null : toolId);
      setOpenCategory(null);
    },
    [activeTool, setActiveTool],
  );

  const handleClearAll = useCallback(() => {
    setActiveTool(null);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('kline:clear-drawings'));
    }
    onClearDrawings?.();
  }, [setActiveTool, onClearDrawings]);

  const isCategoryActive = useCallback(
    (catId: DrawingCategory): boolean => {
      if (!activeTool) return false;
      const tools = getDrawingToolsByCategory(catId);
      return tools.some((t) => t.id === activeTool);
    },
    [activeTool],
  );

  const renderCategoryIcon = (id: DrawingCategory) => {
    switch (id) {
      case 'lines':
        return (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="20" x2="20" y2="4" />
            <circle cx="4" cy="20" r="1.5" fill="currentColor" />
            <circle cx="20" cy="4" r="1.5" fill="currentColor" />
          </svg>
        );
      case 'fibonacci':
        return (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <line x1="3" y1="5" x2="21" y2="5" />
            <line x1="3" y1="9.5" x2="21" y2="9.5" strokeDasharray="2 2" />
            <line x1="3" y1="14" x2="21" y2="14" />
            <line x1="3" y1="19" x2="21" y2="19" />
          </svg>
        );
      case 'shapes':
        return (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <rect x="4" y="5" width="16" height="14" rx="2" />
            <line x1="4" y1="12" x2="20" y2="12" strokeDasharray="3 3" />
          </svg>
        );
    }
  };

  return (
    <aside
      data-testid="drawing-toolbar"
      aria-label="نوار ابزار رسم"
      className={`relative flex flex-col items-center py-2 px-1 w-10 bg-panel border-s border-line select-none z-20 shrink-0 ${className}`}
    >
      {/* دکمه‌های دسته‌بندی ابزارها */}
      <div className="flex flex-col items-center gap-1 w-full">
        {DRAWING_CATEGORIES.map((cat: DrawingCategoryMeta) => {
          const isActive = isCategoryActive(cat.id);
          const isOpen = openCategory === cat.id;

          return (
            <div key={cat.id} className="relative">
              <button
                type="button"
                onClick={() => toggleCategory(cat.id)}
                title={cat.titleFa}
                aria-label={cat.titleFa}
                aria-haspopup="true"
                aria-expanded={isOpen}
                className={`relative flex items-center justify-center w-8 h-8 rounded-[var(--radius-sm)] transition-colors duration-150 ${
                  isActive
                    ? 'bg-panel-3 text-accent border border-accent/40'
                    : isOpen
                    ? 'bg-panel-2 text-text border border-line-strong'
                    : 'text-text-3 hover:text-text hover:bg-panel-2'
                }`}
              >
                {renderCategoryIcon(cat.id)}
                {isActive && (
                  <span className="absolute bottom-1 right-1 w-1 h-1 rounded-full bg-accent" />
                )}
              </button>

              {/* پاپ‌اور انتخاب ابزار */}
              {isOpen && (
                <div
                  ref={popoverRef}
                  role="menu"
                  aria-label={cat.titleFa}
                  className="absolute right-10 top-0 w-60 p-2 bg-panel border border-line rounded-[var(--radius-md)] shadow-xl z-30 text-right"
                  dir="rtl"
                >
                  <div className="px-2 py-1 mb-1 border-b border-line">
                    <p className="t-11 font-bold text-accent">{cat.titleFa}</p>
                    <p className="t-9 text-text-3 mt-0.5 leading-snug">
                      {cat.descriptionFa}
                    </p>
                  </div>

                  <div className="flex flex-col gap-0.5 max-h-72 overflow-y-auto">
                    {getDrawingToolsByCategory(cat.id).map((tool: DrawingToolItem) => {
                      const isToolSelected = activeTool === tool.id;
                      return (
                        <button
                          key={tool.id}
                          type="button"
                          role="menuitem"
                          onClick={() => handleSelectTool(tool.id)}
                          className={`flex items-start gap-2 px-2 py-1.5 rounded-[var(--radius-sm)] t-11 transition-colors duration-100 w-full text-right ${
                            isToolSelected
                              ? 'bg-panel-3 text-accent font-semibold border border-accent/30'
                              : 'text-text-2 hover:bg-panel-2 hover:text-text'
                          }`}
                        >
                          <span className="mt-0.5 shrink-0 text-text-3">
                            <svg
                              className="w-3.5 h-3.5"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <path d={tool.icon} />
                            </svg>
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className="truncate">{tool.nameFa}</span>
                              {isToolSelected && (
                                <span className="t-9 text-accent">فعال</span>
                              )}
                            </div>
                            <p className="t-9 text-text-3 truncate mt-0.5">
                              {tool.descriptionFa}
                            </p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="w-5 h-px bg-line my-1.5" />

      {/* ابزارهای کنترلی انتها */}
      <div className="flex flex-col items-center gap-1 w-full mt-auto">
        {/* آهنربا */}
        <button
          type="button"
          data-testid="magnet-mode-button"
          onClick={toggleMagnetMode}
          title="حالت آهنربا (چسبیدن به نقاط کلیدی کندل‌ها)"
          aria-label="حالت آهنربا"
          className={`flex items-center justify-center w-8 h-8 rounded-[var(--radius-sm)] transition-colors duration-150 cursor-pointer ${
            isMagnetMode
              ? 'bg-panel-3 text-accent border border-accent/40'
              : 'text-text-3 hover:text-text hover:bg-panel-2'
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 3v7a6 6 0 0 0 12 0V3" />
            <line x1="4" y1="7" x2="8" y2="7" />
            <line x1="16" y1="7" x2="20" y2="7" />
          </svg>
        </button>

        {/* قفل تمام ترسیمات */}
        <button
          type="button"
          data-testid="lock-drawings-button"
          onClick={toggleLockAllDrawings}
          title="قفل کردن تمام ترسیمات روی چارت"
          aria-label="قفل کردن تمام ترسیمات"
          className={`flex items-center justify-center w-8 h-8 rounded-[var(--radius-sm)] transition-colors duration-150 cursor-pointer ${
            isLockedAllDrawings
              ? 'bg-panel-3 text-accent border border-accent/40'
              : 'text-text-3 hover:text-text hover:bg-panel-2'
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </button>

        {/* مخفی‌سازی ترسیمات */}
        <button
          type="button"
          data-testid="hide-drawings-button"
          onClick={toggleHideAllDrawings}
          title="مخفی‌سازی یا نمایش ترسیمات"
          aria-label="مخفی‌سازی یا نمایش ترسیمات"
          className={`flex items-center justify-center w-8 h-8 rounded-[var(--radius-sm)] transition-colors duration-150 cursor-pointer ${
            isHideAllDrawings
              ? 'bg-panel-3 text-accent border border-accent/40'
              : 'text-text-3 hover:text-text hover:bg-panel-2'
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {isHideAllDrawings ? (
              <>
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </>
            ) : (
              <>
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </>
            )}
          </svg>
        </button>

        {/* لغو ابزار فعال */}
        <button
          type="button"
          data-testid="cancel-tool-button"
          onClick={() => setActiveTool(null)}
          disabled={!activeTool}
          title="لغو ابزار فعال"
          aria-label="لغو ابزار فعال"
          className={`flex items-center justify-center w-8 h-8 rounded-[var(--radius-sm)] transition-colors duration-150 ${
            activeTool
              ? 'bg-panel-3 text-accent border border-accent/40 cursor-pointer'
              : 'text-text-3/40 cursor-not-allowed opacity-40'
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {/* پاک‌سازی تمام ترسیمات (سطل زباله) */}
        <button
          type="button"
          data-testid="clear-drawings-button"
          onClick={handleClearAll}
          title="پاک‌سازی تمام ترسیمات"
          aria-label="پاک‌سازی تمام ترسیمات"
          className="flex items-center justify-center w-8 h-8 rounded-[var(--radius-sm)] text-text-3 hover:text-down hover:bg-panel-2 transition-colors duration-150 cursor-pointer"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            <line x1="10" y1="11" x2="10" y2="17" />
            <line x1="14" y1="11" x2="14" y2="17" />
          </svg>
        </button>
      </div>
    </aside>
  );
};
