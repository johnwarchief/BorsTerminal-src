// features/technical/components/ComparePanel.tsx -- مقایسهٔ چند نماد روی یک چارت (نرمال‌شده base=100)
// نماد فعال به‌عنوان پایه + تا ۲ نماد دیگر؛ داده از /api/chart/{symbol} (همان useCandleFeed).
// دادهٔ کافی نبود ⇒ «بدون داده» صادقانه (بدون سری ساختگی).
import { useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useCandleFeed } from '../api/useCandleFeed';
import { COMPARE_MAX_SYMBOLS, alignCompare, baseLineY, compareGeometry } from '../lib/compare';

const W = 620;
const H = 200;

export function ComparePanel({ activeSymbol }: { activeSymbol: string }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [extra, setExtra] = useState<string[]>([]);

  const symbols = useMemo(
    () => [...new Set([activeSymbol, ...extra].filter(Boolean))].slice(0, COMPARE_MAX_SYMBOLS),
    [activeSymbol, extra],
  );

  // تعداد ثابت هوک (۳ اسلات) تا ترتیب هوک‌ها با تغییر نمادها نشکند
  const slots = [symbols[0] ?? '', symbols[1] ?? '', symbols[2] ?? ''];
  const f0 = useCandleFeed(slots[0]);
  const f1 = useCandleFeed(slots[1]);
  const f2 = useCandleFeed(slots[2]);
  const feeds = [
    { symbol: slots[0], candles: f0.candles },
    { symbol: slots[1], candles: f1.candles },
    { symbol: slots[2], candles: f2.candles },
  ].filter((f) => f.symbol.length > 0);

  const key = feeds.map((f) => `${f.symbol}:${f.candles.length}`).join('|');
  const result = useMemo(() => alignCompare(feeds), [key]);
  const geo = useMemo(() => compareGeometry(result, W, H), [result]);
  const baseY = geo ? baseLineY(geo, H) : null;

  const add = () => {
    const s = input.trim();
    if (!s) return;
    setExtra((prev) => [...new Set([...prev, s])].slice(0, COMPARE_MAX_SYMBOLS - 1));
    setInput('');
  };

  const loading = f0.isLoading || f1.isLoading || f2.isLoading;

  return (
    <div className="glass-panel flex flex-col gap-2 rounded-2xl p-3" data-testid="compare-panel">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold text-text-secondary">مقایسهٔ نمادها (پایه ۱۰۰)</span>
        <button
          type="button"
          data-testid="compare-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-pressed={open}
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            open ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'
          }`}
        >
          {open ? 'بستن' : 'باز کردن'}
        </button>
        {open ? (
          <>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && add()}
              placeholder="نماد برای افزودن..."
              aria-label="افزودن نماد مقایسه"
              data-testid="compare-input"
              className="rounded-lg border border-border-c bg-bg-card px-2 py-1 text-xs text-text-primary outline-none focus:border-border-accent"
            />
            <button
              type="button"
              data-testid="compare-add"
              onClick={add}
              disabled={extra.length >= COMPARE_MAX_SYMBOLS - 1}
              className="rounded-full border border-border-c bg-bg-card px-3 py-1 text-xs text-text-secondary hover:text-accent-blue disabled:opacity-40"
            >
              افزودن
            </button>
            {extra.map((s) => (
              <button
                key={s}
                type="button"
                data-testid={`compare-remove-${s}`}
                onClick={() => setExtra((prev) => prev.filter((x) => x !== s))}
                className="rounded-full border border-border-c px-2.5 py-0.5 text-[11px] text-text-secondary hover:border-accent-red/50 hover:text-accent-red"
              >
                {s} ✕
              </button>
            ))}
            {loading ? <span className="text-[10px] text-text-muted">در حال دریافت دادهٔ نمادها...</span> : null}
          </>
        ) : null}
      </div>

      {open ? (
        <>
          {geo ? (
            <svg viewBox={`0 0 ${W} ${H}`} className="h-[200px] w-full" role="img" aria-label="مقایسهٔ نمادها" data-testid="compare-chart">
              <line x1={0} x2={W} y1={baseY ?? 0} y2={baseY ?? 0} stroke="var(--border-color)" strokeDasharray="3 5" />
              {geo.lines.map((l) => (
                <path key={l.symbol} d={l.path} fill="none" stroke={l.color} strokeWidth="2" strokeLinejoin="round" />
              ))}
            </svg>
          ) : (
            <div className="rounded-xl border border-dashed border-border-c p-4 text-center text-[11px] text-text-muted" data-testid="compare-empty">
              دادهٔ مشترک کافی برای مقایسه نیست (زمان‌های مشترک کمتر از دو نقطه است)
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3" data-testid="compare-legend">
            {result.lines.map((l, i) => (
              <span key={l.symbol} className="num text-[11px] font-bold" style={{ color: geo?.lines[i]?.color }}>
                {l.symbol}:{' '}
                {l.changePct == null ? 'بدون داده' : `${l.changePct >= 0 ? '+' : ''}${toFaDigits(l.changePct.toFixed(1))}٪`}
              </span>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
