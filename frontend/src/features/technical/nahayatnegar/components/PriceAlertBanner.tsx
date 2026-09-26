// features/technical/nahayatnegar/components/PriceAlertBanner.tsx -- بنرِ هشدارهایِ شلیک‌شده
// فقط آنچه واقعاً شلیک شده و هنوز خوانده نشده نشان داده می‌شود؛ متن از خودِ
// هشدار و قیمتِ تازه ساخته می‌شود، نه از حدس. بی‌شلیک ⇒ هیچ.
import { useMemo } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { usePriceAlertStore } from '../../stores/priceAlertStore';
import { firedLabel, tickPrice, type AlertTick } from '../../lib/priceAlerts';

type Props = {
  /** ردیف‌هایِ فیدِ تابلو برای خواندنِ قیمتِ اکنون؛ اگر نرسید بی‌قیمت نشان داده می‌شود */
  rows?: readonly AlertTick[] | null;
};

export function PriceAlertBanner({ rows }: Props) {
  const alerts = usePriceAlertStore((s) => s.alerts);
  const markSeen = usePriceAlertStore((s) => s.markSeen);

  const fired = useMemo(() => alerts.filter((a) => a.firedAt != null && !a.seen), [alerts]);

  if (fired.length === 0) return null;

  const priceOf = (symbol: string): number | null => {
    if (!rows) return null;
    const hit = rows.find((r) => r.symbol === symbol);
    return tickPrice(hit);
  };

  return (
    <div
      data-testid="price-alert-banner"
      dir="rtl"
      className="fixed bottom-4 left-16 z-[70] flex max-w-[340px] flex-col gap-1 rounded-lg border border-[#ffab00]/60 bg-[#1c1f26]/95 p-2 shadow-2xl"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-2xs font-bold text-[#ffab00]">
          🔔 هشدارهایِ شلیک‌شده <span className="num">{toFaDigits(fired.length)}</span>
        </span>
        <button
          type="button"
          data-testid="price-alert-dismiss"
          onClick={() => markSeen(fired.map((a) => a.id))}
          title="بستن و خوانده‌شدن"
          className="text-3xs font-bold text-[var(--nn-text-secondary)] hover:text-[var(--nn-text-primary)]"
        >
          ✕
        </button>
      </div>
      {fired.map((a) => (
        <div key={a.id} data-testid={`price-alert-line-${a.id}`} className="text-2xs text-[#e6e9ef]">
          {firedLabel(a, priceOf(a.symbol))}
        </div>
      ))}
    </div>
  );
}
