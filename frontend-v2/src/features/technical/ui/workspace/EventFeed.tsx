/**
 * frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx
 *
 * فید رویدادهای پایین میزکار (B3):
 * - تب‌های خود فید طبق §3: رویدادها | ۵۰ نماد | اندیکاتورها | لبه آماری.
 * - هر تب پنل خودش را میزبانی می‌کند: رویدادها → ScannerFeed (فهرست/رویدادها/قواعد،
 *   بدون کارت)، ۵۰ نماد → Top50Panel، اندیکاتورها → IndicatorsPanel، لبه آماری → EdgePanel.
 * - همین تب‌ها activePanel و activeDrawerTab را با هم می‌نویسند تا برچسبِ فید و
 *   محتوای رندرشده هرگز از هم جدا نشوند (R-PB-5).
 * - کارت رویداد فعال در ریل بازرس زندگی می‌کند، نه در این فید.
 */

import React, { useCallback, useState } from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import type { WorkspacePanel } from '../../model/types';
import { ScannerFeed } from '../ScannerFeed';
import { Top50Panel } from '../panels/Top50Panel';
import type { AssetCategoryFilter } from '../panels/Top50Panel';
import { IndicatorsPanel } from '../panels/IndicatorsPanel';
import { EdgePanel } from '../panels/EdgePanel';
import { DRAWER_TAB_BY_PANEL, PANEL_LABELS } from './panelMapping';

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
  const setActiveDrawerTab = useTechnicalStore((s) => s.setActiveDrawerTab);
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

  /** تعویض پنلِ فید: هر دو وضعیت با هم نوشته می‌شوند تا برچسب/محتوا از هم جدا نشوند. */
  const selectPanel = (panel: WorkspacePanel) => {
    setActivePanel(panel);
    setActiveDrawerTab(DRAWER_TAB_BY_PANEL[panel]);
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

  return (
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
            {activePanel === 'events' ? (
              // scanner-panel همان ظرف تب رویدادهاست؛ کارت رویداد فعال این‌جا نیست.
              <div data-testid="scanner-panel" className="h-full overflow-y-auto">
                <ScannerFeed
                  patterns={detectedPatterns}
                  pullbacks={detectedPullbackSignals}
                  chochs={detectedCHoCHSignals}
                />
              </div>
            ) : null}

            {activePanel === 'top50' ? (
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
            ) : null}

            {activePanel === 'indicators' ? (
              <div className="h-full overflow-y-auto">
                <IndicatorsPanel />
              </div>
            ) : null}

            {/* لبه آماری مثل قبل سوار در DOM می‌ماند و فقط با کلاس hidden پنهان می‌شود. */}
            <div className="h-full overflow-y-auto">
              <EdgePanel symbol={activeSymbol} active={activePanel === 'edge'} />
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
};
