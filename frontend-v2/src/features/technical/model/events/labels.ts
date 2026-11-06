import type { ChartEvent, EventFamily } from './types';

export const EVENT_FAMILY_FA: Record<EventFamily, string> = {
  pattern: 'الگو',
  channel: 'کانال',
  divergence: 'واگرایی',
  pullback: 'پولبک',
  breakout: 'شکست',
};

const KIND_FA: Record<string, string> = {
  RSI_REGULAR_BULLISH: 'واگرایی مثبت عادی',
  RSI_REGULAR_BEARISH: 'واگرایی منفی عادی',
  RSI_HIDDEN_BULLISH: 'واگرایی مثبت مخفی (H+)',
  RSI_HIDDEN_BEARISH: 'واگرایی منفی مخفی (H-)',
  REGRESSION_CHANNEL: 'کانال رگرسیون',
  PULLBACK_BULLISH: 'پولبک صعودی',
  PULLBACK_BEARISH: 'پولبک نزولی',
  BREAKOUT_UP: 'شکست صعودی',
  BREAKOUT_DOWN: 'شکست نزولی',
};

export const EVENT_DIRECTION_FA: Record<string, string> = {
  bullish: 'صعودی',
  bearish: 'نزولی',
  neutral: 'خنثی',
};

export const EVENT_STATUS_FA: Record<string, string> = {
  forming: 'در حال تشکیل',
  confirmed: 'تأییدشده',
  invalidated: 'باطل‌شده',
};

export function eventKindFa(event: ChartEvent): string {
  return KIND_FA[event.kind] ?? event.kind;
}

export function eventLabelFa(event: ChartEvent): string {
  return `${eventKindFa(event)} · ${EVENT_DIRECTION_FA[event.direction] ?? event.direction}`;
}
