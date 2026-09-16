// features/technical/lib/ftsPatterns.ts -- موتور شناساگر ۹ الگوی FTS (فاز ۴)
// خالص و تست‌پذیر: هر شناساگر یک توصیف نرمال برمی‌گرداند و ترسیم/سوییچ‌ها جدا انجام می‌شوند.
// دادهٔ ناکافی ⇒ active:false صادقانه (بدون الگوی ساختگی).
import { ma14TrailingExit, rsi, sma, swingHighs, swingLows } from './indicators';

/** الگوهای قدیمی‌تر از این تعداد کندل، «کهنه» و محو می‌شوند (anti-clutter) */
export const PATTERN_STALE_BARS = 50;

/** فاصله از انتهای سری ⇒ کهنه؟ */
export function isStale(barsFromEnd: number, stale = PATTERN_STALE_BARS): boolean {
  return !Number.isFinite(barsFromEnd) || barsFromEnd > stale;
}

function finite(v: number | null | undefined): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

// ---------------------------------------------------------------- ۱) جت
export type JetSignal = { active: boolean; level: number | null; barsSinceBreak: number | null };
/** مقاومت افقی که ≥minBars کندل نشکسته بود و اکنون با Close شکسته شده */
export function detectJet(highs: (number | null)[], closes: (number | null)[], minBars = 30): JetSignal {
  const n = Math.min(highs.length, closes.length);
  if (n < minBars + 1) return { active: false, level: null, barsSinceBreak: null };
  const oldHighs = highs.slice(0, n - minBars).filter(finite);
  if (oldHighs.length === 0) return { active: false, level: null, barsSinceBreak: null };
  const level = oldHighs.reduce((m, v) => (v > m ? v : m), -Infinity);
  const recent = closes.slice(n - minBars);
  let brokenAt = -1;
  for (let i = 0; i < recent.length; i++) {
    const c = recent[i];
    if (finite(c) && c > level) {
      brokenAt = i;
      break;
    }
  }
  if (brokenAt < 0) return { active: false, level, barsSinceBreak: null };
  return { active: true, level, barsSinceBreak: recent.length - brokenAt };
}

// ---------------------------------------------------------------- ۲) فیبوی لگاریتمی
export type FibZone = { from: number; to: number };
export type FibZigzag = { active: boolean; low: number | null; high: number | null; entry1: FibZone | null; entry2: FibZone | null };
const logPoint = (hi: number, lo: number, t: number) => Math.exp(Math.log(hi) + t * (Math.log(lo) - Math.log(hi)));
/** آخرین سوینگ کف → سقف بعدی، با دو کمربند لگاریتمی ۰٫۳۳-۰٫۴۰ و ۰٫۶۱۸-۰٫۷۰ */
export function detectFibZigzag(highs: (number | null)[], lows: (number | null)[]): FibZigzag {
  const sh = swingHighs(highs, 3);
  const sl = swingLows(lows, 3);
  if (sh.length === 0 || sl.length === 0) return { active: false, low: null, high: null, entry1: null, entry2: null };
  const lastHigh = sh[sh.length - 1];
  const lowsBefore = sl.filter((p) => p.index < lastHigh.index);
  const base = lowsBefore.length > 0 ? lowsBefore[lowsBefore.length - 1] : sl[sl.length - 1];
  if (!(base.price > 0) || !(lastHigh.price > base.price)) return { active: false, low: null, high: null, entry1: null, entry2: null };
  const hi = lastHigh.price;
  const lo = base.price;
  const z1a = logPoint(hi, lo, 0.4);
  const z1b = logPoint(hi, lo, 0.33);
  const z2a = logPoint(hi, lo, 0.7);
  const z2b = logPoint(hi, lo, 0.618);
  return {
    active: true,
    low: lo,
    high: hi,
    entry1: { from: Math.min(z1a, z1b), to: Math.max(z1a, z1b) },
    entry2: { from: Math.min(z2a, z2b), to: Math.max(z2a, z2b) },
  };
}

// ---------------------------------------------------------------- ۳) CHoCH تأییدشده
export type ChochSignal = { active: boolean; level: number | null; confirmBars: number };
/** در روند نزولی: کلوز بالای آخرین سقف مینور برای ≥confirm کندل متوالی */
export function detectChochConfirmed(highs: (number | null)[], lows: (number | null)[], closes: (number | null)[], order = 2, confirm = 2): ChochSignal {
  const sh = swingHighs(highs, order);
  const sl = swingLows(lows, order);
  const n = Math.min(highs.length, lows.length, closes.length);
  if (sh.length < 2 || sl.length < 2 || n < order * 2 + confirm) return { active: false, level: null, confirmBars: 0 };
  const downTrend = sl[sl.length - 1].price < sl[sl.length - 2].price && sh[sh.length - 1].price < sh[sh.length - 2].price;
  if (!downTrend) return { active: false, level: null, confirmBars: 0 };
  const level = sh[sh.length - 1].price;
  let count = 0;
  for (let i = n - 1; i >= 0 && count < confirm; i--) {
    const c = closes[i];
    if (finite(c) && c > level) count += 1;
    else break;
  }
  return { active: count >= confirm, level, confirmBars: count };
}

// ---------------------------------------------------------------- ۴) نقطه‌زنی (کف ۳/۴/۵)
export type PointHuntSignal = { active: boolean; slopePct: number | null; hits: number[]; floor: 3 | 4 | 5 | null };
/** خط روند نزولی از دو پیوت‌کف اول/دوم؛ شمردن برخورد کف‌های بعدی (۳/۴/۵) با تلورانس ۱٪ */
export function detectPointHunt(lows: (number | null)[], lookback = 5, tolPct = 1): PointHuntSignal {
  const sl = swingLows(lows, lookback);
  if (sl.length < 3) return { active: false, slopePct: null, hits: [], floor: null };
  const p1 = sl[0];
  const p2 = sl[1];
  const dp = p2.price - p1.price;
  if (!(p1.price > 0) || dp >= 0) return { active: false, slopePct: null, hits: [], floor: null };
  const perBar = dp / Math.max(1, p2.index - p1.index);
  const lineAt = (i: number) => p1.price + perBar * (i - p1.index);
  const hits: number[] = [];
  for (const s of sl.slice(2)) {
    const line = lineAt(s.index);
    const tol = (Math.abs(line) * tolPct) / 100;
    if (Math.abs(s.price - line) <= tol) hits.push(s.index);
  }
  const floor = hits.length >= 3 ? 5 : hits.length === 2 ? 4 : hits.length === 1 ? 3 : null;
  return {
    active: hits.length > 0,
    slopePct: p1.price > 0 ? (perBar / p1.price) * 100 : null,
    hits,
    floor,
  };
}

// ---------------------------------------------------------------- ۵) کف/سقف دوقلو و سر و شانه
export type DoubleSignal = { active: boolean; level: number | null; breakout: boolean };
/** دو کف هم‌تراز (تلورانس <tolPct%) + شکست خط گردن */
export function detectDoubleBottom(lows: (number | null)[], closes: (number | null)[], tolPct = 2): DoubleSignal {
  const sl = swingLows(lows, 3);
  if (sl.length < 2) return { active: false, level: null, breakout: false };
  const a = sl[sl.length - 2];
  const b = sl[sl.length - 1];
  const tol = (Math.abs(a.price) * tolPct) / 100;
  if (Math.abs(a.price - b.price) > tol) return { active: false, level: null, breakout: false };
  const between = lows.slice(a.index, b.index + 1).filter(finite);
  const neckline = between.length > 0 ? between.reduce((m, v) => (v > m ? v : m), -Infinity) : null;
  const last = closes[closes.length - 1];
  const breakout = neckline != null && finite(last) && last > neckline;
  return { active: true, level: neckline, breakout };
}

export type HeadShoulders = { active: boolean; neckline: number | null; warning: boolean };
/** سر و شانه سقف: سه سقف با میانهٔ بلندتر و شانه‌های هم‌تراز ±۳٪ */
export function detectHeadShoulders(highs: (number | null)[], tolPct = 3): HeadShoulders {
  const sh = swingHighs(highs, 3);
  if (sh.length < 3) return { active: false, neckline: null, warning: false };
  const [l, head, r] = sh.slice(-3);
  const tol = (Math.abs(head.price) * tolPct) / 100;
  const ok = head.price > l.price && head.price > r.price && Math.abs(l.price - r.price) <= tol;
  if (!ok) return { active: false, neckline: null, warning: false };
  const lows = highs.slice(l.index, r.index + 1).filter(finite);
  return { active: true, neckline: lows.length > 0 ? lows.reduce((m, v) => (v < m ? v : m), Infinity) : null, warning: true };
}

// ---------------------------------------------------------------- ۶) سقف سوم + خروج MA14
export type ThirdPeak = { active: boolean; level: number | null };
/** امتداد خط دو سقف قبلی؛ نزدیکی <tolPct% ⇒ ناحیهٔ پرریسک */
export function detectThirdPeak(highs: (number | null)[], closes: (number | null)[], tolPct = 5): ThirdPeak {
  const sh = swingHighs(highs, 3);
  if (sh.length < 2) return { active: false, level: null };
  const a = sh[sh.length - 2];
  const b = sh[sh.length - 1];
  const perBar = (b.price - a.price) / Math.max(1, b.index - a.index);
  const lastIdx = highs.length - 1;
  const proj = b.price + perBar * (lastIdx - b.index);
  const last = closes[closes.length - 1];
  if (!finite(last)) return { active: false, level: proj };
  const tol = (Math.abs(proj) * tolPct) / 100;
  return { active: Math.abs(last - proj) <= tol, level: proj };
}

export type Ma14Exit = { active: boolean; level: number | null };
/** خروج کامل: تمام اجزای OHLC زیر MA(14) */
export function detectMa14Exit(opens: (number | null)[], highs: (number | null)[], lows: (number | null)[], closes: (number | null)[], ma14?: (number | null)[]): Ma14Exit {
  const r = ma14TrailingExit(opens, highs, lows, closes, ma14);
  return { active: r.exit, level: r.ma14 };
}

// ---------------------------------------------------------------- ۷) ساعت شنی (MA52 هفتگی + RSI<30)
export type Hourglass = { active: boolean; ma52Weekly: number | null; rsi14: number | null };
/** MA52 هفتگی ≈ میانگین ۲۶۰ روز؛ ورود پله‌ای وقتی قیمت زیر MA52 هفتگی و RSI(14) < ۳۰ */
export function detectHourglass(closes: (number | null)[], period = 14, rsiFloor = 30): Hourglass {
  const ma52Weekly = sma(closes, 260);
  const r14 = rsi(closes, period);
  const lastMa = [...ma52Weekly].reverse().find(finite) ?? null;
  const lastRsi = [...r14].reverse().find(finite) ?? null;
  const last = [...closes].reverse().find(finite) ?? null;
  if (lastMa == null || lastRsi == null || last == null) return { active: false, ma52Weekly: lastMa, rsi14: lastRsi };
  return { active: last < lastMa && lastRsi < rsiFloor, ma52Weekly: lastMa, rsi14: lastRsi };
}

// ---------------------------------------------------------------- نقطهٔ ساخت: محو کردن الگوهای کهنه
export type PatternMark = { kind: string; index: number; stale: boolean };
/** علامت‌گذاری کهنگی بر اساس فاصله از انتهای سری */
export function markStale(marks: { kind: string; index: number }[], total: number): PatternMark[] {
  return marks.map((m) => ({ ...m, stale: isStale(total - 1 - m.index) }));
}
