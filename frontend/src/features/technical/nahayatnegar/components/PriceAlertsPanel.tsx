// features/technical/nahayatnegar/components/PriceAlertsPanel.tsx -- پنلِ هشدارِ قیمتی
// از نوارِ بالایِ چارت باز می‌شود. آستانه به ریال است — همان واحدی که بجِ نماد
// نشان می‌دهد — و هشدار پس از شلیک خاموش می‌شود تا بنر تکراری نشود.
import { useMemo, useState } from 'react';
import { fmtInt, parseNum, toFaDigits } from '@shared/lib/fmt';
import { usePriceAlertStore, type AlertSide } from '../../stores/priceAlertStore';
import { crossed, tickPrice } from '../../lib/priceAlerts';

type Props = {
  symbol: string;
  boardRow?: { p_last?: number | null; p_closing?: number | null } | null;
};

const SIDE_LABEL: Record<AlertSide, string> = { above: 'بالایِ', below: 'زیرِ' };

export function PriceAlertsPanel({ symbol, boardRow }: Props) {
  const alerts = usePriceAlertStore((s) => s.alerts);
  const addAlert = usePriceAlertStore((s) => s.addAlert);
  const removeAlert = usePriceAlertStore((s) => s.removeAlert);
  const rearm = usePriceAlertStore((s) => s.rearm);
  const setEnabled = usePriceAlertStore((s) => s.setEnabled);
  const markSeen = usePriceAlertStore((s) => s.markSeen);
  const clearAll = usePriceAlertStore((s) => s.clearAll);

  const [side, setSide] = useState<AlertSide>('above');
  const [rawPrice, setRawPrice] = useState('');
  const [target, setTarget] = useState(symbol);

  const price = parseNum(rawPrice);
  const now = tickPrice(boardRow);
  const wouldFireNow = price != null && now != null && crossed({ side, price }, now);
  const invalid = rawPrice.trim() !== '' && price == null;

  const unseenFired = useMemo(() => alerts.filter((a) => a.firedAt != null && !a.seen).map((a) => a.id), [alerts]);

  const submit = () => {
    if (price == null) return;
    addAlert({ symbol: target.trim() || symbol, side, price });
    setRawPrice('');
  };

  return (
    <div
      data-testid="price-alerts-panel"
      dir="rtl"
      // کلیکِ داخلِ پنل به هدرِ نواربالا نمی‌رسد، وگرنه هر انتخابی پنل را می‌بندد
      onClick={(e) => e.stopPropagation()}
      className="absolute top-full end-0 z-50 mt-1 w-[300px] rounded-lg border border-[var(--nn-border)] bg-[var(--nn-bg)] p-2 shadow-xl"
    >
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-2xs font-bold text-[var(--nn-text-primary)]">هشدارهایِ قیمتی</span>
        <span className="text-3xs text-[var(--nn-text-secondary)]">آستانه به ریال</span>
      </div>

      <div className="flex items-center gap-1">
        <input
          data-testid="alert-symbol"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="نماد"
          className="min-w-0 flex-1 rounded border border-[var(--nn-border)] bg-transparent px-1.5 py-1 text-2xs text-[var(--nn-text-primary)]"
        />
        <div className="flex overflow-hidden rounded border border-[var(--nn-border)]">
          {(['above', 'below'] as AlertSide[]).map((s) => (
            <button
              key={s}
              type="button"
              data-testid={`alert-side-${s}`}
              onClick={() => setSide(s)}
              className={`px-1.5 py-1 text-3xs font-bold ${
                side === s ? 'bg-[var(--nn-accent)] text-white' : 'text-[var(--nn-text-secondary)]'
              }`}
            >
              {s === 'above' ? '▲' : '▼'} {SIDE_LABEL[s]}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-1 flex items-center gap-1">
        <input
          data-testid="alert-price"
          value={rawPrice}
          inputMode="numeric"
          onChange={(e) => setRawPrice(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submit();
          }}
          placeholder="مثلاً ۱۲۵۰۰۰"
          className="min-w-0 flex-1 rounded border border-[var(--nn-border)] bg-transparent px-1.5 py-1 text-2xs text-[var(--nn-text-primary)]"
        />
        <button
          type="button"
          data-testid="alert-add"
          onClick={submit}
          disabled={price == null}
          className="rounded bg-[var(--nn-accent)] px-2 py-1 text-2xs font-bold text-white disabled:opacity-40"
        >
          افزودن
        </button>
      </div>

      {invalid ? (
        <div data-testid="alert-error" className="mt-1 text-3xs font-bold text-[#f23645]">
          آستانه باید عددی بزرگ‌تر از صفر باشد
        </div>
      ) : null}

      {wouldFireNow ? (
        <div data-testid="alert-immediate" className="mt-1 text-3xs text-[#ffab00]">
          اکنون {fmtInt(now)} ریال است — این شرط همین حالا برقرار است و با افزودن بلافاصله شلیک می‌شود
        </div>
      ) : null}

      <div className="mt-2 max-h-[220px] overflow-y-auto">
        {alerts.length === 0 ? (
          <div data-testid="alert-empty" className="py-3 text-center text-3xs text-[var(--nn-text-secondary)]">
            هنوز هیچ هشداری نساخته‌ای
          </div>
        ) : (
          alerts.map((a) => (
            <div
              key={a.id}
              data-testid={`alert-row-${a.id}`}
              className="mb-1 flex items-center gap-1 rounded border border-[var(--nn-border)] px-1.5 py-1"
            >
              <span className="text-2xs font-bold text-[var(--nn-text-primary)]">{a.symbol}</span>
              <span
                className="text-3xs font-bold"
                style={{ color: a.side === 'above' ? '#089981' : '#f23645' }}
                title={`عبور از ${fmtInt(a.price)} ریال`}
              >
                {a.side === 'above' ? '▲' : '▼'} <span className="num">{fmtInt(a.price)}</span>
              </span>
              {a.firedAt != null ? (
                <span data-testid={`alert-fired-${a.id}`} className="text-3xs font-bold text-[#ffab00]">
                  شلیک شد
                </span>
              ) : (
                <span className="text-3xs text-[var(--nn-text-secondary)]">{a.active ? 'فعال' : 'خاموش'}</span>
              )}
              <div className="ms-auto flex items-center gap-1">
                {a.firedAt != null ? (
                  <button
                    type="button"
                    data-testid={`alert-rearm-${a.id}`}
                    onClick={() => rearm(a.id)}
                    title="بازنشانی برای شلیکِ دوباره"
                    className="text-3xs font-bold text-[var(--nn-text-secondary)] hover:text-[var(--nn-text-primary)]"
                  >
                    ↻
                  </button>
                ) : (
                  <button
                    type="button"
                    data-testid={`alert-toggle-${a.id}`}
                    onClick={() => setEnabled(a.id, !a.active)}
                    title={a.active ? 'خاموش کردنِ موقت' : 'فعال کردن'}
                    className="text-3xs font-bold text-[var(--nn-text-secondary)] hover:text-[var(--nn-text-primary)]"
                  >
                    {a.active ? '⏻' : '⏻'}
                  </button>
                )}
                <button
                  type="button"
                  data-testid={`alert-remove-${a.id}`}
                  onClick={() => removeAlert(a.id)}
                  title="حذفِ هشدار"
                  className="text-3xs font-bold text-[#f23645]"
                >
                  ✕
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {alerts.length > 0 ? (
        <div className="mt-1 flex items-center justify-between">
          <span className="text-3xs text-[var(--nn-text-secondary)]">
            <span className="num">{toFaDigits(alerts.length)}</span> هشدار · واحد: ریالِ تابلو
          </span>
          <div className="flex items-center gap-2">
            {unseenFired.length > 0 ? (
              <button
                type="button"
                data-testid="alert-seen-all"
                onClick={() => markSeen(unseenFired)}
                className="text-3xs font-bold text-[#ffab00]"
                title="بنرهایِ شلیک‌شده را بخوانده کن"
              >
                خوانده شد
              </button>
            ) : null}
            <button
              type="button"
              data-testid="alert-clear-all"
              onClick={clearAll}
              className="text-3xs font-bold text-[var(--nn-text-secondary)] hover:text-[#f23645]"
            >
              پاک کردنِ همه
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
