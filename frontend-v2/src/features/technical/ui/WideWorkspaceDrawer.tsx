/**
 * frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx
 *
 * ستون عریض میزکارهای متنوع در سمت چپ چارت (Wide Workspace Drawer):
 * ۱. جدول ۵۰ نماد برتر بازار بر پایه حجم و ارزش معاملات (Top 50 Market Symbols) با امکان سوییچ فوری چارت
 * ۲. کاتالوگ اندیکاتورها و سوئیچرهای مد (Double Tap 3D, SuperTrend Pullback, CHoCH, Multi-Mode Channel)
 * ۳. انتخاب‌گر دراپ‌داون خانواده چندگانه RSI (استاندارد، فیبوناچی ۸، باندهای بولینگر، آراس‌آی هموار)
 * ۴. اسکنر واحد: الگوهای کلاسیک (کارت، فهرست و قواعد) + رویدادهای پولبک و CHoCH
 * ۵. پنل تحلیل لبه آماری و پرایس‌اکشن نهادی (CandleEdgeCard)
 * ۶. قابلیت تغییر عرض پویا (۴۲۰ تا ۶۴۰ پیکسل) و پشتیبانی از پورتال React (createPortal)
 */

import React, { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import type { DrawerTab } from '../model/types';
import { Top50Panel, useTop50Symbols } from './panels/Top50Panel';
import type { AssetCategoryFilter } from './panels/Top50Panel';
import { IndicatorsPanel } from './panels/IndicatorsPanel';
import { EdgePanel } from './panels/EdgePanel';
import { ScannerFeed } from './ScannerFeed';

export interface WideWorkspaceDrawerProps {
  activeSymbol: string;
  isOpen: boolean;
  onToggleOpen: () => void;
  className?: string;
  /**
   * حالت کنترل‌شده (فید میزکار، R-PB-5): تب فعال از بیرون می‌آید تا برچسب فید و
   * محتوای میزبان هرگز از هم جدا نشوند. نبودِ این prop یعنی خواندن از استور.
   */
  activeTab?: DrawerTab;
  /** گزارش تغییر تب در حالت کنترل‌شده؛ بدون آن، تب‌ها به استور می‌نویسند. */
  onTabChange?: (tab: DrawerTab) => void;
  /** پنهان‌کردن نوار تب داخلی وقتی میزبان (فید) نوار تب خودش را دارد. */
  hideTabs?: boolean;
}

export const WideWorkspaceDrawer: React.FC<WideWorkspaceDrawerProps> = ({
  activeSymbol,
  isOpen,
  onToggleOpen,
  className = '',
  activeTab: controlledTab,
  onTabChange,
  hideTabs = false,
}) => {
  const storeActiveTab = useTechnicalStore((s) => s.activeDrawerTab);
  const storeSetActiveTab = useTechnicalStore((s) => s.setActiveDrawerTab);
  // حالت کنترل‌شده: تبِ میزبان بر محتوای کشو حاکم است (R-PB-5).
  const activeTab = controlledTab ?? storeActiveTab;
  const setActiveTab = onTabChange ?? storeSetActiveTab;
  const drawerWidth = useTechnicalStore((s) => s.leftDrawerWidth);
  const setDrawerWidth = useTechnicalStore((s) => s.setLeftDrawerWidth);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);

  const detectedPullbackSignals = useTechnicalStore((s) => s.detectedPullbackSignals);
  const detectedCHoCHSignals = useTechnicalStore((s) => s.detectedCHoCHSignals);
  const detectedPatterns = useTechnicalStore((s) => s.detectedPatterns);

  const [symbolSearchQuery, setSymbolSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<AssetCategoryFilter>('all');
  const [isPortalModalOpen, setIsPortalModalOpen] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const resizerRef = useRef<HTMLDivElement>(null);

  // ۵۰ نماد برتر بازار؛ بج تب و نوار فعالیت از همین‌جا می‌آید و ردیف‌ها در Top50Panel رندر می‌شوند.
  const top50Symbols = useTop50Symbols();

  // سوییچ سریع نماد در چارت و نوار آدرس
  const handleSelectSymbol = useCallback(
    (sym: string) => {
      setSelectedSymbol(sym);
      if (typeof window !== 'undefined') {
        window.location.hash = `#/technical/${encodeURIComponent(sym)}`;
      }
    },
    [setSelectedSymbol]
  );

  // درگ و تغییر عرض کشویی سایدبار (حرکت به سمت راست عرض را افزایش و به سمت چپ کاهش می‌دهد)
  const handleMouseDownResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsResizing(true);
      const startX = e.clientX;
      const startWidth = drawerWidth;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        setDrawerWidth(startWidth + delta);
      };

      const handleMouseUp = () => {
        setIsResizing(false);
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [drawerWidth, setDrawerWidth]
  );

  // دکمه‌های ناوبری تب‌ها
  const TABS: Array<{ id: DrawerTab; labelFa: string; badge?: string | number }> = [
    { id: 'top50', labelFa: '۵۰ نماد برتر', badge: top50Symbols.length },
    { id: 'indicators', labelFa: 'اندیکاتورها و کانال' },
    { id: 'scanner', labelFa: 'اسکنر الگوها', badge: detectedPatterns.length + detectedPullbackSignals.length + detectedCHoCHSignals.length },
    { id: 'edge', labelFa: 'لبه آماری' },
  ];

  // محتوای مرکزی داخل کشو
  const drawerContent = (
    <div
      data-testid="wide-workspace-drawer"
      aria-label="میزکار عریض تکنیکال و بازار"
      className="flex flex-col h-full bg-panel text-text overflow-hidden select-none"
      dir="rtl"
    >
      {/* سربرگ سایدبار عریض با کنترل‌های تب و دکمه پورتال */}
      <header className="flex flex-col border-b border-line bg-panel-2/60 shrink-0">
        <div className="flex items-center justify-between px-3 py-2 border-b border-line/60">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <h2 className="t-11 font-bold text-accent">میزکار جامع تحلیل و کشف فرصت</h2>
          </div>

          <div className="flex items-center gap-1">
            {/* دکمه پاپ‌اوت به پورتال شناور */}
            <button
              type="button"
              data-testid="portal-modal-btn"
              onClick={() => setIsPortalModalOpen(true)}
              title="باز کردن در پنجره شناور (React Portal)"
              aria-label="باز کردن در پنجره شناور"
              className="p-1 text-text-3 hover:text-accent rounded-[var(--radius-xs)] hover:bg-panel transition-colors"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </button>

            {/* دکمه بستن/جمع کردن سایدبار */}
            <button
              type="button"
              data-testid="close-drawer-btn"
              onClick={onToggleOpen}
              title={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
              aria-label={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
              className="p-1 text-text-3 hover:text-text rounded-[var(--radius-xs)] hover:bg-panel transition-colors"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* نوار تب‌های میزکار؛ وقتی میزبان نوار تب خودش را دارد پنهان می‌شود. */}
        {!hideTabs && (
          <div className="flex items-center gap-1 px-2 py-1 overflow-x-auto" role="tablist">
            {TABS.map((tab) => {
              const isTabActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  data-testid={`drawer-tab-${tab.id}`}
                  aria-selected={isTabActive}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--radius-sm)] text-[11px] font-medium transition-colors shrink-0 ${
                    isTabActive
                      ? 'bg-panel-3 text-accent border border-accent/30 font-semibold shadow-xs'
                      : 'text-text-3 hover:text-text hover:bg-panel'
                  }`}
                >
                  <span>{tab.labelFa}</span>
                  {tab.badge !== undefined && (
                    <span
                      className={`t-85 px-1 py-0.2 rounded-full font-mono ${
                        isTabActive ? 'bg-accent/20 text-accent font-bold' : 'bg-panel-3 text-text-3'
                      }`}
                    >
                      {toFaDigits(tab.badge)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </header>

      {/* ناحیه محتوای تب‌ها */}
      <div className="flex-1 overflow-y-auto min-h-0 relative">
        {/* ۱. تب ۵۰ نماد برتر بازار */}
        {activeTab === 'top50' && (
          <Top50Panel
            activeSymbol={activeSymbol}
            onSelect={handleSelectSymbol}
            searchQuery={symbolSearchQuery}
            onSearchQueryChange={setSymbolSearchQuery}
            selectedCategory={selectedCategory}
            onCategoryChange={setSelectedCategory}
          />
        )}

        {/* ۲. تب کاتالوگ اندیکاتورها و مدهای معاملاتی */}
        {activeTab === 'indicators' && <IndicatorsPanel />}

        {/* ۳. تب اسکنر واحد: الگوهای کلاسیک + رویدادهای پولبک/CHoCH */}
        {activeTab === 'scanner' && (
          <div className="block p-3" data-testid="scanner-panel">
            <ScannerFeed
              patterns={detectedPatterns}
              pullbacks={detectedPullbackSignals}
              chochs={detectedCHoCHSignals}
            />
          </div>
        )}

        {/* ۵. تب لبه آماری کندل‌ها (همیشه سوار در DOM برای آزمون‌های سیستمی) */}
        <EdgePanel symbol={activeSymbol} active={activeTab === 'edge'} />
      </div>
    </div>
  );

  const ACTIVITY_TOOLS: Array<{
    id: DrawerTab;
    labelFa: string;
    icon: React.ReactNode;
    badge?: number;
  }> = [
    {
      id: 'top50',
      labelFa: 'میز کار جامع و ۵۰ نماد برتر',
      badge: top50Symbols.length,
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <line x1="3" y1="9" x2="21" y2="9" />
          <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
      ),
    },
    {
      id: 'indicators',
      labelFa: 'کاتالوگ اندیکاتورها و مدهای کانال',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
        </svg>
      ),
    },
    {
      id: 'scanner',
      labelFa: 'اسکنر الگوهای کلاسیک و ساختار',
      badge: detectedPatterns.length + detectedPullbackSignals.length + detectedCHoCHSignals.length,
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      ),
    },
    {
      id: 'edge',
      labelFa: 'لبه آماری و پرایس‌اکشن نهادی',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
    },
  ];

  const handleActivityIconClick = (tabId: DrawerTab) => {
    if (!isOpen) {
      setActiveTab(tabId);
      onToggleOpen();
    } else {
      if (activeTab === tabId) {
        onToggleOpen();
      } else {
        setActiveTab(tabId);
      }
    }
  };

  // در صورت بسته بودن سایدبار، نوار باریک آیکون‌های فعالیت در منتهی‌الیه چپ نشان داده می‌شود
  if (!isOpen) {
    return (
      <aside
        data-testid="wide-workspace-drawer-collapsed"
        className="w-11 h-full bg-panel border-r border-line flex flex-col items-center py-2 shrink-0 select-none z-15"
        dir="rtl"
      >
        <button
          type="button"
          onClick={onToggleOpen}
          title={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
          aria-label={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
          className="flex items-center justify-center w-8 h-8 rounded text-text-3 hover:text-accent hover:bg-panel-2 transition-colors"
        >
          <svg className="w-4 h-4 rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        {/* نوار باریک آیکون‌های ابزار و میزکار */}
        <div className="flex flex-col items-center gap-2 mt-4 text-text-3 w-full px-1">
          {ACTIVITY_TOOLS.map((tool) => (
            <button
              key={tool.id}
              type="button"
              data-testid={`activity-bar-icon-${tool.id}`}
              onClick={() => handleActivityIconClick(tool.id)}
              title={tool.labelFa}
              className="relative flex items-center justify-center w-8 h-8 rounded text-text-3 hover:text-accent hover:bg-panel-2 transition-colors"
            >
              {tool.icon}
              {tool.badge !== undefined && tool.badge > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-accent text-bg text-[9px] font-bold font-mono flex items-center justify-center">
                  {toFaDigits(Math.min(tool.badge, 99))}
                </span>
              )}
            </button>
          ))}
        </div>
      </aside>
    );
  }

  return (
    <>
      <div
        data-testid="drawer-backdrop"
        aria-hidden="true"
        onClick={onToggleOpen}
        className="absolute inset-0 z-20 bg-black/30"
      />
      <aside
        style={{ width: `${drawerWidth}px` }}
        className={`absolute left-0 top-0 h-full border-e border-line bg-panel flex flex-row select-none z-30 ${
          isResizing ? 'cursor-col-resize select-none' : ''
        } ${className}`}
        dir="rtl"
      >
        {/* دستگیره درگ جهت تغییر عرض روی مرز مشترک با چارت */}
        <div
          ref={resizerRef}
          data-testid="drawer-resizer-handle"
          onMouseDown={handleMouseDownResize}
          title="درگ برای تغییر عرض ستون"
          className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-accent/40 active:bg-accent z-20 transition-colors"
        />

        {/* ستون خیلی باریک آیکون‌ها در منتهی‌الیه چپ */}
        <div
          data-testid="slim-activity-bar"
          className="w-11 h-full bg-panel-2/80 border-e border-line flex flex-col items-center py-2 shrink-0 z-10"
        >
          {/* دکمه بستن/جمع کردن سایدبار */}
          <button
            type="button"
            onClick={onToggleOpen}
            title="جمع کردن نوار فعالیت"
            aria-label="جمع کردن نوار فعالیت"
            className="flex items-center justify-center w-8 h-8 rounded text-text-3 hover:text-accent hover:bg-panel transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>

          {/* آیکون‌های ابزار و تب‌های عمودی */}
          <div className="flex flex-col items-center gap-2 mt-4 text-text-3 w-full px-1">
            {ACTIVITY_TOOLS.map((tool) => {
              const isActive = activeTab === tool.id;
              return (
                <button
                  key={tool.id}
                  type="button"
                  data-testid={`activity-bar-icon-${tool.id}`}
                  onClick={() => handleActivityIconClick(tool.id)}
                  title={tool.labelFa}
                  className={`relative flex items-center justify-center w-8 h-8 rounded transition-colors ${
                    isActive
                      ? 'bg-panel-3 text-accent border border-accent/40 shadow-xs font-bold'
                      : 'hover:text-accent hover:bg-panel'
                  }`}
                >
                  {tool.icon}
                  {tool.badge !== undefined && tool.badge > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-accent text-bg text-[9px] font-bold font-mono flex items-center justify-center">
                      {toFaDigits(Math.min(tool.badge, 99))}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* محتوای سایدبار عریض */}
        <div className="flex-1 h-full min-w-0 overflow-hidden flex flex-col">
          {drawerContent}
        </div>
      </aside>

      {/* مودال پورتال در صورت تمایل کاربر به داشتن میزکار شناور تمام‌صفحه */}
      {isPortalModalOpen && typeof document !== 'undefined' &&
        createPortal(
          <div
            data-testid="portal-modal-backdrop"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6"
            dir="rtl"
          >
            <div className="relative w-full max-w-4xl h-[85vh] bg-panel border border-line rounded-[var(--radius-md)] shadow-2xl overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-line bg-panel-2">
                <span className="font-bold text-accent t-12">میزکار جامع (پنجره شناور پورتال)</span>
                <button
                  type="button"
                  onClick={() => setIsPortalModalOpen(false)}
                  className="px-2 py-0.5 rounded text-text-3 hover:text-text hover:bg-panel"
                >
                  ✕ بستن
                </button>
              </div>
              <div className="flex-1 overflow-hidden">{drawerContent}</div>
            </div>
          </div>,
          document.body
        )}
    </>
  );
};
