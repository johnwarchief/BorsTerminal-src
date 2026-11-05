/**
 * frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx
 *
 * فید رویدادهای پایین میزکار (B1) — طبق §3 جمع‌شونده است.
 * در این تسک فقط پوستهٔ فید و جای‌گیر پنل‌ها ساخته می‌شود؛ برای حفظ کاملِ
 * قابلیت‌ها، محتوای کشوی عریضِ فعلی موقتاً داخل همین فید سوار می‌ماند
 * (پشتِ پرچمِ TEMP_HOST_LEGACY_DRAWER_IN_FEED). تسک‌های B2/B3 پنل‌ها را
 * به فید منتقل و این پرچم را حذف می‌کنند.
 */

import React from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import type { WorkspacePanel } from '../../model/types';
import { WideWorkspaceDrawer } from '../WideWorkspaceDrawer';

/**
 * پرچمِ موقتِ B1: محتوای کشوی موجود تا انتقال پنل‌ها (B2/B3) در فید می‌ماند.
 * هیچ مصرف‌کنندهٔ دیگری نباید به این پرچم وابسته شود.
 */
export const TEMP_HOST_LEGACY_DRAWER_IN_FEED = true;

const PANEL_LABELS: Record<WorkspacePanel, string> = {
  events: 'رویدادها',
  top50: '۵۰ نماد برتر',
  indicators: 'اندیکاتورها',
  edge: 'لبه آماری',
};

export interface EventFeedProps {
  /** نماد فعال؛ به کشوی موقت پاس داده می‌شود. */
  activeSymbol: string;
  className?: string;
}

export const EventFeed: React.FC<EventFeedProps> = ({ activeSymbol, className = '' }) => {
  const activePanel = useTechnicalStore((s) => s.activePanel);
  // R-PB-1: همان پرچمِ کشو؛ هیچ پرچم دومی وجود ندارد.
  const feedOpen = useTechnicalStore((s) => s.isLeftDrawerOpen);
  const toggleFeed = useTechnicalStore((s) => s.toggleFeed);

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
          aria-controls="workspace-feed-body"
          // عنوانِ حالتِ بسته برای سازگاری با آزمون‌های موجود میزکار حفظ شده است.
          title={feedOpen ? 'جمع‌کردن فید رویدادها' : 'باز کردن سایدبار لبه آماری'}
          onClick={toggleFeed}
          className="shrink-0 h-7 px-2.5 rounded-[var(--radius-sm)] border border-line bg-panel-2 text-xs text-text-2 hover:text-text hover:bg-panel-3 transition-colors"
        >
          {feedOpen ? 'جمع‌کردن فید' : 'باز کردن فید'}
        </button>
      </header>

      {feedOpen && (
        <div
          id="workspace-feed-body"
          data-testid="workspace-feed-body"
          className="relative h-80 border-t border-line overflow-hidden"
        >
          {TEMP_HOST_LEGACY_DRAWER_IN_FEED ? (
            <WideWorkspaceDrawer
              activeSymbol={activeSymbol}
              isOpen
              onToggleOpen={toggleFeed}
            />
          ) : (
            <div className="h-full p-3 text-xs leading-6 text-text-3">
              پنل‌های فید (رویدادها، ۵۰ نماد، اندیکاتورها، لبه آماری) در تسک بعدی اینجا ساخته می‌شوند.
            </div>
          )}
        </div>
      )}
    </section>
  );
};
