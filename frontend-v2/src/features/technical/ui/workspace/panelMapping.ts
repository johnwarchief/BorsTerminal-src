/**
 * frontend-v2/src/features/technical/ui/workspace/panelMapping.ts
 *
 * برچسب‌های «پنلِ فید» (WorkspacePanel). پس از بازنشستگی کشوی عریض (B4)
 * نگاشت‌های تبِ کشو حذف شده‌اند؛ پنل‌های فید تنها منبع برچسب و محتوا هستند.
 */

import type { WorkspacePanel } from '../../model/types';

/** برچسب‌های تب‌های فید طبق §3: رویدادها | ۵۰ نماد | اندیکاتورها | لبه آماری */
export const PANEL_LABELS: Record<WorkspacePanel, string> = {
  events: 'رویدادها',
  top50: '۵۰ نماد',
  indicators: 'اندیکاتورها',
  edge: 'لبه آماری',
};
