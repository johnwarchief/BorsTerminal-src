// features/market/components/VolumeFlowMini.tsx -- مینی‌چارت خودکفای توزیع حجم درون‌روز
// props: { symbol: string; compact?: boolean } -- برای نصب در سایدبار چپ (Symbol Inspector).
// میله‌ها بر اساس جهت معامله سبز/قرمز می‌شوند و دو پنجرهٔ حساس FTS (۰۹:۰۰–۰۹:۳۰ و
// ۱۲:۰۰–۱۲:۳۰) هایلایت می‌شوند. نبود داده ⇒ «بدون داده» صادقانه (Circuit Breaker، بدون mock).
import { useMemo } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useIntradayVolume, type IntradayBucket } from '../api/useIntradayVolume';

/** بازهٔ معاملات بازار (زمان محلی) */
export const MARKET_OPEN = '08:45';
export const MARKET_CLOSE = '12:30';

/** پنجره‌های حساس FTS در طول بازار */
export const FTS_WINDOWS: readonly (readonly [string, string])[] = [
  ['09:00', '09:30'],
  ['12:00', '12:30'],
];

/** آیا این زمان داخل یکی از پنجره‌های حساس FTS است؟ (مقایسهٔ رشته‌ای HH:MM) */
export function inFtsWindow(t: string): boolean {
  return FTS_WINDOWS.some(([from, to]) => t >= from && t <= to);
}

/** هندل‌های لب پنجره‌ها برای رسم نوارهای هایلایت روی محور */
export const FTS_WINDOW_LABELS = ['۰۹:۰۰–۰۹:۳۰', '۱۲:۰۰–۱۲:۳۰'] as const;

function barTone(b: IntradayBucket): string {
  if (b.dir === 'up') return 'bg-accent-green/80';
  if (b.dir === 'down') return 'bg-accent-red/80';
  return 'bg-text-muted/50';
}

export function VolumeFlowMini({ symbol, compact = false }: { symbol: string; compact?: boolean }) {
  const { data, isLoading, isError } = useIntradayVolume(symbol);
  const buckets = useMemo(() => data?.buckets ?? [], [data]);

  // بدون نماد انتخابی، مینی‌چارت ارتفاع صفر دارد
  if (!symbol) return null;

  const max = buckets.reduce((m, b) => Math.max(m, b.vol ?? 0), 0);
  const hasData = buckets.length > 0 && max > 0;

  return (
    <section
      data-testid="volume-flow-mini"
      aria-label={`توزیع حجم درون‌روز ${symbol}`}
      className="flex flex-col gap-1.5 rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-2"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-2xs font-bold text-text-secondary">جریان حجم (درون‌روز)</span>
        <span className="num text-2xs text-text-muted">{symbol}</span>
      </div>

      {isLoading ? (
        <div className={`text-center text-2xs text-text-muted ${compact ? 'py-3' : 'py-5'}`} data-testid="volume-mini-loading">
          در حال دریافت...
        </div>
      ) : isError || !hasData ? (
        <div className={`text-center text-2xs text-text-muted ${compact ? 'py-3' : 'py-5'}`} data-testid="volume-mini-empty">
          بدون داده
        </div>
      ) : (
        <>
          <div
            dir="ltr"
            data-testid="volume-mini-chart"
            className={`relative flex items-end gap-[1px] ${compact ? 'h-14' : 'h-20'}`}
          >
            {buckets.map((b) => {
              const hot = inFtsWindow(b.t);
              return (
                <div
                  key={b.t}
                  title={`${b.t} — ${b.vol == null ? 'بدون داده' : toFaDigits(b.vol.toLocaleString('en-US'))}`}
                  data-testid={`volume-mini-bar-${b.t}`}
                  data-fts-window={hot ? 'true' : undefined}
                  className={`flex-1 rounded-[1px] ${
                    hot ? 'bg-accent-yellow/15 ring-1 ring-inset ring-accent-yellow/40' : ''
                  }`}
                  style={{ height: `${Math.max(3, ((b.vol ?? 0) / max) * 100)}%` }}
                >
                  <span className={`block h-full w-full rounded-[1px] ${barTone(b)}`} />
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between text-[9px] text-text-muted">
            <span className="num">{toFaDigits(MARKET_OPEN)}</span>
            <span className="text-accent-yellow">پنجره‌های FTS: {FTS_WINDOW_LABELS.join(' · ')}</span>
            <span className="num">{toFaDigits(MARKET_CLOSE)}</span>
          </div>

          <div className="flex items-center gap-3 text-[9px] text-text-muted">
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm bg-accent-green/80" /> خرید
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm bg-accent-red/80" /> فروش
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm bg-accent-yellow/40" /> پنجرهٔ FTS
            </span>
          </div>
        </>
      )}
    </section>
  );
}
