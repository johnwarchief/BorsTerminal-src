/**
 * frontend-v2/src/features/technical/ui/workspace/InspectorRail.tsx
 *
 * ریل بازرس ۲۸۰px (B1) — طبق §3: لایه‌ها، رویداد فعال و قواعد.
 * در B1 فقط جای‌گیر است؛ کارت رویداد فعال و لایه‌ها در تسک B3 به این ریل
 * منتقل می‌شوند. محتوای فعلی کشو موقتاً در فید (EventFeed) سوار است تا
 * هیچ قابلیتی از دست نرود.
 */

import React from 'react';

export interface InspectorRailProps {
  className?: string;
}

export const InspectorRail: React.FC<InspectorRailProps> = ({ className = '' }) => {
  return (
    <aside
      data-testid="workspace-rail"
      aria-label="ریل بازرس تحلیل"
      style={{ gridArea: 'rail' }}
      className={`h-full min-h-0 flex flex-col bg-panel border-s border-line overflow-hidden select-none ${className}`}
      dir="rtl"
    >
      <header className="h-10 shrink-0 px-3 flex items-center justify-between border-b border-line">
        <h2 className="text-xs font-medium text-text">بازرس تحلیل</h2>
        <span className="text-xs text-text-3">مرحلهٔ ساخت</span>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 flex flex-col gap-3">
        <div className="rounded-[var(--radius-sm)] border border-line bg-panel-2/50 p-3">
          <div className="text-xs font-medium text-text mb-1">رویداد فعال</div>
          <p className="text-xs leading-6 text-text-3">
            کارت رویداد برجسته (نوع، وضعیت، نرخ برد و کیفیت هندسی) در تسک B3 اینجا می‌نشیند.
          </p>
        </div>

        <div className="rounded-[var(--radius-sm)] border border-line bg-panel-2/50 p-3">
          <div className="text-xs font-medium text-text mb-1">لایه‌ها و قواعد</div>
          <p className="text-xs leading-6 text-text-3">
            کلیدهای روشن/خاموش لایه‌ها و دکمهٔ قواعد هم در تسک B3 به این ریل منتقل می‌شوند. تا آن زمان
            همهٔ این کنترل‌ها از فید پایین در دسترس‌اند.
          </p>
        </div>
      </div>
    </aside>
  );
};
