/**
 * frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx
 *
 * فید رویدادهای پایین میزکار (B1، اصلاح R-PB-5):
 * - تب‌های خود فید طبق §3: رویدادها | ۵۰ نماد | اندیکاتورها | لبه آماری.
 * - همین تب‌ها activePanel و activeDrawerTab را با هم می‌نویسند و پنلِ میزبان
 *   (کشوی موقت) را کنترل می‌کنند؛ پس برچسبِ فید هم‌یشه با محتوای رندرشده یکی است.
 */

import React from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import type { DrawerTab, WorkspacePanel } from '../../model/types';
import { WideWorkspaceDrawer } from '../WideWorkspaceDrawer';
import { DRAWER_TAB_BY_PANEL, PANEL_BY_DRAWER_TAB, PANEL_LABELS } from './panelMapping';

/**
 * پرچمِ موقتِ B1: محتوای کشوی موجود تا انتقال پنل‌ها (B2/B3) در فید می‌ماند.
 * هیچ مصرف‌کنندهٔ دیگری نباید به این پرچم وابسته شود.
 */
export const TEMP_HOST_LEGACY_DRAWER_IN_FEED = true;

/** تب‌های فید دقیقاً طبق §3؛ برچسب‌ها از panelMapping می‌آیند تا تک‌منبع بمانند. */
const FEED_TABS: WorkspacePanel[] = ['events', 'top50', 'indicators', 'edge'];

export interface EventFeedProps {
  /** نماد فعال؛ به کشوی موقت پاس داده می‌شود. */
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

  /** تعویض پنلِ فید: هر دو وضعیت با هم نوشته می‌شوند تا برچسب/محتوا از هم جدا نشوند. */
  const selectPanel = (panel: WorkspacePanel) => {
    setActivePanel(panel);
    setActiveDrawerTab(DRAWER_TAB_BY_PANEL[panel]);
    if (!feedOpen) {
      toggleFeed();
    }
  };

  /** تغییر تب از داخل کشوی میزبان (حالت کنترل‌شده) به پنل فید ترجمه می‌شود. */
  const handleHostedTabChange = (tab: DrawerTab) => {
    selectPanel(PANEL_BY_DRAWER_TAB[tab]);
  };

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
          <span className="text-xs text-text-3 truncate hidden md:inline">
            پنل‌های میزکار تا تسک B3 موقتاً در همین فید می‌مانند.
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
        ارتفاع ثابت ۳۲۰px (h-80) در B1 اندازهٔ پذیرش است؛ کشوی موقت absolute
        داخل همین بدنه می‌نشیند. واکنش‌گرایی این ارتفاع در B5 انجام می‌شود.
        بدنه در حالتِ بسته unmount نمی‌شود، فقط hidden می‌شود تا aria-controls معتبر بماند.
      */}
      <div
        id="workspace-feed-body"
        data-testid="workspace-feed-body"
        hidden={!feedOpen}
        className="relative h-80 border-t border-line overflow-hidden"
      >
        {feedOpen ? (
          TEMP_HOST_LEGACY_DRAWER_IN_FEED ? (
            <WideWorkspaceDrawer
              activeSymbol={activeSymbol}
              isOpen
              onToggleOpen={toggleFeed}
              activeTab={DRAWER_TAB_BY_PANEL[activePanel]}
              onTabChange={handleHostedTabChange}
              hideTabs
            />
          ) : (
            <div className="h-full p-3 text-xs leading-6 text-text-3">
              پنل‌های فید (رویدادها، ۵۰ نماد، اندیکاتورها، لبه آماری) در تسک بعدی اینجا ساخته می‌شوند.
            </div>
          )
        ) : null}
      </div>
    </section>
  );
};
