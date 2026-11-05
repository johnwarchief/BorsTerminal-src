/**
 * frontend-v2/src/features/technical/ui/workspace/panelMapping.ts
 *
 * نگاشتِ دوطرفهٔ «پنلِ فید» (WorkspacePanel) و «تبِ کشوی موجود» (DrawerTab).
 * در B1/B2 کشوی عریض هنوز میزبانِ پنل‌هاست؛ پنلِ events همان تبِ scanner است.
 * هر مصرف‌کننده‌ای که پنل را عوض می‌کند باید هر دو مقدار را با هم بنویسد
 * تا برچسب و محتوای میزبان هم‌یشه یکی بمانند (R-PB-5).
 */

import type { DrawerTab, WorkspacePanel } from '../../model/types';

export const DRAWER_TAB_BY_PANEL: Record<WorkspacePanel, DrawerTab> = {
  events: 'scanner',
  top50: 'top50',
  indicators: 'indicators',
  edge: 'edge',
};

export const PANEL_BY_DRAWER_TAB: Record<DrawerTab, WorkspacePanel> = {
  scanner: 'events',
  top50: 'top50',
  indicators: 'indicators',
  edge: 'edge',
};

/** برچسب‌های تب‌های فید طبق §3: رویدادها | ۵۰ نماد | اندیکاتورها | لبه آماری */
export const PANEL_LABELS: Record<WorkspacePanel, string> = {
  events: 'رویدادها',
  top50: '۵۰ نماد',
  indicators: 'اندیکاتورها',
  edge: 'لبه آماری',
};
