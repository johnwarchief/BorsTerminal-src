// features/portfolio/components/WatchMiniChart.tsx -- کندلِ روزانۀِ کوچکِ «دیده‌بان بازار»
//
// SVG درجا (نه klinecharts): پنلِ زیرِ جدول فقط «نقضِ روندِ چندوزیستی آخر» را
// نشان می‌دهد؛ منبعِ داده همان `/api/chart/{symbol}` است (useWatchCandles)،
// یعنی همان کندلِ تعدیل‌شدۀِ مسیرِ production، بی‌منبعِ دوم.
// ضدِ دادهٔ کهنه: کلِ رندر از `q.data` می‌خواند که queryKey‌اش با نماد است؛
// با عوض شدنِ نماد تا آمدنِ پاسخِ تازه فقط «در حال…»/«بدون داده» می‌آید، نه
// کندلِ نمادِ قبلی.
import { toFaDigits, fmtInt } from '@shared/lib/fmt';
import { useWatchCandles, WATCH_CHART_LAST } from '../api/useWatchCandles';

const W = 320;
const H = 150;
const PAD_T = 6;
const PAD_B = 6;
const UP = '#089981';
const DOWN = '#f23645';

/** `۱۴۰۵/۰۷/۱۶` از تاریخِ میلادیِ کندل؛ بی‌تاریخ «—» */
function dateLabel(iso: string): string {
  const ts = Date.parse(`${iso}T00:00:00Z`);
  if (!Number.isFinite(ts)) return '—';
  return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date(ts));
}

export function WatchMiniChart({ symbol }: { symbol: string }) {
  const q = useWatchCandles(symbol);
  const candles = q.data?.candles ?? [];
  const last = candles[candles.length - 1] ?? null;
  const prev = candles.length > 1 ? candles[candles.length - 2] : null;
  const chg = last && prev && prev.close > 0 ? ((last.close - prev.close) / prev.close) * 100 : null;

  let body = <span className="text-3xs text-text-muted" data-testid="watch-chart-empty">بدون داده</span>;
  if (q.isPending && symbol) {
    body = <span className="text-3xs text-text-muted">در حال دریافتِ کندل…</span>;
  } else if (q.isError) {
    body = <span className="text-3xs text-accent-red" data-testid="watch-chart-error">خطا در دریافتِ کندل</span>;
  } else if (candles.length > 0) {
    let lo = Infinity;
    let hi = -Infinity;
    for (const c of candles) {
      lo = Math.min(lo, c.low);
      hi = Math.max(hi, c.high);
    }
    if (!(hi > lo)) { hi = lo + 1; lo -= 0.5; }
    const y = (v: number) => PAD_T + (1 - (v - lo) / (hi - lo)) * (H - PAD_T - PAD_B);
    const step = W / Math.max(candles.length, 1);
    const bw = Math.max(2, Math.min(9, step * 0.62));
    body = (
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-[150px] w-full"
        role="img"
        aria-label={`نمودارِ کندلِ روزانۀِ ${symbol}`}
        preserveAspectRatio="none"
      >
        {candles.map((c, i) => {
          const cx = i * step + step / 2;
          const up = c.close >= c.open;
          const color = up ? UP : DOWN;
          const top = y(Math.max(c.open, c.close));
          const bottom = y(Math.min(c.open, c.close));
          return (
            <g key={c.time}>
              <line x1={cx} x2={cx} y1={y(c.high)} y2={y(c.low)} stroke={color} strokeWidth={1} />
              <rect x={cx - bw / 2} y={top} width={bw} height={Math.max(1, bottom - top)} fill={color} />
            </g>
          );
        })}
      </svg>
    );
  }

  return (
    <div className="glass-panel flex h-full min-w-0 flex-col gap-1 rounded-2xl p-2.5" data-testid="watch-chart" data-symbol={symbol}>
      <div className="flex flex-wrap items-baseline gap-1.5 text-xs">
        <h4 className="font-black text-text-primary">کندلِ روزانه</h4>
        <span className="font-bold text-accent-blue">{symbol || '—'}</span>
        <span className="num text-2xs text-text-secondary">{toFaDigits(WATCH_CHART_LAST)} نشستِ آخر</span>
        {last ? (
          <span className="num ms-auto text-2xs text-text-muted">
            {dateLabel(last.time)} · <span className={chg != null && chg < 0 ? 'text-accent-red' : 'text-accent-green'}>
              {fmtInt(last.close)}
            </span>
          </span>
        ) : null}
      </div>
      <div className="flex min-h-[120px] flex-1 items-center justify-center overflow-hidden">{body}</div>
    </div>
  );
}
