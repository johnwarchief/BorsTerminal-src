/**
 * frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx
 *
 * فید رویدادهای پایین میزکار (B3/B4):
 * - تب‌های خود فید طبق §3: رویدادها | ۵۰ نماد | اندیکاتورها | لبه آماری.
 * - هر تب پنل خودش را میزبانی می‌کند: رویدادها → ScannerFeed (فهرست/رویدادها/قواعد،
 *   بدون کارت)، ۵۰ نماد → Top50Panel، اندیکاتورها → IndicatorsPanel، لبه آماری → EdgePanel.
 * - B4: دکمهٔ پاپ‌اوت (portal-modal-btn) از کشوی بازنشسته به سربرگ فید منتقل شده و
 *   همان پنلِ انتخاب‌شده را در پنجرهٔ شناور React Portal نشان می‌دهد (Escape/دکمه بستن).
 * - کارت رویداد فعال در ریل بازرس زندگی می‌کند، نه در این فید.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTechnicalStore } from '../../model/technicalStore';
import type { WorkspacePanel } from '../../model/types';
import { ScannerFeed } from '../ScannerFeed';
import { Top50Panel } from '../panels/Top50Panel';
import type { AssetCategoryFilter } from '../panels/Top50Panel';
import { IndicatorsPanel } from '../panels/IndicatorsPanel';
import { EdgePanel } from '../panels/EdgePanel';
import { PANEL_LABELS } from './panelMapping';

/** تب‌های فید دقیقاً طبق §3؛ برچسب‌ها از panelMapping می‌آیند تا تک‌منبع بمانند. */
const FEED_TABS: WorkspacePanel[] = ['events', 'top50', 'indicators', 'edge'];

export interface EventFeedProps {
  /** نماد فعال؛ به پنل‌های ۵۰ نماد و لبه آماری پاس داده می‌شود. */
  activeSymbol: string;
  className?: string;
}

export const EventFeed: React.FC<EventFeedProps> = ({ activeSymbol, className = '' }) => {
  const activePanel = useTechnicalStore((s) => s.activePanel);
  const setActivePanel = useTechnicalStore((s) => s.setActivePanel);
  // R-PB-1: همان پرچمِ کشو؛ هیچ پرچم دومی وجود ندارد.
  const feedOpen = useTechnicalStore((s) => s.isLeftDrawerOpen);
  const toggleFeed = useTechnicalStore((s) => s.toggleFeed);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);

  const detectedPatterns = useTechnicalStore((s) => s.detectedPatterns);
  const detectedPullbackSignals = useTechnicalStore((s) => s.detectedPullbackSignals);
  const detectedCHoCHSignals = useTechnicalStore((s) => s.detectedCHoCHSignals);

  // وضعیت جستجو/دستهٔ پنل ۵۰ نماد هنگام تعویض تب حفظ می‌شود.
  const [symbolSearchQuery, setSymbolSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<AssetCategoryFilter>('all');

  // B4: پنجرهٔ شناور پورتال؛ محتوایش همان پنل انتخاب‌شدهٔ فید است.
  const [isPortalOpen, setIsPortalOpen] = useState(false);
  const portalTriggerRef = useRef<HTMLButtonElement>(null);

  const closePortal = useCallback(() => {
    setIsPortalOpen(false);
    portalTriggerRef.current?.focus();
  }, []);

  // Escape پنجرهٔ شناور را می‌بندد و تمرکز را به دکمهٔ پاپ‌اوت برمی‌گرداند.
  useEffect(() => {
    if (!isPortalOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closePortal();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPortalOpen, closePortal]);

  /** تعویض پنلِ فید؛ تنها منبع انتخاب پنل، هم برای بدنه و هم برای پورتال. */
  const selectPanel = (panel: WorkspacePanel) => {
    setActivePanel(panel);
    if (!feedOpen) {
      toggleFeed();
    }
  };

  /** سوییچ سریع نماد در چارت و نوار آدرس، همان رفتار کشوی قبلی. */
  const handleSelectSymbol = useCallback(
    (symbol: string) => {
      setSelectedSymbol(symbol);
      if (typeof window !== 'undefined') {
        window.location.hash = `#/technical/${encodeURIComponent(symbol)}`;
      }
    },
    [setSelectedSymbol]
  );

  /** محتوای پنلِ انتخاب‌شده؛ بدنهٔ فید و پنجرهٔ شناور از همین یک منبع می‌خوانند. */
  const renderPanel = (panel: WorkspacePanel) => {
    if (panel === 'events') {
      // scanner-panel همان ظرف تب رویدادهاست؛ کارت رویداد فعال این‌جا نیست.
      return (
        <div data-testid="scanner-panel" className="h-full overflow-y-auto">
          <ScannerFeed
            patterns={detectedPatterns}
            pullbacks={detectedPullbackSignals}
            chochs={detectedCHoCHSignals}
          />
        </div>
      );
    }

    if (panel === 'top50') {
      return (
        <div className="h-full overflow-y-auto">
          <Top50Panel
            activeSymbol={activeSymbol}
            onSelect={handleSelectSymbol}
            searchQuery={symbolSearchQuery}
            onSearchQueryChange={setSymbolSearchQuery}
            selectedCategory={selectedCategory}
            onCategoryChange={setSelectedCategory}
          />
        </div>
      );
    }

    if (panel === 'indicators') {
      return (
        <div className="h-full overflow-y-auto">
          <IndicatorsPanel />
        </div>
      );
    }

    return (
      <div className="h-full overflow-y-auto">
        <EdgePanel symbol={activeSymbol} active />
      </div>
    );
  };

  return (
    <>
      <section
        data-testid="workspace-feed"
        aria-label="فید رویدادهای میزکار"
        style={{ gridArea: 'feed' }}
        className={`bg-panel border-t border-line select-none ${className}`}
        dir="rtl"
      >
        {/* سربرگ فید: همیشه دیده می‌شود تا فید جمع‌شونده بماند. */}
        <header className="h-10 px-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="text-xs font-medium text-text whitespace-nowrap">فید رویدادها</h2>
            <span aria-hidden className="h-4 w-px bg-line shrink-0" />

            {/* تب‌های خود فید؛ تنها مرجعِ انتخاب پنل (R-PB-5). */}
            <div
              role="tablist"
              aria-label="پنل‌های فید"
              data-testid="workspace-feed-tabs"
              className="flex items-center gap-1 min-w-0 overflow-x-auto"
            >
              {FEED_TABS.map((panel) => {
                const isSelected = activePanel === panel;
                return (
                  <button
                    key={panel}
                    type="button"
                    role="tab"
                    data-testid={`feed-tab-${panel}`}
                    aria-selected={isSelected}
                    onClick={() => selectPanel(panel)}
                    className={`h-8 px-2 rounded-[var(--radius-sm)] text-xs whitespace-nowrap transition-colors ${
                      isSelected
                        ? 'bg-panel-3 text-accent border border-accent/40 font-medium'
                        : 'text-text-3 border border-transparent hover:text-text hover:bg-panel-2'
                    }`}
                  >
                    {PANEL_LABELS[panel]}
                  </button>
                );
              })}
            </div>

            <span aria-hidden className="h-4 w-px bg-line shrink-0" />
            <span data-testid="workspace-feed-active-panel" className="text-xs text-text-3 truncate">
              {PANEL_LABELS[activePanel]}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {/* B4: پاپ‌اوتِ کشوی بازنشسته؛ همان پنلِ انتخاب‌شده را شناور می‌کند. */}
            <button
              ref={portalTriggerRef}
              type="button"
              data-testid="portal-modal-btn"
              onClick={() => setIsPortalOpen(true)}
              title="باز کردن در پنجره شناور (React Portal)"
              aria-label="باز کردن در پنجره شناور"
              aria-haspopup="dialog"
              aria-expanded={isPortalOpen}
              className="p-1 text-text-3 hover:text-accent rounded-[var(--radius-xs)] hover:bg-panel transition-colors"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </button>

            <button
              type="button"
              data-testid="workspace-feed-toggle"
              aria-expanded={feedOpen}
              // بدنه همیشه در DOM می‌ماند (بسته: hidden)، پس هدفِ aria-controls همیشه هست.
              aria-controls="workspace-feed-body"
              // عنوانِ حالتِ بسته برای سازگاری با آزمون‌های موجود میزکار حفظ شده است.
              title={feedOpen ? 'جمع‌کردن فید رویدادها' : 'باز کردن سایدبار لبه آماری'}
              onClick={toggleFeed}
              className="shrink-0 h-8 px-2 rounded-[var(--radius-sm)] border border-line bg-panel-2 text-xs text-text-2 hover:text-text hover:bg-panel-3 transition-colors"
            >
              {feedOpen ? 'جمع‌کردن فید' : 'باز کردن فید'}
            </button>
          </div>
        </header>

        {/*
          ارتفاع ثابت ۳۲۰px (h-80) در B1 اندازهٔ پذیرش است؛ هر پنل داخل همین
          بدنه اسکرول می‌شود. واکنش‌گرایی این ارتفاع در B5 انجام می‌شود.
          بدنه در حالتِ بسته unmount نمی‌شود، فقط hidden می‌شود تا aria-controls معتبر بماند.
        */}
        <div
          id="workspace-feed-body"
          data-testid="workspace-feed-body"
          hidden={!feedOpen}
          className="relative h-80 border-t border-line overflow-hidden"
        >
          {feedOpen ? (
            <>
              {activePanel !== 'edge' ? renderPanel(activePanel) : null}

              {/* لبه آماری مثل قبل سوار در DOM می‌ماند و فقط با کلاس hidden پنهان می‌شود. */}
              <div className="h-full overflow-y-auto">
                <EdgePanel symbol={activeSymbol} active={activePanel === 'edge'} />
              </div>
            </>
          ) : null}
        </div>
      </section>

      {/* B4: پنجرهٔ شناور همان محتوای پنل انتخاب‌شده (پورت‌شده از کشوی بازنشسته). */}
      {isPortalOpen && typeof document !== 'undefined'
        ? createPortal(
            <div
              data-testid="portal-modal-backdrop"
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6"
              dir="rtl"
            >
              <div
                role="dialog"
                aria-modal="true"
                aria-label="میزکار شناور پنل‌های تحلیل"
                className="relative w-full max-w-4xl h-[85vh] bg-panel border border-line rounded-[var(--radius-md)] shadow-2xl overflow-hidden flex flex-col"
              >
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-line bg-panel-2">
                  <span className="font-bold text-accent t-12">میزکار جامع (پنجره شناور پورتال)</span>
                  <button
                    type="button"
                    data-testid="portal-modal-close"
                    onClick={closePortal}
                    autoFocus
                    className="px-2 py-0.5 rounded text-text-3 hover:text-text hover:bg-panel"
                  >
                    ✕ بستن
                  </button>
                </div>
                <div className="flex-1 overflow-hidden">{renderPanel(activePanel)}</div>
              </div>
            </div>,
            document.body
          )
        : null}
    </>
  );
};
