export interface Shortcut {
  id: 'panels' | 'swap' | 'command' | 'undo' | 'escape';
  keys: string;
  label: string;
}

/** تنها منبعِ میانبرها: منوی کاشی، راهنمای سایدبار و تست‌ها از همین می‌خوانند. */
export const SHORTCUTS: ReadonlyArray<Shortcut> = [
  { id: 'panels', keys: 'Alt+۱…۴', label: 'رفتن به پنل' },
  { id: 'swap', keys: '←→↑↓', label: 'جابه‌جاییِ پنلِ انتخاب‌شده' },
  { id: 'command', keys: 'Ctrl+K', label: 'همهٔ کارها' },
  { id: 'undo', keys: 'Ctrl+Z', label: 'برگشتِ چیدمان' },
  { id: 'escape', keys: 'Esc', label: 'بستنِ منو' },
];
