// features/market/components/VolumeFlow.tsx -- بازرسِ جریان حجم نماد انتخابی (Side Sheet)
// تا وقتی سطری انتخاب نشده، ارتفاع صفر است (null)؛ با کلیک روی سهم شیت کشوییِ سمت
// شروع (راست در RTL) باز می‌شود. منطق: کلاس‌های منطقی (start/s/end) تا RTL-امن بماند.
import { useMemo } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { useHistory } from '../api/useHistory';

const LAST_N = 60;

export function VolumeFlow({ symbol, onClose }: { symbol: string; onClose?: () => void }) {
  const { data, isLoading, isError } = useHistory(symbol);
  const volumes = useMemo(() => (data?.volumes ?? []).slice(-LAST_N), [data]);

  // تا سطری انتخاب نشده ⇒ بسته/صفر ارتفاع (جلوگیری از کادر خالیِ مسدودکننده بالای صفحه)
  if (!symbol) return null;

  const max = Math.max(1, ...volumes.map((v) => v.value));
  const avg = volumes.length > 0 ? volumes.reduce((a, v) => a + v.value, 0) / volumes.length : 0;
  const peakIdx = volumes.reduce((best, v, i) => (v.value > volumes[best].value ? i : best), 0);
  const avgH = Math.min(100, (avg / max) * 100);

  return (
    <aside
      data-testid="volume-sheet"
      aria-label={`بازرس جریان حجم ${symbol}`}
      className="glass-panel fixed bottom-0 start-0 top-0 z-50 flex w-[340px] max-w-[88vw] flex-col gap-2 overflow-y-auto rounded-none border-y-0 border-s-0 p-4"
    >
      <div className="flex items-center justify-between gap-2 border-b border-[var(--hairline)] pb-2">
        <div className="min-w-0">
          <div className="text-[13px] font-black text-text-primary">جریان حجم</div>
          <div className="truncate text-2xs text-text-muted">{symbol}</div>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن بازرس جریان حجم"
            className="shrink-0 rounded-md border border-transparent px-1.5 py-0.5 text-xs text-text-muted transition-colors hover:border-[var(--hairline)] hover:text-accent-red"
          >
            ✕
          </button>
        ) : null}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-2xs text-text-muted">
          میانگین: <span className="num">{fmtInt(avg)}</span>
        </span>
        <span className="num text-2xs text-text-muted">{toFaDigits(volumes.length)} جلسه آخر</span>
      </div>

      {isLoading && <div className="py-8 text-center text-xs text-text-secondary">در حال بارگذاری...</div>}
      {isError && <div className="py-8 text-center text-xs text-accent-red">خطا در دریافت تاریخچه</div>}
      {!isLoading && !isError && volumes.length === 0 && (
        <div className="py-8 text-center text-xs text-text-muted">تاریخچه ای نیست</div>
      )}
      {volumes.length > 0 && (
        <>
          <div className="relative flex h-28 items-end gap-[2px]" dir="ltr">
            <div
              className="pointer-events-none absolute inset-x-0 w-full border-t border-dashed border-accent-yellow/50"
              style={{ bottom: `${Math.max(3, avgH)}%` }}
              title={`میانگین: ${fmtInt(avg)}`}
            />
            {volumes.map((v, i) => (
              <div
                key={v.time}
                title={`${v.time}: ${fmtInt(v.value)}`}
                className={`flex-1 rounded-sm ${i === peakIdx ? 'bg-accent-yellow/80' : v.color ?? 'bg-accent-blue/60'}`}
                style={{ height: `${Math.max(3, (v.value / max) * 100)}%` }}
              />
            ))}
          </div>
          <div className="flex items-center justify-between text-2xs text-text-muted">
            <span>{volumes[0]?.time ?? ''}</span>
            <span>
              اوج: <span className="num">{fmtInt(volumes[peakIdx].value)}</span>
            </span>
          </div>
        </>
      )}

      <div className="mt-auto pt-2 text-center text-2xs uppercase tracking-widest text-text-muted">
        Volume Flow · FTS
      </div>
    </aside>
  );
}
