import type { FtsCard } from '../api/useFtsCard';

const BANK_RE = /بانک|بانك|اعتباری/;

export function isHoldingCard(card: FtsCard): boolean {
  const axis4 = card.indicators?.['4'];
  return card.profile?.kind === 'holding'
    || axis4?.na === true
    || axis4?.exempt === true;
}

export function isBankCard(card: FtsCard): boolean {
  return card.profile?.margin_class === 'bank'
    || BANK_RE.test(card.profile?.label ?? '')
    || BANK_RE.test(card.sector ?? '');
}
