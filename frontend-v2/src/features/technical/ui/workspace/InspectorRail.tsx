/**
 * frontend-v2/src/features/technical/ui/workspace/InspectorRail.tsx
 *
 * ریل بازرس ۲۸۰px (B1/B3، اصلاح R-PB-4) — طبق §3: لایه‌ها، رویداد فعال و قواعد.
 * در B3 کارت رویداد فعال (ActiveEventCard) از فید به این ریل منتقل شد و
 * بالای بخش لایه‌ها می‌نشیند؛ فید فقط فهرست/رویدادها/قواعد را میزبانی می‌کند.
 *
 * بخشِ «تنظیمات» نوار فعالیت همین ریل را به نمایش تنظیماتِ موجود می‌برد؛
 * هیچ فیلد یا فرمِ تازه‌ای ساخته نمی‌شود — همان کلیدهای نمایشِ استور که
 * چارت/نوار رسم/کنترل‌های پیش‌بینی از قبل مصرف می‌کنند.
 */

import React from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import type { ChartPattern } from '../../model/patterns/types';
import { ActiveEventCard } from './ActiveEventCard';

interface SettingsToggleProps {
  testId: string;
  label: string;
  checked: boolean;
  onToggle: () => void;
}

const SettingsToggle: React.FC<SettingsToggleProps> = ({ testId, label, checked, onToggle }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    data-testid={testId}
    onClick={onToggle}
    className="flex items-center justify-between gap-2 min-h-8 px-2 rounded-[var(--radius-md)] border border-line bg-panel-2/50 text-xs text-text-2 hover:text-text hover:bg-panel-2 transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
  >
    <span className="truncate">{label}</span>
    <span
      className={`shrink-0 px-2 leading-5 rounded-[var(--radius-md)] border text-xs ${
        checked
          ? 'bg-accent/15 text-accent border-accent/40 font-medium'
          : 'bg-panel text-text-3 border-line'
      }`}
    >
      {checked ? 'روشن' : 'خاموش'}
    </span>
  </button>
);

export interface InspectorRailProps {
  className?: string;
}

export const InspectorRail: React.FC<InspectorRailProps> = ({ className = '' }) => {
  const activeSection = useTechnicalStore((s) => s.activeSection);
  const isSettings = activeSection === 'settings';

  // آخرین الگوی در حال تشکیل = رویداد فعال ریل؛ تأییدشده‌ها این‌جا نمی‌آیند.
  const detectedPatterns = useTechnicalStore((s) => s.detectedPatterns);
  const lastForming: ChartPattern | undefined = [...detectedPatterns]
    .filter((pattern) => pattern.status === 'forming')
    .sort((a, b) => b.anchor.index - a.anchor.index)[0];

  const isLogScale = useTechnicalStore((s) => s.isLogScale);
  const toggleLogScale = useTechnicalStore((s) => s.toggleLogScale);
  const isAutoScale = useTechnicalStore((s) => s.isAutoScale);
  const toggleAutoScale = useTechnicalStore((s) => s.toggleAutoScale);
  const isMagnetMode = useTechnicalStore((s) => s.isMagnetMode);
  const toggleMagnetMode = useTechnicalStore((s) => s.toggleMagnetMode);
  const isLockedAllDrawings = useTechnicalStore((s) => s.isLockedAllDrawings);
  const toggleLockAllDrawings = useTechnicalStore((s) => s.toggleLockAllDrawings);
  const isHideAllDrawings = useTechnicalStore((s) => s.isHideAllDrawings);
  const toggleHideAllDrawings = useTechnicalStore((s) => s.toggleHideAllDrawings);
  const showCorporateEvents = useTechnicalStore((s) => s.showCorporateEvents);
  const toggleCorporateEvents = useTechnicalStore((s) => s.toggleCorporateEvents);
  const showSMCZones = useTechnicalStore((s) => s.showSMCZones);
  const toggleSMCZones = useTechnicalStore((s) => s.toggleSMCZones);
  const showPredictionCone = useTechnicalStore((s) => s.showPredictionCone);
  const togglePredictionCone = useTechnicalStore((s) => s.togglePredictionCone);

  return (
    <aside
      data-testid="workspace-rail"
      aria-label="ریل بازرس تحلیل"
      style={{ gridArea: 'rail' }}
      className={`h-full min-h-0 flex flex-col bg-panel border-s border-line overflow-hidden select-none ${className}`}
      dir="rtl"
    >
      <header className="h-10 shrink-0 px-3 flex items-center justify-between border-b border-line">
        <h2 className="text-xs font-medium text-text">{isSettings ? 'تنظیمات میزکار' : 'بازرس تحلیل'}</h2>
        <span className="text-xs text-text-3">{isSettings ? 'نمایش چارت' : 'مرحلهٔ ساخت'}</span>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 flex flex-col gap-3">
        {isSettings ? (
          <div
            data-testid="workspace-settings-panel"
            aria-label="تنظیمات نمایش میزکار"
            className="flex flex-col gap-2"
          >
            <p className="text-xs leading-6 text-text-3">
              همان کلیدهای نمایشِ موجود میزکار؛ فرم تازه‌ای ساخته نشده است.
            </p>
            <SettingsToggle
              testId="settings-toggle-log-scale"
              label="مقیاس لگاریتمی"
              checked={isLogScale}
              onToggle={toggleLogScale}
            />
            <SettingsToggle
              testId="settings-toggle-auto-scale"
              label="مقیاس خودکار"
              checked={isAutoScale}
              onToggle={toggleAutoScale}
            />
            <SettingsToggle
              testId="settings-toggle-magnet"
              label="مگنت رسم"
              checked={isMagnetMode}
              onToggle={toggleMagnetMode}
            />
            <SettingsToggle
              testId="settings-toggle-lock-drawings"
              label="قفل ترسیم‌ها"
              checked={isLockedAllDrawings}
              onToggle={toggleLockAllDrawings}
            />
            <SettingsToggle
              testId="settings-toggle-hide-drawings"
              label="پنهان‌کردن ترسیم‌ها"
              checked={isHideAllDrawings}
              onToggle={toggleHideAllDrawings}
            />
            <SettingsToggle
              testId="settings-toggle-corporate-events"
              label="رویدادهای شرکتی"
              checked={showCorporateEvents}
              onToggle={toggleCorporateEvents}
            />
            <SettingsToggle
              testId="settings-toggle-smc-zones"
              label="زون‌های SMC"
              checked={showSMCZones}
              onToggle={toggleSMCZones}
            />
            <SettingsToggle
              testId="settings-toggle-prediction-cone"
              label="کان پیش‌بینی"
              checked={showPredictionCone}
              onToggle={togglePredictionCone}
            />
          </div>
        ) : (
          <>
            <ActiveEventCard pattern={lastForming} />

            <div className="rounded-[var(--radius-md)] border border-line bg-panel-2/50 p-3">
              <div className="text-xs font-medium text-text mb-1">لایه‌ها و قواعد</div>
              <p className="text-xs leading-6 text-text-3">
                کلیدهای روشن/خاموش لایه‌ها و دکمهٔ قواعد در تسک بعدی به همین ریل منتقل می‌شوند.
              </p>
            </div>
          </>
        )}
      </div>
    </aside>
  );
};
