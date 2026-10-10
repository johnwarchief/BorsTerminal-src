// shared/components/FormingCandle.tsx -- کندلِ روزِ در حال تشکیل، یک بار درِ برنامه
//
// هندسه از چهار قیمتِ خودِ تابلو می‌آید (p_first/p_max/p_min/p_last ← همان
// ستون‌هایی که `WatchTable` ستون می‌کرد). دو تغییرِ این دور:
//   • رنگ از نشانهٔ جهت می‌آید، نه از «مقایسۀِ دو عددِ گم‌شده»؛
//   • بی‌رسمان (کمینه == بیشینه — مثلاً نمادی که صف است و تکان نخورده) دیگر
//     «خطِ وسط» نیست: حالتِ صریحِ «بی‌دامنۀِ روز» با دلیلش نوشته می‌شود، چون
//     خطِ بی‌ارتفاع درِ مرجع هم همان معنا را دارد و درِ رابطِ قبلی گم می‌شد.
import { fmtInt } from '@shared/lib/fmt';

export interface CandleOHLC {
  p_first?: number | null;
  p_max?: number | null;
  p_min?: number | null;
  p_last?: number | null;
  p_closing?: number | null;
}

type State = 'up' | 'down' | 'flat' | 'incomplete';

const TONE: Record<State, string> = {
  up: 'var(--accent-green, #089981)',
  down: 'var(--accent-red, #f23645)',
  // یکِ دامنۀ بی‌تغییر رنگِ جهت ندارد؛ خنثیِ برنامۀ خودِ ماست.
  flat: 'var(--text-secondary, #8b93a7)',
  incomplete: 'var(--text-muted, #6b7280)',
};

const GROUND = 22;
const TOP = 2;

/** وضعیت و چهار قیمتِ معتبر ⇒ آنچه رابط نمایش می‌دهد (هیچ عددی ساخته نمی‌شود). */
export function candleGeometry(c: CandleOHLC | null | undefined) {
  const open = c?.p_first ?? null;
  const high = c?.p_max ?? null;
  const low = c?.p_min ?? null;
  const last = c?.p_last ?? c?.p_closing ?? null;
  const ok = [open, high, low, last].every((v) => typeof v === 'number' && v > 0);
  if (!ok || high == null || low == null || open == null || last == null || high < low) {
    return { state: 'incomplete' as State, open, high, low, last, top: 0, bottom: 0 };
  }
  if (high === low) {
    return { state: last > open ? 'up' : last < open ? 'down' : ('flat' as State),
             open, high, low, last, top: (TOP + GROUND) / 2, bottom: (TOP + GROUND) / 2 };
  }
  const y = (v: number) => TOP + (1 - (v - low) / (high - low)) * (GROUND - TOP);
  const state: State = last > open ? 'up' : last < open ? 'down' : 'flat';
  return { state, open, high, low, last, top: y(Math.max(open, last)), bottom: y(Math.min(open, last)) };
}

export function FormingCandle({
  candle, width = 14, height = 24, testId = 'forming-candle',
}: {
  candle: CandleOHLC | null | undefined;
  width?: number;
  height?: number;
  testId?: string;
}) {
  const g = candleGeometry(candle);
  const mid = width / 2;
  const tone = TONE[g.state];
  const label = `اول ${g.open != null ? fmtInt(g.open) : '—'} · بیشینه ${g.high != null ? fmtInt(g.high) : '—'} · `
    + `کمینه ${g.low != null ? fmtInt(g.low) : '—'} · آخرین ${g.last != null ? fmtInt(g.last) : '—'}`;
  if (g.state === 'incomplete') {
    return (
      <span className="num-text text-3xs text-text-muted" data-testid={testId}
            data-state="incomplete"
            title="اول/بیشینه/کمینهٔ همین نشست نرسیده — کندلی رسم نمی‌شود">—</span>
    );
  }
  const bodyH = Math.max(1.5, g.bottom - g.top);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img"
         aria-label={label} data-testid={testId} data-state={g.state} data-dir={g.state}>
      <title>{label}</title>
      <line x1={mid} x2={mid} y1={TOP + 0.5} y2={GROUND} stroke={tone} strokeWidth={1} />
      <rect x={width * 0.22} y={g.top} width={width * 0.56} height={bodyH} fill={tone} />
    </svg>
  );
}

/** همان کندل با چهار عددِ کنارش — چیزی که پنلِ «۵ مظنه» بالایِ سرستون‌ها می‌خواهد. */
export function FormingCandleStrip({
  candle, testId = 'forming-candle-strip', symbol,
}: {
  candle: CandleOHLC | null | undefined;
  testId?: string;
  symbol?: string;
}) {
  const g = candleGeometry(candle);
  const cell = (label: string, v: number | null) => (
    <span className="flex items-baseline gap-1" title={`${label}ِ همین نشست`}>
      <span className="text-3xs text-text-muted">{label}</span>
      <span className="num text-[10px] font-bold text-text-primary">{v != null && v > 0 ? fmtInt(v) : '—'}</span>
    </span>
  );
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 rounded-md border border-[var(--hairline)] bg-bg-card/50 px-1.5 py-1"
         data-testid={testId} data-state={g.state}
         title={symbol ? `کندلِ روزِ ${symbol} که هنوز در حالِ تشکیل است` : 'کندلِ روزِ در حالِ تشکیل'}>
      <span className="flex items-center gap-1.5">
        <FormingCandle candle={candle} testId={`${testId}-glyph`} width={18} height={26} />
        <span className="text-3xs font-bold text-text-secondary">کندلِ امروز</span>
      </span>
      <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
        {cell('اول', g.open)}
        {cell('بیش', g.high)}
        {cell('کم', g.low)}
        {cell('آخرین', g.last)}
      </span>
    </div>
  );
}
